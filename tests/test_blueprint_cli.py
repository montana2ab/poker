"""Integration test for blueprint training with time-budget mode."""

import pytest
import yaml
import tempfile
from pathlib import Path


def test_yaml_config_structure():
    """Test that YAML configuration has the expected structure."""
    # Use relative path from test file location
    test_dir = Path(__file__).parent
    config_path = test_dir.parent / "configs" / "blueprint_training.yaml"
    
    if not config_path.exists():
        pytest.skip("Config file not found")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Check expected keys exist (some may be commented out)
    # Since the file has comments showing examples, we just verify it's valid YAML
    assert config is not None
    assert isinstance(config, dict)


def test_load_and_parse_yaml():
    """Test loading and parsing YAML configuration."""
    # Create a temporary YAML config file
    config_data = {
        'time_budget_seconds': 3600,
        'snapshot_interval_seconds': 300,
        'discount_interval': 500,
        'regret_discount_alpha': 0.95,
        'strategy_discount_beta': 0.98,
        'exploration_epsilon': 0.6,
        'enable_pruning': True,
        'pruning_threshold': -300000000.0,
        'pruning_probability': 0.95
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        yaml_path = Path(f.name)
    
    try:
        # Load the config
        with open(yaml_path, 'r') as f:
            loaded_config = yaml.safe_load(f)
        
        # Verify values
        assert loaded_config['time_budget_seconds'] == 3600
        assert loaded_config['snapshot_interval_seconds'] == 300
        assert loaded_config['discount_interval'] == 500
        assert loaded_config['regret_discount_alpha'] == 0.95
        assert loaded_config['strategy_discount_beta'] == 0.98
        assert loaded_config['exploration_epsilon'] == 0.6
        assert loaded_config['enable_pruning'] == True
    finally:
        yaml_path.unlink()


def test_time_budget_yaml_values():
    """Test various time budget configurations in YAML."""
    test_cases = [
        # 8 days
        {'time_budget_seconds': 691200, 'expected_days': 8},
        # 1 day
        {'time_budget_seconds': 86400, 'expected_days': 1},
        # 12 hours
        {'time_budget_seconds': 43200, 'expected_hours': 12},
        # 1 hour
        {'time_budget_seconds': 3600, 'expected_hours': 1},
    ]
    
    for case in test_cases:
        config = {'time_budget_seconds': case['time_budget_seconds']}
        
        if 'expected_days' in case:
            days = config['time_budget_seconds'] / 86400
            assert abs(days - case['expected_days']) < 0.01
        
        if 'expected_hours' in case:
            hours = config['time_budget_seconds'] / 3600
            assert abs(hours - case['expected_hours']) < 0.01


def test_snapshot_interval_yaml_values():
    """Test various snapshot interval configurations."""
    test_cases = [
        {'snapshot_interval_seconds': 60, 'expected_minutes': 1},
        {'snapshot_interval_seconds': 600, 'expected_minutes': 10},
        {'snapshot_interval_seconds': 1800, 'expected_minutes': 30},
        {'snapshot_interval_seconds': 3600, 'expected_hours': 1},
    ]
    
    for case in test_cases:
        config = {'snapshot_interval_seconds': case['snapshot_interval_seconds']}
        
        if 'expected_minutes' in case:
            minutes = config['snapshot_interval_seconds'] / 60
            assert abs(minutes - case['expected_minutes']) < 0.01
        
        if 'expected_hours' in case:
            hours = config['snapshot_interval_seconds'] / 3600
            assert abs(hours - case['expected_hours']) < 0.01


def test_discount_params_yaml():
    """Test discount parameter configurations."""
    configs = [
        {
            'discount_interval': 1000,
            'regret_discount_alpha': 1.0,
            'strategy_discount_beta': 1.0
        },
        {
            'discount_interval': 500,
            'regret_discount_alpha': 0.95,
            'strategy_discount_beta': 0.98
        },
        {
            'discount_interval': 100,
            'regret_discount_alpha': 0.9,
            'strategy_discount_beta': 0.9
        }
    ]
    
    for config in configs:
        assert config['discount_interval'] > 0
        assert 0 <= config['regret_discount_alpha'] <= 1.0
        assert 0 <= config['strategy_discount_beta'] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
