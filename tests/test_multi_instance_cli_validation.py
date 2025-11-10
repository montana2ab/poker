"""Test multi-instance CLI validation for time-budget mode."""

import pytest
import yaml
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

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


def test_multi_instance_accepts_time_budget_from_cli():
    """Test that --num-instances now accepts --time-budget from CLI."""
    from holdem.cli.train_blueprint import main
    from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create fake buckets file
        buckets_path = Path(tmpdir) / "buckets.pkl"
        buckets_path.touch()
        
        test_args = [
            'train_blueprint',
            '--buckets', str(buckets_path),
            '--logdir', tmpdir,
            '--time-budget', '3600',
            '--num-instances', '2'
        ]
        
        with patch('sys.argv', test_args):
            with patch('holdem.cli.train_blueprint.HandBucketing.load') as mock_load:
                with patch.object(MultiInstanceCoordinator, 'train') as mock_train:
                    # Mock the bucketing load
                    mock_load.return_value = MagicMock()
                    # Mock the train method to avoid actually training
                    mock_train.return_value = 0
                    
                    # This should succeed without raising SystemExit
                    try:
                        result = main()
                        assert result == 0 or result is None
                    except SystemExit as e:
                        # Should not exit with error code
                        if e.code != 0 and e.code is not None:
                            pytest.fail(f"Expected success but got exit code {e.code}")


def test_multi_instance_accepts_time_budget_from_yaml():
    """Test that --num-instances now accepts time_budget_seconds from YAML config."""
    from holdem.cli.train_blueprint import main
    from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create YAML config with time_budget_seconds
        config_data = {
            'time_budget_seconds': 1800,
            'snapshot_interval_seconds': 180,
            'discount_interval': 500,
            'exploration_epsilon': 0.6
        }
        
        config_path = Path(tmpdir) / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create fake buckets file
        buckets_path = Path(tmpdir) / "buckets.pkl"
        buckets_path.touch()
        
        test_args = [
            'train_blueprint',
            '--config', str(config_path),
            '--buckets', str(buckets_path),
            '--logdir', tmpdir,
            '--num-instances', '2'
        ]
        
        with patch('sys.argv', test_args):
            with patch('holdem.cli.train_blueprint.HandBucketing.load') as mock_load:
                with patch.object(MultiInstanceCoordinator, 'train') as mock_train:
                    # Mock the bucketing load to avoid file issues
                    mock_load.return_value = MagicMock()
                    # Mock the train method to avoid actually training
                    mock_train.return_value = 0
                    
                    # This should succeed without raising SystemExit
                    try:
                        result = main()
                        assert result == 0 or result is None
                    except SystemExit as e:
                        # Should not exit with error code
                        if e.code != 0 and e.code is not None:
                            pytest.fail(f"Expected success but got exit code {e.code}")


def test_multi_instance_accepts_iters_from_cli():
    """Test that --num-instances works with --iters from CLI."""
    from holdem.cli.train_blueprint import main
    from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create fake buckets file
        buckets_path = Path(tmpdir) / "buckets.pkl"
        buckets_path.touch()
        
        test_args = [
            'train_blueprint',
            '--buckets', str(buckets_path),
            '--logdir', tmpdir,
            '--iters', '1000',
            '--num-instances', '2'
        ]
        
        with patch('sys.argv', test_args):
            with patch('holdem.cli.train_blueprint.HandBucketing.load') as mock_load:
                with patch.object(MultiInstanceCoordinator, 'train') as mock_train:
                    # Mock the bucketing load
                    mock_load.return_value = MagicMock()
                    # Mock the train method to avoid actually training
                    mock_train.return_value = 0
                    
                    # This should succeed without raising SystemExit
                    try:
                        result = main()
                        assert result == 0 or result is None
                    except SystemExit as e:
                        # Should not exit with error code
                        if e.code != 0 and e.code is not None:
                            pytest.fail(f"Expected success but got exit code {e.code}")


def test_multi_instance_accepts_iters_from_yaml():
    """Test that --num-instances works with num_iterations from YAML config."""
    from holdem.cli.train_blueprint import main
    from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create YAML config with num_iterations (not time_budget_seconds)
        config_data = {
            'num_iterations': 1000,
            'checkpoint_interval': 100,
            'discount_interval': 500,
            'exploration_epsilon': 0.6
        }
        
        config_path = Path(tmpdir) / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create fake buckets file
        buckets_path = Path(tmpdir) / "buckets.pkl"
        buckets_path.touch()
        
        test_args = [
            'train_blueprint',
            '--config', str(config_path),
            '--buckets', str(buckets_path),
            '--logdir', tmpdir,
            '--num-instances', '2'
        ]
        
        with patch('sys.argv', test_args):
            with patch('holdem.cli.train_blueprint.HandBucketing.load') as mock_load:
                with patch.object(MultiInstanceCoordinator, 'train') as mock_train:
                    # Mock the bucketing load
                    mock_load.return_value = MagicMock()
                    # Mock the train method to avoid actually training
                    mock_train.return_value = 0
                    
                    # This should succeed without raising SystemExit
                    try:
                        result = main()
                        assert result == 0 or result is None
                    except SystemExit as e:
                        # Should not exit with error code
                        if e.code != 0 and e.code is not None:
                            pytest.fail(f"Expected success but got exit code {e.code}")


def test_multi_instance_cli_iters_override_yaml_time_budget():
    """Test that CLI --iters overrides YAML time_budget_seconds in multi-instance mode."""
    from holdem.cli.train_blueprint import main
    from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create YAML config with time_budget_seconds (should be overridden by CLI)
        config_data = {
            'time_budget_seconds': 1800,
            'snapshot_interval_seconds': 180,
            'discount_interval': 500,
            'exploration_epsilon': 0.6
        }
        
        config_path = Path(tmpdir) / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create fake buckets file
        buckets_path = Path(tmpdir) / "buckets.pkl"
        buckets_path.touch()
        
        test_args = [
            'train_blueprint',
            '--config', str(config_path),
            '--buckets', str(buckets_path),
            '--logdir', tmpdir,
            '--iters', '1000',  # CLI override
            '--num-instances', '2'
        ]
        
        with patch('sys.argv', test_args):
            with patch('holdem.cli.train_blueprint.HandBucketing.load') as mock_load:
                with patch.object(MultiInstanceCoordinator, 'train') as mock_train:
                    # Mock the bucketing load
                    mock_load.return_value = MagicMock()
                    # Mock the train method to avoid actually training
                    mock_train.return_value = 0
                    
                    # This should succeed because CLI --iters overrides YAML time_budget
                    try:
                        result = main()
                        assert result == 0 or result is None
                    except SystemExit as e:
                        # Should not exit with error code
                        if e.code != 0 and e.code is not None:
                            pytest.fail(f"Expected success but got exit code {e.code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
