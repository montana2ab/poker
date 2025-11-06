"""Tests for street and position-based action abstraction."""

import pytest
from holdem.abstraction.actions import AbstractAction, ActionAbstraction
from holdem.types import Street, Action, ActionType


class TestActionAbstraction:
    """Test cases for action abstraction with street and position."""
    
    def test_preflop_actions(self):
        """Test that preflop uses original abstraction."""
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=200.0,
            current_bet=0,
            player_bet=0,
            can_check=True,
            street=Street.PREFLOP,
            in_position=True
        )
        
        # Preflop should have: CHECK_CALL, 0.25p, 0.5p, 1.0p, 2.0p, ALL_IN
        assert AbstractAction.CHECK_CALL in actions
        assert AbstractAction.BET_QUARTER_POT in actions
        assert AbstractAction.BET_HALF_POT in actions
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.BET_DOUBLE_POT in actions
        assert AbstractAction.ALL_IN in actions
        
        # Should not have new bet sizes
        assert AbstractAction.BET_THIRD_POT not in actions
        assert AbstractAction.BET_TWO_THIRDS_POT not in actions
        assert AbstractAction.BET_THREE_QUARTERS_POT not in actions
        assert AbstractAction.BET_ONE_HALF_POT not in actions
    
    def test_flop_ip_actions(self):
        """Test flop in position actions: {33, 75, 100, 150}."""
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=200.0,
            current_bet=0,
            player_bet=0,
            can_check=True,
            street=Street.FLOP,
            in_position=True
        )
        
        # Flop IP should have: CHECK_CALL, 0.33p, 0.75p, 1.0p, 1.5p, ALL_IN
        assert AbstractAction.CHECK_CALL in actions
        assert AbstractAction.BET_THIRD_POT in actions
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.BET_ONE_HALF_POT in actions
        assert AbstractAction.ALL_IN in actions
        
        # Should not have these
        assert AbstractAction.BET_QUARTER_POT not in actions
        assert AbstractAction.BET_HALF_POT not in actions
        assert AbstractAction.BET_TWO_THIRDS_POT not in actions
        assert AbstractAction.BET_DOUBLE_POT not in actions
    
    def test_flop_oop_actions(self):
        """Test flop out of position actions: {33, 75, 100}."""
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=200.0,
            current_bet=0,
            player_bet=0,
            can_check=True,
            street=Street.FLOP,
            in_position=False
        )
        
        # Flop OOP should have: CHECK_CALL, 0.33p, 0.75p, 1.0p, ALL_IN
        assert AbstractAction.CHECK_CALL in actions
        assert AbstractAction.BET_THIRD_POT in actions
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.ALL_IN in actions
        
        # Should NOT have 1.5p (IP only on flop)
        assert AbstractAction.BET_ONE_HALF_POT not in actions
        assert AbstractAction.BET_QUARTER_POT not in actions
        assert AbstractAction.BET_HALF_POT not in actions
        assert AbstractAction.BET_TWO_THIRDS_POT not in actions
        assert AbstractAction.BET_DOUBLE_POT not in actions
    
    def test_turn_actions(self):
        """Test turn actions: {66, 100, 150}."""
        # Test both IP and OOP (turn has same actions for both)
        for in_position in [True, False]:
            actions = ActionAbstraction.get_available_actions(
                pot=100.0,
                stack=200.0,
                current_bet=0,
                player_bet=0,
                can_check=True,
                street=Street.TURN,
                in_position=in_position
            )
            
            # Turn should have: CHECK_CALL, 0.66p, 1.0p, 1.5p, ALL_IN
            assert AbstractAction.CHECK_CALL in actions
            assert AbstractAction.BET_TWO_THIRDS_POT in actions
            assert AbstractAction.BET_POT in actions
            assert AbstractAction.BET_ONE_HALF_POT in actions
            assert AbstractAction.ALL_IN in actions
            
            # Should not have these
            assert AbstractAction.BET_QUARTER_POT not in actions
            assert AbstractAction.BET_THIRD_POT not in actions
            assert AbstractAction.BET_HALF_POT not in actions
            assert AbstractAction.BET_THREE_QUARTERS_POT not in actions
            assert AbstractAction.BET_DOUBLE_POT not in actions
    
    def test_river_actions(self):
        """Test river actions: {75, 100, 150, all-in}."""
        # Test both IP and OOP (river has same actions for both)
        for in_position in [True, False]:
            actions = ActionAbstraction.get_available_actions(
                pot=100.0,
                stack=200.0,
                current_bet=0,
                player_bet=0,
                can_check=True,
                street=Street.RIVER,
                in_position=in_position
            )
            
            # River should have: CHECK_CALL, 0.75p, 1.0p, 1.5p, ALL_IN
            assert AbstractAction.CHECK_CALL in actions
            assert AbstractAction.BET_THREE_QUARTERS_POT in actions
            assert AbstractAction.BET_POT in actions
            assert AbstractAction.BET_ONE_HALF_POT in actions
            assert AbstractAction.ALL_IN in actions
            
            # Should not have these
            assert AbstractAction.BET_QUARTER_POT not in actions
            assert AbstractAction.BET_THIRD_POT not in actions
            assert AbstractAction.BET_HALF_POT not in actions
            assert AbstractAction.BET_TWO_THIRDS_POT not in actions
            assert AbstractAction.BET_DOUBLE_POT not in actions
    
    def test_fold_when_facing_bet(self):
        """Test that fold is available when facing a bet."""
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=200.0,
            current_bet=50.0,
            player_bet=0,
            can_check=False,
            street=Street.FLOP,
            in_position=True
        )
        
        assert AbstractAction.FOLD in actions
    
    def test_no_fold_when_can_check(self):
        """Test that fold is not available when can check for free."""
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=200.0,
            current_bet=0,
            player_bet=0,
            can_check=True,
            street=Street.FLOP,
            in_position=True
        )
        
        assert AbstractAction.FOLD not in actions
    
    def test_stack_constraints(self):
        """Test that actions are limited by stack size."""
        # Small stack that can't make larger bets
        # With pot=100.0 and stack=40.0:
        # - 0.33p = 33.0 (fits in stack, should be available)
        # - 0.75p = 75.0 (exceeds stack, should NOT be available)
        # - 1.0p = 100.0 (exceeds stack, should NOT be available)
        # - 1.5p = 150.0 (exceeds stack, should NOT be available)
        actions = ActionAbstraction.get_available_actions(
            pot=100.0,
            stack=40.0,
            current_bet=0,
            player_bet=0,
            can_check=True,
            street=Street.RIVER,
            in_position=True
        )
        
        # Should have check/call and all-in
        assert AbstractAction.CHECK_CALL in actions
        assert AbstractAction.ALL_IN in actions
        
        # Should not have these (stack too small)
        assert AbstractAction.BET_THREE_QUARTERS_POT not in actions
        assert AbstractAction.BET_POT not in actions
        assert AbstractAction.BET_ONE_HALF_POT not in actions
        
        # Note: 0.33p (33.0) would fit in stack but river doesn't have that bet size
    
    def test_abstract_to_concrete_new_sizes(self):
        """Test conversion of new abstract actions to concrete actions."""
        # Test 0.33p
        action = ActionAbstraction.abstract_to_concrete(
            AbstractAction.BET_THIRD_POT,
            pot=100.0,
            stack=200.0,
            current_bet=0,
            player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.BET
        assert abs(action.amount - 33.0) < 0.1
        
        # Test 0.66p
        action = ActionAbstraction.abstract_to_concrete(
            AbstractAction.BET_TWO_THIRDS_POT,
            pot=100.0,
            stack=200.0,
            current_bet=0,
            player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.BET
        assert abs(action.amount - 66.0) < 0.1
        
        # Test 0.75p
        action = ActionAbstraction.abstract_to_concrete(
            AbstractAction.BET_THREE_QUARTERS_POT,
            pot=100.0,
            stack=200.0,
            current_bet=0,
            player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.BET
        assert abs(action.amount - 75.0) < 0.1
        
        # Test 1.5p
        action = ActionAbstraction.abstract_to_concrete(
            AbstractAction.BET_ONE_HALF_POT,
            pot=100.0,
            stack=200.0,
            current_bet=0,
            player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.BET
        assert abs(action.amount - 150.0) < 0.1
    
    def test_concrete_to_abstract_new_sizes(self):
        """Test conversion of concrete actions to new abstract actions."""
        # Test 0.33p
        abstract = ActionAbstraction.concrete_to_abstract(
            Action(ActionType.BET, amount=33.0),
            pot=100.0,
            stack=200.0
        )
        assert abstract == AbstractAction.BET_THIRD_POT
        
        # Test 0.66p
        abstract = ActionAbstraction.concrete_to_abstract(
            Action(ActionType.BET, amount=66.0),
            pot=100.0,
            stack=200.0
        )
        assert abstract == AbstractAction.BET_TWO_THIRDS_POT
        
        # Test 0.75p
        abstract = ActionAbstraction.concrete_to_abstract(
            Action(ActionType.BET, amount=75.0),
            pot=100.0,
            stack=200.0
        )
        assert abstract == AbstractAction.BET_THREE_QUARTERS_POT
        
        # Test 1.5p
        abstract = ActionAbstraction.concrete_to_abstract(
            Action(ActionType.BET, amount=150.0),
            pot=100.0,
            stack=200.0
        )
        assert abstract == AbstractAction.BET_ONE_HALF_POT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
