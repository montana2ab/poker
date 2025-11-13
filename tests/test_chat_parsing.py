"""Tests for chat parsing and event fusion."""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from holdem.types import Card, ActionType, TableState, PlayerState, Street
from holdem.vision.chat_parser import ChatParser, ChatLine, GameEvent, EventSource
from holdem.vision.event_fusion import EventFuser, FusedEvent
from holdem.vision.ocr import OCREngine


class TestChatParser:
    """Test chat parsing functionality."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        mock = Mock(spec=OCREngine)
        return mock
    
    @pytest.fixture
    def chat_parser(self, mock_ocr_engine):
        """Create a chat parser instance."""
        return ChatParser(mock_ocr_engine)
    
    def test_parse_fold_action(self, chat_parser):
        """Test parsing fold action from chat."""
        chat_line = ChatLine(text="Player1 folds", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "action"
        assert event.player == "Player1"
        assert event.action == ActionType.FOLD
        assert EventSource.CHAT in event.sources
    
    def test_parse_check_action(self, chat_parser):
        """Test parsing check action from chat."""
        chat_line = ChatLine(text="Player2 checks", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "action"
        assert event.player == "Player2"
        assert event.action == ActionType.CHECK
    
    def test_parse_call_action(self, chat_parser):
        """Test parsing call action with amount."""
        chat_line = ChatLine(text="Player3 calls $10.50", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "action"
        assert event.player == "Player3"
        assert event.action == ActionType.CALL
        assert event.amount == 10.50
    
    def test_parse_bet_action(self, chat_parser):
        """Test parsing bet action with amount."""
        chat_line = ChatLine(text="Hero bets $25.00", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "action"
        assert event.player == "Hero"
        assert event.action == ActionType.BET
        assert event.amount == 25.00
    
    def test_parse_raise_action(self, chat_parser):
        """Test parsing raise action with amount."""
        chat_line = ChatLine(text="Player1 raises to $50", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "action"
        assert event.player == "Player1"
        assert event.action == ActionType.RAISE
        assert event.amount == 50.0
    
    def test_parse_allin_action(self, chat_parser):
        """Test parsing all-in action."""
        chat_line = ChatLine(text="Player2 is all-in", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "action"
        assert event.player == "Player2"
        assert event.action == ActionType.ALLIN
    
    def test_parse_flop(self, chat_parser):
        """Test parsing flop street change."""
        chat_line = ChatLine(text="*** FLOP *** [Ah Kd Qs]", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "street_change"
        assert event.street == "FLOP"
        assert len(event.cards) == 3
        assert str(event.cards[0]) == "Ah"
        assert str(event.cards[1]) == "Kd"
        assert str(event.cards[2]) == "Qs"
    
    def test_parse_turn(self, chat_parser):
        """Test parsing turn street change."""
        chat_line = ChatLine(text="*** TURN *** [Ah Kd Qs Jc]", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "street_change"
        assert event.street == "TURN"
        assert len(event.cards) == 4
    
    def test_parse_river(self, chat_parser):
        """Test parsing river street change."""
        chat_line = ChatLine(text="*** RIVER *** [Ah Kd Qs Jc Ts]", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "street_change"
        assert event.street == "RIVER"
        assert len(event.cards) == 5
    
    def test_parse_hole_cards(self, chat_parser):
        """Test parsing hole card deal."""
        chat_line = ChatLine(text="Dealt to Hero [As Kh]", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "card_deal"
        assert event.player == "Hero"
        assert len(event.cards) == 2
        assert str(event.cards[0]) == "As"
        assert str(event.cards[1]) == "Kh"
    
    def test_parse_showdown(self, chat_parser):
        """Test parsing showdown."""
        chat_line = ChatLine(text="Player1 shows [Ah Ac]", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "showdown"
        assert event.player == "Player1"
        assert len(event.cards) == 2
    
    def test_parse_pot_update(self, chat_parser):
        """Test parsing pot update."""
        chat_line = ChatLine(text="Pot is $125.50", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "pot_update"
        assert event.pot_amount == 125.50
    
    def test_parse_pot_win(self, chat_parser):
        """Test parsing pot win."""
        chat_line = ChatLine(text="Hero wins $200.00", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.event_type == "pot_win"
        assert event.player == "Hero"
        assert event.pot_amount == 200.00
    
    def test_parse_amount_formats(self, chat_parser):
        """Test parsing various amount formats."""
        # With dollar sign
        assert chat_parser._parse_amount("$100.50") == 100.50
        
        # With comma thousands separator
        assert chat_parser._parse_amount("1,234.56") == 1234.56
        
        # Without currency symbol
        assert chat_parser._parse_amount("50.25") == 50.25
        
        # Invalid input
        assert chat_parser._parse_amount("abc") is None
        assert chat_parser._parse_amount("") is None
    
    def test_parse_cards(self, chat_parser):
        """Test parsing card strings."""
        # Space-separated
        cards = chat_parser._parse_cards("Ah Kd Qs")
        assert len(cards) == 3
        assert str(cards[0]) == "Ah"
        assert str(cards[1]) == "Kd"
        assert str(cards[2]) == "Qs"
        
        # Comma-separated
        cards = chat_parser._parse_cards("As, Kh")
        assert len(cards) == 2
        
        # Mixed case
        cards = chat_parser._parse_cards("aH kD")
        assert len(cards) == 2
        assert str(cards[0]) == "Ah"
        assert str(cards[1]) == "Kd"
    
    def test_parse_multi_action_line(self, chat_parser):
        """Test parsing multiple actions from a single line (Case 1)."""
        # Example: "Dealer: Rapyxa bets 850 Dealer: daly43 calls 850 Dealer: palianica folds"
        chat_line = ChatLine(
            text="Dealer: Rapyxa bets 850 Dealer: daly43 calls 850 Dealer: palianica folds",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 3
        
        # First event: Rapyxa bets 850
        assert events[0].event_type == "action"
        assert events[0].player == "Rapyxa"
        assert events[0].action == ActionType.BET
        assert events[0].amount == 850.0
        
        # Second event: daly43 calls 850
        assert events[1].event_type == "action"
        assert events[1].player == "daly43"
        assert events[1].action == ActionType.CALL
        assert events[1].amount == 850.0
        
        # Third event: palianica folds
        assert events[2].event_type == "action"
        assert events[2].player == "palianica"
        assert events[2].action == ActionType.FOLD
        assert events[2].amount is None
    
    def test_parse_multi_action_with_board_dealing(self, chat_parser):
        """Test parsing actions mixed with board dealing (Case 2)."""
        # Example: "Dealer: hilanderJOjo calls 639 Dealer: Dealing River: [Jc] Dealer: Rapyxa checks"
        chat_line = ChatLine(
            text="Dealer: hilanderJOjo calls 639 Dealer: Dealing River: [Jc] Dealer: Rapyxa checks",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        # Should only extract action events, not board dealing
        assert len(events) == 2
        
        # First event: hilanderJOjo calls 639
        assert events[0].event_type == "action"
        assert events[0].player == "hilanderJOjo"
        assert events[0].action == ActionType.CALL
        assert events[0].amount == 639.0
        
        # Second event: Rapyxa checks
        assert events[1].event_type == "action"
        assert events[1].player == "Rapyxa"
        assert events[1].action == ActionType.CHECK
        assert events[1].amount is None
    
    def test_parse_board_dealing_only(self, chat_parser):
        """Test parsing line with only board dealing (Case 3)."""
        # Example: "Dealer: Dealing Flop: [Ac Jd 9d]"
        chat_line = ChatLine(
            text="Dealer: Dealing Flop: [Ac Jd 9d]",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        # Should return no action events
        assert len(events) == 0
    
    def test_parse_single_action_backward_compatibility(self, chat_parser):
        """Test backward compatibility with single action lines (Case 4)."""
        # Example: "Dealer: palianica folds"
        chat_line = ChatLine(
            text="Dealer: palianica folds",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        assert events[0].event_type == "action"
        assert events[0].player == "palianica"
        assert events[0].action == ActionType.FOLD
        
        # Also test old API
        event = chat_parser.parse_chat_line(chat_line)
        assert event is not None
        assert event.action == ActionType.FOLD
    
    def test_parse_leave_table_action(self, chat_parser):
        """Test parsing 'leaves the table' action."""
        chat_line = ChatLine(
            text="Dealer: palianica leaves the table",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        assert events[0].event_type == "action"
        assert events[0].player == "palianica"
        assert events[0].action == ActionType.FOLD  # Leave is treated as fold
        assert events[0].raw_data.get('original_action') == 'leave'
    
    def test_parse_multi_action_with_raises(self, chat_parser):
        """Test parsing multiple actions including raises."""
        chat_line = ChatLine(
            text="Dealer: Player1 raises to 100 Dealer: Player2 calls 100 Dealer: Player3 folds",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 3
        
        assert events[0].action == ActionType.RAISE
        assert events[0].amount == 100.0
        
        assert events[1].action == ActionType.CALL
        assert events[1].amount == 100.0
        
        assert events[2].action == ActionType.FOLD
    
    def test_parse_non_dealer_format(self, chat_parser):
        """Test parsing chat lines without 'Dealer:' prefix."""
        chat_line = ChatLine(text="Player1 folds", timestamp=datetime.now())
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        assert events[0].player == "Player1"
        assert events[0].action == ActionType.FOLD


class TestEventFusion:
    """Test event fusion functionality."""
    
    @pytest.fixture
    def event_fuser(self):
        """Create an event fuser instance."""
        return EventFuser(time_window_seconds=5.0, confidence_threshold=0.5)
    
    def test_match_same_action(self, event_fuser):
        """Test matching identical actions from different sources."""
        now = datetime.now()
        
        chat_event = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.FOLD,
            sources=[EventSource.CHAT],
            timestamp=now
        )
        
        vision_event = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.FOLD,
            sources=[EventSource.VISION],
            timestamp=now
        )
        
        assert event_fuser._events_match(chat_event, vision_event)
    
    def test_match_different_actions(self, event_fuser):
        """Test that different actions don't match."""
        now = datetime.now()
        
        event1 = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.FOLD,
            sources=[EventSource.CHAT],
            timestamp=now
        )
        
        event2 = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.CALL,
            sources=[EventSource.VISION],
            timestamp=now
        )
        
        assert not event_fuser._events_match(event1, event2)
    
    def test_match_time_window(self, event_fuser):
        """Test time window matching."""
        now = datetime.now()
        
        event1 = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.FOLD,
            sources=[EventSource.CHAT],
            timestamp=now
        )
        
        # Within time window
        event2 = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.FOLD,
            sources=[EventSource.VISION],
            timestamp=now + timedelta(seconds=2)
        )
        assert event_fuser._events_match(event1, event2)
        
        # Outside time window
        event3 = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.FOLD,
            sources=[EventSource.VISION],
            timestamp=now + timedelta(seconds=10)
        )
        assert not event_fuser._events_match(event1, event3)
    
    def test_fuse_confirmed_event(self, event_fuser):
        """Test fusion of events confirmed by multiple sources."""
        now = datetime.now()
        
        chat_event = GameEvent(
            event_type="action",
            player="Hero",
            action=ActionType.BET,
            amount=25.0,
            sources=[EventSource.CHAT],
            timestamp=now
        )
        
        vision_event = GameEvent(
            event_type="action",
            player="Hero",
            action=ActionType.BET,
            amount=24.5,  # Slightly different due to OCR
            sources=[EventSource.VISION],
            timestamp=now + timedelta(seconds=1)
        )
        
        fused_events = event_fuser.fuse_events([chat_event], [vision_event])
        
        assert len(fused_events) == 1
        fused = fused_events[0]
        assert fused.is_multi_source()
        assert fused.confidence >= 0.9
        assert EventSource.CHAT in fused.sources
        assert EventSource.VISION in fused.sources
        # Should prefer chat amount (more precise)
        assert fused.amount == 25.0
    
    def test_fuse_single_source_event(self, event_fuser):
        """Test single-source event has lower confidence."""
        chat_event = GameEvent(
            event_type="action",
            player="Player1",
            action=ActionType.FOLD,
            sources=[EventSource.CHAT],
            timestamp=datetime.now()
        )
        
        fused_events = event_fuser.fuse_events([chat_event], [])
        
        assert len(fused_events) == 1
        fused = fused_events[0]
        assert not fused.is_multi_source()
        assert fused.confidence < 0.9
    
    def test_create_vision_events_street_change(self, event_fuser):
        """Test creating vision events from street change."""
        prev_state = TableState(
            street=Street.PREFLOP,
            pot=10.0,
            board=[],
            players=[]
        )
        
        current_state = TableState(
            street=Street.FLOP,
            pot=15.0,
            board=[
                Card(rank='A', suit='h'),
                Card(rank='K', suit='d'),
                Card(rank='Q', suit='s')
            ],
            players=[]
        )
        
        events = event_fuser.create_vision_events_from_state(prev_state, current_state)
        
        # Should have street change and pot update events
        assert len(events) >= 1
        street_events = [e for e in events if e.event_type == "street_change"]
        assert len(street_events) == 1
        assert street_events[0].street == "FLOP"
        assert len(street_events[0].cards) == 3
    
    def test_create_vision_events_action(self, event_fuser):
        """Test creating vision events from player actions."""
        player1_prev = PlayerState(name="Player1", stack=100.0, bet_this_round=0.0, folded=False)
        player1_curr = PlayerState(name="Player1", stack=100.0, bet_this_round=0.0, folded=True)
        
        prev_state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[player1_prev],
            current_bet=5.0
        )
        
        current_state = TableState(
            street=Street.FLOP,
            pot=10.0,
            players=[player1_curr],
            current_bet=5.0
        )
        
        events = event_fuser.create_vision_events_from_state(prev_state, current_state)
        
        # Should detect fold
        action_events = [e for e in events if e.event_type == "action"]
        assert len(action_events) >= 1
        fold_events = [e for e in action_events if e.action == ActionType.FOLD]
        assert len(fold_events) == 1
        assert fold_events[0].player == "Player1"
    
    def test_merge_amounts_prefer_chat(self, event_fuser):
        """Test that chat amounts are preferred over vision."""
        chat_event = GameEvent(
            event_type="action",
            amount=25.0,
            sources=[EventSource.CHAT]
        )
        
        vision_event = GameEvent(
            event_type="action",
            amount=24.5,
            sources=[EventSource.VISION]
        )
        
        merged = event_fuser._merge_amounts([chat_event, vision_event])
        assert merged == 25.0  # Should prefer chat
    
    def test_merge_cards_prefer_chat(self, event_fuser):
        """Test that chat cards are preferred over vision."""
        chat_cards = [Card(rank='A', suit='h'), Card(rank='K', suit='d')]
        vision_cards = [Card(rank='A', suit='h'), Card(rank='Q', suit='d')]
        
        chat_event = GameEvent(
            event_type="card_deal",
            cards=chat_cards,
            sources=[EventSource.CHAT]
        )
        
        vision_event = GameEvent(
            event_type="card_deal",
            cards=vision_cards,
            sources=[EventSource.VISION]
        )
        
        merged = event_fuser._merge_cards([chat_event, vision_event])
        assert len(merged) == 2
        assert merged == chat_cards  # Should prefer chat
    
    def test_calculate_confidence_multi_source(self, event_fuser):
        """Test confidence calculation for multi-source events."""
        chat_event = GameEvent(
            event_type="action",
            amount=25.0,
            sources=[EventSource.CHAT]
        )
        
        vision_event = GameEvent(
            event_type="action",
            amount=25.0,
            sources=[EventSource.VISION]
        )
        
        confidence = event_fuser._calculate_confidence([chat_event, vision_event])
        assert confidence >= 0.9  # High confidence for multi-source
    
    def test_calculate_confidence_inconsistent_amounts(self, event_fuser):
        """Test confidence calculation with inconsistent amounts."""
        event1 = GameEvent(
            event_type="action",
            amount=25.0,
            sources=[EventSource.CHAT]
        )
        
        event2 = GameEvent(
            event_type="action",
            amount=50.0,  # Very different
            sources=[EventSource.VISION]
        )
        
        confidence = event_fuser._calculate_confidence([event1, event2])
        assert confidence < 0.95  # Should be lower due to inconsistency
    
    def test_get_reliable_events(self, event_fuser):
        """Test filtering for reliable events."""
        high_conf = FusedEvent(
            event_type="action",
            confidence=0.9,
            sources=[EventSource.CHAT, EventSource.VISION]
        )
        
        low_conf = FusedEvent(
            event_type="action",
            confidence=0.3,
            sources=[EventSource.VISION]
        )
        
        reliable = event_fuser.get_reliable_events([high_conf, low_conf])
        assert len(reliable) == 1
        assert reliable[0].confidence >= event_fuser.confidence_threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
