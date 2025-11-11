"""Tests for rt_resolver module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import Card, Street, TableState, RTResolverConfig
from holdem.abstraction.action_translator import ActionSetMode
from holdem.mccfr.policy_store import PolicyStore
from holdem.rt_resolver.subgame_builder import SubgameBuilder, SubgameState
from holdem.rt_resolver.leaf_evaluator import LeafEvaluator
from holdem.rt_resolver.depth_limited_cfr import DepthLimitedCFR


def test_rt_resolver_config():
    """Test RTResolverConfig."""
    config = RTResolverConfig(
        max_depth=2,
        time_ms=100,
        min_iterations=500,
        max_iterations=1500,
        samples_per_leaf=15,
        action_set_mode="tight",
        kl_weight=0.6
    )
    
    assert config.max_depth == 2
    assert config.time_ms == 100
    assert config.min_iterations == 500
    assert config.max_iterations == 1500
    assert config.samples_per_leaf == 15
    assert config.action_set_mode == "tight"
    assert config.kl_weight == 0.6
    
    print("✓ RTResolverConfig works")


def test_subgame_builder():
    """Test SubgameBuilder."""
    builder = SubgameBuilder(
        max_depth=1,
        action_set_mode=ActionSetMode.BALANCED
    )
    
    # Create a simple table state
    table_state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[
            Card('A', 'h'),
            Card('K', 's'),
            Card('Q', 'd')
        ],
        current_bet=0.0,
        small_blind=1.0,
        big_blind=2.0
    )
    
    # Build subgame root
    root = builder.build_from_state(table_state, history=[])
    
    assert root.street == Street.FLOP
    assert root.pot == 100.0
    assert len(root.board) == 3
    assert root.depth == 0
    
    print("✓ SubgameBuilder works")


def test_subgame_depth_limit():
    """Test depth limiting in subgame."""
    builder = SubgameBuilder(max_depth=1, action_set_mode=ActionSetMode.TIGHT)
    
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    # At depth 0, should allow full actions
    actions_d0 = builder.get_actions(state, stack=200.0, in_position=True)
    assert len(actions_d0) > 2  # More than just fold/call
    
    # At depth limit, should only allow passive actions
    state_at_limit = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=['bet_1.0p'],
        active_players=2,
        depth=1
    )
    
    actions_at_limit = builder.get_actions(state_at_limit, stack=200.0, in_position=True)
    assert len(actions_at_limit) == 2  # Only fold/call
    
    print(f"✓ Depth limiting works: d=0 has {len(actions_d0)} actions, d=1 has {len(actions_at_limit)} actions")


def test_action_set_restriction():
    """Test action set restriction by mode."""
    # Tight mode
    tight_builder = SubgameBuilder(max_depth=1, action_set_mode=ActionSetMode.TIGHT)
    
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    tight_actions = tight_builder.get_actions(state, stack=200.0, in_position=True)
    
    # Balanced mode
    balanced_builder = SubgameBuilder(max_depth=1, action_set_mode=ActionSetMode.BALANCED)
    balanced_actions = balanced_builder.get_actions(state, stack=200.0, in_position=True)
    
    # Loose mode
    loose_builder = SubgameBuilder(max_depth=1, action_set_mode=ActionSetMode.LOOSE)
    loose_actions = loose_builder.get_actions(state, stack=200.0, in_position=True)
    
    print(f"✓ Action set restriction: tight={len(tight_actions)}, balanced={len(balanced_actions)}, loose={len(loose_actions)}")


def test_leaf_evaluator():
    """Test LeafEvaluator."""
    blueprint = PolicyStore()
    
    evaluator = LeafEvaluator(
        blueprint=blueprint,
        num_rollout_samples=5,
        use_cfv=False  # Use rollouts for testing
    )
    
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=1
    )
    
    hero_hand = [Card('A', 's'), Card('K', 'h')]
    villain_range = {"AA": 0.5, "KK": 0.5}
    
    value = evaluator.evaluate(state, hero_hand, villain_range, hero_position=0)
    
    # Value should be within reasonable range
    assert -state.pot <= value <= state.pot
    
    print(f"✓ LeafEvaluator works: value={value:.2f}")


def test_depth_limited_cfr():
    """Test DepthLimitedCFR solver."""
    blueprint = PolicyStore()
    
    builder = SubgameBuilder(max_depth=1, action_set_mode=ActionSetMode.BALANCED)
    evaluator = LeafEvaluator(blueprint=blueprint, num_rollout_samples=5, use_cfv=False)
    
    solver = DepthLimitedCFR(
        blueprint=blueprint,
        subgame_builder=builder,
        leaf_evaluator=evaluator,
        min_iterations=10,  # Small for testing
        max_iterations=20,
        time_limit_ms=1000,  # 1 second for testing
        kl_weight=0.5
    )
    
    # Create root state
    root = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    hero_hand = [Card('A', 's'), Card('K', 'h')]
    villain_range = {"AA": 0.5, "KK": 0.5}
    
    strategy = solver.solve(root, hero_hand, villain_range, hero_position=0)
    
    # Check that strategy is a valid probability distribution
    assert len(strategy) > 0
    total_prob = sum(strategy.values())
    assert abs(total_prob - 1.0) < 0.1  # Should sum to ~1.0
    
    # Check metrics (using rt/* prefix)
    metrics = solver.get_metrics()
    assert metrics['rt/iterations'] >= 10
    assert metrics['rt/decision_time_ms'] > 0
    
    print(f"✓ DepthLimitedCFR works: {int(metrics['rt/iterations'])} iterations in {metrics['rt/decision_time_ms']:.1f}ms")


if __name__ == "__main__":
    print("Testing rt_resolver module...")
    print()
    
    test_rt_resolver_config()
    print()
    
    test_subgame_builder()
    print()
    
    test_subgame_depth_limit()
    print()
    
    test_action_set_restriction()
    print()
    
    test_leaf_evaluator()
    print()
    
    test_depth_limited_cfr()
    print()
    
    print("All tests passed! ✓")
