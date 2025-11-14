"""Tests for HeroCardsTracker downgrade prevention.

This tests the fix for the issue where hero cards would degrade from 2 confirmed
cards to 1 card when one card's confidence temporarily dropped.
"""

import pytest
from holdem.types import Card
from holdem.vision.parse_state import HeroCardsTracker


class TestHeroCardsTrackerDowngradePrevention:
    """Test that HeroCardsTracker prevents downgrading from 2 confirmed cards to 1."""
    
    def test_prevents_downgrade_from_2_to_1_card(self):
        """Test that once 2 cards are confirmed, we never downgrade to 1 card."""
        tracker = HeroCardsTracker(stability_threshold=2)
        
        # First detection: 2 cards
        cards_2 = [Card('Q', 'c'), Card('3', 's')]
        scores_2 = [0.99, 0.70]
        
        # Frame 1: Detect 2 cards
        result = tracker.update(cards_2, scores_2)
        assert result == cards_2  # Should return candidate
        
        # Frame 2: Same 2 cards - should confirm
        result = tracker.update(cards_2, scores_2)
        assert result == cards_2  # Should return confirmed
        assert tracker.confirmed_cards == cards_2  # Should be confirmed now
        assert len(tracker.confirmed_cards) == 2
        
        # Frame 3: Only 1 card detected (3s dropped below threshold)
        cards_1 = [Card('Q', 'c')]
        scores_1 = [0.99]
        
        result = tracker.update(cards_1, scores_1)
        # CRITICAL: Should still return 2 confirmed cards, NOT downgrade to 1
        assert result == cards_2
        assert len(result) == 2
        assert tracker.confirmed_cards == cards_2
        assert len(tracker.confirmed_cards) == 2
    
    def test_prevents_downgrade_from_2_to_0_cards(self):
        """Test that once 2 cards are confirmed, we never downgrade to 0 cards."""
        tracker = HeroCardsTracker(stability_threshold=2)
        
        # Confirm 2 cards
        cards_2 = [Card('A', 'h'), Card('K', 'd')]
        scores_2 = [0.95, 0.85]
        
        tracker.update(cards_2, scores_2)
        tracker.update(cards_2, scores_2)
        assert tracker.confirmed_cards == cards_2
        assert len(tracker.confirmed_cards) == 2
        
        # Frame: No cards detected
        result = tracker.update(None, None)
        # Should still return 2 confirmed cards
        assert result == cards_2
        assert len(result) == 2
        
        # Frame: Empty list
        result = tracker.update([], [])
        # Should still return 2 confirmed cards
        assert result == cards_2
        assert len(result) == 2
    
    def test_allows_upgrade_from_1_to_2_cards(self):
        """Test that we can upgrade from 1 card to 2 cards."""
        tracker = HeroCardsTracker(stability_threshold=2)
        
        # First detection: 1 card only
        cards_1 = [Card('7', 'h')]
        scores_1 = [0.88]
        
        tracker.update(cards_1, scores_1)
        tracker.update(cards_1, scores_1)
        assert tracker.confirmed_cards == cards_1
        assert len(tracker.confirmed_cards) == 1
        
        # Now both cards detected
        cards_2 = [Card('7', 'h'), Card('8', 'h')]
        scores_2 = [0.90, 0.75]
        
        tracker.update(cards_2, scores_2)
        tracker.update(cards_2, scores_2)
        
        # Should upgrade to 2 cards
        assert tracker.confirmed_cards == cards_2
        assert len(tracker.confirmed_cards) == 2
    
    def test_allows_change_from_2_to_different_2_cards(self):
        """Test that we can change from one 2-card hand to a different 2-card hand (new hand)."""
        tracker = HeroCardsTracker(stability_threshold=2)
        
        # Confirm first hand: Qc 3s
        cards_hand1 = [Card('Q', 'c'), Card('3', 's')]
        scores1 = [0.95, 0.80]
        
        tracker.update(cards_hand1, scores1)
        tracker.update(cards_hand1, scores1)
        assert tracker.confirmed_cards == cards_hand1
        
        # New hand detected: Ah Kd
        cards_hand2 = [Card('A', 'h'), Card('K', 'd')]
        scores2 = [0.92, 0.88]
        
        tracker.update(cards_hand2, scores2)
        # After 1 frame, should still have old hand
        assert tracker.confirmed_cards == cards_hand1
        
        tracker.update(cards_hand2, scores2)
        # After 2 frames of stability, should confirm new hand
        assert tracker.confirmed_cards == cards_hand2
        assert len(tracker.confirmed_cards) == 2
    
    def test_reset_clears_confirmed_cards(self):
        """Test that reset() properly clears confirmed cards."""
        tracker = HeroCardsTracker(stability_threshold=2)
        
        # Confirm 2 cards
        cards = [Card('K', 'h'), Card('Q', 'h')]
        tracker.update(cards, [0.90, 0.85])
        tracker.update(cards, [0.90, 0.85])
        assert tracker.confirmed_cards == cards
        
        # Reset tracker
        tracker.reset()
        
        # Should be cleared
        assert tracker.confirmed_cards is None
        assert tracker.current_candidate is None
        assert tracker.frames_stable == 0
    
    def test_ignores_single_card_when_2_confirmed(self):
        """Test specific scenario from bug report: Qc,3s confirmed → Qc only detected → keep Qc,3s."""
        tracker = HeroCardsTracker(stability_threshold=2)
        
        # Confirm Qc, 3s
        qc = Card('Q', 'c')
        three_s = Card('3', 's')
        cards_confirmed = [qc, three_s]
        
        tracker.update(cards_confirmed, [0.991, 0.70])
        tracker.update(cards_confirmed, [0.991, 0.70])
        assert tracker.confirmed_cards == cards_confirmed
        assert len(tracker.confirmed_cards) == 2
        
        # Later frame: Only Qc detected (3s score = 0.609 < threshold 0.65)
        cards_single = [qc]
        result = tracker.update(cards_single, [0.991])
        
        # Should keep both cards
        assert result == cards_confirmed
        assert len(result) == 2
        assert str(result[0]) == 'Qc'
        assert str(result[1]) == '3s'
        
        # Confirmed cards should not change
        assert tracker.confirmed_cards == cards_confirmed
        assert len(tracker.confirmed_cards) == 2


class TestHeroCardsTrackerLogging:
    """Test that logging messages are appropriate for confirmed hands."""
    
    def test_logs_confirmed_hero_cards_message(self, caplog):
        """Test that confirming 2 cards logs the appropriate message."""
        import logging
        caplog.set_level(logging.INFO)
        
        tracker = HeroCardsTracker(stability_threshold=2)
        
        cards = [Card('A', 's'), Card('A', 'c')]
        tracker.update(cards, [0.95, 0.90])
        tracker.update(cards, [0.95, 0.90])
        
        # Should log confirmation message for 2-card hand
        assert any("Confirmed hero cards for current hand" in record.message 
                  for record in caplog.records)
    
    def test_logs_downgrade_prevention(self, caplog):
        """Test that downgrade prevention is logged."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        tracker = HeroCardsTracker(stability_threshold=2)
        
        # Confirm 2 cards
        cards_2 = [Card('J', 'd'), Card('T', 'd')]
        tracker.update(cards_2, [0.92, 0.78])
        tracker.update(cards_2, [0.92, 0.78])
        
        caplog.clear()
        
        # Try to downgrade to 1 card
        cards_1 = [Card('J', 'd')]
        tracker.update(cards_1, [0.92])
        
        # Should log that downgrade was prevented
        assert any("Ignoring downgrade from 2 confirmed cards" in record.message 
                  for record in caplog.records)
