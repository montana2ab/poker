"""Tests for chunked training mode."""

import pytest
import tempfile
from pathlib import Path
from holdem.types import BucketConfig, MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.mccfr.chunked_coordinator import ChunkedTrainingCoordinator


def create_test_bucketing():
    """Create minimal bucketing for testing."""
    config = BucketConfig(
        k_preflop=4,
        k_flop=4,
        k_turn=4,
        k_river=4,
        num_samples=100,
        seed=42
    )
    return HandBucketing(config)


def test_chunked_config_validation():
    """Test that chunked training config validation works."""
    bucketing = create_test_bucketing()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Should fail without enable_chunked_training
        config = MCCFRConfig(
            num_iterations=1000,
            enable_chunked_training=False
        )
        
        with pytest.raises(ValueError, match="Chunked training not enabled"):
            ChunkedTrainingCoordinator(
                config=config,
                bucketing=bucketing,
                logdir=logdir
            )
        
        # Should fail without chunk size specified
        config = MCCFRConfig(
            num_iterations=1000,
            enable_chunked_training=True
        )
        
        with pytest.raises(ValueError, match="Must specify either chunk_size_iterations or chunk_size_minutes"):
            ChunkedTrainingCoordinator(
                config=config,
                bucketing=bucketing,
                logdir=logdir
            )


def test_chunked_training_cumulative_time():
    """Test that cumulative elapsed time is tracked correctly across chunks."""
    bucketing = create_test_bucketing()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Create solver and run some iterations
        config = MCCFRConfig(
            num_iterations=100,
            checkpoint_interval=50,
            discount_interval=10,
            discount_mode="none",
            enable_chunked_training=False  # Not using coordinator, just testing solver
        )
        
        solver = MCCFRSolver(
            config=config,
            bucketing=bucketing,
            num_players=2
        )
        
        # Simulate elapsed time and save checkpoint
        solver.iteration = 50
        elapsed_1 = 10.0  # 10 seconds
        solver.save_checkpoint(logdir, solver.iteration, elapsed_1)
        
        # Verify cumulative time is stored
        metadata_file = logdir / "checkpoints" / f"checkpoint_iter50_t{int(elapsed_1)}s_metadata.json"
        assert metadata_file.exists()
        
        # Load checkpoint in a new solver
        solver2 = MCCFRSolver(
            config=config,
            bucketing=bucketing,
            num_players=2
        )
        
        checkpoint_file = logdir / "checkpoints" / f"checkpoint_iter50_t{int(elapsed_1)}s.pkl"
        loaded_iter = solver2.load_checkpoint(checkpoint_file)
        
        assert loaded_iter == 50
        assert solver2._cumulative_elapsed_seconds == elapsed_1
        
        # Continue training and save another checkpoint
        solver2.iteration = 100
        elapsed_2 = 15.0  # Another 15 seconds
        solver2.save_checkpoint(logdir, solver2.iteration, elapsed_2)
        
        # Check that cumulative time is updated
        metadata_file2 = logdir / "checkpoints" / f"checkpoint_iter100_t{int(elapsed_1 + elapsed_2)}s_metadata.json"
        assert metadata_file2.exists()
        
        from holdem.utils.serialization import load_json
        metadata = load_json(metadata_file2)
        assert metadata['elapsed_seconds'] == elapsed_1 + elapsed_2
        assert metadata['chunk_elapsed_seconds'] == elapsed_2


def test_chunked_training_checkpoint_resume():
    """Test that chunked training can resume from checkpoint."""
    bucketing = create_test_bucketing()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # First chunk
        config = MCCFRConfig(
            num_iterations=100,
            enable_chunked_training=True,
            chunk_size_iterations=50,
            checkpoint_interval=25,
            discount_interval=10,
            discount_mode="none"
        )
        
        coordinator = ChunkedTrainingCoordinator(
            config=config,
            bucketing=bucketing,
            logdir=logdir,
            num_players=2,
            use_tensorboard=False
        )
        
        # Run first chunk (should run 50 iterations and save checkpoint)
        coordinator.run()
        
        # Verify checkpoint exists
        checkpoint_files = list((logdir / "checkpoints").glob("checkpoint_*.pkl"))
        assert len(checkpoint_files) > 0
        
        # Find latest checkpoint
        latest_checkpoint = coordinator._find_latest_checkpoint()
        assert latest_checkpoint is not None
        
        # Load and verify
        from holdem.utils.serialization import load_json
        metadata_file = latest_checkpoint.parent / f"{latest_checkpoint.stem}_metadata.json"
        metadata = load_json(metadata_file)
        
        # Should have completed first chunk (50 iterations)
        assert metadata['iteration'] >= 50


