"""Tests for compact storage functionality."""

import pytest
import numpy as np
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.regrets import RegretTracker
from holdem.mccfr.compact_storage import CompactRegretStorage


def test_compact_storage_basic_operations():
    """Test basic operations of compact storage."""
    storage = CompactRegretStorage()
    
    # Test update and get regret
    infoset = "preflop|0|AA"
    action = AbstractAction.BET_HALF_POT
    
    storage.update_regret(infoset, action, 10.0)
    regret = storage.get_regret(infoset, action)
    
    assert abs(regret - 10.0) < 1e-5
    
    # Test multiple actions
    storage.update_regret(infoset, AbstractAction.FOLD, -5.0)
    storage.update_regret(infoset, AbstractAction.CHECK_CALL, 2.0)
    
    assert abs(storage.get_regret(infoset, AbstractAction.FOLD) - (-5.0)) < 1e-5
    assert abs(storage.get_regret(infoset, AbstractAction.CHECK_CALL) - 2.0) < 1e-5


def test_compact_vs_dense_regret_updates():
    """Test that compact storage produces same results as dense storage."""
    dense = RegretTracker()
    compact = CompactRegretStorage()
    
    infoset = "preflop|0|KK"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_HALF_POT]
    
    # Apply same updates to both
    for i in range(10):
        for action in actions:
            regret = np.random.randn() * 100
            dense.update_regret(infoset, action, regret)
            compact.update_regret(infoset, action, regret)
    
    # Check regrets match
    for action in actions:
        dense_regret = dense.get_regret(infoset, action)
        compact_regret = compact.get_regret(infoset, action)
        
        # Allow small floating point differences (float32 vs float64)
        assert abs(dense_regret - compact_regret) < 1e-3, \
            f"Regret mismatch for {action}: dense={dense_regret}, compact={compact_regret}"


def test_compact_vs_dense_strategy():
    """Test that strategy computation matches between storage modes."""
    dense = RegretTracker()
    compact = CompactRegretStorage()
    
    infoset = "flop|0|QQ|c"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_HALF_POT]
    
    # Apply regret updates
    dense.update_regret(infoset, AbstractAction.FOLD, -20.0)
    dense.update_regret(infoset, AbstractAction.CHECK_CALL, 30.0)
    dense.update_regret(infoset, AbstractAction.BET_HALF_POT, 50.0)
    
    compact.update_regret(infoset, AbstractAction.FOLD, -20.0)
    compact.update_regret(infoset, AbstractAction.CHECK_CALL, 30.0)
    compact.update_regret(infoset, AbstractAction.BET_HALF_POT, 50.0)
    
    # Get strategies
    dense_strategy = dense.get_strategy(infoset, actions)
    compact_strategy = compact.get_strategy(infoset, actions)
    
    # Check strategies match
    for action in actions:
        assert abs(dense_strategy[action] - compact_strategy[action]) < 1e-5, \
            f"Strategy mismatch for {action}"


def test_compact_vs_dense_average_strategy():
    """Test that average strategy matches between storage modes."""
    dense = RegretTracker()
    compact = CompactRegretStorage()
    
    infoset = "river|0|AA|c|c|c"
    actions = [AbstractAction.CHECK_CALL, AbstractAction.BET_HALF_POT, AbstractAction.BET_POT]
    
    # Build strategy over iterations
    for i in range(20):
        # Update regrets
        for action in actions:
            regret = np.random.randn() * 10
            dense.update_regret(infoset, action, regret)
            compact.update_regret(infoset, action, regret)
        
        # Get current strategy
        dense_strategy = dense.get_strategy(infoset, actions)
        compact_strategy = compact.get_strategy(infoset, actions)
        
        # Add to strategy sum (with linear weighting)
        weight = float(i + 1)
        dense.add_strategy(infoset, dense_strategy, weight)
        compact.add_strategy(infoset, compact_strategy, weight)
    
    # Compare average strategies
    dense_avg = dense.get_average_strategy(infoset, actions)
    compact_avg = compact.get_average_strategy(infoset, actions)
    
    for action in actions:
        assert abs(dense_avg[action] - compact_avg[action]) < 1e-4, \
            f"Average strategy mismatch for {action}"


def test_compact_vs_dense_discounting():
    """Test that discounting works the same in both modes."""
    dense = RegretTracker()
    compact = CompactRegretStorage()
    
    infoset = "turn|0|KK|r|c"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
    
    # Initialize with some regrets
    for action in actions:
        regret = np.random.randn() * 50
        dense.update_regret(infoset, action, regret)
        compact.update_regret(infoset, action, regret)
    
    # Apply discount
    dense.discount(regret_factor=0.9, strategy_factor=0.95)
    compact.discount(regret_factor=0.9, strategy_factor=0.95)
    
    # Check regrets match after discount
    for action in actions:
        dense_regret = dense.get_regret(infoset, action)
        compact_regret = compact.get_regret(infoset, action)
        
        assert abs(dense_regret - compact_regret) < 1e-3, \
            f"Regret mismatch after discount for {action}"


