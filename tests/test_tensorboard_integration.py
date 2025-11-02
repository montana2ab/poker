"""Tests for TensorBoard integration in MCCFR solver."""

import pytest
import tempfile
from pathlib import Path
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver


def test_tensorboard_import():
    """Test that TensorBoard import is handled gracefully."""
    try:
        from torch.utils.tensorboard import SummaryWriter
        assert True, "TensorBoard is available"
    except ImportError:
        pytest.skip("TensorBoard not installed")


def test_solver_initialization():
    """Test that solver initializes with TensorBoard support."""
    # Create minimal bucketing
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    config = MCCFRConfig(
        num_iterations=100,
        checkpoint_interval=50,
        exploration_epsilon=0.6
    )
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    assert solver.writer is None  # Not initialized until training starts
    assert solver.iteration == 0


def test_training_creates_tensorboard_logs():
    """Test that training creates TensorBoard log files."""
    # Create minimal bucketing
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    config = MCCFRConfig(
        num_iterations=100,
        checkpoint_interval=50,
        exploration_epsilon=0.6
    )
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Train with TensorBoard enabled
        solver.train(logdir=logdir, use_tensorboard=True)
        
        # Check that TensorBoard directory exists
        tensorboard_dir = logdir / "tensorboard"
        
        # If TensorBoard is available, check for event files
        try:
            from torch.utils.tensorboard import SummaryWriter
            assert tensorboard_dir.exists(), "TensorBoard directory should be created"
            
            # Check for event files (TensorBoard creates files with 'events.out.tfevents' pattern)
            event_files = list(tensorboard_dir.glob("events.out.tfevents.*"))
            assert len(event_files) > 0, "Should create at least one TensorBoard event file"
        except ImportError:
            pytest.skip("TensorBoard not installed, skipping event file check")


def test_training_without_tensorboard():
    """Test that training works without TensorBoard."""
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    config = MCCFRConfig(
        num_iterations=50,
        checkpoint_interval=25,
        exploration_epsilon=0.6
    )
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Train with TensorBoard disabled
        solver.train(logdir=logdir, use_tensorboard=False)
        
        # TensorBoard directory should not be created
        tensorboard_dir = logdir / "tensorboard"
        assert not tensorboard_dir.exists(), "TensorBoard directory should not be created when disabled"


def test_training_metrics_logged():
    """Test that training metrics are logged to TensorBoard."""
    try:
        from torch.utils.tensorboard import SummaryWriter
    except ImportError:
        pytest.skip("TensorBoard not installed")
    
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    config = MCCFRConfig(
        num_iterations=200,  # Need enough iterations to trigger logging
        checkpoint_interval=100,
        exploration_epsilon=0.6
    )
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Train with TensorBoard enabled
        solver.train(logdir=logdir, use_tensorboard=True)
        
        # Check that event files were created
        tensorboard_dir = logdir / "tensorboard"
        event_files = list(tensorboard_dir.glob("events.out.tfevents.*"))
        
        assert len(event_files) > 0, "Should create TensorBoard event files"
        
        # Check file is not empty
        assert event_files[0].stat().st_size > 0, "Event file should contain data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
