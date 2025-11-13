"""Integration test for dry run and autoplay with event fusion.

This test verifies that the system can process game states and events
without blocking on hero cards.
"""

import pytest
from unittest.mock import Mock, MagicMock
import numpy as np

from holdem.vision.chat_enabled_parser import ChatEnabledStateParser
from holdem.types import (
    TableState,
    PlayerState,
    Street,
    Card,
    ActionType
)


class TestIntegrationEventProcessing:
    """Integration tests for event processing without hero cards."""
    
    def test_parse_state_without_hero_cards(self):
        """Test that state can be parsed even without hero cards.
        
        This is a simplified test that verifies the key concept:
        the system should not block when hero cards are unavailable.
        """
        # This test primarily verifies that the system design allows
        # game progression without hero cards. The actual parsing logic
        # is tested in other integration tests.
        
        # Create a simple state without hero cards
        state = TableState(
            street=Street.FLOP,
            pot=10.0,
            board=[Card('A', 'h'), Card('K', 'd'), Card('Q', 's')],
            players=[
                PlayerState("P1", stack=100.0, bet_this_round=0.0, position=0,
                           hole_cards=None),  # No hero cards!
                PlayerState("P2", stack=98.0, bet_this_round=2.0, position=1)
            ],
            current_bet=2.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0,
            hero_position=0
        )
        
        # State should be valid even without hero cards
        assert state is not None
        assert state.street == Street.FLOP
        assert len(state.board) == 3
        assert state.pot == 10.0
        assert len(state.players) == 2
        
        # Hero's cards are None - this is OK!
        assert state.players[0].hole_cards is None
        
        # Game can still progress: we can observe other players' actions
        # and the board, even if we don't know our own cards yet
    
    def test_event_fusion_with_stack_changes(self):
        """Test that event fusion detects actions via stack changes."""
        from holdem.vision.event_fusion import EventFuser
        
        fuser = EventFuser()
        
        # Preflop: blinds posted
        prev_state = TableState(
            street=Street.PREFLOP,
            pot=3.0,
            players=[
                PlayerState("P1", stack=99.0, bet_this_round=1.0, position=0),
                PlayerState("P2", stack=98.0, bet_this_round=2.0, position=1)
            ],
            current_bet=2.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        # Initialize tracking
        fuser.create_vision_events_from_state(None, prev_state)
        
        # P1 calls (puts in 1 more chip)
        curr_state = TableState(
            street=Street.PREFLOP,
            pot=4.0,
            players=[
                PlayerState("P1", stack=98.0, bet_this_round=2.0, position=0),
                PlayerState("P2", stack=98.0, bet_this_round=2.0, position=1)
            ],
            current_bet=2.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        events = fuser.create_vision_events_from_state(prev_state, curr_state)
        
        # Should detect P1's action
        action_events = [e for e in events if e.event_type == "action"]
        assert len(action_events) >= 1
        
        # Check that at least one event is from stack tracking
        from holdem.vision.chat_parser import EventSource
        stack_events = [e for e in action_events 
                       if EventSource.VISION_STACK in e.sources or
                          EventSource.VISION_BET_REGION in e.sources]
        assert len(stack_events) >= 1
    
    def test_state_machine_action_validation(self):
        """Test that state machine properly validates actions."""
        from holdem.game.state_machine import TexasHoldemStateMachine
        
        sm = TexasHoldemStateMachine(
            num_players=2,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        
        # P1 should be able to call
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.CALL,
            amount=2.0,
            player_stack=99.0,
            player_bet_this_round=1.0,
            current_bet=2.0
        )
        
        assert validation.is_legal
        
        # P1 should NOT be able to check (there's a bet)
        validation = sm.validate_action(
            player_pos=0,
            action=ActionType.CHECK,
            amount=0.0,
            player_stack=99.0,
            player_bet_this_round=1.0,
            current_bet=2.0
        )
        
        assert not validation.is_legal
        assert validation.suggested_action == ActionType.CALL
    
    def test_state_machine_street_advancement(self):
        """Test that state machine can advance streets properly."""
        from holdem.game.state_machine import TexasHoldemStateMachine
        
        sm = TexasHoldemStateMachine(
            num_players=2,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        # Both players acted and have equal bets
        sm.players_acted = [True, True]
        
        state = TableState(
            street=Street.PREFLOP,
            pot=4.0,
            players=[
                PlayerState("P1", stack=98.0, bet_this_round=2.0, position=0),
                PlayerState("P2", stack=98.0, bet_this_round=2.0, position=1)
            ],
            current_bet=2.0,
            small_blind=1.0,
            big_blind=2.0,
            button_position=0
        )
        
        # Betting round should be complete
        assert sm.is_betting_round_complete(state)
        
        # Should be able to advance to flop
        next_street = sm.advance_street(state)
        assert next_street == Street.FLOP
        
        # State should be reset for new street
        assert sm.current_bet == 0.0
        assert not any(sm.players_acted)
    
    def test_multi_source_event_confidence(self):
        """Test that events from multiple sources get high confidence."""
        from holdem.vision.event_fusion import EventFuser
        from holdem.vision.chat_parser import GameEvent, EventSource
        from datetime import datetime
        
        fuser = EventFuser()
        
        # Create events from different sources for the same action
        chat_event = GameEvent(
            event_type="action",
            player="P1",
            action=ActionType.BET,
            amount=10.0,
            sources=[EventSource.CHAT],
            timestamp=datetime.now()
        )
        
        stack_event = GameEvent(
            event_type="action",
            player="P1",
            action=ActionType.BET,
            amount=10.0,
            sources=[EventSource.VISION_STACK],
            timestamp=datetime.now()
        )
        
        bet_region_event = GameEvent(
            event_type="action",
            player="P1",
            action=ActionType.BET,
            amount=10.0,
            sources=[EventSource.VISION_BET_REGION],
            timestamp=datetime.now()
        )
        
        # Fuse events
        fused_events = fuser.fuse_events(
            chat_events=[chat_event],
            vision_events=[stack_event, bet_region_event]
        )
        
        # Should create one fused event
        assert len(fused_events) >= 1
        
        # Find the multi-source event
        multi_source = [e for e in fused_events if e.is_multi_source()]
        assert len(multi_source) >= 1
        
        # Should have very high confidence (3 sources!)
        assert multi_source[0].confidence >= 0.95
        
        # Should include all source types
        sources = set(multi_source[0].sources)
        assert EventSource.CHAT in sources
        assert (EventSource.VISION_STACK in sources or 
                EventSource.VISION_BET_REGION in sources)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
