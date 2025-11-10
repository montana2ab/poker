"""Tests for SubgameResolver with public card sampling."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import numpy as np
from holdem.types import Card, Street, SearchConfig, TableState
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.resolver import SubgameResolver
from holdem.realtime.subgame import SubgameTree


def test_resolver_solve_without_sampling():
    """Test basic resolver without sampling."""
    # Create config with no sampling
    config = SearchConfig(
        time_budget_ms=50,
        min_iterations=10,
        samples_per_solve=1  # No sampling
    )
    
    # Create mock blueprint
    blueprint = PolicyStore()
    
    # Initialize resolver
    resolver = SubgameResolver(config, blueprint)
    
    # Create simple subgame
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
    )
    subgame = SubgameTree([Street.FLOP], state, [Card('J', 'c'), Card('T', 'c')])
    
    # Solve
    strategy = resolver.solve(subgame, "test_infoset", street=Street.FLOP)
    
    # Check we got a strategy
    assert isinstance(strategy, dict)
    assert len(strategy) > 0
    
    # Check probabilities sum to ~1.0
    total_prob = sum(strategy.values())
    assert abs(total_prob - 1.0) < 0.01, f"Probabilities should sum to ~1.0, got {total_prob}"
    
    print("✓ Resolver solve without sampling works")


def test_resolver_solve_with_sampling():
    """Test resolver with public card sampling enabled."""
    # Create config with sampling
    config = SearchConfig(
        time_budget_ms=100,
        min_iterations=10,
        samples_per_solve=5  # Sample 5 boards
    )
    
    # Create mock blueprint
    blueprint = PolicyStore()
    
    # Initialize resolver
    resolver = SubgameResolver(config, blueprint)
    
    # Create subgame on flop (will sample turn cards)
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
    
    # Check we got a strategy
    assert isinstance(strategy, dict)
    assert len(strategy) > 0
    
    # Check probabilities sum to ~1.0
    total_prob = sum(strategy.values())
    assert abs(total_prob - 1.0) < 0.01, f"Probabilities should sum to ~1.0, got {total_prob}"
    
    print("✓ Resolver solve with sampling works")


def test_resolver_sampling_river_fallback():
    """Test that sampling falls back on river (no future cards to sample)."""
    config = SearchConfig(
        time_budget_ms=50,
        min_iterations=10,
        samples_per_solve=5
    )
    
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Create subgame on river (can't sample future cards)
    state = TableState(
        street=Street.RIVER,
        pot=100.0,
        board=[
            Card('A', 'h'), Card('K', 's'), Card('Q', 'd'),
            Card('J', 'h'), Card('T', 's')
        ]
    )
    subgame = SubgameTree([Street.RIVER], state, [Card('9', 'c'), Card('8', 'c')])
    
    our_cards = [Card('9', 'c'), Card('8', 'c')]
    strategy = resolver.solve_with_sampling(
        subgame,
        "test_infoset",
        our_cards,
        street=Street.RIVER
    )
    
    assert isinstance(strategy, dict)
    assert len(strategy) > 0
    
    print("✓ Resolver sampling river fallback works")


def test_average_strategies():
    """Test strategy averaging function."""
    config = SearchConfig()
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Create test strategies
    strategy1 = {
        AbstractAction.FOLD: 0.1,
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.4
    }
    
    strategy2 = {
        AbstractAction.FOLD: 0.2,
        AbstractAction.CHECK_CALL: 0.3,
        AbstractAction.BET_POT: 0.5
    }
    
    strategy3 = {
        AbstractAction.FOLD: 0.15,
        AbstractAction.CHECK_CALL: 0.35,
        AbstractAction.BET_POT: 0.5
    }
    
    # Average
    averaged = resolver._average_strategies([strategy1, strategy2, strategy3])
    
    # Check result
    assert AbstractAction.FOLD in averaged
    assert AbstractAction.CHECK_CALL in averaged
    assert AbstractAction.BET_POT in averaged
    
    # Check values (average of 0.1, 0.2, 0.15 = 0.15, etc.)
    assert abs(averaged[AbstractAction.FOLD] - 0.15) < 0.01
    assert abs(averaged[AbstractAction.CHECK_CALL] - (0.5 + 0.3 + 0.35) / 3) < 0.01
    assert abs(averaged[AbstractAction.BET_POT] - (0.4 + 0.5 + 0.5) / 3) < 0.01
    
    # Check normalization
    total = sum(averaged.values())
    assert abs(total - 1.0) < 0.01
    
    print("✓ Strategy averaging works")


def test_strategy_variance():
    """Test strategy variance calculation."""
    config = SearchConfig()
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Identical strategies should have 0 variance
    strategy1 = {
        AbstractAction.FOLD: 0.2,
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.3
    }
    
    variance = resolver._strategy_variance(strategy1, strategy1)
    assert abs(variance) < 0.001, "Identical strategies should have ~0 variance"
    
    # Different strategies should have non-zero variance
    strategy2 = {
        AbstractAction.FOLD: 0.3,
        AbstractAction.CHECK_CALL: 0.4,
        AbstractAction.BET_POT: 0.3
    }
    
    variance = resolver._strategy_variance(strategy1, strategy2)
    assert variance > 0, "Different strategies should have positive variance"
    
    print(f"✓ Strategy variance calculation works (variance={variance:.4f})")


def test_sampling_reduces_to_single_solve():
    """Test that samples_per_solve=1 uses standard solve."""
    config = SearchConfig(
        time_budget_ms=50,
        min_iterations=10,
        samples_per_solve=1  # Should use standard solve
    )
    
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
    )
    subgame = SubgameTree([Street.FLOP], state, [Card('J', 'c'), Card('T', 'c')])
    
    our_cards = [Card('J', 'c'), Card('T', 'c')]
    
    # Both methods should give similar results (they're the same code path)
    strategy1 = resolver.solve(subgame, "test_infoset", street=Street.FLOP)
    strategy2 = resolver.solve_with_sampling(subgame, "test_infoset", our_cards, street=Street.FLOP)
    
    # Should have same actions
    assert set(strategy1.keys()) == set(strategy2.keys())
    
    print("✓ samples_per_solve=1 correctly uses standard solve")


def test_config_samples_per_solve_default():
    """Test that samples_per_solve defaults to 1."""
    config = SearchConfig()
    assert config.samples_per_solve == 1
    
    config2 = SearchConfig(samples_per_solve=20)
    assert config2.samples_per_solve == 20
    
    print("✓ SearchConfig samples_per_solve defaults work")


if __name__ == "__main__":
    test_resolver_solve_without_sampling()
    test_resolver_solve_with_sampling()
    test_resolver_sampling_river_fallback()
    test_average_strategies()
    test_strategy_variance()
    test_sampling_reduces_to_single_solve()
    test_config_samples_per_solve_default()
    
    print("\n✅ All resolver sampling integration tests passed!")
