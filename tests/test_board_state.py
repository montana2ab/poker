"""Tests for board state machine and zone-based detection."""

import pytest
from holdem.types import Card, Street
from holdem.vision.vision_cache import BoardCache


class TestBoardState:
    """Test BoardCache state machine functionality."""
    
    @pytest.fixture
    def board_state(self):
        """Create a fresh board state instance."""
        return BoardCache(stability_threshold=2)
    
    def test_initial_state(self, board_state):
        """Test initial state of board cache."""
        assert not board_state.has_flop()
        assert not board_state.has_turn()
        assert not board_state.has_river()
        assert board_state.should_scan_flop()
        assert not board_state.should_scan_turn()
        assert not board_state.should_scan_river()
        assert board_state.cards == [None] * 5
    
    def test_mark_flop(self, board_state):
        """Test marking flop as detected."""
        flop_cards = [Card('A', 'h'), Card('K', 'd'), Card('Q', 's')]
        board_state.mark_flop(flop_cards)
        
        assert board_state.has_flop()
        assert not board_state.has_turn()
        assert not board_state.has_river()
        assert not board_state.should_scan_flop()
        assert board_state.should_scan_turn()
        assert not board_state.should_scan_river()
        assert board_state.cards[0:3] == flop_cards
        assert board_state.cards[3] is None
        assert board_state.cards[4] is None
        assert board_state.street == Street.FLOP
    
    def test_mark_turn(self, board_state):
        """Test marking turn as detected."""
        flop_cards = [Card('A', 'h'), Card('K', 'd'), Card('Q', 's')]
        turn_card = Card('J', 'c')
        
        board_state.mark_flop(flop_cards)
        board_state.mark_turn(turn_card)
        
        assert board_state.has_flop()
        assert board_state.has_turn()
        assert not board_state.has_river()
        assert not board_state.should_scan_flop()
        assert not board_state.should_scan_turn()
        assert board_state.should_scan_river()
        assert board_state.cards[0:3] == flop_cards
        assert board_state.cards[3] == turn_card
        assert board_state.cards[4] is None
        assert board_state.street == Street.TURN
    
    def test_mark_river(self, board_state):
        """Test marking river as detected."""
        flop_cards = [Card('A', 'h'), Card('K', 'd'), Card('Q', 's')]
        turn_card = Card('J', 'c')
        river_card = Card('T', 'h')
        
        board_state.mark_flop(flop_cards)
        board_state.mark_turn(turn_card)
        board_state.mark_river(river_card)
        
        assert board_state.has_flop()
        assert board_state.has_turn()
        assert board_state.has_river()
        assert not board_state.should_scan_flop()
        assert not board_state.should_scan_turn()
        assert not board_state.should_scan_river()
        assert board_state.cards[0:3] == flop_cards
        assert board_state.cards[3] == turn_card
        assert board_state.cards[4] == river_card
        assert board_state.street == Street.RIVER
    
    def test_mark_turn_without_flop_warns(self, board_state):
        """Test that marking turn without flop logs a warning but doesn't crash."""
        turn_card = Card('J', 'c')
        board_state.mark_turn(turn_card)
        
        # Should not have marked turn since flop wasn't detected
        assert not board_state.has_turn()
    
    def test_mark_river_without_turn_warns(self, board_state):
        """Test that marking river without turn logs a warning but doesn't crash."""
        river_card = Card('T', 'h')
        board_state.mark_river(river_card)
        
        # Should not have marked river since turn wasn't detected
        assert not board_state.has_river()
    
    def test_reset_for_new_hand(self, board_state):
        """Test resetting board state for new hand."""
        flop_cards = [Card('A', 'h'), Card('K', 'd'), Card('Q', 's')]
        turn_card = Card('J', 'c')
        
        board_state.mark_flop(flop_cards)
        board_state.mark_turn(turn_card)
        
        # Reset for new hand
        board_state.reset_for_new_hand()
        
        assert not board_state.has_flop()
        assert not board_state.has_turn()
        assert not board_state.has_river()
        assert board_state.should_scan_flop()
        assert not board_state.should_scan_turn()
        assert not board_state.should_scan_river()
        assert board_state.cards == [None] * 5
        assert board_state.street is None
        assert board_state.flop_stability_frames == 0
        assert board_state.turn_stability_frames == 0
        assert board_state.river_stability_frames == 0
    
    def test_progressive_detection(self, board_state):
        """Test progressive detection through all streets."""
        # Start - no cards
        assert board_state.should_scan_flop()
        assert not board_state.should_scan_turn()
        assert not board_state.should_scan_river()
        
        # Flop detected
        flop_cards = [Card('A', 'h'), Card('K', 'd'), Card('Q', 's')]
        board_state.mark_flop(flop_cards)
        assert not board_state.should_scan_flop()
        assert board_state.should_scan_turn()
        assert not board_state.should_scan_river()
        
        # Turn detected
        turn_card = Card('J', 'c')
        board_state.mark_turn(turn_card)
        assert not board_state.should_scan_flop()
        assert not board_state.should_scan_turn()
        assert board_state.should_scan_river()
        
        # River detected
        river_card = Card('T', 'h')
        board_state.mark_river(river_card)
        assert not board_state.should_scan_flop()
        assert not board_state.should_scan_turn()
        assert not board_state.should_scan_river()
    
    def test_mark_flop_with_wrong_count(self, board_state):
        """Test that mark_flop with wrong number of cards logs warning."""
        # Try with 2 cards (should be 3)
        wrong_cards = [Card('A', 'h'), Card('K', 'd')]
        board_state.mark_flop(wrong_cards)
        
        # Should not have marked flop
        assert not board_state.has_flop()
    
    def test_cards_str_helper(self, board_state):
        """Test internal card string helper."""
        # Empty board
        assert board_state._cards_str() == "None"
        
        # With cards
        flop_cards = [Card('A', 'h'), Card('K', 'd'), Card('Q', 's')]
        board_state.mark_flop(flop_cards)
        cards_str = board_state._cards_str()
        assert "Ah" in cards_str
        assert "Kd" in cards_str
        assert "Qs" in cards_str
    
    def test_cards_str_range_helper(self, board_state):
        """Test internal card string range helper."""
        flop_cards = [Card('A', 'h'), Card('K', 'd'), Card('Q', 's')]
        turn_card = Card('J', 'c')
        
        board_state.mark_flop(flop_cards)
        board_state.mark_turn(turn_card)
        
        # Get flop only
        flop_str = board_state._cards_str_range(0, 3)
        assert "Ah" in flop_str
        assert "Kd" in flop_str
        assert "Qs" in flop_str
        assert "Jc" not in flop_str
        
        # Get turn only
        turn_str = board_state._cards_str_range(3, 4)
        assert "Jc" in turn_str
        assert "Ah" not in turn_str
