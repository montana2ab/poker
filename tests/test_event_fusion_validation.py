"""Tests for event fusion with stack delta tracking and validation."""

import pytest
from datetime import datetime
from holdem.types import TableState, PlayerState, Street, ActionType, Card
from holdem.vision.event_fusion import EventFuser
from holdem.vision.chat_parser import GameEvent, EventSource


class TestEventFusionStackDelta:
    """Test event fusion with stack delta tracking."""
    
    @pytest.fixture
    def event_fuser(self):
        """Create an event fuser instance."""
        return EventFuser(time_window_seconds=5.0, confidence_threshold=0.7)
    
    def test_valid_bet_from_stack_delta(self, event_fuser):
        """Test valid BET/RAISE action inferred from stack delta."""
        # Previous state: preflop, BB posted
        prev_state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[
                PlayerState(name="Player1", stack=1000.0, position=0, bet_this_round=0.0),
                PlayerState(name="Player2", stack=998.0, position=1, bet_this_round=2.0)
            ],
            current_bet=2.0
        )
        
        # Current state: Player1 raises to 50 (over the 2.0 BB)
        current_state = TableState(
            street=Street.PREFLOP,
            pot=53.0,
            players=[
                PlayerState(name="Player1", stack=950.0, position=0, bet_this_round=50.0),
                PlayerState(name="Player2", stack=998.0, position=1, bet_this_round=2.0)
            ],
            current_bet=50.0
        )
        
        # Initialize tracking with previous state
        event_fuser._previous_stacks = {0: 1000.0, 1: 998.0}
        event_fuser._previous_pot = 3.0
        
        # Create vision events
        events = event_fuser.create_vision_events_from_state(prev_state, current_state)
        
        # Should have action event from stack delta
        action_events = [e for e in events if e.event_type == "action"]
        assert len(action_events) >= 1
        
        # Find the RAISE event (since there was a bet before - the BB)
        raise_event = next((e for e in action_events if e.action == ActionType.RAISE), None)
        assert raise_event is not None
        assert raise_event.player == "Player1"
        assert raise_event.amount == 50.0
        assert EventSource.VISION_STACK in raise_event.sources
    
    def test_invalid_amount_filtered(self, event_fuser):
        """Test that invalid amounts (e.g., BET 0.0) are filtered."""
        # Previous state
        prev_state = TableState(
            street=Street.FLOP,
            pot=100.0,
            players=[
                PlayerState(name="Player1", stack=900.0, position=0, bet_this_round=0.0)
            ],
            current_bet=0.0
        )
        
        # Current state: stack changed but bet_this_round is 0 (OCR error)
        current_state = TableState(
            street=Street.FLOP,
            pot=100.0,  # Pot didn't change either
            players=[
                PlayerState(name="Player1", stack=895.0, position=0, bet_this_round=0.0)
            ],
            current_bet=0.0
        )
        
        # Initialize tracking
        event_fuser._previous_stacks = {0: 900.0}
        event_fuser._previous_pot = 100.0
        
        # Create vision events
        events = event_fuser.create_vision_events_from_state(prev_state, current_state)
        
        # Should NOT create BET 0.0 event
        action_events = [e for e in events if e.event_type == "action"]
        for event in action_events:
            if event.action in [ActionType.BET, ActionType.RAISE, ActionType.CALL]:
                assert event.amount > 0.0, "Should not create action with 0.0 amount"
    
    def test_scale_mismatch_detection(self, event_fuser):
        """Test detection of scale mismatches (e.g., 4.74 vs 4736)."""
        # Test the validation method directly
        # Case 1: Normal match
        assert event_fuser._is_valid_action_amount(
            amount_put_in=50.0,
            curr_bet=50.0,
            curr_pot=103.0,
            prev_pot=53.0,
            delta_pot=50.0
        )
        
        # Case 2: Scale mismatch - should still be considered valid but flagged
        assert event_fuser._is_valid_action_amount(
            amount_put_in=4.74,
            curr_bet=4736.0,
            curr_pot=5000.0,
            prev_pot=500.0,
            delta_pot=4500.0
        )
        
        # Case 3: Zero amount - should be invalid
        assert not event_fuser._is_valid_action_amount(
            amount_put_in=0.0,
            curr_bet=0.0,
            curr_pot=100.0,
            prev_pot=100.0,
            delta_pot=0.0
        )
    
    def test_multi_source_fusion_confidence(self, event_fuser):
        """Test that multi-source events have higher confidence."""
        timestamp = datetime.now()
        
        # Chat event: Player1 bets 100
        chat_event = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.BET,
            amount=100.0,
            sources=[EventSource.CHAT],
            timestamp=timestamp
        )
        
        # Vision bet region event: same action
        vision_bet_event = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.BET,
            amount=98.0,  # Slightly different due to OCR
            sources=[EventSource.VISION_BET_REGION],
            timestamp=timestamp
        )
        
        # Vision stack event: same action
        vision_stack_event = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.BET,
            amount=100.0,
            sources=[EventSource.VISION_STACK],
            timestamp=timestamp
        )
        
        # Fuse events
        fused_events = event_fuser.fuse_events([chat_event], [vision_bet_event, vision_stack_event])
        
        # Should have one fused event with high confidence
        assert len(fused_events) >= 1
        
        # Find the multi-source event
        multi_source = next((e for e in fused_events if e.is_multi_source()), None)
        assert multi_source is not None
        
        # Should have high confidence (>= 0.85) due to multiple sources
        assert multi_source.confidence >= 0.85
        
        # Should include all three source types
        assert EventSource.CHAT in multi_source.sources
        assert EventSource.VISION_BET_REGION in multi_source.sources
        assert EventSource.VISION_STACK in multi_source.sources
    
    def test_single_source_lower_confidence(self, event_fuser):
        """Test that single-source events have lower confidence."""
        # Vision stack event only
        vision_event = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.CALL,
            amount=50.0,
            sources=[EventSource.VISION_STACK],
            confidence=0.75,
            timestamp=datetime.now()
        )
        
        # Fuse (no other events)
        fused_events = event_fuser.fuse_events([], [vision_event])
        
        assert len(fused_events) == 1
        # Single source, should have medium confidence
        assert fused_events[0].confidence < 0.85
    
    def test_pot_delta_event_creation(self, event_fuser):
        """Test that pot changes create pot_update events."""
        prev_state = TableState(
            street=Street.FLOP,
            pot=100.0,
            players=[PlayerState(name="Player1", stack=900.0, position=0)]
        )
        
        current_state = TableState(
            street=Street.FLOP,
            pot=200.0,
            players=[PlayerState(name="Player1", stack=800.0, position=0)]
        )
        
        # Initialize tracking
        event_fuser._previous_pot = 100.0
        event_fuser._previous_stacks = {0: 900.0}
        
        # Create events
        events = event_fuser.create_vision_events_from_state(prev_state, current_state)
        
        # Should have pot update event
        pot_events = [e for e in events if e.event_type == "pot_update"]
        assert len(pot_events) >= 1
        assert pot_events[0].pot_amount == 200.0
        assert EventSource.VISION_POT in pot_events[0].sources
    
    def test_fold_detection_from_player_state(self, event_fuser):
        """Test that fold detection works from player state changes."""
        prev_state = TableState(
            street=Street.FLOP,
            pot=100.0,
            players=[
                PlayerState(name="Player1", stack=900.0, position=0, folded=False)
            ]
        )
        
        current_state = TableState(
            street=Street.FLOP,
            pot=100.0,
            players=[
                PlayerState(name="Player1", stack=900.0, position=0, folded=True)
            ]
        )
        
        # Initialize tracking
        event_fuser._previous_stacks = {0: 900.0}
        event_fuser._previous_pot = 100.0
        
        # Create events
        events = event_fuser.create_vision_events_from_state(prev_state, current_state)
        
        # Should have fold event
        fold_events = [e for e in events if e.action == ActionType.FOLD]
        assert len(fold_events) >= 1
        assert fold_events[0].player == "Player1"
