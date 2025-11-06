"""Tests for bucket validation and checkpoint resume functionality."""

import pytest
import tempfile
from pathlib import Path
from holdem.types import MCCFRConfig, BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver


def test_bucket_hash_calculation():
    """Test that bucket hash is calculated consistently."""
    bucketing1 = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2, seed=42)
    bucketing2 = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2, seed=42)
    
    config = MCCFRConfig(num_iterations=10)
    
    solver1 = MCCFRSolver(config=config, bucketing=bucketing1, num_players=2)
    solver2 = MCCFRSolver(config=config, bucketing=bucketing2, num_players=2)
    
    hash1 = solver1._calculate_bucket_hash()
    hash2 = solver2._calculate_bucket_hash()
    
    assert hash1 == hash2, "Same bucket configuration should produce same hash"


def test_different_buckets_different_hash():
    """Test that different bucket configurations produce different hashes."""
    bucketing1 = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2, seed=42)
    bucketing2 = HandBucketing(k_preflop=3, k_flop=2, k_turn=2, k_river=2, seed=42)
    
    config = MCCFRConfig(num_iterations=10)
    
    solver1 = MCCFRSolver(config=config, bucketing=bucketing1, num_players=2)
    solver2 = MCCFRSolver(config=config, bucketing=bucketing2, num_players=2)
    
    hash1 = solver1._calculate_bucket_hash()
    hash2 = solver2._calculate_bucket_hash()
    
    assert hash1 != hash2, "Different bucket configurations should produce different hashes"


def test_checkpoint_saves_bucket_metadata():
    """Test that checkpoint includes bucket metadata."""
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2, seed=42)
    
    config = MCCFRConfig(
        num_iterations=100,
        checkpoint_interval=50
    )
    
    solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Run a few iterations and save checkpoint
        for i in range(50):
            solver.sampler.sample_iteration(i + 1)
        solver.iteration = 50
        
        solver.save_checkpoint(logdir, iteration=50)
        
        # Check that metadata file exists
        metadata_file = logdir / "checkpoints" / "checkpoint_iter50_metadata.json"
        assert metadata_file.exists(), "Checkpoint metadata should be saved"
        
        # Load and verify metadata
        from holdem.utils.serialization import load_json
        metadata = load_json(metadata_file)
        
        assert 'bucket_metadata' in metadata
        assert 'bucket_file_sha' in metadata['bucket_metadata']
        assert metadata['bucket_metadata']['k_preflop'] == 2
        assert metadata['bucket_metadata']['seed'] == 42


def test_checkpoint_validation_accepts_matching_buckets():
    """Test that checkpoint validation succeeds with matching buckets."""
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2, seed=42)
    
    config = MCCFRConfig(
        num_iterations=100,
        checkpoint_interval=50
    )
    
    solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Save a checkpoint
        for i in range(50):
            solver.sampler.sample_iteration(i + 1)
        solver.iteration = 50
        solver.save_checkpoint(logdir, iteration=50)
        
        checkpoint_file = logdir / "checkpoints" / "checkpoint_iter50.pkl"
        
        # Create new solver with same bucketing
        solver2 = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
        
        # Should not raise error
        iteration = solver2.load_checkpoint(checkpoint_file, validate_buckets=True)
        assert iteration == 50


def test_checkpoint_validation_rejects_mismatched_buckets():
    """Test that checkpoint validation fails with mismatched buckets."""
    bucketing1 = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2, seed=42)
    bucketing2 = HandBucketing(k_preflop=3, k_flop=2, k_turn=2, k_river=2, seed=42)
    
    config = MCCFRConfig(
        num_iterations=100,
        checkpoint_interval=50
    )
    
    solver1 = MCCFRSolver(config=config, bucketing=bucketing1, num_players=2)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Save a checkpoint with bucketing1
        for i in range(50):
            solver1.sampler.sample_iteration(i + 1)
        solver1.iteration = 50
        solver1.save_checkpoint(logdir, iteration=50)
        
        checkpoint_file = logdir / "checkpoints" / "checkpoint_iter50.pkl"
        
        # Try to load with different bucketing
        solver2 = MCCFRSolver(config=config, bucketing=bucketing2, num_players=2)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Bucket configuration mismatch"):
            solver2.load_checkpoint(checkpoint_file, validate_buckets=True)


def test_snapshot_saves_bucket_metadata():
    """Test that snapshot includes bucket metadata."""
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2, seed=42)
    
    config = MCCFRConfig(
        num_iterations=100,
        time_budget_seconds=10,
        snapshot_interval_seconds=5
    )
    
    solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Save a snapshot
        solver.iteration = 50
        solver.save_snapshot(logdir, iteration=50, elapsed_seconds=5.0)
        
        # Check that metadata file exists
        snapshot_dir = logdir / "snapshots" / "snapshot_iter50_t5s"
        metadata_file = snapshot_dir / "metadata.json"
        assert metadata_file.exists(), "Snapshot metadata should be saved"
        
        # Load and verify metadata
        from holdem.utils.serialization import load_json
        metadata = load_json(metadata_file)
        
        assert 'bucket_metadata' in metadata
        assert 'bucket_file_sha' in metadata['bucket_metadata']
        assert metadata['bucket_metadata']['k_preflop'] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
