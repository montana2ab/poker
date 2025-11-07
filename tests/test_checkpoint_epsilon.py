"""Test checkpoint integration with CLI."""

import pytest
import tempfile
from pathlib import Path
from holdem.types import BucketConfig, MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.mccfr.parallel_solver import ParallelMCCFRSolver


def test_single_solver_saves_epsilon_in_checkpoint():
    """Test that single-process solver saves epsilon in checkpoint metadata."""
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
        
        mccfr_config = MCCFRConfig(
            num_iterations=10,
            exploration_epsilon=0.6,
            regret_discount_alpha=0.95,
            strategy_discount_beta=0.90
        )
        
        solver = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        solver._current_epsilon = 0.6
        
        # Save checkpoint
        solver.save_checkpoint(tmpdir, iteration=5, elapsed_seconds=1.0)
        
        # Check metadata contains epsilon and discount params
        from holdem.utils.serialization import load_json
        metadata_file = tmpdir / "checkpoints" / "checkpoint_iter5_t1s_metadata.json"
        metadata = load_json(metadata_file)
        
        assert 'epsilon' in metadata
        assert metadata['epsilon'] == 0.6
        assert 'regret_discount_alpha' in metadata
        assert metadata['regret_discount_alpha'] == 0.95
        assert 'strategy_discount_beta' in metadata
        assert metadata['strategy_discount_beta'] == 0.90


def test_single_solver_restores_epsilon_from_checkpoint():
    """Test that single-process solver restores epsilon when loading checkpoint."""
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
        
        # Save checkpoint with epsilon = 0.4
        mccfr_config1 = MCCFRConfig(num_iterations=10, exploration_epsilon=0.4)
        solver1 = MCCFRSolver(mccfr_config1, bucketing, num_players=2)
        solver1._current_epsilon = 0.4
        
        # Run a few iterations
        for i in range(5):
            solver1.sampler.sample_iteration(i + 1)
        
        solver1.save_checkpoint(tmpdir, iteration=5, elapsed_seconds=1.0)
        
        # Load checkpoint with a new solver that has different initial epsilon
        mccfr_config2 = MCCFRConfig(num_iterations=100, exploration_epsilon=0.8)
        solver2 = MCCFRSolver(mccfr_config2, bucketing, num_players=2)
        solver2._current_epsilon = 0.8
        
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter5_t1s.pkl"
        iteration = solver2.load_checkpoint(checkpoint_path, validate_buckets=True)
        
        # Epsilon should be restored to 0.4 from checkpoint
        assert solver2._current_epsilon == 0.4
        assert solver2.iteration == 5


def test_parallel_solver_restores_epsilon_from_checkpoint():
    """Test that parallel solver restores epsilon when loading checkpoint."""
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
        
        # Save checkpoint with epsilon = 0.3
        mccfr_config1 = MCCFRConfig(
            num_iterations=100,
            num_workers=2,
            exploration_epsilon=0.3
        )
        solver1 = ParallelMCCFRSolver(mccfr_config1, bucketing, num_players=2)
        solver1._current_epsilon = 0.3
        solver1.iteration = 10
        
        solver1._save_checkpoint(tmpdir, iteration=10, elapsed_seconds=2.0)
        
        # Load with a new parallel solver
        mccfr_config2 = MCCFRConfig(
            num_iterations=200,
            num_workers=4,
            exploration_epsilon=0.7
        )
        solver2 = ParallelMCCFRSolver(mccfr_config2, bucketing, num_players=2)
        solver2._current_epsilon = 0.7
        
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter10_t2s.pkl"
        iteration = solver2.load_checkpoint(checkpoint_path, validate_buckets=True)
        
        # Epsilon should be restored to 0.3 from checkpoint
        assert solver2._current_epsilon == 0.3
        assert solver2.iteration == 10


def test_cross_mode_checkpoint_resume():
    """Test that parallel solver can resume from single-process checkpoint with epsilon."""
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
        
        # Save single-process checkpoint with epsilon = 0.35
        single_config = MCCFRConfig(num_iterations=10, exploration_epsilon=0.35)
        single_solver = MCCFRSolver(single_config, bucketing, num_players=2)
        single_solver._current_epsilon = 0.35
        
        for i in range(10):
            single_solver.sampler.sample_iteration(i + 1)
        
        single_solver.save_checkpoint(tmpdir, iteration=10, elapsed_seconds=2.0)
        
        # Resume with parallel solver
        parallel_config = MCCFRConfig(
            num_iterations=100,
            num_workers=2,
            exploration_epsilon=0.8
        )
        parallel_solver = ParallelMCCFRSolver(parallel_config, bucketing, num_players=2)
        
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter10_t2s.pkl"
        iteration = parallel_solver.load_checkpoint(checkpoint_path, validate_buckets=True)
        
        # Should have restored iteration and epsilon from single-process checkpoint
        assert iteration == 10
        assert parallel_solver.iteration == 10
        assert parallel_solver._current_epsilon == 0.35


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
