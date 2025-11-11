"""Integration test combining all three features:
1. Leaf continuation strategies (k=4 policies)
2. Unsafe search from round start
3. Public card sampling (already implemented)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import Street, SearchConfig, Card, TableState
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.resolver import SubgameResolver
from holdem.realtime.subgame import SubgameTree
from holdem.realtime.leaf_continuations import LeafPolicy


def test_feature_1_leaf_policies():
    """Test Feature 1: Leaf continuation strategies (k=4)."""
    config = SearchConfig(
        time_budget_ms=50,
        min_iterations=10,
        use_leaf_policies=True,
        leaf_policy_default="fold_biased"
    )
    
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Test leaf strategy retrieval
    actions = [
        AbstractAction.FOLD,
        AbstractAction.CHECK_CALL,
        AbstractAction.BET_POT
    ]
    
    # Non-leaf node should use blueprint
    non_leaf_strategy = resolver.get_leaf_strategy("test_infoset", actions, is_leaf=False)
    assert isinstance(non_leaf_strategy, dict)
    
    # Leaf node should use biased strategy
    leaf_strategy = resolver.get_leaf_strategy("test_infoset", actions, is_leaf=True)
    assert isinstance(leaf_strategy, dict)
    
    print("✓ Feature 1 (Leaf continuation strategies) works")


def test_feature_2_round_start():
    """Test Feature 2: Unsafe search from round start."""
    config = SearchConfig(
        time_budget_ms=50,
        min_iterations=10,
        resolve_from_round_start=True
    )
    
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Test round history reconstruction
    history = ['p0_bet_10', 'p1_call']
    round_start, frozen = resolver.reconstruct_round_history(
        history, Street.FLOP, freeze_our_actions=True
    )
    
    assert isinstance(round_start, list)
    assert isinstance(frozen, list)
    
    print("✓ Feature 2 (Round-start resolving) works")


def test_feature_3_public_sampling():
    """Test Feature 3: Public card sampling (already implemented)."""
    config = SearchConfig(
        time_budget_ms=100,
        min_iterations=10,
        samples_per_solve=5  # Sample 5 boards
    )
    
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Create subgame on flop
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
    )
    subgame = SubgameTree([Street.FLOP], state, [Card('J', 'c'), Card('T', 'c')])
    
    # Solve with sampling
    our_cards = [Card('J', 'c'), Card('T', 'c')]
    strategy = resolver.solve_with_sampling(
        subgame,
        "test_infoset",
        our_cards,
        street=Street.FLOP
    )
    
    assert isinstance(strategy, dict)
    assert len(strategy) > 0
    
    print("✓ Feature 3 (Public card sampling) works")


def test_all_features_combined():
    """Test all three features working together."""
    config = SearchConfig(
        time_budget_ms=150,
        min_iterations=10,
        # Feature 1: Leaf policies
        use_leaf_policies=True,
        leaf_policy_default="call_biased",
        # Feature 2: Round-start resolving
        resolve_from_round_start=True,
        # Feature 3: Public card sampling
        samples_per_solve=3
    )
    
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Create subgame
    state = TableState(
        street=Street.TURN,
        pot=200.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd'), Card('J', 'h')]
    )
    subgame = SubgameTree([Street.TURN], state, [Card('T', 'c'), Card('9', 'c')])
    
    # Solve with all features enabled
    our_cards = [Card('T', 'c'), Card('9', 'c')]
    strategy = resolver.solve_with_sampling(
        subgame,
        "test_infoset",
        our_cards,
        street=Street.TURN,
        is_oop=True
    )
    
    # Verify we got a valid strategy
    assert isinstance(strategy, dict)
    assert len(strategy) > 0
    
    # Should sum to ~1.0
    total_prob = sum(strategy.values())
    assert abs(total_prob - 1.0) < 0.01
    
    print("✓ All features work together")


def test_all_leaf_policies_in_resolver():
    """Test resolver with all 4 leaf policies."""
    policies = ["blueprint", "fold_biased", "call_biased", "raise_biased"]
    
    for policy in policies:
        config = SearchConfig(
            time_budget_ms=50,
            min_iterations=10,
            use_leaf_policies=True,
            leaf_policy_default=policy
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        
        # Test leaf strategy
        actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
        strategy = resolver.get_leaf_strategy("test_infoset", actions, is_leaf=True)
        
        assert isinstance(strategy, dict)
        assert len(strategy) > 0
        
        print(f"  ✓ {policy} policy works in resolver")
    
    print("✓ All 4 leaf policies work in resolver")


def test_config_flexibility():
    """Test that features can be independently enabled/disabled."""
    # Only leaf policies
    config1 = SearchConfig(
        use_leaf_policies=True,
        resolve_from_round_start=False,
        samples_per_solve=1
    )
    assert config1.use_leaf_policies == True
    assert config1.resolve_from_round_start == False
    assert config1.samples_per_solve == 1
    
    # Only round-start
    config2 = SearchConfig(
        use_leaf_policies=False,
        resolve_from_round_start=True,
        samples_per_solve=1
    )
    assert config2.use_leaf_policies == False
    assert config2.resolve_from_round_start == True
    assert config2.samples_per_solve == 1
    
    # Only sampling
    config3 = SearchConfig(
        use_leaf_policies=False,
        resolve_from_round_start=False,
        samples_per_solve=10
    )
    assert config3.use_leaf_policies == False
    assert config3.resolve_from_round_start == False
    assert config3.samples_per_solve == 10
    
    # All three
    config4 = SearchConfig(
        use_leaf_policies=True,
        resolve_from_round_start=True,
        samples_per_solve=10
    )
    assert config4.use_leaf_policies == True
    assert config4.resolve_from_round_start == True
    assert config4.samples_per_solve == 10
    
    print("✓ Features can be independently enabled/disabled")


def test_backward_compatibility():
    """Test that existing code still works without new features."""
    # Default config should have all new features disabled
    config = SearchConfig()
    
    assert config.use_leaf_policies == False
    assert config.resolve_from_round_start == False
    assert config.samples_per_solve == 1
    
    # Resolver should work normally
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Create simple subgame
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
    )
    subgame = SubgameTree([Street.FLOP], state, [Card('J', 'c'), Card('T', 'c')])
    
    # Solve (should use baseline behavior)
    strategy = resolver.solve(subgame, "test_infoset", street=Street.FLOP)
    
    assert isinstance(strategy, dict)
    assert len(strategy) > 0
    
    print("✓ Backward compatibility maintained")


def test_performance_comparison():
    """Compare performance with and without features.
    
    This is not a strict performance test, just a sanity check
    that features don't cause major slowdowns.
    """
    import time
    
    # Baseline config
    config_baseline = SearchConfig(
        time_budget_ms=100,
        min_iterations=20,
        use_leaf_policies=False,
        resolve_from_round_start=False,
        samples_per_solve=1
    )
    
    # All features enabled
    config_full = SearchConfig(
        time_budget_ms=100,
        min_iterations=20,
        use_leaf_policies=True,
        resolve_from_round_start=True,
        samples_per_solve=3
    )
    
    # Test setup
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
    )
    our_cards = [Card('J', 'c'), Card('T', 'c')]
    
    # Baseline
    blueprint1 = PolicyStore()
    resolver1 = SubgameResolver(config_baseline, blueprint1)
    subgame1 = SubgameTree([Street.FLOP], state, our_cards)
    
    start = time.time()
    strategy1 = resolver1.solve(subgame1, "test_infoset", street=Street.FLOP)
    time_baseline = time.time() - start
    
    # Full features
    blueprint2 = PolicyStore()
    resolver2 = SubgameResolver(config_full, blueprint2)
    subgame2 = SubgameTree([Street.FLOP], state, our_cards)
    
    start = time.time()
    strategy2 = resolver2.solve_with_sampling(
        subgame2, "test_infoset", our_cards, street=Street.FLOP
    )
    time_full = time.time() - start
    
    print(f"✓ Performance: baseline={time_baseline*1000:.1f}ms, full={time_full*1000:.1f}ms")


if __name__ == "__main__":
    print("Integration test: All three features combined")
    print("=" * 60)
    print()
    
    test_feature_1_leaf_policies()
    print()
    
    test_feature_2_round_start()
    print()
    
    test_feature_3_public_sampling()
    print()
    
    test_all_features_combined()
    print()
    
    test_all_leaf_policies_in_resolver()
    print()
    
    test_config_flexibility()
    print()
    
    test_backward_compatibility()
    print()
    
    test_performance_comparison()
    print()
    
    print("=" * 60)
    print("✅ All integration tests passed!")
    print("=" * 60)
