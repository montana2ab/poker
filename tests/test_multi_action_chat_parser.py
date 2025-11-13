"""Tests for multi-action chat parsing enhancements."""

import pytest
from datetime import datetime
from unittest.mock import Mock

from holdem.types import ActionType
from holdem.vision.chat_parser import ChatParser, ChatLine, EventSource
from holdem.vision.ocr import OCREngine


class TestMultiActionChatParser:
    """Test multi-action chat parsing functionality."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        mock = Mock(spec=OCREngine)
        return mock
    
    @pytest.fixture
    def chat_parser(self, mock_ocr_engine):
        """Create a chat parser instance."""
        return ChatParser(mock_ocr_engine)
    
    def test_parse_multiple_actions_single_line(self, chat_parser):
        """Test parsing multiple actions from a single line."""
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
        assert EventSource.CHAT in events[0].sources
        
        # Second event: daly43 calls 850
        assert events[1].event_type == "action"
        assert events[1].player == "daly43"
        assert events[1].action == ActionType.CALL
        assert events[1].amount == 850.0
        
        # Third event: palianica folds
        assert events[2].event_type == "action"
        assert events[2].player == "palianica"
        assert events[2].action == ActionType.FOLD
    
    def test_parse_action_with_board_dealing(self, chat_parser):
        """Test that board dealing segments are filtered out."""
        chat_line = ChatLine(
            text="Dealer: Player1 calls 100 Dealer: Dealing Flop: [Ah Kd Qs] Dealer: Player2 checks",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        # Should have 2 player actions, board dealing filtered out
        assert len(events) == 2
        
        assert events[0].player == "Player1"
        assert events[0].action == ActionType.CALL
        
        assert events[1].player == "Player2"
        assert events[1].action == ActionType.CHECK
    
    def test_filter_informational_messages(self, chat_parser):
        """Test that informational messages don't become CHECK events."""
        test_cases = [
            "it's your turn",
            "It's your turn to act",
            "waiting for Player1",
            "Please make a decision",
            "Time bank activated",
            "Player has timed out",
        ]
        
        for text in test_cases:
            chat_line = ChatLine(text=text, timestamp=datetime.now())
            events = chat_parser.parse_chat_line_multi(chat_line)
            
            # Should not create any action events
            assert len(events) == 0, f"Informational message '{text}' should not create events"
    
    def test_board_dealing_only(self, chat_parser):
        """Test that lines with only board dealing don't create player actions."""
        chat_line = ChatLine(
            text="Dealer: Dealing Flop: [Ah Kd Qs]",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        # Should not create player action events (board dealing is filtered)
        assert len(events) == 0
    
    def test_mixed_case_dealer_delimiter(self, chat_parser):
        """Test that 'Dealer:' delimiter works case-insensitively."""
        chat_line = ChatLine(
            text="dealer: Player1 bets 100 DEALER: Player2 calls 100",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 2
        assert events[0].action == ActionType.BET
        assert events[1].action == ActionType.CALL
    
    def test_single_action_format_still_works(self, chat_parser):
        """Test that single action format (no Dealer: prefix) still works."""
        chat_line = ChatLine(text="Player1 raises to 200", timestamp=datetime.now())
        event = chat_parser.parse_chat_line(chat_line)
        
        assert event is not None
        assert event.player == "Player1"
        assert event.action == ActionType.RAISE
        assert event.amount == 200.0
    
    def test_empty_segments_ignored(self, chat_parser):
        """Test that empty segments between delimiters are ignored."""
        chat_line = ChatLine(
            text="Dealer: Dealer: Player1 bets 50 Dealer: Dealer:",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        # Should have exactly 1 event (Player1 bets), empty segments ignored
        assert len(events) == 1
        assert events[0].player == "Player1"
        assert events[0].action == ActionType.BET
