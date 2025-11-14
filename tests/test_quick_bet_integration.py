"""Integration tests for BET_HALF_POT and BET_POT actions.

These tests verify the full integration from abstract actions to concrete
action types without requiring GUI interactions.
"""

import pytest
from unittest.mock import Mock
from holdem.types import ActionType, Street
from holdem.abstraction.actions import AbstractAction
from holdem.abstraction.backmapping import ActionBackmapper


class TestQuickBetIntegration:
    """Test quick bet button integration without GUI."""
    
    def test_bet_half_pot_mapping_with_quick_buttons_enabled(self):
        """Test BET_HALF_POT maps to ActionType.BET_HALF_POT when enabled."""
        backmapper = ActionBackmapper(
            big_blind=2.0,
            use_quick_bet_buttons=True
        )
        
        # Scenario: facing no bet, can make fresh bet
        action = backmapper.backmap_action(
            abstract_action=AbstractAction.BET_HALF_POT,
            pot=100.0,
            stack=500.0,
            current_bet=0.0,
            player_bet=0.0,
            can_check=True,
            street=Street.FLOP
        )
        
        assert action.action_type == ActionType.BET_HALF_POT
        assert action.amount == 0.0  # No amount needed for quick bet buttons
    
    def test_bet_pot_mapping_with_quick_buttons_enabled(self):
        """Test BET_POT maps to ActionType.BET_POT when enabled."""
        backmapper = ActionBackmapper(
            big_blind=2.0,
            use_quick_bet_buttons=True
        )
        
        action = backmapper.backmap_action(
            abstract_action=AbstractAction.BET_POT,
            pot=100.0,
            stack=500.0,
            current_bet=0.0,
            player_bet=0.0,
            can_check=True,
            street=Street.FLOP
        )
        
        assert action.action_type == ActionType.BET_POT
        assert action.amount == 0.0
    
    def test_bet_half_pot_fallback_when_facing_bet(self):
        """Test BET_HALF_POT uses standard sizing when facing a bet."""
        backmapper = ActionBackmapper(
            big_blind=2.0,
            use_quick_bet_buttons=True
        )
        
        # Scenario: facing a bet, cannot use quick buttons (must raise)
        action = backmapper.backmap_action(
            abstract_action=AbstractAction.BET_HALF_POT,
            pot=100.0,
            stack=500.0,
            current_bet=20.0,
            player_bet=0.0,
            can_check=False,
            street=Street.FLOP
        )
        
        # Should use standard raise sizing, not quick button
        assert action.action_type == ActionType.RAISE
        assert action.amount > 0
    
    def test_bet_half_pot_standard_sizing_when_disabled(self):
        """Test BET_HALF_POT uses standard BET sizing when quick buttons disabled."""
        backmapper = ActionBackmapper(
            big_blind=2.0,
            use_quick_bet_buttons=False  # Disabled
        )
        
        action = backmapper.backmap_action(
            abstract_action=AbstractAction.BET_HALF_POT,
            pot=100.0,
            stack=500.0,
            current_bet=0.0,
            player_bet=0.0,
            can_check=True,
            street=Street.FLOP
        )
        
        # Should use standard bet sizing
        assert action.action_type == ActionType.BET
        assert action.amount == 50.0  # 0.5 * pot
    
    def test_bet_pot_standard_sizing_when_disabled(self):
        """Test BET_POT uses standard BET sizing when quick buttons disabled."""
        backmapper = ActionBackmapper(
            big_blind=2.0,
            use_quick_bet_buttons=False
        )
        
        action = backmapper.backmap_action(
            abstract_action=AbstractAction.BET_POT,
            pot=100.0,
            stack=500.0,
            current_bet=0.0,
            player_bet=0.0,
            can_check=True,
            street=Street.FLOP
        )
        
        assert action.action_type == ActionType.BET
        assert action.amount == 100.0  # 1.0 * pot
    
    def test_other_abstract_actions_unaffected(self):
        """Test that other abstract actions work normally with quick buttons enabled."""
        backmapper = ActionBackmapper(
            big_blind=2.0,
            use_quick_bet_buttons=True
        )
        
        # Test FOLD
        action = backmapper.backmap_action(
            abstract_action=AbstractAction.FOLD,
            pot=100.0,
            stack=500.0,
            current_bet=20.0,
            player_bet=0.0,
            can_check=False,
            street=Street.FLOP
        )
        assert action.action_type == ActionType.FOLD
        
        # Test CHECK_CALL
        action = backmapper.backmap_action(
            abstract_action=AbstractAction.CHECK_CALL,
            pot=100.0,
            stack=500.0,
            current_bet=0.0,
            player_bet=0.0,
            can_check=True,
            street=Street.FLOP
        )
        assert action.action_type == ActionType.CHECK
        
        # Test ALL_IN
        action = backmapper.backmap_action(
            abstract_action=AbstractAction.ALL_IN,
            pot=100.0,
            stack=500.0,
            current_bet=0.0,
            player_bet=0.0,
            can_check=True,
            street=Street.FLOP
        )
        assert action.action_type == ActionType.ALLIN
    
    def test_action_type_enums_exist(self):
        """Test that new ActionType enums are properly defined."""
        # Verify the enums exist
        assert hasattr(ActionType, 'BET_HALF_POT')
        assert hasattr(ActionType, 'BET_POT')
        
        # Verify they have the expected string values
        assert ActionType.BET_HALF_POT.value == "bet_half_pot"
        assert ActionType.BET_POT.value == "bet_pot"
    
    def test_abstract_action_enums_unchanged(self):
        """Test that AbstractAction enums still exist and work."""
        # These should still exist and have their original values
        assert AbstractAction.BET_HALF_POT.value == "bet_0.5p"
        assert AbstractAction.BET_POT.value == "bet_1.0p"
        
        # Other actions should be unaffected
        assert AbstractAction.FOLD.value == "fold"
        assert AbstractAction.CHECK_CALL.value == "check_call"
        assert AbstractAction.ALL_IN.value == "all_in"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
