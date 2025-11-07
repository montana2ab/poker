"""Test parallel solver checkpoint loading and metadata."""

import pytest
import tempfile
from pathlib import Path
from holdem.types import BucketConfig, MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.mccfr.parallel_solver import ParallelMCCFRSolver


def test_parallel_solver_save_checkpoint_with_metadata():
    """Test that parallel solver saves complete checkpoint metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create small bucketing
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
        
        # Create parallel solver
        mccfr_config = MCCFRConfig(
            num_iterations=100,
            checkpoint_interval=50,
            num_workers=2,
            batch_size=10,
            exploration_epsilon=0.5,
            regret_discount_alpha=0.9,
            strategy_discount_beta=0.8
        )
        
        solver = ParallelMCCFRSolver(mccfr_config, bucketing, num_players=2)
        
        # Run a few iterations manually
        solver.iteration = 50
        solver._current_epsilon = 0.5
        
        # Save checkpoint
        solver._save_checkpoint(tmpdir, iteration=50, elapsed_seconds=10.0)
        
        # Check metadata exists and contains required fields
        from holdem.utils.serialization import load_json
        metadata_file = tmpdir / "checkpoints" / "checkpoint_iter50_t10s_metadata.json"
        assert metadata_file.exists()
        
        metadata = load_json(metadata_file)
        assert 'iteration' in metadata
        assert metadata['iteration'] == 50
        assert 'epsilon' in metadata
        assert metadata['epsilon'] == 0.5
        assert 'regret_discount_alpha' in metadata
        assert metadata['regret_discount_alpha'] == 0.9
        assert 'strategy_discount_beta' in metadata
        assert metadata['strategy_discount_beta'] == 0.8
        assert 'bucket_metadata' in metadata
        assert metadata['bucket_metadata']['k_preflop'] == 4


def test_parallel_solver_load_checkpoint():
    """Test that parallel solver can load checkpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create bucketing
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
        
        # Create and save checkpoint with single-process solver
        mccfr_config = MCCFRConfig(num_iterations=10)
        solver = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        
        # Run a few iterations
        for i in range(5):
            solver.sampler.sample_iteration(i + 1)
        
        # Save checkpoint
        solver.save_checkpoint(tmpdir, iteration=5, elapsed_seconds=1.0)
        
        # Load checkpoint with parallel solver
        parallel_config = MCCFRConfig(num_iterations=100, num_workers=2)
        parallel_solver = ParallelMCCFRSolver(parallel_config, bucketing, num_players=2)
        
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter5_t1s.pkl"
        iteration = parallel_solver.load_checkpoint(checkpoint_path, validate_buckets=True)
        
        # Should load successfully
        assert parallel_solver.iteration == 5
        # Should have some regrets loaded
        assert len(parallel_solver.regret_tracker.regrets) > 0


def test_parallel_solver_load_checkpoint_bucket_validation_fails():
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
        
        mccfr_config = MCCFRConfig(num_iterations=10, num_workers=2)
        solver1 = ParallelMCCFRSolver(mccfr_config, bucketing1, num_players=2)
        solver1.iteration = 5
        
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter5_t1s.pkl"
        solver1._save_checkpoint(tmpdir, iteration=5, elapsed_seconds=1.0)
        
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
        
        solver2 = ParallelMCCFRSolver(mccfr_config, bucketing2, num_players=2)
        
        # Should raise ValueError due to bucket mismatch
        with pytest.raises(ValueError, match="Bucket configuration mismatch"):
            solver2.load_checkpoint(checkpoint_path, validate_buckets=True)


def test_parallel_solver_can_resume_from_single_process_checkpoint():
    """Test that parallel solver can resume from single-process checkpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create bucketing
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
        
        # Create single-process checkpoint
        single_config = MCCFRConfig(num_iterations=10)
        single_solver = MCCFRSolver(single_config, bucketing, num_players=2)
        
        # Run a few iterations
        for i in range(10):
            single_solver.sampler.sample_iteration(i + 1)
        
        single_solver.save_checkpoint(tmpdir, iteration=10, elapsed_seconds=2.0)
        
        # Load with parallel solver
        parallel_config = MCCFRConfig(num_iterations=100, num_workers=4)
        parallel_solver = ParallelMCCFRSolver(parallel_config, bucketing, num_players=2)
        
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter10_t2s.pkl"
        iteration = parallel_solver.load_checkpoint(checkpoint_path, validate_buckets=True)
        
        assert iteration == 10
        assert parallel_solver.iteration == 10
        # Should have loaded regrets from single-process solver
        assert len(parallel_solver.regret_tracker.regrets) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
