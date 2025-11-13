"""Tests for stable player identity and overlay action detection."""

import pytest
from holdem.types import PlayerSeatState, ActionType


class TestPlayerSeatState:
    """Test PlayerSeatState for stable player identity."""
    
    def test_initial_name_recognition(self):
        """Test that first OCR reading sets canonical name."""
        seat = PlayerSeatState(seat_index=0)
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        event = seat.update_from_ocr("hilanderjojo", action_keywords)
        
        assert seat.canonical_name == "hilanderjojo"
        assert seat.overlay_text == "hilanderjojo"
        assert event is None  # No action event for name
    
    def test_action_overlay_does_not_change_name(self):
        """Test that action overlay text doesn't replace canonical name."""
        seat = PlayerSeatState(seat_index=0)
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        # First reading: establish canonical name
        seat.update_from_ocr("hilanderjojo", action_keywords)
        assert seat.canonical_name == "hilanderjojo"
        
        # Second reading: action overlay
        event = seat.update_from_ocr("Call 4736", action_keywords)
        
        # Name should remain unchanged
        assert seat.canonical_name == "hilanderjojo"
        assert seat.overlay_text == "Call 4736"
        
        # Should create an action event
        assert event is not None
        assert event.player == "hilanderjojo"
        assert event.action == ActionType.CALL
        assert event.amount == 4736.0
    
    def test_bet_action_overlay(self):
        """Test BET action from overlay."""
        seat = PlayerSeatState(seat_index=0, canonical_name="player1")
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        event = seat.update_from_ocr("Bet 2055", action_keywords)
        
        assert seat.canonical_name == "player1"
        assert event is not None
        assert event.player == "player1"
        assert event.action == ActionType.BET
        assert event.amount == 2055.0
    
    def test_check_action_overlay(self):
        """Test CHECK action from overlay."""
        seat = PlayerSeatState(seat_index=0, canonical_name="player2")
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        event = seat.update_from_ocr("Check", action_keywords)
        
        assert event is not None
        assert event.player == "player2"
        assert event.action == ActionType.CHECK
        assert event.amount is None
    
    def test_fold_action_overlay(self):
        """Test FOLD action from overlay."""
        seat = PlayerSeatState(seat_index=0, canonical_name="player3")
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        event = seat.update_from_ocr("Fold", action_keywords)
        
        assert event is not None
        assert event.player == "player3"
        assert event.action == ActionType.FOLD
    
    def test_raise_action_overlay(self):
        """Test RAISE action from overlay."""
        seat = PlayerSeatState(seat_index=0, canonical_name="player4")
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        event = seat.update_from_ocr("Raise to 8000", action_keywords)
        
        assert event is not None
        assert event.player == "player4"
        assert event.action == ActionType.RAISE
        assert event.amount == 8000.0
    
    def test_allin_action_overlay(self):
        """Test ALL-IN action from overlay."""
        seat = PlayerSeatState(seat_index=0, canonical_name="player5")
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        event = seat.update_from_ocr("All-in", action_keywords)
        
        assert event is not None
        assert event.player == "player5"
        assert event.action == ActionType.ALLIN
    
    def test_no_ghost_players(self):
        """Test that action keywords never become player names."""
        seat = PlayerSeatState(seat_index=0)
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        # Try to set name to action keyword - should not work
        seat.update_from_ocr("Call", action_keywords)
        
        # canonical_name should remain None (no valid name set)
        assert seat.canonical_name is None
        assert seat.overlay_text == "Call"
    
    def test_similar_name_recognition(self):
        """Test that similar names (truncation/OCR errors) are recognized as same player."""
        seat = PlayerSeatState(seat_index=0)
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        # First reading: full name
        seat.update_from_ocr("hilanderjojo", action_keywords)
        assert seat.canonical_name == "hilanderjojo"
        
        # Second reading: truncated name
        seat.update_from_ocr("hilanderj", action_keywords)
        
        # Should keep original name (recognized as similar)
        assert seat.canonical_name == "hilanderjojo"
    
    def test_different_player_replaces_name(self):
        """Test that a different player name replaces the canonical name."""
        seat = PlayerSeatState(seat_index=0)
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        # First player
        seat.update_from_ocr("player1", action_keywords)
        assert seat.canonical_name == "player1"
        
        # Different player takes seat
        seat.update_from_ocr("player2", action_keywords)
        
        # Name should be updated
        assert seat.canonical_name == "player2"
    
    def test_action_without_canonical_name(self):
        """Test that action overlay without canonical name doesn't create event."""
        seat = PlayerSeatState(seat_index=0)
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        # Try to process action before establishing name
        event = seat.update_from_ocr("Call 100", action_keywords)
        
        # Should not create event (no canonical name)
        assert event is None
        assert seat.canonical_name is None
