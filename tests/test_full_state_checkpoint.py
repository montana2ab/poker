"""Test full state checkpoint validation and loading."""

import pytest
import tempfile
from pathlib import Path
from holdem.types import BucketConfig, MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
from holdem.utils.serialization import save_json, save_pickle


def test_is_checkpoint_complete_valid():
    """Test that a complete checkpoint is recognized as valid."""
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
        
        mccfr_config = MCCFRConfig(num_iterations=10)
        solver = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        
        # Save a complete checkpoint
        solver.save_checkpoint(tmpdir, iteration=5, elapsed_seconds=1.0)
        
        # Check that is_checkpoint_complete returns True
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter5_t1s.pkl"
        assert MCCFRSolver.is_checkpoint_complete(checkpoint_path)


def test_is_checkpoint_complete_missing_metadata():
    """Test that a checkpoint without metadata is recognized as incomplete."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        checkpoint_dir = tmpdir / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        
        # Create only the main .pkl file
        checkpoint_path = checkpoint_dir / "checkpoint_iter5.pkl"
        save_pickle({"dummy": "data"}, checkpoint_path)
        
        # Create regrets file but not metadata
        regrets_path = checkpoint_dir / "checkpoint_iter5_regrets.pkl"
        save_pickle({"regrets": "data"}, regrets_path)
        
        # Should be incomplete (missing metadata)
        assert not MCCFRSolver.is_checkpoint_complete(checkpoint_path)


def test_is_checkpoint_complete_missing_regrets():
    """Test that a checkpoint without regrets is recognized as incomplete."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        checkpoint_dir = tmpdir / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        
        # Create only the main .pkl file
        checkpoint_path = checkpoint_dir / "checkpoint_iter5.pkl"
        save_pickle({"dummy": "data"}, checkpoint_path)
        
        # Create metadata file but not regrets
        metadata_path = checkpoint_dir / "checkpoint_iter5_metadata.json"
        save_json({"iteration": 5}, metadata_path)
        
        # Should be incomplete (missing regrets)
        assert not MCCFRSolver.is_checkpoint_complete(checkpoint_path)


def test_is_checkpoint_complete_missing_all():
    """Test that a checkpoint with only the main file is recognized as incomplete."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        checkpoint_dir = tmpdir / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        
        # Create only the main .pkl file
        checkpoint_path = checkpoint_dir / "checkpoint_iter5.pkl"
        save_pickle({"dummy": "data"}, checkpoint_path)
        
        # Should be incomplete (missing metadata and regrets)
        assert not MCCFRSolver.is_checkpoint_complete(checkpoint_path)


def test_is_checkpoint_complete_nonexistent():
    """Test that a non-existent checkpoint is recognized as incomplete."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        checkpoint_path = tmpdir / "nonexistent" / "checkpoint.pkl"
        
        # Should be incomplete (file doesn't exist)
        assert not MCCFRSolver.is_checkpoint_complete(checkpoint_path)


def test_load_checkpoint_rejects_incomplete():
    """Test that load_checkpoint raises ValueError for incomplete checkpoints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        checkpoint_dir = tmpdir / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        
        # Create incomplete checkpoint (only main .pkl file)
        checkpoint_path = checkpoint_dir / "checkpoint_iter5.pkl"
        save_pickle({"dummy": "data"}, checkpoint_path)
        
        # Create solver
        config = BucketConfig(k_preflop=4, num_samples=50, seed=42)
        bucketing = HandBucketing(config)
        bucketing.build(num_samples=50)
        
        mccfr_config = MCCFRConfig(num_iterations=10)
        solver = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        
        # Should raise ValueError for incomplete checkpoint
        with pytest.raises(ValueError, match="Incomplete checkpoint"):
            solver.load_checkpoint(checkpoint_path)


def test_load_checkpoint_accepts_complete():
    """Test that load_checkpoint successfully loads complete checkpoints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create bucketing and solver
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
        
        # Run a few iterations
        for i in range(5):
            solver.sampler.sample_iteration(i + 1)
            solver.iteration = i + 1
        
        # Save complete checkpoint
        solver.save_checkpoint(tmpdir, iteration=5, elapsed_seconds=1.0)
        
        # Create a new solver and load the checkpoint
        solver2 = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter5_t1s.pkl"
        
        # Should successfully load without error
        iteration = solver2.load_checkpoint(checkpoint_path, validate_buckets=True)
        assert iteration == 5


