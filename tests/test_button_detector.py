"""Tests for automatic button position detection."""

import pytest
from holdem.vision.button_detector import (
    ButtonDetector,
    ButtonInferenceResult,
    assign_positions_for_6max
)


class MockEvent:
    """Mock game event for testing."""
    def __init__(self, event_type: str, player: str = None, amount: float = None):
        self.event_type = event_type
        self.player = player
        self.amount = amount


class TestButtonDetector:
    """Tests for ButtonDetector class."""
    
    def test_init(self):
        """Test ButtonDetector initialization."""
        detector = ButtonDetector(num_seats=6)
        assert detector.num_seats == 6
    
    def test_heads_up_button_is_sb(self):
        """Test heads-up: button IS small blind."""
        detector = ButtonDetector(num_seats=6)
        
        # Create blind events
        events = [
            MockEvent('post_small_blind', player='Alice', amount=50),
            MockEvent('post_big_blind', player='Bob', amount=100),
        ]
        
        # Name to seat mapping
        name_to_seat = {
            'Alice': 0,
            'Bob': 1,
        }
        
        # Active seats (2 players)
        active_seats = [0, 1]
        
        # Infer button
        result = detector.infer_button(events, name_to_seat, active_seats)
        
        # In heads-up, button = SB
        assert result.button_seat == 0
        assert result.sb_seat == 0
        assert result.bb_seat == 1
    
    def test_three_player_button_before_sb(self):
        """Test 3-player: button is seat before SB."""
        detector = ButtonDetector(num_seats=6)
        
        # Create blind events
        events = [
            MockEvent('post_small_blind', player='Bob', amount=50),
            MockEvent('post_big_blind', player='Charlie', amount=100),
        ]
        
        # Name to seat mapping
        name_to_seat = {
            'Alice': 0,
            'Bob': 1,
            'Charlie': 2,
        }
        
        # Active seats (3 players)
        active_seats = [0, 1, 2]
        
        # Infer button
        result = detector.infer_button(events, name_to_seat, active_seats)
        
        # Button should be seat before SB in circular order
        # SB=1, so button = (1-1) % 3 = 0
        assert result.button_seat == 0
        assert result.sb_seat == 1
        assert result.bb_seat == 2
    
    def test_six_player_button_detection(self):
        """Test 6-max: button is seat before SB."""
        detector = ButtonDetector(num_seats=6)
        
        # Create blind events
        events = [
            MockEvent('post_small_blind', player='Player3', amount=50),
            MockEvent('post_big_blind', player='Player4', amount=100),
        ]
        
        # Name to seat mapping (6 players)
        name_to_seat = {
            'Player0': 0,
            'Player1': 1,
            'Player2': 2,
            'Player3': 3,
            'Player4': 4,
            'Player5': 5,
        }
        
        # Active seats (all 6 players)
        active_seats = [0, 1, 2, 3, 4, 5]
        
        # Infer button
        result = detector.infer_button(events, name_to_seat, active_seats)
        
        # Button should be seat before SB
        # SB=3, so button = (3-1) % 6 = 2
        assert result.button_seat == 2
        assert result.sb_seat == 3
        assert result.bb_seat == 4
    
    def test_circular_wrap_around(self):
        """Test button detection with circular wrap-around."""
        detector = ButtonDetector(num_seats=6)
        
        # SB is at seat 0, button should wrap to last seat
        events = [
            MockEvent('post_small_blind', player='Player0', amount=50),
            MockEvent('post_big_blind', player='Player1', amount=100),
        ]
        
        name_to_seat = {
            'Player0': 0,
            'Player1': 1,
            'Player2': 2,
            'Player3': 3,
        }
        
        active_seats = [0, 1, 2, 3]
        
        result = detector.infer_button(events, name_to_seat, active_seats)
        
        # SB=0, button = (0-1) % 4 = 3
        assert result.button_seat == 3
        assert result.sb_seat == 0
        assert result.bb_seat == 1
    
    def test_no_blind_events(self):
        """Test button detection fails gracefully with no blind events."""
        detector = ButtonDetector(num_seats=6)
        
        # No blind events
        events = [
            MockEvent('action', player='Alice'),
        ]
        
        name_to_seat = {'Alice': 0, 'Bob': 1}
        active_seats = [0, 1]
        
        result = detector.infer_button(events, name_to_seat, active_seats)
        
        # Should return None for all positions
        assert result.button_seat is None
        assert result.sb_seat is None
        assert result.bb_seat is None
    
    def test_sb_not_in_active_seats(self):
        """Test button detection when SB is not in active seats."""
        detector = ButtonDetector(num_seats=6)
        
        events = [
            MockEvent('post_small_blind', player='Folded', amount=50),
            MockEvent('post_big_blind', player='Active', amount=100),
        ]
        
        name_to_seat = {
            'Folded': 0,
            'Active': 1,
            'Other': 2,
        }
        
        # SB player has folded (not in active seats)
        active_seats = [1, 2]
        
        result = detector.infer_button(events, name_to_seat, active_seats)
        
        # Should fail to infer button if SB not active
        assert result.button_seat is None
        assert result.sb_seat == 0  # SB seat found but not active
        assert result.bb_seat == 1
    
    def test_player_name_not_in_mapping(self):
        """Test button detection when player name not in name_to_seat."""
        detector = ButtonDetector(num_seats=6)
        
        events = [
            MockEvent('post_small_blind', player='UnknownPlayer', amount=50),
            MockEvent('post_big_blind', player='Bob', amount=100),
        ]
        
        name_to_seat = {
            'Bob': 1,
            'Charlie': 2,
        }
        
        active_seats = [1, 2]
        
        result = detector.infer_button(events, name_to_seat, active_seats)
        
        # Should not find SB seat
        assert result.button_seat is None
        assert result.sb_seat is None
        assert result.bb_seat == 1


