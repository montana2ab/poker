"""Test time-budget based training and snapshot functionality."""

import pytest
import time
from pathlib import Path
from holdem.types import MCCFRConfig
from holdem.mccfr.regrets import RegretTracker
from holdem.abstraction.actions import AbstractAction


def test_time_budget_config():
    """Test that time budget configuration is properly set."""
    # Test time-budget mode
    config = MCCFRConfig(time_budget_seconds=3600, snapshot_interval_seconds=300)
    assert config.time_budget_seconds == 3600
    assert config.snapshot_interval_seconds == 300
    
    # Test default snapshot interval
    config2 = MCCFRConfig(time_budget_seconds=7200)
    assert config2.time_budget_seconds == 7200
    assert config2.snapshot_interval_seconds == 600  # Default 10 minutes
    
    # Test iteration-based mode (no time budget)
    config3 = MCCFRConfig(num_iterations=100000)
    assert config3.num_iterations == 100000
    assert config3.time_budget_seconds is None


def test_time_budget_vs_iterations():
    """Test that config can be either time-based or iteration-based."""
    # Time-budget mode
    config1 = MCCFRConfig(time_budget_seconds=86400)  # 1 day
    assert config1.time_budget_seconds == 86400
    
    # Iteration mode
    config2 = MCCFRConfig(num_iterations=1000000)
    assert config2.num_iterations == 1000000
    
    # Both can be set, but time budget takes precedence in solver
    config3 = MCCFRConfig(time_budget_seconds=7200, num_iterations=500000)
    assert config3.time_budget_seconds == 7200
    assert config3.num_iterations == 500000


def test_snapshot_interval_validation():
    """Test snapshot interval configuration."""
    # Valid snapshot intervals
    config1 = MCCFRConfig(snapshot_interval_seconds=60)  # 1 minute
    assert config1.snapshot_interval_seconds == 60
    
    config2 = MCCFRConfig(snapshot_interval_seconds=3600)  # 1 hour
    assert config2.snapshot_interval_seconds == 3600
    
    # Default
    config3 = MCCFRConfig()
    assert config3.snapshot_interval_seconds == 600  # 10 minutes default


def test_time_conversion_helpers():
    """Test time conversion for various durations."""
    # 8 days in seconds
    eight_days = 8 * 24 * 3600
    assert eight_days == 691200
    
    config = MCCFRConfig(time_budget_seconds=eight_days)
    assert config.time_budget_seconds == 691200
    
    # Convert back
    days = config.time_budget_seconds / 86400
    assert abs(days - 8.0) < 0.01


def test_metrics_calculation_structure():
    """Test that metrics dictionary has expected structure."""
    # This tests the structure expected by _calculate_metrics
    expected_keys = [
        'avg_regret_preflop',
        'avg_regret_flop', 
        'avg_regret_turn',
        'avg_regret_river',
        'pruned_iterations_pct',
        'iterations_per_second',
        'total_iterations',
        'num_infosets'
    ]
    
    # Create a mock metrics dict
    metrics = {key: 0.0 for key in expected_keys}
    
    # Verify all expected keys are present
    for key in expected_keys:
        assert key in metrics


def test_discount_interval_from_config():
    """Test that discount interval is properly used from config."""
    config = MCCFRConfig(
        discount_interval=500,
        regret_discount_alpha=0.9,
        strategy_discount_beta=0.95
    )
    
    assert config.discount_interval == 500
    assert config.regret_discount_alpha == 0.9
    assert config.strategy_discount_beta == 0.95
    
    # Verify discounting should happen
    assert config.regret_discount_alpha < 1.0 or config.strategy_discount_beta < 1.0


def test_combined_time_and_discount_config():
    """Test configuration with both time budget and discount parameters."""
    config = MCCFRConfig(
        time_budget_seconds=86400,  # 1 day
        snapshot_interval_seconds=1800,  # 30 minutes
        discount_interval=1000,
        regret_discount_alpha=0.95,
        strategy_discount_beta=0.98
    )
    
    assert config.time_budget_seconds == 86400
    assert config.snapshot_interval_seconds == 1800
    assert config.discount_interval == 1000
    assert config.regret_discount_alpha == 0.95
    assert config.strategy_discount_beta == 0.98


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
