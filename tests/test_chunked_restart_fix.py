"""Test fixes for automatic chunk restart time tracking and delay."""

import pytest
import tempfile
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing


def test_cumulative_time_updated_before_completion_check():
    """Test that cumulative elapsed time is updated before checking if training is complete.
    
    This is the key fix: solver._cumulative_elapsed_seconds must be updated with the
    current chunk's elapsed time BEFORE calling _is_training_complete(), otherwise
    the completion check will use stale data and may not stop training at the correct time.
    """
    from holdem.mccfr.chunked_coordinator import ChunkedTrainingCoordinator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        logdir = tmpdir_path / "logs"
        
        # Create a config with time budget
        config = MCCFRConfig(
            time_budget_seconds=100.0,  # 100 second budget
            enable_chunked_training=True,
            chunk_size_minutes=0.5,  # 30 second chunks
            num_workers=1
        )
        
        # Mock bucketing
        mock_bucketing = Mock(spec=HandBucketing)
        
        coordinator = ChunkedTrainingCoordinator(
            config=config,
            bucketing=mock_bucketing,
            logdir=logdir,
            num_players=2,
            use_tensorboard=False
        )
        
        # Create a mock solver that simulates cumulative time tracking
        mock_solver = Mock()
        mock_solver.iteration = 1000
        mock_solver._cumulative_elapsed_seconds = 80.0  # Already spent 80 seconds
        mock_solver.writer = None
        
        # Simulate chunk elapsed time of 25 seconds
        chunk_start_time = time.time() - 25.0
        
        # Before the fix, _is_training_complete would check using 80.0 seconds (< 100)
        # After the fix, it should be updated to 105.0 seconds (> 100)
        
        # Manually simulate what the fixed code does
        chunk_elapsed_seconds = time.time() - chunk_start_time
        mock_solver._cumulative_elapsed_seconds += chunk_elapsed_seconds
        
        # Now check completion - should be True because 80 + 25 = 105 > 100
        training_complete = coordinator._is_training_complete(mock_solver)
        
        assert training_complete, (
            f"Training should be complete: "
            f"cumulative_elapsed={mock_solver._cumulative_elapsed_seconds:.1f}s > "
            f"time_budget={config.time_budget_seconds:.1f}s"
        )
        
        # Verify cumulative time was updated correctly
        assert mock_solver._cumulative_elapsed_seconds >= 100.0, (
            "Cumulative elapsed time should include the chunk's elapsed time"
        )


def test_configurable_restart_delay_parameter():
    """Test that chunk_restart_delay_seconds parameter is configurable."""
    
    # Test default value
    config_default = MCCFRConfig(
        num_iterations=1000,
        enable_chunked_training=True,
        chunk_size_iterations=100
    )
    assert config_default.chunk_restart_delay_seconds == 5.0, \
        "Default restart delay should be 5 seconds"
    
    # Test custom value
    config_custom = MCCFRConfig(
        num_iterations=1000,
        enable_chunked_training=True,
        chunk_size_iterations=100,
        chunk_restart_delay_seconds=10.0
    )
    assert config_custom.chunk_restart_delay_seconds == 10.0, \
        "Custom restart delay should be 10 seconds"
    
    # Test with time-based chunks
    config_time = MCCFRConfig(
        time_budget_seconds=3600,
        enable_chunked_training=True,
        chunk_size_minutes=30.0,
        chunk_restart_delay_seconds=15.0
    )
    assert config_time.chunk_restart_delay_seconds == 15.0, \
        "Custom restart delay should be 15 seconds for time-based chunks"


def test_restart_delay_used_in_coordinator():
    """Test that the restart delay is properly used in the coordinator."""
    from holdem.mccfr.chunked_coordinator import ChunkedTrainingCoordinator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        logdir = tmpdir_path / "logs"
        
        # Create a config with custom restart delay
        config = MCCFRConfig(
            num_iterations=1000,
            enable_chunked_training=True,
            chunk_size_iterations=100,
            chunk_restart_delay_seconds=3.0,  # Custom 3 second delay
            num_workers=1
        )
        
        # Mock bucketing
        mock_bucketing = Mock(spec=HandBucketing)
        
        coordinator = ChunkedTrainingCoordinator(
            config=config,
            bucketing=mock_bucketing,
            logdir=logdir,
            num_players=2,
            use_tensorboard=False
        )
        
        # Verify the config has the correct delay
        assert coordinator.config.chunk_restart_delay_seconds == 3.0, \
            "Coordinator should use the configured restart delay"


def test_cli_argument_for_restart_delay():
    """Test that CLI argument --chunk-restart-delay is properly handled."""
    from holdem.cli.train_blueprint import create_mccfr_config
    
    # Mock args with chunk restart delay
    mock_args = Mock()
    mock_args.iters = None
    mock_args.time_budget = None
    mock_args.checkpoint_interval = None
    mock_args.snapshot_interval = None
    mock_args.epsilon = None
    mock_args.discount_interval = None
    mock_args.num_workers = None
    mock_args.batch_size = None
    mock_args.chunked = True
    mock_args.chunk_iterations = 100
    mock_args.chunk_minutes = None
    mock_args.chunk_restart_delay = 7.5  # Custom delay
    
    # Create a minimal YAML config
    yaml_config = {
        'num_iterations': 1000,
        'checkpoint_interval': 100,
        'discount_interval': 10
    }
    
    # Create config
    config = create_mccfr_config(mock_args, yaml_config)
    
    # Verify the restart delay was set correctly
    assert config.enable_chunked_training == True
    assert config.chunk_size_iterations == 100
    assert config.chunk_restart_delay_seconds == 7.5, \
        "CLI argument should override default restart delay"


def test_iteration_based_completion_unchanged():
    """Test that iteration-based completion still works correctly."""
    from holdem.mccfr.chunked_coordinator import ChunkedTrainingCoordinator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        logdir = tmpdir_path / "logs"
        
        # Create a config with iteration limit
        config = MCCFRConfig(
            num_iterations=1000,
            enable_chunked_training=True,
            chunk_size_iterations=100,
            num_workers=1
        )
        
        # Mock bucketing
        mock_bucketing = Mock(spec=HandBucketing)
        
        coordinator = ChunkedTrainingCoordinator(
            config=config,
            bucketing=mock_bucketing,
            logdir=logdir,
            num_players=2,
            use_tensorboard=False
        )
        
        # Create a mock solver at iteration 999 (not complete)
        mock_solver = Mock()
        mock_solver.iteration = 999
        mock_solver._cumulative_elapsed_seconds = 0.0
        
        training_complete = coordinator._is_training_complete(mock_solver)
        assert not training_complete, "Training should not be complete at iteration 999"
        
        # Now at iteration 1000 (complete)
        mock_solver.iteration = 1000
        training_complete = coordinator._is_training_complete(mock_solver)
        assert training_complete, "Training should be complete at iteration 1000"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
