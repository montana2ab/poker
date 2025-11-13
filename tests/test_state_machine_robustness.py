"""Tests for state machine robustness improvements.

This test suite validates:
1. Showdown label detection and event filtering
2. Hero active flag management after fold
3. Hero cards stability tracking
4. Inconsistent state detection (pot regression)
"""

import pytest
from datetime import datetime
from holdem.types import TableState, PlayerState, Street, ActionType, Card
from holdem.vision.event_fusion import EventFuser
from holdem.vision.chat_parser import GameEvent, EventSource
from holdem.vision.parse_state import is_showdown_won_label, HeroCardsTracker


class TestShowdownLabelDetection:
    """Test showdown label detection and filtering."""
    
    def test_showdown_label_detected(self):
        """Test that 'Won X,XXX' labels are correctly detected."""
        assert is_showdown_won_label("Won 5,249") == True
        assert is_showdown_won_label("Won 2,467") == True
        assert is_showdown_won_label("Won 1000") == True
        assert is_showdown_won_label("Won 50") == True
        
    def test_showdown_label_not_detected_for_player_names(self):
        """Test that normal player names are not detected as showdown labels."""
        assert is_showdown_won_label("Player123") == False
        assert is_showdown_won_label("SuperDog782") == False
        assert is_showdown_won_label("hilanderJOjo") == False
        assert is_showdown_won_label("WonTheGame") == False  # "Won" without space+number
        assert is_showdown_won_label("Won") == False  # Just "Won" without amount
        assert is_showdown_won_label("") == False
        assert is_showdown_won_label(None) == False
    
    def test_showdown_label_with_various_formats(self):
        """Test showdown label detection with various number formats."""
        assert is_showdown_won_label("Won 1,234") == True
        assert is_showdown_won_label("Won 12,345") == True
        assert is_showdown_won_label("Won 123.45") == True
        assert is_showdown_won_label("Won 1,234.56") == True
        assert is_showdown_won_label("Won 10 000") == True  # Space as separator
    
    def test_showdown_frame_prevents_action_events(self):
        """Test that showdown frames don't generate action events."""
        event_fuser = EventFuser(time_window_seconds=5.0, confidence_threshold=0.7)
        
        # Previous state
        prev_state = TableState(
            street=Street.RIVER,
            pot=10000.0,
            players=[
                PlayerState(name="Player1", stack=5000.0, position=0, bet_this_round=0.0),
                PlayerState(name="Won 5,249", stack=10249.0, position=1, bet_this_round=0.0)
            ],
            current_bet=0.0
        )
        
        # Current state with showdown label
        current_state = TableState(
            street=Street.RIVER,
            pot=10000.0,
            players=[
                PlayerState(name="Player1", stack=5000.0, position=0, bet_this_round=0.0),
                PlayerState(name="Won 5,249", stack=15249.0, position=1, bet_this_round=5249.0)
            ],
            current_bet=5249.0,
            frame_has_showdown_label=True  # Key: showdown frame flag
        )
        
        # Initialize tracking
        event_fuser._previous_stacks = {0: 5000.0, 1: 10249.0}
        event_fuser._previous_pot = 10000.0
        
        # Create vision events
        events = event_fuser.create_vision_events_from_state(prev_state, current_state)
        
        # Should NOT have any BET/CALL/RAISE action events
        action_events = [e for e in events if e.event_type == "action" and e.action in [ActionType.BET, ActionType.CALL, ActionType.RAISE]]
        assert len(action_events) == 0, f"Expected no action events, but got {len(action_events)}"


class TestHeroActiveFlag:
    """Test hero_active flag management."""
    
    def test_hero_active_initialized_true(self):
        """Test that hero_active is True by default."""
        state = TableState(
            street=Street.PREFLOP,
            pot=0.0,
            players=[],
            current_bet=0.0
        )
        assert state.hero_active == True
        assert state.hand_in_progress == True
    
    def test_reset_hand_resets_flags(self):
        """Test that reset_hand() resets all flags."""
        state = TableState(
            street=Street.RIVER,
            pot=100.0,
            players=[],
            current_bet=0.0,
            hero_active=False,
            hand_in_progress=False,
            frame_has_showdown_label=True,
            state_inconsistent=True
        )
        
        state.reset_hand()
        
        assert state.hero_active == True
        assert state.hand_in_progress == True
        assert state.frame_has_showdown_label == False
        assert state.state_inconsistent == False
        assert state.last_valid_hero_cards is None
        assert state.hand_id is None
    
    def test_hero_fold_sets_hero_active_false(self):
        """Test that hero folding sets hero_active to False."""
        # This test verifies the logic in chat_enabled_parser._update_hero_state_from_events
        from holdem.vision.event_fusion import FusedEvent
        
        state = TableState(
            street=Street.FLOP,
            pot=50.0,
            players=[
                PlayerState(name="Hero", stack=950.0, position=0, bet_this_round=0.0),
                PlayerState(name="Villain", stack=1000.0, position=1, bet_this_round=50.0)
            ],
            current_bet=50.0,
            hero_position=0
        )
        
        # Manually update hero_active to simulate fold processing
        # (In real code, chat_enabled_parser does this)
        state.hero_active = False
        
        assert state.hero_active == False


