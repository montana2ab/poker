"""Test logging setup in multi-instance coordinator."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Mock heavy dependencies before importing
sys.modules['numpy'] = MagicMock()
sys.modules['scipy'] = MagicMock()
sys.modules['scipy.stats'] = MagicMock()
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()
sys.modules['eval7'] = MagicMock()
sys.modules['torch'] = MagicMock()
sys.modules['torch.utils'] = MagicMock()
sys.modules['torch.utils.tensorboard'] = MagicMock()
sys.modules['cv2'] = MagicMock()
sys.modules['PIL'] = MagicMock()

import pytest


def test_setup_logger_with_log_file():
    """Test that setup_logger correctly accepts log_file parameter."""
    from holdem.utils.logging import setup_logger
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        log_file = logdir / "test.log"
        
        # This should work without error
        logger = setup_logger("test_logger", log_file=log_file)
        
        # Verify logger was created
        assert logger is not None
        assert logger.name == "test_logger"
        
        # Verify log file was created
        assert log_file.exists()
        
        # Verify logger has at least 2 handlers (console + file)
        assert len(logger.handlers) >= 2


def test_multi_instance_logger_setup():
    """Test that _run_solver_instance correctly sets up logger."""
    from holdem.mccfr.multi_instance_coordinator import _run_solver_instance
    from holdem.types import MCCFRConfig
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        progress_file = logdir / "progress.json"
        
        # Create a minimal config for time-budget mode
        config = MCCFRConfig(
            time_budget_seconds=10,  # Short time for test
            snapshot_interval_seconds=5,
            discount_interval=100,
            num_workers=1
        )
        
        # Mock the bucketing and solver to avoid actual training
        mock_bucketing = MagicMock()
        
        with patch('holdem.mccfr.multi_instance_coordinator.MCCFRSolver') as mock_solver_class:
            mock_solver = MagicMock()
            mock_solver_class.return_value = mock_solver
            mock_solver.train.return_value = None
            
            # This should not raise TypeError about log level
            try:
                _run_solver_instance(
                    instance_id=0,
                    config=config,
                    bucketing=mock_bucketing,
                    num_players=6,
                    logdir=logdir,
                    use_tensorboard=False,
                    progress_file=progress_file,
                    use_time_budget=True
                )
            except TypeError as e:
                if "Level not an integer" in str(e):
                    pytest.fail(f"setup_logger called with wrong parameter: {e}")
                # Other TypeErrors might be expected due to mocking
                pass
            except Exception:
                # Other exceptions are fine for this test - we're just checking
                # that setup_logger is called correctly
                pass
            
            # Verify log file was created
            instance_log = logdir / "instance_0.log"
            assert instance_log.exists(), "Instance log file should be created"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
