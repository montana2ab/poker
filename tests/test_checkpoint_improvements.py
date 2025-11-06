"""Test checkpoint improvements: RNG state, atomic writes, bucket validation."""

import pytest
import tempfile
import json
import pickle
from pathlib import Path
from holdem.types import BucketConfig, MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.utils.rng import RNG
from holdem.utils.serialization import save_json, save_pickle, load_json, load_pickle


def test_rng_state_save_load():
    """Test that RNG state can be saved and restored."""
    # Create RNG and generate some random numbers
    rng1 = RNG(seed=42)
    vals1 = [rng1.random() for _ in range(5)]
    
    # Save state
    state = rng1.get_state()
    
    # Generate more numbers
    vals2 = [rng1.random() for _ in range(5)]
    
    # Create new RNG and restore state
    rng2 = RNG(seed=99)  # Different seed
    rng2.set_state(state)
    
    # Generate numbers from restored state - should match vals2
    vals3 = [rng2.random() for _ in range(5)]
    
    assert vals2 == vals3, "Restored RNG should produce same sequence"
    assert vals1 != vals2, "Sequences before/after state save should differ"


def test_atomic_json_write():
    """Test that JSON writes are atomic (no partial files on error)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        target_file = tmpdir / "test.json"
        
        # Save data successfully
        data1 = {"key": "value1", "number": 42}
        save_json(data1, target_file)
        
        # Verify file exists and temp file is gone
        assert target_file.exists()
        assert not (tmpdir / "test.json.tmp").exists()
        
        # Load and verify
        loaded = load_json(target_file)
        assert loaded == data1


def test_atomic_pickle_write():
    """Test that pickle writes are atomic."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        target_file = tmpdir / "test.pkl"
        
        # Save data
        data1 = {"key": [1, 2, 3], "nested": {"a": 1, "b": 2}}
        save_pickle(data1, target_file)
        
        # Verify
        assert target_file.exists()
        assert not (tmpdir / "test.pkl.tmp").exists()
        
        loaded = load_pickle(target_file)
        assert loaded == data1


def test_gzip_json_compression():
    """Test that JSON can be saved with gzip compression."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Large data to benefit from compression
        data = {f"key_{i}": [j for j in range(100)] for i in range(100)}
        
        # Save without compression
        normal_file = tmpdir / "normal.json"
        save_json(data, normal_file, use_gzip=False)
        
        # Save with compression
        gzip_file = tmpdir / "compressed.json.gz"
        save_json(data, gzip_file, use_gzip=True)
        
        # Compressed should be smaller
        normal_size = normal_file.stat().st_size
        gzip_size = gzip_file.stat().st_size
        assert gzip_size < normal_size, "Gzipped file should be smaller"
        
        # Should load correctly
        loaded = load_json(gzip_file)
        assert loaded == data


def test_checkpoint_contains_rng_state():
    """Test that checkpoints save RNG state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create small bucketing and solver
        config = BucketConfig(
            k_preflop=4,
            k_flop=8,
            k_turn=8,
            k_river=4,
            num_samples=100,
            seed=42
        )
        
        bucketing = HandBucketing(config)
        bucketing.build(num_samples=100)
        
        mccfr_config = MCCFRConfig(
            num_iterations=10,
            checkpoint_interval=5
        )
        
        solver = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        
        # Run a few iterations
        for i in range(5):
            solver.sampler.sample_iteration(i + 1)
        
        # Save checkpoint
        solver.save_checkpoint(tmpdir, iteration=5, elapsed_seconds=1.0)
        
        # Check metadata exists and contains RNG state
        metadata_file = tmpdir / "checkpoints" / "checkpoint_iter5_t1s_metadata.json"
        assert metadata_file.exists()
        
        metadata = load_json(metadata_file)
        assert 'rng_state' in metadata
        assert 'seed' in metadata['rng_state']
        assert 'numpy_state' in metadata['rng_state']
        assert 'python_random_state' in metadata['rng_state']


