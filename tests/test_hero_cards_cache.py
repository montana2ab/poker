"""Tests for hero cards caching and state machine progression."""

import pytest
from holdem.types import TableState, PlayerState, Street, Card, ActionType


class TestHeroCardsCache:
    """Test hero cards caching functionality."""
    
    def test_get_hero_cards_from_current(self):
        """Test getting hero cards from current player state."""
        hero_cards = [Card('A', 'h'), Card('K', 'd')]
        hero = PlayerState(
            name="Hero",
            stack=1000.0,
            position=0,
            hole_cards=hero_cards
        )
        
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[hero],
            hero_position=0
        )
        
        # Should return current cards
        cards = state.get_hero_cards()
        assert cards == hero_cards
        
        # Should also update cache
        assert state.last_valid_hero_cards == hero_cards
    
    def test_get_hero_cards_from_cache(self):
        """Test getting hero cards from cache when current cards are missing."""
        cached_cards = [Card('Q', 's'), Card('J', 's')]
        hero = PlayerState(
            name="Hero",
            stack=1000.0,
            position=0,
            hole_cards=None  # Cards missing (OCR failed)
        )
        
        state = TableState(
            street=Street.TURN,
            pot=50.0,
            players=[hero],
            hero_position=0,
            last_valid_hero_cards=cached_cards  # But we have cached cards
        )
        
        # Should return cached cards
        cards = state.get_hero_cards()
        assert cards == cached_cards
    
    def test_cache_updates_on_recognition(self):
        """Test that cache is updated when cards are recognized."""
        initial_cards = [Card('7', 'h'), Card('8', 'h')]
        hero = PlayerState(
            name="Hero",
            stack=1000.0,
            position=0,
            hole_cards=None
        )
        
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[hero],
            hero_position=0
        )
        
        # Initially no cards
        assert state.get_hero_cards() is None
        
        # Cards get recognized
        hero.hole_cards = initial_cards
        
        # Should return and cache the cards
        cards = state.get_hero_cards()
        assert cards == initial_cards
        assert state.last_valid_hero_cards == initial_cards
    
    def test_cache_persists_across_streets(self):
        """Test that cached cards persist when OCR temporarily loses them."""
        cards = [Card('A', 's'), Card('A', 'c')]
        
        # Preflop: cards recognized
        hero = PlayerState(
            name="Hero",
            stack=1000.0,
            position=0,
            hole_cards=cards
        )
        
        state = TableState(
            street=Street.PREFLOP,
            pot=10.0,
            players=[hero],
            hero_position=0
        )
        
        # Get cards (caches them)
        assert state.get_hero_cards() == cards
        
        # Flop: OCR loses cards temporarily
        state.street = Street.FLOP
        hero.hole_cards = None
        
        # Should still have cards from cache
        assert state.get_hero_cards() == cards
        
        # Turn: OCR loses cards again
        state.street = Street.TURN
        hero.hole_cards = None
        
        # Should still have cards from cache
        assert state.get_hero_cards() == cards
    
    def test_reset_hand_clears_cache(self):
        """Test that reset_hand() clears the hero cards cache."""
        cards = [Card('K', 'h'), Card('Q', 'h')]
        hero = PlayerState(
            name="Hero",
            stack=1000.0,
            position=0,
            hole_cards=cards
        )
        
        state = TableState(
            street=Street.RIVER,
            pot=100.0,
            players=[hero],
            hero_position=0,
            hand_id="hand_123"
        )
        
        # Cache the cards
        state.get_hero_cards()
        assert state.last_valid_hero_cards == cards
        assert state.hand_id == "hand_123"
        
        # Reset for new hand
        state.reset_hand()
        
        # Cache should be cleared
        assert state.last_valid_hero_cards is None
        assert state.hand_id is None
    
    def test_no_hero_position(self):
        """Test behavior when hero_position is None."""
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[PlayerState(name="Player1", stack=1000.0, position=0)],
            hero_position=None  # No hero
        )
        
        # Should return None
        assert state.get_hero_cards() is None
    
    def test_invalid_hero_position(self):
        """Test behavior when hero_position is out of range."""
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[PlayerState(name="Player1", stack=1000.0, position=0)],
            hero_position=5  # Out of range
        )
        
        # Should return None (or cached if available)
        assert state.get_hero_cards() is None


class TestStateMachineProgressionWithoutCards:
    """Test that state machine can progress without hero cards."""
    
    def test_street_progression_without_cards(self):
        """Test that streets can progress without hero cards."""
        # Start on preflop without hero cards
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[
                PlayerState(name="Hero", stack=998.0, position=0, bet_this_round=1.0),
                PlayerState(name="Villain", stack=996.0, position=1, bet_this_round=2.0)
            ],
            current_bet=2.0,
            hero_position=0
        )
        
        # Hero cards not detected yet
        assert state.get_hero_cards() is None
        
        # State should still be valid
        assert state.street == Street.PREFLOP
        assert state.pot == 3.0
        assert state.current_bet == 2.0
        
        # Can progress to flop
        state.street = Street.FLOP
        state.board = [Card('A', 'h'), Card('K', 'd'), Card('Q', 's')]
        
        # Still valid without hero cards
        assert state.street == Street.FLOP
        assert len(state.board) == 3
    
    def test_action_tracking_without_hero_cards(self):
        """Test that actions can be tracked without hero cards."""
        hero = PlayerState(
            name="Hero",
            stack=950.0,
            position=0,
            bet_this_round=50.0,
            last_action=ActionType.BET
        )
        
        villain = PlayerState(
            name="Villain",
            stack=950.0,
            position=1,
            bet_this_round=50.0,
            last_action=ActionType.CALL
        )
        
        state = TableState(
            street=Street.FLOP,
            pot=103.0,
            board=[Card('7', 'c'), Card('8', 'c'), Card('9', 'h')],
            players=[hero, villain],
            current_bet=50.0,
            hero_position=0
        )
        
        # No hero cards
        assert state.get_hero_cards() is None
        
        # But actions are tracked
        assert hero.last_action == ActionType.BET
        assert villain.last_action == ActionType.CALL
        assert state.pot == 103.0
    
    def test_pot_and_stack_updates_without_cards(self):
        """Test that pot and stacks update correctly without hero cards."""
        state = TableState(
            street=Street.TURN,
            pot=200.0,
            board=[Card('2', 'h'), Card('3', 'd'), Card('4', 's'), Card('5', 'c')],
            players=[
                PlayerState(name="Hero", stack=800.0, position=0),
                PlayerState(name="Villain", stack=800.0, position=1)
            ],
            hero_position=0
        )
        
        # No hero cards
        assert state.get_hero_cards() is None
        
        # State values are still meaningful
        assert state.pot == 200.0
        assert state.players[0].stack == 800.0
        assert state.players[1].stack == 800.0
        assert len(state.board) == 4