class TestAssignPositionsFor6Max:
    """Tests for position assignment function."""
    
    def test_six_player_positions(self):
        """Test position assignment for full 6-max table."""
        button_seat = 0
        active_seats = [0, 1, 2, 3, 4, 5]
        
        positions = assign_positions_for_6max(button_seat, active_seats)
        
        assert positions[0] == "BTN"
        assert positions[1] == "SB"
        assert positions[2] == "BB"
        assert positions[3] == "UTG"
        assert positions[4] == "MP"
        assert positions[5] == "CO"
    
    def test_three_player_positions(self):
        """Test position assignment for 3-handed."""
        button_seat = 0
        active_seats = [0, 1, 2]
        
        positions = assign_positions_for_6max(button_seat, active_seats)
        
        # Only BTN, SB, BB exist in 3-handed
        assert positions[0] == "BTN"
        assert positions[1] == "SB"
        assert positions[2] == "BB"
    
    def test_heads_up_positions(self):
        """Test position assignment for heads-up."""
        button_seat = 0
        active_seats = [0, 1]
        
        positions = assign_positions_for_6max(button_seat, active_seats)
        
        # Heads-up: BTN and SB
        assert positions[0] == "BTN"
        assert positions[1] == "SB"
    
    def test_position_with_different_button(self):
        """Test positions rotate correctly with different button seat."""
        button_seat = 3
        active_seats = [0, 1, 2, 3, 4, 5]
        
        positions = assign_positions_for_6max(button_seat, active_seats)
        
        # Distance from button_seat=3:
        # seat 3: dist=0 -> BTN
        # seat 4: dist=1 -> SB
        # seat 5: dist=2 -> BB
        # seat 0: dist=3 -> UTG
        # seat 1: dist=4 -> MP
        # seat 2: dist=5 -> CO
        assert positions[3] == "BTN"
        assert positions[4] == "SB"
        assert positions[5] == "BB"
        assert positions[0] == "UTG"
        assert positions[1] == "MP"
        assert positions[2] == "CO"
    
    def test_four_player_positions(self):
        """Test position assignment for 4-handed."""
        button_seat = 1
        active_seats = [0, 1, 2, 3]
        
        positions = assign_positions_for_6max(button_seat, active_seats)
        
        # 4-handed: BTN, SB, BB, UTG
        # Distance from button_seat=1:
        # seat 1: dist=0 -> BTN
        # seat 2: dist=1 -> SB
        # seat 3: dist=2 -> BB
        # seat 0: dist=3 -> UTG
        assert positions[1] == "BTN"
        assert positions[2] == "SB"
        assert positions[3] == "BB"
        assert positions[0] == "UTG"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