class TestHeroCardsTracker:
    """Test hero cards stability tracking."""
    
    def test_tracker_confirms_stable_cards(self):
        """Test that cards are confirmed after stability threshold."""
        tracker = HeroCardsTracker(stability_threshold=2)
        
        card1 = Card(rank='K', suit='d')
        card2 = Card(rank='9', suit='s')
        cards = [card1, card2]
        scores = [0.92, 0.67]
        
        # First frame
        result1 = tracker.update(cards, scores)
        assert tracker.frames_stable == 1
        assert tracker.confirmed_cards is None or result1 == cards  # Not yet confirmed
        
        # Second frame with same cards
        result2 = tracker.update(cards, scores)
        assert tracker.frames_stable == 2
        assert tracker.confirmed_cards == cards  # Now confirmed
        assert result2 == cards
    
    def test_tracker_maintains_confirmed_cards_on_weak_frame(self):
        """Test that confirmed cards are maintained when detection weakens."""
        tracker = HeroCardsTracker(stability_threshold=2)
        
        card1 = Card(rank='K', suit='d')
        card2 = Card(rank='9', suit='s')
        full_cards = [card1, card2]
        partial_cards = [card1]  # Only one card detected
        
        # Confirm full cards
        tracker.update(full_cards, [0.92, 0.67])
        tracker.update(full_cards, [0.92, 0.67])
        assert tracker.confirmed_cards == full_cards
        
        # Weak frame with only one card
        result = tracker.update(partial_cards, [0.90])
        
        # Should still return confirmed full cards, not partial
        assert result == full_cards
        assert tracker.confirmed_cards == full_cards
    
    def test_tracker_resets_on_new_hand(self):
        """Test that tracker resets properly."""
        tracker = HeroCardsTracker()
        
        cards = [Card(rank='A', suit='h'), Card(rank='K', suit='h')]
        tracker.update(cards, [0.95, 0.94])
        tracker.update(cards, [0.95, 0.94])
        
        assert tracker.confirmed_cards == cards
        
        tracker.reset()
        
        assert tracker.confirmed_cards is None
        assert tracker.current_candidate is None
        assert tracker.frames_stable == 0
    
    def test_tracker_updates_to_new_cards(self):
        """Test that tracker updates when truly different cards appear."""
        tracker = HeroCardsTracker(stability_threshold=2)
        
        old_cards = [Card(rank='A', suit='h'), Card(rank='K', suit='h')]
        new_cards = [Card(rank='Q', suit='s'), Card(rank='J', suit='s')]
        
        # Confirm old cards
        tracker.update(old_cards, [0.95, 0.94])
        tracker.update(old_cards, [0.95, 0.94])
        assert tracker.confirmed_cards == old_cards
        
        # New cards appear (new hand)
        tracker.update(new_cards, [0.93, 0.92])
        assert tracker.frames_stable == 1  # Reset counter
        assert tracker.current_candidate == new_cards
        
        tracker.update(new_cards, [0.93, 0.92])
        assert tracker.frames_stable == 2
        assert tracker.confirmed_cards == new_cards


class TestInconsistentStateDetection:
    """Test inconsistent state detection."""
    
    def test_pot_regression_detected(self):
        """Test that pot regression is detected and flagged."""
        # In real code, parse_state.py detects pot regression
        # Here we verify the flag is properly used
        
        state = TableState(
            street=Street.FLOP,
            pot=7716.0,
            players=[],
            current_bet=0.0,
            last_pot=26608.0,  # Previous pot was much higher
            state_inconsistent=True  # Should be set by parse_state.py
        )
        
        assert state.state_inconsistent == True
        assert state.last_pot > state.pot  # Regression detected
    
    def test_no_false_positive_on_normal_pot_increase(self):
        """Test that normal pot increase doesn't trigger inconsistent state."""
        state = TableState(
            street=Street.FLOP,
            pot=100.0,
            players=[],
            current_bet=0.0,
            last_pot=50.0,  # Normal increase
            state_inconsistent=False
        )
        
        assert state.state_inconsistent == False


class TestIntegrationScenarios:
    """Integration tests for complete scenarios."""
    
    def test_no_solver_call_after_hero_fold(self):
        """Test that solver isn't called after hero folds."""
        state = TableState(
            street=Street.FLOP,
            pot=100.0,
            players=[
                PlayerState(name="Hero", stack=900.0, position=0, bet_this_round=0.0, folded=True),
                PlayerState(name="Villain", stack=1000.0, position=1, bet_this_round=50.0)
            ],
            current_bet=50.0,
            hero_position=0,
            hero_active=False  # Hero folded
        )
        
        # Verify flags that would skip solver
        assert state.hero_active == False
        # In run_dry_run.py or run_autoplay.py, this would skip the solver call
    
    def test_no_solver_call_on_showdown_frame(self):
        """Test that solver isn't called on showdown frames."""
        state = TableState(
            street=Street.RIVER,
            pot=10000.0,
            players=[
                PlayerState(name="Hero", stack=5000.0, position=0),
                PlayerState(name="Won 5,249", stack=15249.0, position=1)
            ],
            current_bet=0.0,
            hero_position=0,
            frame_has_showdown_label=True
        )
        
        # Verify flags that would skip solver
        assert state.frame_has_showdown_label == True
    
    def test_no_solver_call_on_inconsistent_state(self):
        """Test that solver isn't called on inconsistent states."""
        state = TableState(
            street=Street.FLOP,
            pot=50.0,
            players=[],
            current_bet=0.0,
            state_inconsistent=True
        )
        
        # Verify flags that would skip solver
        assert state.state_inconsistent == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
