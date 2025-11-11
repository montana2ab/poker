"""Tests for leaf continuation strategies (k=4 policies)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.abstraction.actions import AbstractAction
from holdem.realtime.leaf_continuations import (
    LeafPolicy,
    LeafContinuationStrategy,
    create_leaf_strategy
)


def test_leaf_policy_enum():
    """Test LeafPolicy enum."""
    assert LeafPolicy.BLUEPRINT.value == "blueprint"
    assert LeafPolicy.FOLD_BIASED.value == "fold_biased"
    assert LeafPolicy.CALL_BIASED.value == "call_biased"
    assert LeafPolicy.RAISE_BIASED.value == "raise_biased"
    
    print("✓ LeafPolicy enum works")


def test_leaf_continuation_strategy_init():
    """Test LeafContinuationStrategy initialization."""
    # Default initialization
    strategy = LeafContinuationStrategy()
    assert strategy.default_policy == LeafPolicy.BLUEPRINT
    
    # Custom initialization
    strategy2 = LeafContinuationStrategy(default_policy=LeafPolicy.FOLD_BIASED)
    assert strategy2.default_policy == LeafPolicy.FOLD_BIASED
    
    print("✓ LeafContinuationStrategy initialization works")


def test_blueprint_policy_unchanged():
    """Test that blueprint policy returns unchanged strategy."""
    strategy_manager = LeafContinuationStrategy(default_policy=LeafPolicy.BLUEPRINT)
    
    blueprint = {
        AbstractAction.FOLD: 0.2,
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.3
    }
    
    result = strategy_manager.get_biased_strategy(blueprint, LeafPolicy.BLUEPRINT)
    
    # Should be identical to blueprint
    assert result[AbstractAction.FOLD] == 0.2
    assert result[AbstractAction.CHECK_CALL] == 0.5
    assert result[AbstractAction.BET_POT] == 0.3
    
    # Should sum to 1.0
    assert abs(sum(result.values()) - 1.0) < 0.001
    
    print("✓ Blueprint policy returns unchanged strategy")


def test_fold_biased_policy():
    """Test fold-biased policy increases fold probability."""
    strategy_manager = LeafContinuationStrategy()
    
    blueprint = {
        AbstractAction.FOLD: 0.2,
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.3
    }
    
    result = strategy_manager.get_biased_strategy(blueprint, LeafPolicy.FOLD_BIASED)
    
    # Fold should increase (2x bias = 0.2 * 2.0 = 0.4 before normalization)
    # Call should decrease slightly (0.8x bias)
    # Raise should decrease significantly (0.5x bias)
    assert result[AbstractAction.FOLD] > blueprint[AbstractAction.FOLD]
    assert result[AbstractAction.BET_POT] < blueprint[AbstractAction.BET_POT]
    
    # Should still sum to 1.0
    assert abs(sum(result.values()) - 1.0) < 0.001
    
    print(f"✓ Fold-biased policy works: fold {blueprint[AbstractAction.FOLD]:.2f} -> {result[AbstractAction.FOLD]:.2f}")


def test_call_biased_policy():
    """Test call-biased policy increases call probability."""
    strategy_manager = LeafContinuationStrategy()
    
    blueprint = {
        AbstractAction.FOLD: 0.2,
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.3
    }
    
    result = strategy_manager.get_biased_strategy(blueprint, LeafPolicy.CALL_BIASED)
    
    # Call should increase (2x bias)
    # Fold should decrease (0.7x bias)
    # Raise should decrease (0.6x bias)
    assert result[AbstractAction.CHECK_CALL] > blueprint[AbstractAction.CHECK_CALL]
    assert result[AbstractAction.FOLD] < blueprint[AbstractAction.FOLD]
    assert result[AbstractAction.BET_POT] < blueprint[AbstractAction.BET_POT]
    
    # Should sum to 1.0
    assert abs(sum(result.values()) - 1.0) < 0.001
    
    print(f"✓ Call-biased policy works: call {blueprint[AbstractAction.CHECK_CALL]:.2f} -> {result[AbstractAction.CHECK_CALL]:.2f}")


def test_raise_biased_policy():
    """Test raise-biased policy increases raise probability."""
    strategy_manager = LeafContinuationStrategy()
    
    blueprint = {
        AbstractAction.FOLD: 0.2,
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.3
    }
    
    result = strategy_manager.get_biased_strategy(blueprint, LeafPolicy.RAISE_BIASED)
    
    # Raise should increase significantly (2.5x bias)
    # Fold should decrease (0.5x bias)
    # Call should decrease (0.7x bias)
    assert result[AbstractAction.BET_POT] > blueprint[AbstractAction.BET_POT]
    assert result[AbstractAction.FOLD] < blueprint[AbstractAction.FOLD]
    assert result[AbstractAction.CHECK_CALL] < blueprint[AbstractAction.CHECK_CALL]
    
    # Should sum to 1.0
    assert abs(sum(result.values()) - 1.0) < 0.001
    
    print(f"✓ Raise-biased policy works: raise {blueprint[AbstractAction.BET_POT]:.2f} -> {result[AbstractAction.BET_POT]:.2f}")


def test_action_categorization():
    """Test action categorization into fold/call/raise."""
    strategy_manager = LeafContinuationStrategy()
    
    # Test fold
    assert strategy_manager._categorize_action(AbstractAction.FOLD) == 'fold'
    
    # Test call/check
    assert strategy_manager._categorize_action(AbstractAction.CHECK_CALL) == 'call'
    
    # Test raise/bet
    assert strategy_manager._categorize_action(AbstractAction.BET_POT) == 'raise'
    assert strategy_manager._categorize_action(AbstractAction.BET_HALF_POT) == 'raise'
    assert strategy_manager._categorize_action(AbstractAction.BET_THREE_QUARTERS_POT) == 'raise'
    assert strategy_manager._categorize_action(AbstractAction.ALL_IN) == 'raise'
    
    print("✓ Action categorization works")


def test_multiple_raise_actions():
    """Test biasing with multiple raise actions."""
    strategy_manager = LeafContinuationStrategy()
    
    blueprint = {
        AbstractAction.FOLD: 0.1,
        AbstractAction.CHECK_CALL: 0.4,
        AbstractAction.BET_HALF_POT: 0.2,
        AbstractAction.BET_POT: 0.2,
        AbstractAction.BET_OVERBET_150: 0.1
    }
    
    result = strategy_manager.get_biased_strategy(blueprint, LeafPolicy.RAISE_BIASED)
    
    # All raise actions should increase proportionally
    total_raise_before = (
        blueprint[AbstractAction.BET_HALF_POT] +
        blueprint[AbstractAction.BET_POT] +
        blueprint[AbstractAction.BET_OVERBET_150]
    )
    total_raise_after = (
        result[AbstractAction.BET_HALF_POT] +
        result[AbstractAction.BET_POT] +
        result[AbstractAction.BET_OVERBET_150]
    )
    
    assert total_raise_after > total_raise_before
    assert result[AbstractAction.FOLD] < blueprint[AbstractAction.FOLD]
    
    # Should sum to 1.0
    assert abs(sum(result.values()) - 1.0) < 0.001
    
    print(f"✓ Multiple raise actions work: total_raise {total_raise_before:.2f} -> {total_raise_after:.2f}")


def test_zero_probability_actions():
    """Test handling of actions with zero probability."""
    strategy_manager = LeafContinuationStrategy()
    
    blueprint = {
        AbstractAction.FOLD: 0.0,
        AbstractAction.CHECK_CALL: 1.0,
        AbstractAction.BET_POT: 0.0
    }
    
    result = strategy_manager.get_biased_strategy(blueprint, LeafPolicy.FOLD_BIASED)
    
    # Should still normalize properly even with zeros
    assert abs(sum(result.values()) - 1.0) < 0.001
    
    # Zero actions should stay zero or become very small
    assert result[AbstractAction.FOLD] >= 0.0
    assert result[AbstractAction.BET_POT] >= 0.0
    
    print("✓ Zero probability actions handled correctly")


def test_uniform_strategy():
    """Test biasing a uniform strategy."""
    strategy_manager = LeafContinuationStrategy()
    
    # Uniform strategy
    blueprint = {
        AbstractAction.FOLD: 0.333,
        AbstractAction.CHECK_CALL: 0.333,
        AbstractAction.BET_POT: 0.334
    }
    
    # Apply fold bias
    result = strategy_manager.get_biased_strategy(blueprint, LeafPolicy.FOLD_BIASED)
    
    # Fold should be highest
    assert result[AbstractAction.FOLD] > result[AbstractAction.CHECK_CALL]
    assert result[AbstractAction.FOLD] > result[AbstractAction.BET_POT]
    
    # Should sum to 1.0
    assert abs(sum(result.values()) - 1.0) < 0.001
    
    print("✓ Uniform strategy biasing works")


def test_get_policy_description():
    """Test policy descriptions."""
    strategy_manager = LeafContinuationStrategy()
    
    desc_blueprint = strategy_manager.get_policy_description(LeafPolicy.BLUEPRINT)
    assert "blueprint" in desc_blueprint.lower()
    
    desc_fold = strategy_manager.get_policy_description(LeafPolicy.FOLD_BIASED)
    assert "fold" in desc_fold.lower() or "defensive" in desc_fold.lower()
    
    desc_call = strategy_manager.get_policy_description(LeafPolicy.CALL_BIASED)
    assert "call" in desc_call.lower() or "passive" in desc_call.lower()
    
    desc_raise = strategy_manager.get_policy_description(LeafPolicy.RAISE_BIASED)
    assert "raise" in desc_raise.lower() or "aggressive" in desc_raise.lower()
    
    print("✓ Policy descriptions work")


def test_get_all_policies():
    """Test getting all available policies."""
    strategy_manager = LeafContinuationStrategy()
    
    policies = strategy_manager.get_all_policies()
    
    assert len(policies) == 4
    assert LeafPolicy.BLUEPRINT in policies
    assert LeafPolicy.FOLD_BIASED in policies
    assert LeafPolicy.CALL_BIASED in policies
    assert LeafPolicy.RAISE_BIASED in policies
    
    print("✓ Get all policies works")


def test_create_leaf_strategy_convenience():
    """Test convenience function for creating leaf strategies."""
    blueprint = {
        AbstractAction.FOLD: 0.2,
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.3
    }
    
    # Test with different policies
    result_blueprint = create_leaf_strategy(blueprint, LeafPolicy.BLUEPRINT)
    assert result_blueprint == blueprint
    
    result_fold = create_leaf_strategy(blueprint, LeafPolicy.FOLD_BIASED)
    assert result_fold[AbstractAction.FOLD] > blueprint[AbstractAction.FOLD]
    
    result_call = create_leaf_strategy(blueprint, LeafPolicy.CALL_BIASED)
    assert result_call[AbstractAction.CHECK_CALL] > blueprint[AbstractAction.CHECK_CALL]
    
    result_raise = create_leaf_strategy(blueprint, LeafPolicy.RAISE_BIASED)
    assert result_raise[AbstractAction.BET_POT] > blueprint[AbstractAction.BET_POT]
    
    print("✓ Convenience function works")


def test_ablation_comparison():
    """Ablation test: Compare all 4 policies on the same blueprint.
    
    This test demonstrates the strategic diversity provided by k=4 policies.
    """
    strategy_manager = LeafContinuationStrategy()
    
    blueprint = {
        AbstractAction.FOLD: 0.15,
        AbstractAction.CHECK_CALL: 0.45,
        AbstractAction.BET_HALF_POT: 0.15,
        AbstractAction.BET_POT: 0.15,
        AbstractAction.BET_OVERBET_150: 0.10
    }
    
    print("\n=== Ablation Study: k=4 Policy Comparison ===")
    print(f"Blueprint strategy:")
    for action, prob in blueprint.items():
        print(f"  {action.name}: {prob:.3f}")
    
    for policy in LeafPolicy:
        result = strategy_manager.get_biased_strategy(blueprint, policy)
        print(f"\n{policy.value} policy:")
        for action, prob in result.items():
            change = prob - blueprint[action]
            print(f"  {action.name}: {prob:.3f} (Δ {change:+.3f})")
    
    print("\n✓ Ablation comparison completed")


if __name__ == "__main__":
    print("Testing leaf continuation strategies (k=4 policies)...")
    print()
    
    test_leaf_policy_enum()
    test_leaf_continuation_strategy_init()
    test_blueprint_policy_unchanged()
    test_fold_biased_policy()
    test_call_biased_policy()
    test_raise_biased_policy()
    test_action_categorization()
    test_multiple_raise_actions()
    test_zero_probability_actions()
    test_uniform_strategy()
    test_get_policy_description()
    test_get_all_policies()
    test_create_leaf_strategy_convenience()
    test_ablation_comparison()
    
    print("\n" + "="*60)
    print("✅ All leaf continuation strategy tests passed!")
    print("="*60)
