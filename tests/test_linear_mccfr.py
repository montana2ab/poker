"""Test Linear MCCFR with discounting and dynamic pruning."""

import pytest
import numpy as np
from holdem.types import MCCFRConfig
from holdem.mccfr.regrets import RegretTracker
from holdem.abstraction.actions import AbstractAction


def test_linear_weighting_regret_update():
    """Test that linear weighting is applied correctly to regret updates."""
    tracker = RegretTracker()
    
    infoset = "test_infoset"
    action = AbstractAction.FOLD
    
    # Update with weight = 1 (iteration 1)
    tracker.update_regret(infoset, action, regret=10.0, weight=1.0)
    assert abs(tracker.get_regret(infoset, action) - 10.0) < 0.01
    
    # Update with weight = 2 (iteration 2)
    tracker.update_regret(infoset, action, regret=5.0, weight=2.0)
    # Total should be 10.0 + 2.0 * 5.0 = 20.0
    assert abs(tracker.get_regret(infoset, action) - 20.0) < 0.01
    
    # Update with weight = 3 (iteration 3)
    tracker.update_regret(infoset, action, regret=-2.0, weight=3.0)
    # Total should be 20.0 + 3.0 * (-2.0) = 14.0
    assert abs(tracker.get_regret(infoset, action) - 14.0) < 0.01


def test_linear_weighting_strategy_accumulation():
    """Test that linear weighting is applied correctly to strategy accumulation."""
    tracker = RegretTracker()
    
    infoset = "test_infoset"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL]
    strategy = {
        AbstractAction.FOLD: 0.3,
        AbstractAction.CHECK_CALL: 0.7
    }
    
    # Add strategy with weight = 1 (iteration 1)
    tracker.add_strategy(infoset, strategy, weight=1.0)
    
    # Add strategy with weight = 2 (iteration 2)
    tracker.add_strategy(infoset, strategy, weight=2.0)
    
    # Total weight = 1.0 + 2.0 = 3.0
    # FOLD: 0.3 * 1.0 + 0.3 * 2.0 = 0.9
    # CHECK_CALL: 0.7 * 1.0 + 0.7 * 2.0 = 2.1
    # Average: FOLD = 0.9/3.0 = 0.3, CHECK_CALL = 2.1/3.0 = 0.7
    avg_strategy = tracker.get_average_strategy(infoset, actions)
    assert abs(avg_strategy[AbstractAction.FOLD] - 0.3) < 0.01
    assert abs(avg_strategy[AbstractAction.CHECK_CALL] - 0.7) < 0.01


def test_separate_discount_factors():
    """Test that separate alpha and beta discount factors work correctly."""
    tracker = RegretTracker()
    
    infoset = "test_infoset"
    action = AbstractAction.FOLD
    
    # Set up initial regrets and strategy
    tracker.update_regret(infoset, action, regret=100.0, weight=1.0)
    tracker.add_strategy(infoset, {action: 1.0}, weight=100.0)
    
    # Apply different discount factors
    alpha = 0.5  # Regret discount
    beta = 0.8   # Strategy discount
    tracker.discount(regret_factor=alpha, strategy_factor=beta)
    
    # Check regret is discounted by alpha
    assert abs(tracker.get_regret(infoset, action) - 50.0) < 0.01
    
    # Check strategy is discounted by beta
    assert abs(tracker.strategy_sum[infoset][action] - 80.0) < 0.01


def test_should_prune_logic():
    """Test the should_prune method for dynamic pruning."""
    tracker = RegretTracker()
    
    infoset = "test_infoset"
    actions = [
        AbstractAction.FOLD,
        AbstractAction.CHECK_CALL,
        AbstractAction.BET_HALF_POT
    ]
    threshold = -300_000_000.0
    
    # No regrets yet - should not prune
    assert not tracker.should_prune(infoset, actions, threshold)
    
    # All regrets below threshold - should prune
    tracker.update_regret(infoset, AbstractAction.FOLD, -400_000_000.0)
    tracker.update_regret(infoset, AbstractAction.CHECK_CALL, -350_000_000.0)
    tracker.update_regret(infoset, AbstractAction.BET_HALF_POT, -500_000_000.0)
    assert tracker.should_prune(infoset, actions, threshold)
    
    # One action above threshold - should not prune
    tracker.update_regret(infoset, AbstractAction.CHECK_CALL, 100_000_000.0)
    assert not tracker.should_prune(infoset, actions, threshold)
    
    # All regrets exactly at threshold - should not prune
    tracker.update_regret(infoset, AbstractAction.FOLD, 100_000_000.0)
    tracker.update_regret(infoset, AbstractAction.BET_HALF_POT, 200_000_000.0)
    for action in actions:
        tracker.regrets[infoset][action] = threshold
    assert not tracker.should_prune(infoset, actions, threshold)


