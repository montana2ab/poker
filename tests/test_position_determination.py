"""Tests for position determination in MCCFR."""

import pytest
from holdem.types import Street
from holdem.abstraction.actions import AbstractAction
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.mccfr_os import OutcomeSampler


class TestPositionDetermination:
    """Test cases for position-aware action selection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a minimal bucketing for testing
        self.bucketing = HandBucketing(num_preflop_buckets=10, num_postflop_buckets=10)
        self.sampler = OutcomeSampler(self.bucketing)
    
    def test_preflop_position_determination(self):
        """Test that preflop position is determined correctly.
        
        Preflop: SB acts first (OOP), BB second (IP)
        - History length 0 -> OOP (SB first to act)
        - History length 1 -> IP (BB responds)
        - History length 2 -> OOP (SB responds to BB)
        """
        # Empty history: OOP (SB to act)
        actions = self.sampler._get_available_actions(
            pot=3.0,
            street=Street.PREFLOP,
            history=[]
        )
        # Preflop should have 0.25, 0.5, 1.0, 2.0
        assert AbstractAction.BET_QUARTER_POT in actions
        assert AbstractAction.BET_HALF_POT in actions
        
        # History length 1: IP (BB to act)
        actions = self.sampler._get_available_actions(
            pot=3.0,
            street=Street.PREFLOP,
            history=["check_call"]
        )
        # Should still be preflop actions
        assert AbstractAction.BET_QUARTER_POT in actions
    
    def test_flop_position_determination(self):
        """Test that flop position is determined correctly.
        
        Postflop: SB (button) has position, BB is OOP
        - History length 0 -> IP (SB/button first to act postflop, has position)
        - History length 1 -> OOP (BB responds)
        """
        # Empty history postflop: IP (button to act)
        actions_ip = self.sampler._get_available_actions(
            pot=6.0,
            street=Street.FLOP,
            history=[]
        )
        # Flop IP should include 150% overbet
        assert AbstractAction.BET_OVERBET_150 in actions_ip
        assert AbstractAction.BET_THIRD_POT in actions_ip
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions_ip
        
        # History length 1: OOP (BB to act)
        actions_oop = self.sampler._get_available_actions(
            pot=6.0,
            street=Street.FLOP,
            history=["check_call"]
        )
        # Flop OOP should NOT include 150% overbet
        assert AbstractAction.BET_OVERBET_150 not in actions_oop
        assert AbstractAction.BET_THIRD_POT in actions_oop
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions_oop
    
    def test_turn_position_determination(self):
        """Test that turn position uses same logic as flop.
        
        Turn: Both IP and OOP have same actions {66, 100, 150}
        """
        # IP (history length 0)
        actions_ip = self.sampler._get_available_actions(
            pot=10.0,
            street=Street.TURN,
            history=[]
        )
        # Turn should have 66, 100, 150
        assert AbstractAction.BET_TWO_THIRDS_POT in actions_ip
        assert AbstractAction.BET_POT in actions_ip
        assert AbstractAction.BET_OVERBET_150 in actions_ip
        
        # OOP (history length 1)
        actions_oop = self.sampler._get_available_actions(
            pot=10.0,
            street=Street.TURN,
            history=["bet_0.66p"]
        )
        # Turn OOP should have same actions as IP
        assert AbstractAction.BET_TWO_THIRDS_POT in actions_oop
        assert AbstractAction.BET_POT in actions_oop
        assert AbstractAction.BET_OVERBET_150 in actions_oop
    
    def test_river_position_determination(self):
        """Test that river position uses same logic as other postflop streets.
        
        River: Both IP and OOP have same actions {75, 100, 150, all-in}
        """
        # IP (history length 0)
        actions_ip = self.sampler._get_available_actions(
            pot=20.0,
            street=Street.RIVER,
            history=[]
        )
        # River should have 75, 100, 150
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions_ip
        assert AbstractAction.BET_POT in actions_ip
        assert AbstractAction.BET_OVERBET_150 in actions_ip
        
        # OOP (history length 1)
        actions_oop = self.sampler._get_available_actions(
            pot=20.0,
            street=Street.RIVER,
            history=["bet_0.75p"]
        )
        # River OOP should have same actions as IP
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions_oop
        assert AbstractAction.BET_POT in actions_oop
        assert AbstractAction.BET_OVERBET_150 in actions_oop
    
    def test_position_flips_postflop(self):
        """Test that position correctly flips between preflop and postflop.
        
        This is the key fix: in HU poker, the player who is OOP preflop
        becomes IP postflop (and vice versa).
        """
        # Preflop history length 0: OOP
        preflop_actions = self.sampler._get_available_actions(
            pot=3.0,
            street=Street.PREFLOP,
            history=[]
        )
        # Should have preflop sizing (no 1.5x)
        assert AbstractAction.BET_OVERBET_150 not in preflop_actions
        assert AbstractAction.BET_QUARTER_POT in preflop_actions
        
        # Flop history length 0: IP (position flipped!)
        flop_actions = self.sampler._get_available_actions(
            pot=6.0,
            street=Street.FLOP,
            history=[]
        )
        # Should have IP flop sizing (includes 1.5x)
        assert AbstractAction.BET_OVERBET_150 in flop_actions
        assert AbstractAction.BET_QUARTER_POT not in flop_actions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