def test_coordinator_finds_complete_checkpoints():
    """Test that coordinator only considers complete checkpoints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create instance checkpoint directory
        instance_dir = tmpdir / "instance_0"
        checkpoint_dir = instance_dir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Create incomplete checkpoint (iter 1)
        incomplete_path = checkpoint_dir / "checkpoint_iter1.pkl"
        save_pickle({"data": "incomplete"}, incomplete_path)
        
        # Create complete checkpoint (iter 2)
        complete_path = checkpoint_dir / "checkpoint_iter2.pkl"
        save_pickle({"data": "complete"}, complete_path)
        save_json({"iteration": 2}, checkpoint_dir / "checkpoint_iter2_metadata.json")
        save_pickle({"regrets": "data"}, checkpoint_dir / "checkpoint_iter2_regrets.pkl")
        
        # Create coordinator
        config = BucketConfig(k_preflop=4, num_samples=50, seed=42)
        bucketing = HandBucketing(config)
        bucketing.build(num_samples=50)
        
        mccfr_config = MCCFRConfig(num_iterations=100)
        coordinator = MultiInstanceCoordinator(
            num_instances=1,
            config=mccfr_config,
            bucketing=bucketing,
            num_players=2
        )
        
        # Find checkpoints
        checkpoints = coordinator._find_resume_checkpoints(tmpdir)
        
        # Should find only the complete checkpoint (iter 2)
        assert len(checkpoints) == 1
        assert checkpoints[0] is not None
        assert checkpoints[0].name == "checkpoint_iter2.pkl"


def test_coordinator_handles_no_complete_checkpoints():
    """Test that coordinator handles case when no complete checkpoints exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create instance checkpoint directory with only incomplete checkpoints
        instance_dir = tmpdir / "instance_0"
        checkpoint_dir = instance_dir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Create several incomplete checkpoints
        for i in range(1, 4):
            incomplete_path = checkpoint_dir / f"checkpoint_iter{i}.pkl"
            save_pickle({"data": f"incomplete_{i}"}, incomplete_path)
            # Only create metadata for some, not regrets
            if i % 2 == 0:
                save_json({"iteration": i}, checkpoint_dir / f"checkpoint_iter{i}_metadata.json")
        
        # Create coordinator
        config = BucketConfig(k_preflop=4, num_samples=50, seed=42)
        bucketing = HandBucketing(config)
        bucketing.build(num_samples=50)
        
        mccfr_config = MCCFRConfig(num_iterations=100)
        coordinator = MultiInstanceCoordinator(
            num_instances=1,
            config=mccfr_config,
            bucketing=bucketing,
            num_players=2
        )
        
        # Find checkpoints
        checkpoints = coordinator._find_resume_checkpoints(tmpdir)
        
        # Should find no complete checkpoints
        assert len(checkpoints) == 1
        assert checkpoints[0] is None


def test_coordinator_selects_latest_complete_checkpoint():
    """Test that coordinator selects the most recent complete checkpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create instance checkpoint directory
        instance_dir = tmpdir / "instance_0"
        checkpoint_dir = instance_dir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Create multiple complete checkpoints with different timestamps
        import time
        for i in range(1, 4):
            complete_path = checkpoint_dir / f"checkpoint_iter{i}.pkl"
            save_pickle({"data": f"complete_{i}"}, complete_path)
            save_json({"iteration": i}, checkpoint_dir / f"checkpoint_iter{i}_metadata.json")
            save_pickle({"regrets": f"data_{i}"}, checkpoint_dir / f"checkpoint_iter{i}_regrets.pkl")
            time.sleep(0.01)  # Ensure different modification times
        
        # Create coordinator
        config = BucketConfig(k_preflop=4, num_samples=50, seed=42)
        bucketing = HandBucketing(config)
        bucketing.build(num_samples=50)
        
        mccfr_config = MCCFRConfig(num_iterations=100)
        coordinator = MultiInstanceCoordinator(
            num_instances=1,
            config=mccfr_config,
            bucketing=bucketing,
            num_players=2
        )
        
        # Find checkpoints
        checkpoints = coordinator._find_resume_checkpoints(tmpdir)
        
        # Should find the latest complete checkpoint (iter 3)
        assert len(checkpoints) == 1
        assert checkpoints[0] is not None
        assert checkpoints[0].name == "checkpoint_iter3.pkl"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
