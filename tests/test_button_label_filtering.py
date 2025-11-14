"""Tests for button label filtering.

This tests the fix for the issue where button labels like "Raise", "Call", "Bet",
"Fold", "Check", "All-in" were being interpreted as player names in action events.
"""

import pytest
from holdem.vision.parse_state import is_button_label, is_showdown_won_label


class TestIsButtonLabel:
    """Test the is_button_label() utility function."""
    
    def test_detects_raise(self):
        """Test that 'Raise' is detected as a button label."""
        assert is_button_label("Raise") is True
        assert is_button_label("raise") is True
        assert is_button_label("RAISE") is True
        assert is_button_label("  Raise  ") is True
    
    def test_detects_call(self):
        """Test that 'Call' is detected as a button label."""
        assert is_button_label("Call") is True
        assert is_button_label("call") is True
        assert is_button_label("CALL") is True
    
    def test_detects_bet(self):
        """Test that 'Bet' is detected as a button label."""
        assert is_button_label("Bet") is True
        assert is_button_label("bet") is True
        assert is_button_label("BET") is True
    
    def test_detects_fold(self):
        """Test that 'Fold' is detected as a button label."""
        assert is_button_label("Fold") is True
        assert is_button_label("fold") is True
        assert is_button_label("FOLD") is True
    
    def test_detects_check(self):
        """Test that 'Check' is detected as a button label."""
        assert is_button_label("Check") is True
        assert is_button_label("check") is True
        assert is_button_label("CHECK") is True
    
    def test_detects_all_in_variants(self):
        """Test that 'All-in' variants are detected as button labels."""
        assert is_button_label("All-in") is True
        assert is_button_label("all-in") is True
        assert is_button_label("ALL-IN") is True
        assert is_button_label("All in") is True
        assert is_button_label("all in") is True
        assert is_button_label("allin") is True
        assert is_button_label("ALLIN") is True
    
    def test_rejects_real_player_names(self):
        """Test that real player names are not detected as button labels."""
        assert is_button_label("Player123") is False
        assert is_button_label("guyeast") is False
        assert is_button_label("hilanderJojo") is False
        assert is_button_label("aria6767") is False
        assert is_button_label("kolpez78") is False
        assert is_button_label("ProPoker99") is False
    
    def test_rejects_empty_or_none(self):
        """Test that empty strings and None are not detected as button labels."""
        assert is_button_label("") is False
        assert is_button_label(None) is False
        assert is_button_label("   ") is False
    
    def test_rejects_partial_matches(self):
        """Test that partial matches are not detected as button labels."""
        assert is_button_label("Raised") is False
        assert is_button_label("Called") is False
        assert is_button_label("Calling") is False
        assert is_button_label("RaiseAmount") is False
        assert is_button_label("CheckBack") is False


class TestIsShowdownWonLabel:
    """Test the is_showdown_won_label() utility function."""
    
    def test_detects_won_labels(self):
        """Test that 'Won X,XXX' labels are detected."""
        assert is_showdown_won_label("Won 5,249") is True
        assert is_showdown_won_label("Won 2,467") is True
        assert is_showdown_won_label("Won 1234") is True
        assert is_showdown_won_label("won 999") is True
        assert is_showdown_won_label("WON 10,000") is True
    
    def test_rejects_won_without_amount(self):
        """Test that 'Won' without an amount is not detected."""
        assert is_showdown_won_label("Won") is False
        assert is_showdown_won_label("Won ") is False
    
    def test_rejects_real_player_names(self):
        """Test that real player names are not detected as showdown labels."""
        assert is_showdown_won_label("Player123") is False
        assert is_showdown_won_label("WonTon") is False
        assert is_showdown_won_label("Winner99") is False
    
    def test_rejects_empty_or_none(self):
        """Test that empty strings and None are not detected as showdown labels."""
        assert is_showdown_won_label("") is False
        assert is_showdown_won_label(None) is False


class TestButtonLabelFilteringInEventFusion:
    """Test that button labels are filtered out in event fusion."""
    
    def test_button_label_not_used_as_player_name(self):
        """Test that button labels are not used as player names in events.
        
        This is an integration test that verifies the full flow, but we can
        test the logic separately by checking the filtering conditions.
        """
        from holdem.vision.event_fusion import EventFuser
        from holdem.types import TableState, PlayerState, Street, ActionType
        
        # Create a mock previous state with a player named "Player0"
        prev_state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            board=[],
            players=[
                PlayerState(
                    name="Player0",  # Default name
                    stack=1000.0,
                    position=0,
                    bet_this_round=0.0
                )
            ],
            current_bet=0.0,
            button_position=0,
            hero_position=0
        )
        
        # Create a current state where OCR read "Raise" as the player name
        current_state = TableState(
            street=Street.PREFLOP,
            pot=8.0,
            board=[],
            players=[
                PlayerState(
                    name="Raise",  # Button label misread as player name
                    stack=995.0,
                    position=0,
                    bet_this_round=5.0
                )
            ],
            current_bet=5.0,
            button_position=0,
            hero_position=0
        )
        
        # Create event fuser
        fuser = EventFuser()
        fuser._previous_stacks[0] = 1000.0
        fuser._previous_pot = 3.0
        
        # Create vision events
        events = fuser.create_vision_events_from_state(prev_state, current_state)
        
        # Check that no event has "Raise" as the player name
        for event in events:
            if event.event_type == "action":
                # Button labels should be filtered out
                assert event.player != "Raise", \
                    "Button label 'Raise' should not appear as player name in events"
    
    def test_real_player_names_still_work(self):
        """Test that real player names are not filtered out."""
        from holdem.vision.event_fusion import EventFuser
        from holdem.types import TableState, PlayerState, Street, ActionType
        
        # Create a mock previous state
        prev_state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            board=[],
            players=[
                PlayerState(
                    name="guyeast",  # Real player name
                    stack=1000.0,
                    position=0,
                    bet_this_round=0.0
                )
            ],
            current_bet=0.0,
            button_position=0,
            hero_position=0
        )
        
        # Create a current state with the same real player name
        current_state = TableState(
            street=Street.PREFLOP,
            pot=8.0,
            board=[],
            players=[
                PlayerState(
                    name="guyeast",  # Real player name
                    stack=995.0,
                    position=0,
                    bet_this_round=5.0
                )
            ],
            current_bet=5.0,
            button_position=0,
            hero_position=0
        )
        
        # Create event fuser
        fuser = EventFuser()
        fuser._previous_stacks[0] = 1000.0
        fuser._previous_pot = 3.0
        
        # Create vision events
        events = fuser.create_vision_events_from_state(prev_state, current_state)
        
        # Real player names should still appear in events
        action_events = [e for e in events if e.event_type == "action"]
        if action_events:
            # At least one action event should have the real player name
            assert any(e.player == "guyeast" for e in action_events), \
                "Real player name 'guyeast' should appear in action events"
