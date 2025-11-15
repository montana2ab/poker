"""Tests for apply_fused_events_to_state function."""

from datetime import datetime

from holdem.types import TableState, PlayerState, Street, ActionType, Card
from holdem.vision.event_fusion import FusedEvent
from holdem.vision.chat_parser import EventSource
from holdem.vision.chat_enabled_parser import apply_fused_events_to_state


class TestApplyFusedEventsToState:
    """Test applying fused events to table state."""
    
    def test_street_update_from_chat_flop(self):
        """Test that board_update event from chat updates street from PREFLOP to FLOP."""
        # Initial state: PREFLOP
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            board=[],
            players=[
                PlayerState(name="Player1", stack=1000.0, position=0, bet_this_round=1.0),
                PlayerState(name="Player2", stack=998.0, position=1, bet_this_round=2.0)
            ],
            current_bet=2.0
        )
        
        # Create board_update event from chat: FLOP
        cards = [Card(rank='A', suit='h'), Card(rank='K', suit='d'), Card(rank='Q', suit='s')]
        event = FusedEvent(
            event_type="board_update",
            street="FLOP",
            cards=cards,
            sources=[EventSource.CHAT_OCR],
            confidence=0.9
        )
        
        # Apply events
        apply_fused_events_to_state(state, [event])
        
        # Verify street was updated
        assert state.street == Street.FLOP
        assert len(state.board) >= 3
        assert state.board[0] == cards[0]
        assert state.board[1] == cards[1]
        assert state.board[2] == cards[2]
    
    def test_street_update_from_chat_turn(self):
        """Test that board_update event from chat updates street from FLOP to TURN."""
        # Initial state: FLOP
        flop_cards = [Card(rank='A', suit='h'), Card(rank='K', suit='d'), Card(rank='Q', suit='s')]
        state = TableState(
            street=Street.FLOP,
            pot=50.0,
            board=flop_cards,
            players=[
                PlayerState(name="Player1", stack=950.0, position=0, bet_this_round=10.0),
                PlayerState(name="Player2", stack=950.0, position=1, bet_this_round=10.0)
            ],
            current_bet=10.0
        )
        
        # Create board_update event from chat: TURN
        turn_card = [Card(rank='2', suit='c')]
        event = FusedEvent(
            event_type="board_update",
            street="TURN",
            cards=turn_card,
            sources=[EventSource.CHAT_OCR],
            confidence=0.9
        )
        
        # Apply events
        apply_fused_events_to_state(state, [event])
        
        # Verify street was updated
        assert state.street == Street.TURN
        assert len(state.board) >= 4
        assert state.board[3] == turn_card[0]
    
    def test_street_update_from_chat_river(self):
        """Test that board_update event from chat updates street from TURN to RIVER."""
        # Initial state: TURN
        board_cards = [
            Card(rank='A', suit='h'), 
            Card(rank='K', suit='d'), 
            Card(rank='Q', suit='s'),
            Card(rank='2', suit='c')
        ]
        state = TableState(
            street=Street.TURN,
            pot=100.0,
            board=board_cards,
            players=[
                PlayerState(name="Player1", stack=900.0, position=0, bet_this_round=25.0),
                PlayerState(name="Player2", stack=900.0, position=1, bet_this_round=25.0)
            ],
            current_bet=25.0
        )
        
        # Create board_update event from chat: RIVER
        river_card = [Card(rank='J', suit='h')]
        event = FusedEvent(
            event_type="board_update",
            street="RIVER",
            cards=river_card,
            sources=[EventSource.CHAT_OCR],
            confidence=0.9
        )
        
        # Apply events
        apply_fused_events_to_state(state, [event])
        
        # Verify street was updated
        assert state.street == Street.RIVER
        assert len(state.board) == 5
        assert state.board[4] == river_card[0]
    
    def test_street_no_backwards_transition(self):
        """Test that street doesn't go backwards (RIVER -> FLOP should be ignored)."""
        # Initial state: RIVER
        board_cards = [
            Card(rank='A', suit='h'), 
            Card(rank='K', suit='d'), 
            Card(rank='Q', suit='s'),
            Card(rank='2', suit='c'),
            Card(rank='J', suit='h')
        ]
        state = TableState(
            street=Street.RIVER,
            pot=200.0,
            board=board_cards,
            players=[
                PlayerState(name="Player1", stack=800.0, position=0, bet_this_round=50.0),
                PlayerState(name="Player2", stack=800.0, position=1, bet_this_round=50.0)
            ],
            current_bet=50.0
        )
        
        # Create board_update event trying to go back to FLOP (should be ignored)
        event = FusedEvent(
            event_type="board_update",
            street="FLOP",
            cards=[Card(rank='9', suit='s')],
            sources=[EventSource.CHAT_OCR],
            confidence=0.9
        )
        
        # Apply events
        apply_fused_events_to_state(state, [event])
        
        # Verify street was NOT updated (stayed at RIVER)
        assert state.street == Street.RIVER
    
    def test_pot_update_from_chat(self):
        """Test that pot_update event updates pot value."""
        # Initial state
        state = TableState(
            street=Street.FLOP,
            pot=50.0,
            board=[],
            players=[
                PlayerState(name="Player1", stack=950.0, position=0, bet_this_round=10.0),
                PlayerState(name="Player2", stack=950.0, position=1, bet_this_round=10.0)
            ],
            current_bet=10.0
        )
        
        # Create pot_update event from chat
        event = FusedEvent(
            event_type="pot_update",
            pot_amount=150.0,
            sources=[EventSource.CHAT_OCR],
            confidence=0.85
        )
        
        # Apply events
        apply_fused_events_to_state(state, [event])
        
        # Verify pot was updated
        assert state.pot == 150.0
    
    def test_player_action_fold(self):
        """Test that player_action event updates player state (FOLD)."""
        # Initial state
        state = TableState(
            street=Street.FLOP,
            pot=50.0,
            board=[],
            players=[
                PlayerState(name="Player1", stack=950.0, position=0, bet_this_round=10.0, folded=False),
                PlayerState(name="Player2", stack=950.0, position=1, bet_this_round=10.0, folded=False)
            ],
            current_bet=10.0
        )
        
        # Create action event: Player1 folds
        event = FusedEvent(
            event_type="action",
            player="Player1",
            action=ActionType.FOLD,
            sources=[EventSource.CHAT_OCR],
            confidence=0.95
        )
        
        # Apply events
        apply_fused_events_to_state(state, [event])
        
        # Verify player1 is now folded
        assert state.players[0].folded == True
        assert state.players[0].last_action == ActionType.FOLD
    
    def test_player_action_bet(self):
        """Test that player_action event updates player bet amount."""
        # Initial state
        state = TableState(
            street=Street.FLOP,
            pot=50.0,
            board=[],
            players=[
                PlayerState(name="Player1", stack=950.0, position=0, bet_this_round=10.0),
                PlayerState(name="Player2", stack=900.0, position=1, bet_this_round=10.0)
            ],
            current_bet=10.0
        )
        
        # Create action event: Player2 raises to 50
        event = FusedEvent(
            event_type="action",
            player="Player2",
            action=ActionType.RAISE,
            amount=50.0,
            sources=[EventSource.CHAT_OCR],
            confidence=0.9
        )
        
        # Apply events
        apply_fused_events_to_state(state, [event])
        
        # Verify player2's bet was updated
        assert state.players[1].bet_this_round == 50.0
        assert state.players[1].last_action == ActionType.RAISE
    
    def test_low_confidence_event_ignored(self):
        """Test that events with confidence < 0.7 are ignored."""
        # Initial state: PREFLOP
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            board=[],
            players=[
                PlayerState(name="Player1", stack=1000.0, position=0, bet_this_round=1.0)
            ],
            current_bet=2.0
        )
        
        # Create board_update event with LOW confidence
        event = FusedEvent(
            event_type="board_update",
            street="FLOP",
            cards=[Card(rank='A', suit='h')],
            sources=[EventSource.VISION],  # Not from chat
            confidence=0.5  # Low confidence
        )
        
        # Apply events
        apply_fused_events_to_state(state, [event])
        
        # Verify street was NOT updated (stayed at PREFLOP)
        assert state.street == Street.PREFLOP
    
    def test_multiple_events_applied_in_order(self):
        """Test that multiple events are applied in order."""
        # Initial state: PREFLOP
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            board=[],
            players=[
                PlayerState(name="Player1", stack=1000.0, position=0, bet_this_round=1.0),
                PlayerState(name="Player2", stack=998.0, position=1, bet_this_round=2.0)
            ],
            current_bet=2.0
        )
        
        # Create multiple events
        flop_cards = [Card(rank='A', suit='h'), Card(rank='K', suit='d'), Card(rank='Q', suit='s')]
        events = [
            FusedEvent(
                event_type="board_update",
                street="FLOP",
                cards=flop_cards,
                sources=[EventSource.CHAT_OCR],
                confidence=0.9
            ),
            FusedEvent(
                event_type="pot_update",
                pot_amount=50.0,
                sources=[EventSource.CHAT_OCR],
                confidence=0.85
            ),
            FusedEvent(
                event_type="action",
                player="Player1",
                action=ActionType.BET,
                amount=20.0,
                sources=[EventSource.CHAT_OCR],
                confidence=0.9
            )
        ]
        
        # Apply all events
        apply_fused_events_to_state(state, events)
        
        # Verify all updates were applied
        assert state.street == Street.FLOP
        assert state.pot == 50.0
        assert state.players[0].bet_this_round == 20.0
        assert state.players[0].last_action == ActionType.BET
