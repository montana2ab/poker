"""Integration test for street update from chat events.

This test verifies that the street correctly transitions from PREFLOP to FLOP
when chat events indicate a board change, even if vision hasn't detected the cards yet.
"""

from datetime import datetime

from holdem.types import TableState, PlayerState, Street, Card
from holdem.vision.chat_parser import GameEvent, EventSource
from holdem.vision.event_fusion import EventFuser, FusedEvent
from holdem.vision.chat_enabled_parser import apply_fused_events_to_state


class TestStreetUpdateIntegration:
    """Integration tests for street updates via chat events."""
    
    def test_preflop_to_flop_transition(self):
        """Test complete flow: PREFLOP → FLOP via chat event.
        
        Scenario:
        - Vision parses state as PREFLOP (no board cards detected yet)
        - Chat OCR detects "*** FLOP *** [Ah Kd Qs]"
        - Event fusion creates board_update event
        - apply_fused_events_to_state updates state.street to FLOP
        """
        # Step 1: Initial state from vision (PREFLOP)
        state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            board=[],  # No cards detected by vision yet
            players=[
                PlayerState(name="Player1", stack=999.0, position=0, bet_this_round=1.0),
                PlayerState(name="Player2", stack=998.0, position=1, bet_this_round=2.0)
            ],
            current_bet=2.0
        )
        
        # Step 2: Chat detects flop
        chat_event = GameEvent(
            event_type="board_update",
            street="FLOP",
            cards=[Card(rank='A', suit='h'), Card(rank='K', suit='d'), Card(rank='Q', suit='s')],
            sources=[EventSource.CHAT_OCR],
            confidence=0.9,
            timestamp=datetime.now(),
            raw_data={'chat': '*** FLOP *** [Ah Kd Qs]', 'format': 'street_marker'}
        )
        
        # Step 3: Event fusion
        fuser = EventFuser(time_window_seconds=5.0, confidence_threshold=0.7)
        fused_events = fuser.fuse_events([chat_event], [])  # Only chat events
        reliable_events = fuser.get_reliable_events(fused_events)
        
        # Step 4: Apply events to state
        assert state.street == Street.PREFLOP  # Before
        apply_fused_events_to_state(state, reliable_events)
        
        # Step 5: Verify street was updated
        assert state.street == Street.FLOP  # After ✅
        print("✓ Street successfully updated from PREFLOP to FLOP via chat event")
    
    def test_flop_to_turn_transition(self):
        """Test FLOP → TURN transition via chat event."""
        # Initial state: FLOP
        state = TableState(
            street=Street.FLOP,
            pot=50.0,
            board=[Card(rank='A', suit='h'), Card(rank='K', suit='d'), Card(rank='Q', suit='s')],
            players=[
                PlayerState(name="Player1", stack=950.0, position=0, bet_this_round=10.0),
                PlayerState(name="Player2", stack=950.0, position=1, bet_this_round=10.0)
            ],
            current_bet=10.0
        )
        
        # Chat detects turn
        chat_event = GameEvent(
            event_type="board_update",
            street="TURN",
            cards=[Card(rank='2', suit='c')],
            sources=[EventSource.CHAT_OCR],
            confidence=0.9,
            timestamp=datetime.now(),
            raw_data={'chat': '*** TURN *** [2c]', 'format': 'street_marker'}
        )
        
        # Fuse and apply
        fuser = EventFuser(time_window_seconds=5.0, confidence_threshold=0.7)
        fused_events = fuser.fuse_events([chat_event], [])
        reliable_events = fuser.get_reliable_events(fused_events)
        
        assert state.street == Street.FLOP  # Before
        apply_fused_events_to_state(state, reliable_events)
        assert state.street == Street.TURN  # After ✅
        print("✓ Street successfully updated from FLOP to TURN via chat event")
    
    def test_turn_to_river_transition(self):
        """Test TURN → RIVER transition via chat event."""
        # Initial state: TURN
        state = TableState(
            street=Street.TURN,
            pot=100.0,
            board=[
                Card(rank='A', suit='h'), 
                Card(rank='K', suit='d'), 
                Card(rank='Q', suit='s'),
                Card(rank='2', suit='c')
            ],
            players=[
                PlayerState(name="Player1", stack=900.0, position=0, bet_this_round=25.0),
                PlayerState(name="Player2", stack=900.0, position=1, bet_this_round=25.0)
            ],
            current_bet=25.0
        )
        
        # Chat detects river
        chat_event = GameEvent(
            event_type="board_update",
            street="RIVER",
            cards=[Card(rank='J', suit='h')],
            sources=[EventSource.CHAT_OCR],
            confidence=0.9,
            timestamp=datetime.now(),
            raw_data={'chat': '*** RIVER *** [Jh]', 'format': 'street_marker'}
        )
        
        # Fuse and apply
        fuser = EventFuser(time_window_seconds=5.0, confidence_threshold=0.7)
        fused_events = fuser.fuse_events([chat_event], [])
        reliable_events = fuser.get_reliable_events(fused_events)
        
        assert state.street == Street.TURN  # Before
        apply_fused_events_to_state(state, reliable_events)
        assert state.street == Street.RIVER  # After ✅
        print("✓ Street successfully updated from TURN to RIVER via chat event")
    
    def test_full_hand_progression(self):
        """Test complete hand progression: PREFLOP → FLOP → TURN → RIVER."""
        # Start with PREFLOP
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
        
        fuser = EventFuser(time_window_seconds=5.0, confidence_threshold=0.7)
        
        # PREFLOP → FLOP
        flop_event = GameEvent(
            event_type="board_update",
            street="FLOP",
            cards=[Card(rank='A', suit='h'), Card(rank='K', suit='d'), Card(rank='Q', suit='s')],
            sources=[EventSource.CHAT_OCR],
            confidence=0.9,
            timestamp=datetime.now()
        )
        fused = fuser.fuse_events([flop_event], [])
        reliable = fuser.get_reliable_events(fused)
        apply_fused_events_to_state(state, reliable)
        assert state.street == Street.FLOP
        print("  ✓ PREFLOP → FLOP")
        
        # FLOP → TURN
        turn_event = GameEvent(
            event_type="board_update",
            street="TURN",
            cards=[Card(rank='2', suit='c')],
            sources=[EventSource.CHAT_OCR],
            confidence=0.9,
            timestamp=datetime.now()
        )
        fused = fuser.fuse_events([turn_event], [])
        reliable = fuser.get_reliable_events(fused)
        apply_fused_events_to_state(state, reliable)
        assert state.street == Street.TURN
        print("  ✓ FLOP → TURN")
        
        # TURN → RIVER
        river_event = GameEvent(
            event_type="board_update",
            street="RIVER",
            cards=[Card(rank='J', suit='h')],
            sources=[EventSource.CHAT_OCR],
            confidence=0.9,
            timestamp=datetime.now()
        )
        fused = fuser.fuse_events([river_event], [])
        reliable = fuser.get_reliable_events(fused)
        apply_fused_events_to_state(state, reliable)
        assert state.street == Street.RIVER
        print("  ✓ TURN → RIVER")
        
        print("✓ Complete hand progression test passed!")


if __name__ == "__main__":
    # Run tests manually
    test = TestStreetUpdateIntegration()
    
    print("\n=== Running Street Update Integration Tests ===\n")
    
    print("Test 1: PREFLOP → FLOP transition")
    test.test_preflop_to_flop_transition()
    print()
    
    print("Test 2: FLOP → TURN transition")
    test.test_flop_to_turn_transition()
    print()
    
    print("Test 3: TURN → RIVER transition")
    test.test_turn_to_river_transition()
    print()
    
    print("Test 4: Full hand progression")
    test.test_full_hand_progression()
    print()
    
    print("=== All integration tests passed! ===\n")
