"""Tests for fallback to blueprint and metrics (P0 requirement)."""

import pytest
import time
from unittest.mock import Mock
from holdem.rt_resolver.depth_limited_cfr import DepthLimitedCFR
from holdem.rt_resolver.subgame_builder import SubgameBuilder, SubgameState
from holdem.rt_resolver.leaf_evaluator import LeafEvaluator
from holdem.mccfr.policy_store import PolicyStore
from holdem.abstraction.actions import AbstractAction
from holdem.types import Street, Card


def test_fallback_to_blueprint_on_timeout():
    """Test that solver falls back to blueprint when time expires before min_iterations."""
    # Create mock blueprint with a strategy
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {
        AbstractAction.CHECK_CALL: 0.6,
        AbstractAction.BET_POT: 0.3,
        AbstractAction.FOLD: 0.1
    }
    
    # Create subgame builder and leaf evaluator
    subgame_builder = SubgameBuilder(max_depth=1)
    leaf_evaluator = Mock(spec=LeafEvaluator)
    
    # Create solver with very short time limit and high min_iterations
    # This forces timeout before min_iterations
    solver = DepthLimitedCFR(
        blueprint=blueprint,
        subgame_builder=subgame_builder,
        leaf_evaluator=leaf_evaluator,
        min_iterations=1000,  # High minimum
        max_iterations=2000,
        time_limit_ms=1,  # Very short time limit (1ms)
        kl_weight=0.5,
        fallback_to_blueprint=True
    )
    
    # Create test state
    root_state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    # Solve - should fallback to blueprint
    strategy = solver.solve(
        root_state=root_state,
        hero_hand=[Card('A', 's'), Card('K', 'h')],
        villain_range={'AsKh': 1.0},
        hero_position=0
    )
    
    # Strategy should be the blueprint strategy
    assert AbstractAction.CHECK_CALL in strategy
    assert strategy[AbstractAction.CHECK_CALL] == 0.6
    
    # Metrics should show fallback
    metrics = solver.get_metrics()
    assert metrics['rt/failsafe_fallback_rate'] > 0
    assert metrics['rt/total_fallbacks'] == 1
    assert metrics['rt/ev_delta_bbs'] == 0.0  # No EV delta when using blueprint


def test_no_fallback_when_min_iterations_reached():
    """Test that solver uses computed strategy when min_iterations is reached."""
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.5
    }
    
    subgame_builder = SubgameBuilder(max_depth=1)
    leaf_evaluator = Mock(spec=LeafEvaluator)
    
    # Very low min_iterations so we can reach it quickly
    solver = DepthLimitedCFR(
        blueprint=blueprint,
        subgame_builder=subgame_builder,
        leaf_evaluator=leaf_evaluator,
        min_iterations=2,  # Very low
        max_iterations=10,
        time_limit_ms=100,  # Sufficient time
        kl_weight=0.5,
        fallback_to_blueprint=True
    )
    
    root_state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    strategy = solver.solve(
        root_state=root_state,
        hero_hand=[Card('A', 's'), Card('K', 'h')],
        villain_range={'AsKh': 1.0},
        hero_position=0
    )
    
    # Should have completed iterations without fallback
    metrics = solver.get_metrics()
    assert metrics['rt/iterations'] >= 2
    assert metrics['rt/total_fallbacks'] == 0


def test_metrics_tracking():
    """Test that all required rt/* metrics are tracked."""
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.5
    }
    
    subgame_builder = SubgameBuilder(max_depth=1)
    leaf_evaluator = Mock(spec=LeafEvaluator)
    
    solver = DepthLimitedCFR(
        blueprint=blueprint,
        subgame_builder=subgame_builder,
        leaf_evaluator=leaf_evaluator,
        min_iterations=5,
        max_iterations=10,
        time_limit_ms=100,
        kl_weight=0.5
    )
    
    root_state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    solver.solve(
        root_state=root_state,
        hero_hand=[Card('A', 's'), Card('K', 'h')],
        villain_range={'AsKh': 1.0},
        hero_position=0
    )
    
    metrics = solver.get_metrics()
    
    # Check all required metrics are present
    assert 'rt/decision_time_ms' in metrics
    assert 'rt/iterations' in metrics
    assert 'rt/failsafe_fallback_rate' in metrics
    assert 'rt/ev_delta_bbs' in metrics
    assert 'rt/time_per_iteration_ms' in metrics
    assert 'rt/total_solves' in metrics
    assert 'rt/total_fallbacks' in metrics
    
    # Check metric values are reasonable
    assert metrics['rt/decision_time_ms'] > 0
    assert metrics['rt/iterations'] >= 5
    assert 0 <= metrics['rt/failsafe_fallback_rate'] <= 1.0
    assert metrics['rt/total_solves'] == 1


def test_fallback_disabled():
    """Test behavior when fallback_to_blueprint is disabled."""
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {
        AbstractAction.CHECK_CALL: 0.5,
        AbstractAction.BET_POT: 0.5
    }
    
    subgame_builder = SubgameBuilder(max_depth=1)
    leaf_evaluator = Mock(spec=LeafEvaluator)
    
    solver = DepthLimitedCFR(
        blueprint=blueprint,
        subgame_builder=subgame_builder,
        leaf_evaluator=leaf_evaluator,
        min_iterations=1000,
        max_iterations=2000,
        time_limit_ms=1,
        kl_weight=0.5,
        fallback_to_blueprint=False  # Disabled
    )
    
    root_state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    # Should not fallback, but will use partial results
    strategy = solver.solve(
        root_state=root_state,
        hero_hand=[Card('A', 's'), Card('K', 'h')],
        villain_range={'AsKh': 1.0},
        hero_position=0
    )
    
    # Metrics should show no fallbacks
    metrics = solver.get_metrics()
    assert metrics['rt/total_fallbacks'] == 0
    
    # Strategy should exist (even if based on few iterations)
    assert len(strategy) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