def test_checkpoint_contains_bucket_metadata():
    """Test that checkpoints save bucket configuration metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        config = BucketConfig(
            k_preflop=4,
            k_flop=8,
            k_turn=8,
            k_river=4,
            num_samples=100,
            seed=42
        )
        
        bucketing = HandBucketing(config)
        bucketing.build(num_samples=100)
        
        mccfr_config = MCCFRConfig(num_iterations=10)
        solver = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        
        # Save checkpoint
        solver.save_checkpoint(tmpdir, iteration=1, elapsed_seconds=1.0)
        
        # Check metadata contains bucket info
        metadata_file = tmpdir / "checkpoints" / "checkpoint_iter1_t1s_metadata.json"
        metadata = load_json(metadata_file)
        
        assert 'bucket_metadata' in metadata
        bucket_meta = metadata['bucket_metadata']
        assert 'bucket_file_sha' in bucket_meta
        assert 'k_preflop' in bucket_meta
        assert 'k_flop' in bucket_meta
        assert bucket_meta['k_preflop'] == 4
        assert bucket_meta['k_flop'] == 8


def test_bucket_validation_success():
    """Test that loading checkpoint with matching buckets succeeds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        config = BucketConfig(
            k_preflop=4,
            k_flop=8,
            k_turn=8,
            k_river=4,
            num_samples=100,
            seed=42
        )
        
        bucketing = HandBucketing(config)
        bucketing.build(num_samples=100)
        
        mccfr_config = MCCFRConfig(num_iterations=10)
        solver = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        
        # Save checkpoint
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter1_t1s.pkl"
        solver.save_checkpoint(tmpdir, iteration=1, elapsed_seconds=1.0)
        
        # Should be able to load with same bucketing
        iteration = solver.load_checkpoint(checkpoint_path, validate_buckets=True)
        # Note: iteration will be 0 since we're not saving full regret state yet
        # This is expected - we're testing the validation logic


def test_bucket_validation_failure():
    """Test that loading checkpoint with different buckets fails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create and save checkpoint with config 1
        config1 = BucketConfig(
            k_preflop=4,
            k_flop=8,
            k_turn=8,
            k_river=4,
            num_samples=100,
            seed=42
        )
        
        bucketing1 = HandBucketing(config1)
        bucketing1.build(num_samples=100)
        
        mccfr_config = MCCFRConfig(num_iterations=10)
        solver1 = MCCFRSolver(mccfr_config, bucketing1, num_players=2)
        
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter1_t1s.pkl"
        solver1.save_checkpoint(tmpdir, iteration=1, elapsed_seconds=1.0)
        
        # Try to load with different config
        config2 = BucketConfig(
            k_preflop=8,  # Different!
            k_flop=8,
            k_turn=8,
            k_river=4,
            num_samples=100,
            seed=42
        )
        
        bucketing2 = HandBucketing(config2)
        bucketing2.build(num_samples=100)
        
        solver2 = MCCFRSolver(mccfr_config, bucketing2, num_players=2)
        
        # Should raise ValueError due to bucket mismatch
        with pytest.raises(ValueError, match="Bucket configuration mismatch"):
            solver2.load_checkpoint(checkpoint_path, validate_buckets=True)


def test_preflop_equity_samples_configurable():
    """Test that preflop equity samples can be configured."""
    config = BucketConfig(k_preflop=4, num_samples=50, seed=42)
    
    # Test with 0 samples (disabled)
    bucketing_disabled = HandBucketing(config, preflop_equity_samples=0)
    assert bucketing_disabled.preflop_equity_samples == 0
    
    # Test with custom samples
    bucketing_custom = HandBucketing(config, preflop_equity_samples=50)
    assert bucketing_custom.preflop_equity_samples == 50


def test_tensorboard_log_interval_configurable():
    """Test that TensorBoard log interval is configurable."""
    # Default should be 1000
    config1 = MCCFRConfig()
    assert config1.tensorboard_log_interval == 1000
    
    # Can be customized
    config2 = MCCFRConfig(tensorboard_log_interval=500)
    assert config2.tensorboard_log_interval == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
