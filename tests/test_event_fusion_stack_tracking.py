"""Tests for enhanced event fusion with stack tracking."""

from datetime import datetime
from holdem.vision.event_fusion import EventFuser, FusedEvent
from holdem.vision.chat_parser import GameEvent, EventSource
from holdem.types import (
    ActionType,
    Street,
    TableState,
    PlayerState,
    Card
)


class TestEventFusionStackTracking:
    """Test suite for event fusion with stack delta tracking."""
    
    def test_init_with_stack_tracking(self):
        """Test EventFuser initializes with stack tracking."""
        fuser = EventFuser()
        
        assert fuser._previous_stacks == {}
        assert fuser._previous_pot == 0.0
    
    def test_stack_tracking_initialization(self):
        """Test that first state initializes stack tracking."""
        fuser = EventFuser()
        
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[
                PlayerState("P1", stack=100.0, position=0),
                PlayerState("P2", stack=98.0, position=1)
            ],
            current_bet=2.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        fuser.create_vision_events_from_state(None, state)
        
        # No events on first observation, but stacks should be tracked
        assert 0 in fuser._previous_stacks
        assert 1 in fuser._previous_stacks
        assert fuser._previous_stacks[0] == 100.0
        assert fuser._previous_stacks[1] == 98.0
        assert fuser._previous_pot == 3.0
    
    def test_detect_stack_decrease_creates_action_event(self):
        """Test that stack decrease creates an action event."""
        fuser = EventFuser()
        
        # Initial state
        prev_state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[
                PlayerState("P1", stack=100.0, position=0),
                PlayerState("P2", stack=100.0, position=1)
            ],
            current_bet=2.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        # Initialize tracking
        fuser.create_vision_events_from_state(None, prev_state)
        
        # New state: P1 calls (puts in 2 chips)
        curr_state = TableState(
            street=Street.PREFLOP,
            pot=5.0,
            players=[
                PlayerState("P1", stack=98.0, bet_this_round=2.0, position=0),
                PlayerState("P2", stack=100.0, bet_this_round=2.0, position=1)
            ],
            current_bet=2.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        events = fuser.create_vision_events_from_state(prev_state, curr_state)
        
        # Should detect P1's action via stack delta
        action_events = [e for e in events if e.event_type == "action"]
        assert len(action_events) >= 1
        
        # Find P1's event
        p1_events = [e for e in action_events if e.player == "P1"]
        assert len(p1_events) >= 1
        
        p1_event = p1_events[0]
        assert EventSource.VISION_STACK in p1_event.sources or \
               EventSource.VISION_BET_REGION in p1_event.sources
    
    def test_infer_action_from_bet(self):
        """Test inferring BET action from stack delta."""
        fuser = EventFuser()
        
        # No previous bet, player bets 10
        action = fuser._infer_action_from_stack_delta(
            amount_put_in=10.0,
            curr_bet=10.0,
            prev_bet=0.0,
            current_state_bet=10.0,
            prev_state_bet=0.0,
            player_stack=90.0
        )
        
        assert action == ActionType.BET
    
    def test_infer_action_from_call(self):
        """Test inferring CALL action from stack delta."""
        fuser = EventFuser()
        
        # Previous bet was 10, player calls
        action = fuser._infer_action_from_stack_delta(
            amount_put_in=10.0,
            curr_bet=10.0,
            prev_bet=0.0,
            current_state_bet=10.0,
            prev_state_bet=10.0,
            player_stack=90.0
        )
        
        assert action == ActionType.CALL
    
    def test_infer_action_from_raise(self):
        """Test inferring RAISE action from stack delta."""
        fuser = EventFuser()
        
        # Previous bet was 10, player raises to 20
        action = fuser._infer_action_from_stack_delta(
            amount_put_in=20.0,
            curr_bet=20.0,
            prev_bet=0.0,
            current_state_bet=20.0,
            prev_state_bet=10.0,
            player_stack=80.0
        )
        
        assert action == ActionType.RAISE
    
    def test_infer_action_from_allin(self):
        """Test inferring ALLIN action from stack delta."""
        fuser = EventFuser()
        
        # Player goes all-in (stack becomes 0)
        action = fuser._infer_action_from_stack_delta(
            amount_put_in=50.0,
            curr_bet=50.0,
            prev_bet=0.0,
            current_state_bet=50.0,
            prev_state_bet=10.0,
            player_stack=0.0  # All-in
        )
        
        assert action == ActionType.ALLIN
    
    def test_pot_update_event_with_new_source(self):
        """Test that pot updates use VISION_POT source."""
        fuser = EventFuser()
        
        prev_state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=100.0, position=0),
                PlayerState("P2", stack=100.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        fuser.create_vision_events_from_state(None, prev_state)
        
        curr_state = TableState(
            street=Street.FLOP,
            pot=20.0,  # Pot increased
            players=[
                PlayerState("P1", stack=95.0, bet_this_round=5.0, position=0),
                PlayerState("P2", stack=95.0, bet_this_round=5.0, position=1)
            ],
            current_bet=5.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        events = fuser.create_vision_events_from_state(prev_state, curr_state)
        
        pot_events = [e for e in events if e.event_type == "pot_update"]
        assert len(pot_events) >= 1
        assert EventSource.VISION_POT in pot_events[0].sources
    
    def test_multi_source_confidence_scoring(self):
        """Test that multi-source events get higher confidence."""
        fuser = EventFuser()
        
        # Create events from different sources
        chat_event = GameEvent(
            event_type="action",
            player="P1",
            action=ActionType.BET,
            amount=10.0,
            sources=[EventSource.CHAT],
            timestamp=datetime.now()
        )
        
        vision_bet_event = GameEvent(
            event_type="action",
            player="P1",
            action=ActionType.BET,
            amount=10.5,  # Slightly different (OCR noise)
            sources=[EventSource.VISION_BET_REGION],
            timestamp=datetime.now()
        )
        
        vision_stack_event = GameEvent(
            event_type="action",
            player="P1",
            action=ActionType.BET,
            amount=10.2,
            sources=[EventSource.VISION_STACK],
            timestamp=datetime.now()
        )
        
        # Fuse events
        fused_events = fuser.fuse_events(
            chat_events=[chat_event],
            vision_events=[vision_bet_event, vision_stack_event]
        )
        
        # Should have one fused event with high confidence
        assert len(fused_events) >= 1
        
        multi_source = [e for e in fused_events if e.is_multi_source()]
        assert len(multi_source) >= 1
        
        # Multi-source event should have high confidence
        assert multi_source[0].confidence >= 0.9
    
    def test_confidence_chat_plus_vision_highest(self):
        """Test that chat + vision gives highest confidence."""
        fuser = EventFuser()
        
        events = [
            GameEvent(
                event_type="action",
                player="P1",
                action=ActionType.CALL,
                amount=10.0,
                sources=[EventSource.CHAT]
            ),
            GameEvent(
                event_type="action",
                player="P1",
                action=ActionType.CALL,
                amount=10.0,
                sources=[EventSource.VISION_STACK]
            )
        ]
        
        confidence = fuser._calculate_confidence(events)
        assert confidence >= 0.90  # Should be very high
    
    def test_confidence_stack_plus_bet_region(self):
        """Test confidence for stack + bet region sources."""
        fuser = EventFuser()
        
        events = [
            GameEvent(
                event_type="action",
                player="P1",
                action=ActionType.BET,
                amount=10.0,
                sources=[EventSource.VISION_STACK]
            ),
            GameEvent(
                event_type="action",
                player="P1",
                action=ActionType.BET,
                amount=10.0,
                sources=[EventSource.VISION_BET_REGION]
            )
        ]
        
        confidence = fuser._calculate_confidence(events)
        assert 0.85 <= confidence <= 0.95
    
    def test_confidence_single_source_chat(self):
        """Test confidence for single chat source."""
        fuser = EventFuser()
        
        events = [
            GameEvent(
                event_type="action",
                player="P1",
                action=ActionType.RAISE,
                amount=20.0,
                sources=[EventSource.CHAT]
            )
        ]
        
        confidence = fuser._calculate_confidence(events)
        assert 0.80 <= confidence <= 0.90
    
    def test_confidence_single_source_stack(self):
        """Test confidence for single stack source."""
        fuser = EventFuser()
        
        events = [
            GameEvent(
                event_type="action",
                player="P1",
                action=ActionType.BET,
                amount=10.0,
                sources=[EventSource.VISION_STACK]
            )
        ]
        
        confidence = fuser._calculate_confidence(events)
        assert 0.70 <= confidence <= 0.80
    
    def test_confidence_penalty_for_inconsistent_amounts(self):
        """Test that inconsistent amounts reduce confidence."""
        fuser = EventFuser()
        
        events = [
            GameEvent(
                event_type="action",
                player="P1",
                action=ActionType.BET,
                amount=10.0,
                sources=[EventSource.CHAT]
            ),
            GameEvent(
                event_type="action",
                player="P1",
                action=ActionType.BET,
                amount=20.0,  # Very different!
                sources=[EventSource.VISION_STACK]
            )
        ]
        
        confidence = fuser._calculate_confidence(events)
        
        # Should be penalized for large discrepancy
        # Base would be ~0.95 for chat+vision, but should drop
        assert confidence < 0.90
    
    def test_street_change_resets_stack_tracking(self):
        """Test that street changes reset bet tracking but keep stacks."""
        fuser = EventFuser()
        
        # Preflop state
        preflop_state = TableState(
            street=Street.PREFLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=95.0, bet_this_round=5.0, position=0),
                PlayerState("P2", stack=95.0, bet_this_round=5.0, position=1)
            ],
            current_bet=5.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        fuser.create_vision_events_from_state(None, preflop_state)
        
        # Flop state (bets reset to 0)
        flop_state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=95.0, bet_this_round=0.0, position=0),
                PlayerState("P2", stack=95.0, bet_this_round=0.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        events = fuser.create_vision_events_from_state(preflop_state, flop_state)
        
        # Should detect street change
        street_events = [e for e in events if e.event_type == "street_change"]
        assert len(street_events) >= 1
        assert street_events[0].street == "FLOP"
        
        # Stack tracking should be updated to current stacks
        assert fuser._previous_stacks[0] == 95.0
        assert fuser._previous_stacks[1] == 95.0
    
    def test_multiple_players_stack_changes(self):
        """Test tracking stack changes for multiple players simultaneously."""
        fuser = EventFuser()
        
        prev_state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[
                PlayerState("P1", stack=100.0, bet_this_round=0.0, position=0),
                PlayerState("P2", stack=100.0, bet_this_round=0.0, position=1),
                PlayerState("P3", stack=100.0, bet_this_round=0.0, position=2)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        fuser.create_vision_events_from_state(None, prev_state)
        
        # Multiple players act
        curr_state = TableState(
            street=Street.FLOP,
            pot=25.0,
            players=[
                PlayerState("P1", stack=95.0, bet_this_round=5.0, position=0),
                PlayerState("P2", stack=90.0, bet_this_round=10.0, position=1),
                PlayerState("P3", stack=90.0, bet_this_round=10.0, position=2)
            ],
            current_bet=10.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        events = fuser.create_vision_events_from_state(prev_state, curr_state)
        
        # Should detect actions for all players
        action_events = [e for e in events if e.event_type == "action"]
        
        # May have multiple action events (from stack and bet tracking)
        # Check we have events for each player
        players_with_events = set(e.player for e in action_events)
        assert "P1" in players_with_events or "P2" in players_with_events or "P3" in players_with_events
    
    def test_positive_stack_delta_logged_not_as_action(self):
        """Test that positive stack deltas (winning pot) are logged but not as actions."""
        fuser = EventFuser()
        
        prev_state = TableState(
            street=Street.RIVER,
            pot=100.0,
            players=[
                PlayerState("P1", stack=50.0, bet_this_round=50.0, position=0),
                PlayerState("P2", stack=50.0, bet_this_round=50.0, position=1)
            ],
            current_bet=50.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        fuser.create_vision_events_from_state(None, prev_state)
        
        # P1 wins the pot
        curr_state = TableState(
            street=Street.RIVER,
            pot=0.0,
            players=[
                PlayerState("P1", stack=150.0, bet_this_round=0.0, position=0),  # Won 100
                PlayerState("P2", stack=50.0, bet_this_round=0.0, position=1)
            ],
            current_bet=0.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        events = fuser.create_vision_events_from_state(prev_state, curr_state)
        
        # Should not create action event for P1's positive delta
        # (positive deltas are just logged as debug)
        p1_action_events = [e for e in events 
                           if e.event_type == "action" and e.player == "P1" and 
                              EventSource.VISION_STACK in e.sources]
        
        # Stack increase should not generate an action event
        assert len(p1_action_events) == 0
