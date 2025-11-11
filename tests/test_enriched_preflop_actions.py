"""Tests for enriched preflop action abstraction."""

import pytest
from holdem.abstraction.actions import AbstractAction, ActionAbstraction
from holdem.types import Street, Action, ActionType


class TestEnrichedPreflopActions:
    """Test cases for enriched preflop action abstraction with position-specific sizings."""
    
    def test_preflop_ip_rich_actions(self):
        """Test that preflop IP has rich action menu (up to ~14 actions)."""
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=500.0,  # Large stack to include all actions
            current_bet=0,
            player_bet=0,
            can_check=True,
            street=Street.PREFLOP,
            in_position=True
        )
        
        # IP should have: CHECK_CALL + 10 bet sizes + ALL_IN = 12 actions
        assert AbstractAction.CHECK_CALL in actions
        assert AbstractAction.BET_QUARTER_POT in actions
        assert AbstractAction.BET_THIRD_POT in actions
        assert AbstractAction.BET_HALF_POT in actions
        assert AbstractAction.BET_TWO_THIRDS_POT in actions
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.BET_OVERBET_150 in actions
        assert AbstractAction.BET_DOUBLE_POT in actions
        assert AbstractAction.BET_TWO_HALF_POT in actions
        assert AbstractAction.BET_TRIPLE_POT in actions
        assert AbstractAction.ALL_IN in actions
        
        # Should have at least 12 actions (can have more with FOLD)
        assert len(actions) >= 12
    
    def test_preflop_oop_rich_actions(self):
        """Test that preflop OOP has slightly reduced menu."""
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=500.0,
            current_bet=0,
            player_bet=0,
            can_check=True,
            street=Street.PREFLOP,
            in_position=False
        )
        
        # OOP should have: CHECK_CALL + 8 bet sizes + ALL_IN = 10 actions
        assert AbstractAction.CHECK_CALL in actions
        # OOP doesn't have 0.25p
        assert AbstractAction.BET_QUARTER_POT not in actions
        # OOP has these
        assert AbstractAction.BET_THIRD_POT in actions
        assert AbstractAction.BET_HALF_POT in actions
        assert AbstractAction.BET_TWO_THIRDS_POT in actions
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.BET_OVERBET_150 in actions
        assert AbstractAction.BET_DOUBLE_POT in actions
        assert AbstractAction.BET_TWO_HALF_POT in actions
        # OOP doesn't have 3.0p
        assert AbstractAction.BET_TRIPLE_POT not in actions
        assert AbstractAction.ALL_IN in actions
        
        # Should have at least 10 actions
        assert len(actions) >= 10
    
    def test_preflop_with_facing_bet(self):
        """Test preflop actions when facing a bet (includes FOLD)."""
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=500.0,
            current_bet=20.0,
            player_bet=0,
            can_check=False,
            street=Street.PREFLOP,
            in_position=True
        )
        
        # Should include FOLD when facing a bet
        assert AbstractAction.FOLD in actions
        # Should have ~13 actions total (FOLD + CHECK_CALL + bet sizes + ALL_IN)
        assert len(actions) >= 13
    
    def test_new_bet_sizes_concrete_conversion(self):
        """Test conversion of new bet sizes to concrete actions."""
        # Test 2.5p
        action = ActionAbstraction.abstract_to_concrete(
            AbstractAction.BET_TWO_HALF_POT,
            pot=100.0,
            stack=500.0,
            current_bet=0,
            player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.BET
        assert abs(action.amount - 250.0) < 0.1
        
        # Test 3.0p
        action = ActionAbstraction.abstract_to_concrete(
            AbstractAction.BET_TRIPLE_POT,
            pot=100.0,
            stack=500.0,
            current_bet=0,
            player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.BET
        assert abs(action.amount - 300.0) < 0.1
    
    def test_new_bet_sizes_abstract_conversion(self):
        """Test conversion of concrete actions to new abstract bet sizes."""
        # Test 2.5p
        abstract = ActionAbstraction.concrete_to_abstract(
            Action(ActionType.BET, amount=250.0),
            pot=100.0,
            stack=500.0
        )
        assert abstract == AbstractAction.BET_TWO_HALF_POT
        
        # Test 3.0p
        abstract = ActionAbstraction.concrete_to_abstract(
            Action(ActionType.BET, amount=300.0),
            pot=100.0,
            stack=500.0
        )
        assert abstract == AbstractAction.BET_TRIPLE_POT
        
        # Test boundary case: 2.6p should map to 2.5p
        abstract = ActionAbstraction.concrete_to_abstract(
            Action(ActionType.BET, amount=260.0),
            pot=100.0,
            stack=500.0
        )
        assert abstract == AbstractAction.BET_TWO_HALF_POT
        
        # Test boundary case: 2.8p should map to 3.0p
        abstract = ActionAbstraction.concrete_to_abstract(
            Action(ActionType.BET, amount=280.0),
            pot=100.0,
            stack=500.0
        )
        assert abstract == AbstractAction.BET_TRIPLE_POT
    
    def test_stack_constraints_with_new_sizes(self):
        """Test that new large bet sizes are properly constrained by stack."""
        # With small stack, large overbets should not be available
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=130.0,  # Reduced stack to exclude some larger bets
            current_bet=0,
            player_bet=0,
            can_check=True,
            street=Street.PREFLOP,
            in_position=True
        )
        
        # Should have pot-sized bets but not 1.5p, 2.0p, 2.5p or 3.0p
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.BET_OVERBET_150 not in actions  # 150 > 130
        assert AbstractAction.BET_DOUBLE_POT not in actions  # 200 > 130
        assert AbstractAction.BET_TWO_HALF_POT not in actions  # 250 > 130
        assert AbstractAction.BET_TRIPLE_POT not in actions  # 300 > 130
        assert AbstractAction.ALL_IN in actions
    
    def test_preflop_action_order_consistency(self):
        """Test that preflop actions maintain canonical order."""
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=500.0,
            current_bet=10.0,  # Facing a bet
            player_bet=0,
            can_check=False,
            street=Street.PREFLOP,
            in_position=True
        )
        
        # Check that FOLD comes first, then CHECK_CALL, then bet sizes in order
        assert actions[0] == AbstractAction.FOLD
        assert actions[1] == AbstractAction.CHECK_CALL
        
        # Bet sizes should be in ascending order
        bet_actions = actions[2:-1]  # Exclude FOLD, CHECK_CALL, and ALL_IN
        expected_bet_order = [
            AbstractAction.BET_QUARTER_POT,
            AbstractAction.BET_THIRD_POT,
            AbstractAction.BET_HALF_POT,
            AbstractAction.BET_TWO_THIRDS_POT,
            AbstractAction.BET_THREE_QUARTERS_POT,
            AbstractAction.BET_POT,
            AbstractAction.BET_OVERBET_150,
            AbstractAction.BET_DOUBLE_POT,
            AbstractAction.BET_TWO_HALF_POT,
            AbstractAction.BET_TRIPLE_POT
        ]
        
        for i, action in enumerate(bet_actions):
            assert action == expected_bet_order[i], f"Action {i} mismatch: {action} != {expected_bet_order[i]}"
        
        # ALL_IN should be last
        assert actions[-1] == AbstractAction.ALL_IN
    
    def test_postflop_actions_unchanged(self):
        """Test that postflop actions are not affected by preflop changes."""
        # Flop IP should still have {33, 75, 100, 150}
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=500.0,
            current_bet=0,
            player_bet=0,
            can_check=True,
            street=Street.FLOP,
            in_position=True
        )
        
        assert AbstractAction.CHECK_CALL in actions
        assert AbstractAction.BET_THIRD_POT in actions
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.BET_OVERBET_150 in actions
        assert AbstractAction.ALL_IN in actions
        
        # Should NOT have these (preflop-only)
        assert AbstractAction.BET_QUARTER_POT not in actions
        assert AbstractAction.BET_HALF_POT not in actions
        assert AbstractAction.BET_TWO_THIRDS_POT not in actions
        assert AbstractAction.BET_DOUBLE_POT not in actions
        assert AbstractAction.BET_TWO_HALF_POT not in actions
        assert AbstractAction.BET_TRIPLE_POT not in actions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