def test_compact_vs_dense_reset_regrets():
    """Test that CFR+ reset works the same in both modes."""
    dense = RegretTracker()
    compact = CompactRegretStorage()
    
    infoset = "preflop|0|JJ"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
    
    # Set some negative and positive regrets
    dense.update_regret(infoset, AbstractAction.FOLD, -50.0)
    dense.update_regret(infoset, AbstractAction.CHECK_CALL, 30.0)
    dense.update_regret(infoset, AbstractAction.BET_POT, -20.0)
    
    compact.update_regret(infoset, AbstractAction.FOLD, -50.0)
    compact.update_regret(infoset, AbstractAction.CHECK_CALL, 30.0)
    compact.update_regret(infoset, AbstractAction.BET_POT, -20.0)
    
    # Reset negative regrets
    dense.reset_regrets()
    compact.reset_regrets()
    
    # Check results
    assert dense.get_regret(infoset, AbstractAction.FOLD) == 0.0
    assert compact.get_regret(infoset, AbstractAction.FOLD) == 0.0
    
    assert abs(dense.get_regret(infoset, AbstractAction.CHECK_CALL) - 30.0) < 1e-5
    assert abs(compact.get_regret(infoset, AbstractAction.CHECK_CALL) - 30.0) < 1e-5
    
    assert dense.get_regret(infoset, AbstractAction.BET_POT) == 0.0
    assert compact.get_regret(infoset, AbstractAction.BET_POT) == 0.0


def test_compact_state_serialization():
    """Test that compact storage can be serialized and restored."""
    original = CompactRegretStorage()
    
    # Create some state
    infoset1 = "preflop|0|AA"
    infoset2 = "flop|0|KK|c"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_HALF_POT]
    
    for infoset in [infoset1, infoset2]:
        for action in actions:
            regret = np.random.randn() * 100
            original.update_regret(infoset, action, regret)
        
        strategy = original.get_strategy(infoset, actions)
        original.add_strategy(infoset, strategy, weight=1.0)
    
    # Serialize
    state = original.get_state()
    
    # Restore to new storage
    restored = CompactRegretStorage()
    restored.set_state(state)
    
    # Verify state matches
    for infoset in [infoset1, infoset2]:
        for action in actions:
            orig_regret = original.get_regret(infoset, action)
            rest_regret = restored.get_regret(infoset, action)
            assert abs(orig_regret - rest_regret) < 1e-5
        
        orig_avg = original.get_average_strategy(infoset, actions)
        rest_avg = restored.get_average_strategy(infoset, actions)
        for action in actions:
            assert abs(orig_avg[action] - rest_avg[action]) < 1e-5


def test_compact_memory_efficiency():
    """Test that compact storage uses less memory than dense storage."""
    dense = RegretTracker()
    compact = CompactRegretStorage()
    
    # Create many infosets
    num_infosets = 1000
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, 
               AbstractAction.BET_HALF_POT, AbstractAction.BET_POT]
    
    for i in range(num_infosets):
        infoset = f"test|{i}|AA"
        for action in actions:
            regret = np.random.randn() * 50
            dense.update_regret(infoset, action, regret)
            compact.update_regret(infoset, action, regret)
    
    # Get memory usage for compact storage
    compact_mem = compact.get_memory_usage()
    
    # Estimate dense storage memory (rough estimate)
    # Each float is 8 bytes (float64), each string key ~50 bytes
    # Dict overhead is significant
    dense_estimate = num_infosets * len(actions) * (8 + 50) * 2  # regrets + strategy_sum
    
    # Compact should use significantly less memory
    # (We can't easily measure Python dict memory, so just verify compact reports reasonable size)
    assert compact_mem['total_bytes'] > 0
    assert compact_mem['num_infosets_regrets'] == num_infosets
    
    # Compact storage should be at least somewhat memory efficient
    # With float32 (4 bytes) vs float64 (8 bytes) and indexed actions (4 bytes),
    # we expect roughly 50-60% of dense storage size
    compact_bytes_per_infoset = compact_mem['total_bytes'] / num_infosets
    assert compact_bytes_per_infoset < 200  # Should be much less than dict-based storage


def test_compact_pruning():
    """Test that pruning check works correctly in compact storage."""
    compact = CompactRegretStorage()
    
    infoset = "preflop|0|AA"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_HALF_POT]
    
    # Set all regrets below threshold
    threshold = -100.0
    for action in actions:
        compact.update_regret(infoset, action, -150.0)
    
    # Should be prunable
    assert compact.should_prune(infoset, actions, threshold) == True
    
    # Set one regret above threshold
    compact.update_regret(infoset, AbstractAction.CHECK_CALL, 200.0)  # Now above threshold
    
    # Should not be prunable
    assert compact.should_prune(infoset, actions, threshold) == False


def test_multiple_infosets_iteration():
    """Test operations across multiple infosets."""
    compact = CompactRegretStorage()
    
    # Create diverse infosets
    infosets = [
        "preflop|0|AA",
        "flop|0|KK|c",
        "turn|0|QQ|r|c",
        "river|0|JJ|r|r|c"
    ]
    
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_HALF_POT]
    
    # Update all infosets
    for infoset in infosets:
        for action in actions:
            regret = np.random.randn() * 100
            compact.update_regret(infoset, action, regret)
    
    # Apply discount
    compact.discount(regret_factor=0.9, strategy_factor=0.95)
    
    # Verify all infosets still accessible
    for infoset in infosets:
        strategy = compact.get_strategy(infoset, actions)
        assert len(strategy) == len(actions)
        assert abs(sum(strategy.values()) - 1.0) < 1e-5  # Probabilities sum to 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
