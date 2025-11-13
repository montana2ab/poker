"""Integration tests for complete hand scenarios with vision and state machine."""

import pytest
from datetime import datetime
from holdem.types import TableState, PlayerState, Street, Card, ActionType, PlayerSeatState
from holdem.vision.event_fusion import EventFuser
from holdem.vision.chat_parser import ChatParser, ChatLine, EventSource
from unittest.mock import Mock


class TestCompleteHandScenarios:
    """Test complete hand scenarios from preflop to river."""
    
    @pytest.fixture
    def event_fuser(self):
        return EventFuser(time_window_seconds=5.0, confidence_threshold=0.7)
    
    @pytest.fixture
    def chat_parser(self):
        mock_ocr = Mock()
        return ChatParser(mock_ocr)
    
    def test_complete_hand_without_hero_cards(self, event_fuser, chat_parser):
        """Test that a complete hand can be tracked without hero cards."""
        # Initial state: Preflop, blinds posted
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[
                PlayerState(name="Hero", stack=998.0, position=0, bet_this_round=1.0),
                PlayerState(name="Villain", stack=996.0, position=1, bet_this_round=2.0)
            ],
            current_bet=2.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0,
            hero_position=0
        )
        
        # Hero cards not detected yet
        assert state.get_hero_cards() is None
        
        # But state is still valid and tracks game
        assert state.street == Street.PREFLOP
        assert state.pot == 3.0
        assert len(state.active_players) == 2
        
        # Hero calls the BB
        state.players[0].stack = 996.0
        state.players[0].bet_this_round = 2.0
        state.pot = 4.0
        state.players[0].last_action = ActionType.CALL
        
        # Still no hero cards, but game continues
        assert state.get_hero_cards() is None
        assert state.pot == 4.0
        
        # Flop comes
        state.street = Street.FLOP
        state.board = [Card('A', 'h'), Card('K', 'd'), Card('Q', 's')]
        state.current_bet = 0.0
        state.players[0].bet_this_round = 0.0
        state.players[1].bet_this_round = 0.0
        
        # Hero cards get recognized on flop
        hero_cards = [Card('A', 's'), Card('K', 'c')]
        state.players[0].hole_cards = hero_cards
        
        # Now we have cards
        assert state.get_hero_cards() == hero_cards
        
        # Turn comes, OCR loses cards temporarily
        state.street = Street.TURN
        state.board.append(Card('J', 'h'))
        state.players[0].hole_cards = None  # OCR lost them
        
        # But cache provides them
        assert state.get_hero_cards() == hero_cards
        
        # River, still no OCR
        state.street = Street.RIVER
        state.board.append(Card('T', 'c'))
        
        # Cache still works
        assert state.get_hero_cards() == hero_cards
    
    def test_multi_action_sequence_with_chat(self, chat_parser):
        """Test parsing a sequence of actions from chat."""
        # Parse multiple actions from one line
        chat_line = ChatLine(
            text="Dealer: Player1 bets 100 Dealer: Player2 raises to 300 Dealer: Player3 folds",
            timestamp=datetime.now()
        )
        
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        # Should have 3 events
        assert len(events) == 3
        
        # Verify sequence
        assert events[0].player == "Player1"
        assert events[0].action == ActionType.BET
        assert events[0].amount == 100.0
        
        assert events[1].player == "Player2"
        assert events[1].action == ActionType.RAISE
        assert events[1].amount == 300.0
        
        assert events[2].player == "Player3"
        assert events[2].action == ActionType.FOLD
    
    def test_player_identity_stability_across_actions(self):
        """Test that player identity remains stable when action overlays appear."""
        seat = PlayerSeatState(seat_index=0)
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        # Initial name recognition
        seat.update_from_ocr("PokerPro123", action_keywords)
        assert seat.canonical_name == "PokerPro123"
        
        # Action overlays don't change name
        seat.update_from_ocr("Bet 500", action_keywords)
        assert seat.canonical_name == "PokerPro123"
        
        seat.update_from_ocr("Call 1000", action_keywords)
        assert seat.canonical_name == "PokerPro123"
        
        seat.update_from_ocr("Raise to 2000", action_keywords)
        assert seat.canonical_name == "PokerPro123"
        
        seat.update_from_ocr("All-in", action_keywords)
        assert seat.canonical_name == "PokerPro123"
        
        # Name comes back after action
        seat.update_from_ocr("PokerPro123", action_keywords)
        assert seat.canonical_name == "PokerPro123"
    
    def test_no_ghost_players_from_actions(self):
        """Test that action keywords never become player names."""
        seats = [PlayerSeatState(seat_index=i) for i in range(3)]
        action_keywords = {'check', 'call', 'bet', 'raise', 'fold', 'all-in', 'all in'}
        
        # Real names
        seats[0].update_from_ocr("Alice", action_keywords)
        seats[1].update_from_ocr("Bob", action_keywords)
        seats[2].update_from_ocr("Charlie", action_keywords)
        
        # Action overlays
        seats[0].update_from_ocr("Call 50", action_keywords)
        seats[1].update_from_ocr("Bet 100", action_keywords)
        seats[2].update_from_ocr("Fold", action_keywords)
        
        # Verify no ghost players
        assert seats[0].canonical_name == "Alice"
        assert seats[1].canonical_name == "Bob"
        assert seats[2].canonical_name == "Charlie"
        
        # Verify no player named "Call", "Bet", or "Fold" exists
        all_names = [s.canonical_name for s in seats]
        assert "Call" not in all_names
        assert "Bet" not in all_names
        assert "Fold" not in all_names
    
    def test_stack_delta_prevents_invalid_events(self, event_fuser):
        """Test that invalid stack deltas don't create BET 0.0 events."""
        # Scenario: Stack changed but bet is 0 (OCR timing issue)
        prev_state = TableState(
            street=Street.FLOP,
            pot=100.0,
            players=[
                PlayerState(name="Player1", stack=900.0, position=0, bet_this_round=0.0)
            ],
            current_bet=0.0
        )
        
        current_state = TableState(
            street=Street.FLOP,
            pot=100.0,  # Pot didn't change
            players=[
                PlayerState(name="Player1", stack=895.0, position=0, bet_this_round=0.0)  # Stack changed, bet didn't
            ],
            current_bet=0.0
        )
        
        event_fuser._previous_stacks = {0: 900.0}
        event_fuser._previous_pot = 100.0
        
        # Create events
        events = event_fuser.create_vision_events_from_state(prev_state, current_state)
        
        # Should not create BET 0.0
        for event in events:
            if event.event_type == "action" and event.action in [ActionType.BET, ActionType.RAISE, ActionType.CALL]:
                assert event.amount is None or event.amount > 0.0, "Should not create action with 0.0 amount"
    
    def test_hero_cards_cache_reset_on_new_hand(self):
        """Test that hero cards cache is reset when a new hand starts."""
        # Hand 1: Hero has AA
        state = TableState(
            street=Street.RIVER,
            pot=500.0,
            players=[
                PlayerState(
                    name="Hero",
                    stack=500.0,
                    position=0,
                    hole_cards=[Card('A', 's'), Card('A', 'c')]
                )
            ],
            hero_position=0,
            hand_id="hand_001"
        )
        
        # Cache the cards
        cached_cards = state.get_hero_cards()
        assert cached_cards == [Card('A', 's'), Card('A', 'c')]
        
        # New hand starts
        state.reset_hand()
        
        # Cache should be cleared
        assert state.last_valid_hero_cards is None
        assert state.hand_id is None
        
        # Even though player still has old cards in state, cache is empty
        state.players[0].hole_cards = None  # New hand, cards not dealt yet
        assert state.get_hero_cards() is None
