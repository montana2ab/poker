"""Test RT solver improvements: warm-start and documentation."""

import pytest
from holdem.types import SearchConfig, TableState, Street
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.realtime.resolver import SubgameResolver
from holdem.realtime.subgame import SubgameTree


def test_resolver_warm_start():
    """Test that resolver can warm-start from blueprint."""
    # Create a simple policy store
    regret_tracker = RegretTracker()
    
    # Add a simple strategy to the regret tracker
    infoset = "test_infoset"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
    
    # Set blueprint strategy favoring BET_POT
    for i, action in enumerate(actions):
        if action == AbstractAction.BET_POT:
            regret_tracker.strategy_sum[infoset] = {action: 70.0}
        else:
            if infoset not in regret_tracker.strategy_sum:
                regret_tracker.strategy_sum[infoset] = {}
            regret_tracker.strategy_sum[infoset][action] = 15.0
    
    blueprint = PolicyStore(regret_tracker)
    
    # Create resolver
    config = SearchConfig(time_budget_ms=100, min_iterations=10)
    resolver = SubgameResolver(config, blueprint)
    
    # Warm-start
    resolver.warm_start_from_blueprint(infoset, actions)
    
    # Check that regrets were initialized
    assert infoset in resolver.regret_tracker.regrets
    
    # BET_POT should have highest regret since it has highest probability in blueprint
    bet_pot_regret = resolver.regret_tracker.get_regret(infoset, AbstractAction.BET_POT)
    fold_regret = resolver.regret_tracker.get_regret(infoset, AbstractAction.FOLD)
    
    assert bet_pot_regret > fold_regret


def test_resolver_solve_uses_warm_start():
    """Test that resolver.solve() uses warm-start."""
    # Create a simple policy store
    regret_tracker = RegretTracker()
    
    infoset = "test_infoset"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
    
    # Set blueprint strategy
    regret_tracker.strategy_sum[infoset] = {
        AbstractAction.FOLD: 10.0,
        AbstractAction.CHECK_CALL: 20.0,
        AbstractAction.BET_POT: 70.0
    }
    
    blueprint = PolicyStore(regret_tracker)
    
    # Create resolver
    config = SearchConfig(time_budget_ms=50, min_iterations=5)
    resolver = SubgameResolver(config, blueprint)
    
    # Create dummy subgame
    state = TableState(
        street=Street.FLOP,
        pot=100,
        stacks=[1000, 1000],
        community_cards=[],
        active_players=[0, 1],
        button_pos=0
    )
    subgame = SubgameTree([Street.FLOP], state, [])
    
    # Solve
    strategy = resolver.solve(subgame, infoset, time_budget_ms=50)
    
    # Should return a valid strategy
    assert len(strategy) > 0
    
    # Probabilities should sum to approximately 1.0
    total_prob = sum(strategy.values())
    assert 0.9 <= total_prob <= 1.1


def test_resolver_cfr_iteration_has_documentation():
    """Test that _cfr_iteration has proper documentation about limitations."""
    import inspect
    
    # Check that the method has a docstring mentioning the limitation
    docstring = SubgameResolver._cfr_iteration.__doc__
    assert docstring is not None
    assert "LIMITATION" in docstring or "PLACEHOLDER" in docstring
    assert "subgame traversal" in docstring.lower() or "simplified" in docstring.lower()


def test_warm_start_improves_convergence():
    """Test that warm-start leads to strategies closer to blueprint initially."""
    # Create policy store with strong preference for CHECK_CALL
    regret_tracker = RegretTracker()
    infoset = "test_infoset"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
    
    regret_tracker.strategy_sum[infoset] = {
        AbstractAction.FOLD: 5.0,
        AbstractAction.CHECK_CALL: 85.0,  # Strong preference
        AbstractAction.BET_POT: 10.0
    }
    
    blueprint = PolicyStore(regret_tracker)
    
    # Create two resolvers - one with warm-start, one without
    config = SearchConfig(time_budget_ms=10, min_iterations=1)
    
    # Resolver with warm-start
    resolver_warm = SubgameResolver(config, blueprint)
    resolver_warm.warm_start_from_blueprint(infoset, actions)
    strategy_warm = resolver_warm.regret_tracker.get_strategy(infoset, actions)
    
    # Resolver without warm-start
    resolver_cold = SubgameResolver(config, blueprint)
    strategy_cold = resolver_cold.regret_tracker.get_strategy(infoset, actions)
    
    # Warm-start strategy should be closer to blueprint initially
    # (not uniform like cold start)
    blueprint_strategy = blueprint.get_strategy(infoset)
    
    # Check that warm-started strategy is non-uniform
    check_call_prob_warm = strategy_warm.get(AbstractAction.CHECK_CALL, 0.0)
    check_call_prob_cold = strategy_cold.get(AbstractAction.CHECK_CALL, 0.0)
    
    # Warm-start should have higher probability for CHECK_CALL (blueprint favorite)
    assert check_call_prob_warm > check_call_prob_cold


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