def test_default_config_values():
    """Test that default MCCFRConfig values are set correctly."""
    config = MCCFRConfig()
    
    # Check Linear MCCFR defaults
    assert config.use_linear_weighting == True
    assert config.discount_interval == 1000
    assert config.regret_discount_alpha == 1.0
    assert config.strategy_discount_beta == 1.0
    
    # Check pruning defaults
    assert config.enable_pruning == True
    assert config.pruning_threshold == -300_000_000.0
    assert config.pruning_probability == 0.95


def test_backward_compatibility():
    """Test backward compatibility with old update_regret signature."""
    tracker = RegretTracker()
    
    infoset = "test_infoset"
    action = AbstractAction.FOLD
    
    # Old signature: update_regret(infoset, action, regret)
    # Should default to weight=1.0
    tracker.update_regret(infoset, action, 10.0)
    assert abs(tracker.get_regret(infoset, action) - 10.0) < 0.01
    
    # New signature: update_regret(infoset, action, regret, weight)
    tracker.update_regret(infoset, action, 5.0, 2.0)
    assert abs(tracker.get_regret(infoset, action) - 20.0) < 0.01


def test_linear_weighting_impact():
    """Test that linear weighting gives more weight to later iterations."""
    tracker = RegretTracker()
    
    infoset = "test_infoset"
    action = AbstractAction.FOLD
    
    # Without linear weighting (weight=1.0 for all iterations)
    tracker_standard = RegretTracker()
    for i in range(1, 11):
        tracker_standard.update_regret(infoset, action, 1.0, 1.0)
    standard_regret = tracker_standard.get_regret(infoset, action)
    assert abs(standard_regret - 10.0) < 0.01  # 10 iterations × 1.0
    
    # With linear weighting (weight=iteration number)
    tracker_linear = RegretTracker()
    for i in range(1, 11):
        tracker_linear.update_regret(infoset, action, 1.0, float(i))
    linear_regret = tracker_linear.get_regret(infoset, action)
    # Sum of 1 to 10 = 55
    assert abs(linear_regret - 55.0) < 0.01
    
    # Linear weighting should give more total regret
    assert linear_regret > standard_regret


def test_discount_preserves_ratios():
    """Test that discounting preserves relative ratios for regrets."""
    tracker = RegretTracker()
    
    infoset = "test_infoset"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_HALF_POT]
    
    # Set up regrets with specific ratios
    tracker.update_regret(infoset, AbstractAction.FOLD, 100.0)
    tracker.update_regret(infoset, AbstractAction.CHECK_CALL, 200.0)
    tracker.update_regret(infoset, AbstractAction.BET_HALF_POT, 300.0)
    
    # Get ratios before discount
    r1_before = tracker.get_regret(infoset, AbstractAction.FOLD)
    r2_before = tracker.get_regret(infoset, AbstractAction.CHECK_CALL)
    r3_before = tracker.get_regret(infoset, AbstractAction.BET_HALF_POT)
    ratio_12_before = r1_before / r2_before if r2_before != 0 else 0
    ratio_23_before = r2_before / r3_before if r3_before != 0 else 0
    
    # Apply discount
    tracker.discount(regret_factor=0.5, strategy_factor=1.0)
    
    # Get ratios after discount
    r1_after = tracker.get_regret(infoset, AbstractAction.FOLD)
    r2_after = tracker.get_regret(infoset, AbstractAction.CHECK_CALL)
    r3_after = tracker.get_regret(infoset, AbstractAction.BET_HALF_POT)
    ratio_12_after = r1_after / r2_after if r2_after != 0 else 0
    ratio_23_after = r2_after / r3_after if r3_after != 0 else 0
    
    # Ratios should be preserved
    assert abs(ratio_12_before - ratio_12_after) < 0.01
    assert abs(ratio_23_before - ratio_23_after) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