def test_chunked_training_iteration_boundaries():
    """Test that chunked training respects iteration boundaries."""
    bucketing = create_test_bucketing()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        config = MCCFRConfig(
            num_iterations=100,
            enable_chunked_training=True,
            chunk_size_iterations=30,
            discount_interval=10,
            discount_mode="none"
        )
        
        coordinator = ChunkedTrainingCoordinator(
            config=config,
            bucketing=bucketing,
            logdir=logdir,
            num_players=2,
            use_tensorboard=False
        )
        
        # Run first chunk
        coordinator.run()
        
        # Check iteration count
        latest_checkpoint = coordinator._find_latest_checkpoint()
        from holdem.utils.serialization import load_json
        metadata_file = latest_checkpoint.parent / f"{latest_checkpoint.stem}_metadata.json"
        metadata = load_json(metadata_file)
        
        # Should be at or near chunk boundary (30 iterations)
        assert 28 <= metadata['iteration'] <= 32


def test_find_latest_checkpoint():
    """Test finding the latest complete checkpoint."""
    bucketing = create_test_bucketing()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        checkpoint_dir = logdir / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        
        config = MCCFRConfig(
            num_iterations=100,
            enable_chunked_training=True,
            chunk_size_iterations=50
        )
        
        coordinator = ChunkedTrainingCoordinator(
            config=config,
            bucketing=bucketing,
            logdir=logdir
        )
        
        # No checkpoint should exist initially
        assert coordinator._find_latest_checkpoint() is None
        
        # Create a solver and save some checkpoints
        solver_config = MCCFRConfig(
            num_iterations=100,
            discount_interval=10,
            discount_mode="none"
        )
        
        solver = MCCFRSolver(
            config=solver_config,
            bucketing=bucketing,
            num_players=2
        )
        
        # Save checkpoint 1
        solver.iteration = 25
        solver.save_checkpoint(logdir, solver.iteration, 10.0)
        
        # Save checkpoint 2
        solver.iteration = 50
        solver.save_checkpoint(logdir, solver.iteration, 20.0)
        
        # Should find the latest (checkpoint 2)
        latest = coordinator._find_latest_checkpoint()
        assert latest is not None
        assert "iter50" in latest.name


def test_training_completion_detection():
    """Test that training completion is detected correctly."""
    bucketing = create_test_bucketing()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Test iteration-based completion
        config = MCCFRConfig(
            num_iterations=100,
            enable_chunked_training=True,
            chunk_size_iterations=50,
            discount_interval=10,
            discount_mode="none"
        )
        
        coordinator = ChunkedTrainingCoordinator(
            config=config,
            bucketing=bucketing,
            logdir=logdir
        )
        
        solver = MCCFRSolver(
            config=config,
            bucketing=bucketing,
            num_players=2
        )
        
        # Not complete yet
        solver.iteration = 50
        assert not coordinator._is_training_complete(solver)
        
        # Complete
        solver.iteration = 100
        assert coordinator._is_training_complete(solver)
        
        # Test time-budget completion
        config_time = MCCFRConfig(
            time_budget_seconds=100.0,
            enable_chunked_training=True,
            chunk_size_minutes=1.0,
            discount_interval=10,
            discount_mode="none"
        )
        
        coordinator_time = ChunkedTrainingCoordinator(
            config=config_time,
            bucketing=bucketing,
            logdir=logdir
        )
        
        solver_time = MCCFRSolver(
            config=config_time,
            bucketing=bucketing,
            num_players=2
        )
        
        # Not complete yet
        solver_time._cumulative_elapsed_seconds = 50.0
        assert not coordinator_time._is_training_complete(solver_time)
        
        # Complete
        solver_time._cumulative_elapsed_seconds = 100.0
        assert coordinator_time._is_training_complete(solver_time)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
