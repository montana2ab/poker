"""Tests for subgame street start validation (P0 requirement)."""

import pytest
from holdem.rt_resolver.subgame_builder import SubgameBuilder, SubgameState
from holdem.abstraction.action_translator import ActionSetMode
from holdem.types import TableState, Street, Card


def test_subgame_street_start_validation():
    """Test that SubgameBuilder validates street start when begin_at_street_start=True."""
    builder = SubgameBuilder(
        max_depth=1,
        action_set_mode=ActionSetMode.BALANCED,
        begin_at_street_start=True
    )
    
    # Create a table state on the flop
    table_state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        num_players=2
    )
    
    # Test 1: Empty history should be valid (start of street)
    root = builder.build_from_state(table_state, [])
    assert root.street == Street.FLOP
    assert root.pot == 100.0
    
    # Test 2: History with street-completing action should be valid
    root = builder.build_from_state(table_state, ['check', 'check'])
    assert root.street == Street.FLOP
    
    # Test 3: History with call should be valid
    root = builder.build_from_state(table_state, ['bet_1.0p', 'call'])
    assert root.street == Street.FLOP


def test_subgame_street_start_disabled():
    """Test that SubgameBuilder allows any history when begin_at_street_start=False."""
    builder = SubgameBuilder(
        max_depth=1,
        action_set_mode=ActionSetMode.BALANCED,
        begin_at_street_start=False
    )
    
    table_state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        num_players=2
    )
    
    # Any history should be accepted when validation is disabled
    root = builder.build_from_state(table_state, ['bet_1.0p'])
    assert root.street == Street.FLOP
    
    root = builder.build_from_state(table_state, ['bet_1.0p', 'bet_1.5p'])
    assert root.street == Street.FLOP


def test_sentinel_actions_in_tight_mode():
    """Test that sentinel actions are added in tight mode to prevent exploitation."""
    builder = SubgameBuilder(
        max_depth=1,
        action_set_mode=ActionSetMode.TIGHT,
        sentinel_probability=0.02
    )
    
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    actions = builder.get_actions(
        state,
        stack=200.0,
        current_bet=0.0,
        player_bet=0.0,
        in_position=True
    )
    
    # Should have at least: FOLD, CHECK_CALL, some bet sizes, and ALL_IN
    from holdem.abstraction.actions import AbstractAction
    assert AbstractAction.CHECK_CALL in actions
    assert AbstractAction.ALL_IN in actions
    
    # Should have multiple actions (not just 2-3)
    # Sentinel actions should expand the action set
    assert len(actions) >= 4, f"Expected at least 4 actions in tight mode with sentinels, got {len(actions)}"


def test_sentinel_actions_families():
    """Test that sentinel actions cover different families (small, overbet, shove)."""
    builder = SubgameBuilder(
        max_depth=1,
        action_set_mode=ActionSetMode.TIGHT,
        sentinel_probability=0.02
    )
    
    from holdem.abstraction.actions import AbstractAction
    
    # Create a mock scenario
    all_actions = [
        AbstractAction.FOLD,
        AbstractAction.CHECK_CALL,
        AbstractAction.BET_QUARTER_POT,
        AbstractAction.BET_HALF_POT,
        AbstractAction.BET_POT,
        AbstractAction.BET_OVERBET_150,
        AbstractAction.ALL_IN
    ]
    
    restricted = [
        AbstractAction.FOLD,
        AbstractAction.CHECK_CALL,
        AbstractAction.BET_POT,
        AbstractAction.ALL_IN
    ]
    
    sentinels = builder._get_sentinel_actions(all_actions, restricted)
    
    # Should add a small bet (since none in restricted)
    small_bets = [AbstractAction.BET_QUARTER_POT, AbstractAction.BET_HALF_POT]
    has_small_bet = any(s in sentinels for s in small_bets)
    assert has_small_bet, "Should add a small bet sentinel"
    
    # Should add an overbet (since none in restricted besides pot)
    assert AbstractAction.BET_OVERBET_150 in sentinels, "Should add overbet sentinel"


def test_subgame_builder_initialization():
    """Test SubgameBuilder initialization with new parameters."""
    builder = SubgameBuilder(
        max_depth=2,
        action_set_mode=ActionSetMode.BALANCED,
        begin_at_street_start=True,
        sentinel_probability=0.03
    )
    
    assert builder.max_depth == 2
    assert builder.action_set_mode == ActionSetMode.BALANCED
    assert builder.begin_at_street_start is True
    assert builder.sentinel_probability == 0.03


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
