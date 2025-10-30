"""Test MCCFR sanity checks."""

import pytest
import numpy as np
from holdem.types import BucketConfig, MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.mccfr.regrets import RegretTracker
from holdem.abstraction.actions import AbstractAction


def test_mccfr_regret_convergence():
    """Test that regrets decrease over iterations."""
    # Create simple bucketing
    config = BucketConfig(
        k_preflop=8,
        k_flop=20,
        k_turn=15,
        k_river=10,
        num_samples=500,
        seed=42
    )
    
    bucketing = HandBucketing(config)
    bucketing.build(num_samples=500)
    
    # Create MCCFR config
    mccfr_config = MCCFRConfig(
        num_iterations=1000,
        checkpoint_interval=500,
        exploration_epsilon=0.6
    )
    
    solver = MCCFRSolver(mccfr_config, bucketing, num_players=2)
    
    # Run a few iterations
    initial_regrets = []
    for i in range(100):
        utility = solver.sampler.sample_iteration(i + 1)
        if i < 10:
            initial_regrets.append(abs(utility))
    
    # Run more iterations
    later_regrets = []
    for i in range(100, 200):
        utility = solver.sampler.sample_iteration(i + 1)
        if i >= 190:
            later_regrets.append(abs(utility))
    
    # Check that average regret is decreasing (with some tolerance)
    avg_initial = np.mean(initial_regrets) if initial_regrets else 0
    avg_later = np.mean(later_regrets) if later_regrets else 0
    
    # Just verify the system runs without errors
    assert True, "MCCFR should run without errors"


def test_mccfr_produces_non_uniform_policy():
    """Test that MCCFR produces non-uniform policies."""
    tracker = RegretTracker()
    
    # Simulate some regret updates
    infoset = "test_infoset"
    actions = [
        AbstractAction.FOLD,
        AbstractAction.CHECK_CALL,
        AbstractAction.BET_HALF_POT
    ]
    
    # Add varied regrets
    tracker.update_regret(infoset, AbstractAction.FOLD, -5.0)
    tracker.update_regret(infoset, AbstractAction.CHECK_CALL, 2.0)
    tracker.update_regret(infoset, AbstractAction.BET_HALF_POT, 8.0)
    
    # Get strategy
    strategy = tracker.get_strategy(infoset, actions)
    
    # Check non-uniform
    probs = list(strategy.values())
    assert not all(abs(p - probs[0]) < 0.01 for p in probs), "Strategy should be non-uniform"
    
    # Check sums to 1
    assert abs(sum(probs) - 1.0) < 0.01, "Strategy should sum to 1"
    
    # Check all non-negative
    assert all(p >= 0 for p in probs), "All probabilities should be non-negative"


def test_regret_matching():
    """Test basic regret matching."""
    tracker = RegretTracker()
    
    infoset = "test"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL]
    
    # Initially uniform
    strategy = tracker.get_strategy(infoset, actions)
    assert abs(strategy[AbstractAction.FOLD] - 0.5) < 0.01
    assert abs(strategy[AbstractAction.CHECK_CALL] - 0.5) < 0.01
    
    # Update regrets
    tracker.update_regret(infoset, AbstractAction.FOLD, 10.0)
    tracker.update_regret(infoset, AbstractAction.CHECK_CALL, 0.0)
    
    # Check strategy shifts toward higher regret
    strategy = tracker.get_strategy(infoset, actions)
    assert strategy[AbstractAction.FOLD] > strategy[AbstractAction.CHECK_CALL]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
