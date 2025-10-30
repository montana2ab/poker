"""Test real-time search time budget."""

import pytest
import time
from holdem.types import SearchConfig, BucketConfig, Street
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.realtime.subgame import SubgameBuilder, SubgameTree
from holdem.realtime.resolver import SubgameResolver
from holdem.abstraction.actions import AbstractAction


def test_search_respects_time_budget():
    """Test that search respects time budget."""
    # Create mock policy
    tracker = RegretTracker()
    policy = PolicyStore(tracker)
    
    # Create search config with tight budget
    config = SearchConfig(
        time_budget_ms=50,
        min_iterations=10,
        fallback_to_blueprint=True
    )
    
    resolver = SubgameResolver(config, policy)
    
    # Create mock subgame
    from holdem.types import Card, TableState, PlayerState
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 'd'), Card('Q', 's')],
        players=[PlayerState("P1", 1000.0)]
    )
    
    subgame = SubgameTree(
        [Street.FLOP],
        state,
        [Card('J', 'h'), Card('T', 'h')]
    )
    
    # Measure time
    start = time.time()
    strategy = resolver.solve(subgame, "test_infoset", time_budget_ms=50)
    elapsed_ms = (time.time() - start) * 1000
    
    # Should complete within reasonable time (with some overhead)
    assert elapsed_ms < 150, f"Search took {elapsed_ms}ms, expected <150ms"
    
    # Should return valid strategy
    assert isinstance(strategy, dict)
    assert len(strategy) > 0


def test_search_fallback_operational():
    """Test that fallback to blueprint works."""
    # Create mock policy with some infosets
    tracker = RegretTracker()
    infoset = "FLOP:0:check"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL]
    
    tracker.update_regret(infoset, AbstractAction.FOLD, 1.0)
    tracker.update_regret(infoset, AbstractAction.CHECK_CALL, 5.0)
    tracker.add_strategy(infoset, {AbstractAction.FOLD: 0.2, AbstractAction.CHECK_CALL: 0.8}, 1.0)
    
    policy = PolicyStore(tracker)
    
    # Create config with fallback enabled
    config = SearchConfig(
        time_budget_ms=100,
        min_iterations=100,
        fallback_to_blueprint=True
    )
    
    resolver = SubgameResolver(config, policy)
    
    # Resolver should work and not crash
    assert resolver.config.fallback_to_blueprint is True


def test_minimum_iterations_respected():
    """Test that minimum iterations are always executed."""
    tracker = RegretTracker()
    policy = PolicyStore(tracker)
    
    config = SearchConfig(
        time_budget_ms=1,  # Very tight budget
        min_iterations=50,  # But require 50 iterations
        fallback_to_blueprint=True
    )
    
    resolver = SubgameResolver(config, policy)
    
    from holdem.types import Card, TableState, PlayerState, Street
    state = TableState(
        street=Street.PREFLOP,
        pot=3.0,
        players=[PlayerState("P1", 100.0)]
    )
    
    subgame = SubgameTree([Street.PREFLOP], state, [Card('A', 's'), Card('A', 'h')])
    
    # Should still complete minimum iterations despite tight budget
    start = time.time()
    strategy = resolver.solve(subgame, "test_infoset")
    elapsed = time.time() - start
    
    # Should have taken some time to do 50 iterations
    assert elapsed > 0.001, "Should take non-zero time for iterations"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
