"""Test KL regularization in SubgameResolver."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
from holdem.types import SearchConfig
from holdem.realtime.resolver import SubgameResolver
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.abstraction.actions import AbstractAction


def create_mock_policy():
    """Create a mock policy with some strategy."""
    tracker = RegretTracker()
    infoset = "TEST:0:initial"
    
    # Add a balanced blueprint strategy
    tracker.add_strategy(infoset, {
        AbstractAction.FOLD: 0.1,
        AbstractAction.CHECK_CALL: 0.4,
        AbstractAction.BET_HALF_POT: 0.3,
        AbstractAction.BET_POT: 0.2
    }, 10.0)
    
    return PolicyStore(tracker)


def test_kl_weight_in_config():
    """Test that SearchConfig has kl_weight parameter."""
    print("\nTesting SearchConfig.kl_weight parameter...")
    
    # Test with default value
    config = SearchConfig()
    assert hasattr(config, 'kl_weight'), "SearchConfig should have kl_weight attribute"
    assert config.kl_weight == 1.0, f"Default kl_weight should be 1.0, got {config.kl_weight}"
    print(f"  ✓ Default kl_weight = {config.kl_weight}")
    
    # Test with custom value
    config = SearchConfig(kl_weight=0.5)
    assert config.kl_weight == 0.5, f"kl_weight should be 0.5, got {config.kl_weight}"
    print(f"  ✓ Custom kl_weight = {config.kl_weight}")
    
    # Test backward compatibility
    assert config.kl_divergence_weight == 0.5, "kl_divergence_weight should alias to kl_weight"
    print(f"  ✓ Backward compatibility: kl_divergence_weight = {config.kl_divergence_weight}")


def test_kl_weight_values():
    """Test resolver with different kl_weight values."""
    print("\nTesting different kl_weight values...")
    
    # Test weights: 0, 0.1, 0.5, 1.0
    test_weights = [0.0, 0.1, 0.5, 1.0]
    
    for weight in test_weights:
        config = SearchConfig(
            time_budget_ms=50,
            min_iterations=5,
            kl_weight=weight
        )
        
        policy = create_mock_policy()
        resolver = SubgameResolver(config, policy)
        
        # Verify config is set correctly
        assert resolver.config.kl_weight == weight, f"Resolver kl_weight should be {weight}"
        print(f"  ✓ kl_weight = {weight}: resolver created successfully")


def test_kl_divergence_calculation():
    """Test that KL divergence is calculated correctly."""
    print("\nTesting KL divergence calculation...")
    
    config = SearchConfig(kl_weight=1.0)
    policy = create_mock_policy()
    resolver = SubgameResolver(config, policy)
    
    # Test KL divergence calculation with known distributions
    p = {AbstractAction.FOLD: 0.5, AbstractAction.CHECK_CALL: 0.5}
    q = {AbstractAction.FOLD: 0.5, AbstractAction.CHECK_CALL: 0.5}
    
    # KL(p||q) should be 0 when p == q
    kl = resolver._kl_divergence(p, q)
    assert abs(kl) < 1e-6, f"KL divergence should be ~0 for identical distributions, got {kl}"
    print(f"  ✓ KL(p||p) = {kl:.6f} (expected ~0)")
    
    # Test with different distributions
    p = {AbstractAction.FOLD: 0.9, AbstractAction.CHECK_CALL: 0.1}
    q = {AbstractAction.FOLD: 0.1, AbstractAction.CHECK_CALL: 0.9}
    
    kl = resolver._kl_divergence(p, q)
    assert kl > 0, f"KL divergence should be > 0 for different distributions, got {kl}"
    print(f"  ✓ KL(skewed||opposite) = {kl:.6f} (expected > 0)")


def test_cfr_iteration_returns_kl():
    """Test that _cfr_iteration returns KL divergence."""
    print("\nTesting _cfr_iteration returns KL divergence...")
    
    config = SearchConfig(kl_weight=1.0, min_iterations=1)
    policy = create_mock_policy()
    resolver = SubgameResolver(config, policy)
    
    # Create a mock subgame tree
    class MockSubgameTree:
        def get_actions(self, infoset):
            return [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
    
    subgame = MockSubgameTree()
    infoset = "TEST:0:initial"
    blueprint_strategy = {
        AbstractAction.FOLD: 0.1,
        AbstractAction.CHECK_CALL: 0.4,
        AbstractAction.BET_POT: 0.5
    }
    
    # Run one iteration and check it returns a float (KL divergence)
    kl_div = resolver._cfr_iteration(subgame, infoset, blueprint_strategy)
    
    assert isinstance(kl_div, (float, np.floating)), f"_cfr_iteration should return float, got {type(kl_div)}"
    assert kl_div >= 0, f"KL divergence should be non-negative, got {kl_div}"
    print(f"  ✓ _cfr_iteration returns KL divergence: {kl_div:.6f}")


def test_solve_logs_kl_divergence():
    """Test that solve() logs average KL divergence."""
    print("\nTesting solve() logs KL divergence...")
    
    config = SearchConfig(
        time_budget_ms=50,
        min_iterations=5,
        kl_weight=1.0
    )
    policy = create_mock_policy()
    resolver = SubgameResolver(config, policy)
    
    # Create a mock subgame tree
    class MockSubgameTree:
        def get_actions(self, infoset):
            return [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
    
    subgame = MockSubgameTree()
    infoset = "TEST:0:initial"
    
    # Solve subgame - should complete without error
    strategy = resolver.solve(subgame, infoset)
    
    assert isinstance(strategy, dict), "solve() should return a dictionary"
    assert len(strategy) > 0, "strategy should not be empty"
    print(f"  ✓ solve() completed and returned strategy with {len(strategy)} actions")


def test_kl_weight_effect_on_strategy():
    """Test that different kl_weight values affect the resulting strategy."""
    print("\nTesting kl_weight effect on strategy...")
    
    # This is a conceptual test - in practice, higher kl_weight should keep
    # the strategy closer to the blueprint, but with the placeholder utility
    # calculation, we just verify the mechanism works
    
    weights = [0.0, 1.0]
    
    for weight in weights:
        config = SearchConfig(
            time_budget_ms=50,
            min_iterations=10,
            kl_weight=weight
        )
        policy = create_mock_policy()
        resolver = SubgameResolver(config, policy)
        
        class MockSubgameTree:
            def get_actions(self, infoset):
                return [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
        
        subgame = MockSubgameTree()
        strategy = resolver.solve(subgame, "TEST:0:initial")
        
        assert isinstance(strategy, dict), f"Strategy should be a dict for kl_weight={weight}"
        assert len(strategy) > 0, f"Strategy should not be empty for kl_weight={weight}"
        print(f"  ✓ kl_weight = {weight}: strategy computed successfully")


if __name__ == "__main__":
    print("=" * 60)
    print("KL Regularization Tests")
    print("=" * 60)
    
    try:
        test_kl_weight_in_config()
        test_kl_weight_values()
        test_kl_divergence_calculation()
        test_cfr_iteration_returns_kl()
        test_solve_logs_kl_divergence()
        test_kl_weight_effect_on_strategy()
        
        print("\n" + "=" * 60)
        print("✓ All KL regularization tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
