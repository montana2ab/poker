"""Tests for vision system bug fixes and improvements."""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock


from holdem.vision.ocr import OCREngine
from holdem.vision.cards import CardRecognizer
from holdem.vision.chat_parser import ChatParser, ChatLine
from holdem.vision.event_fusion import EventFuser
from holdem.types import TableState, Street


class TestCardRecognizerBugFixes:
    """Test bug fixes in CardRecognizer."""
    
    def test_recognize_cards_with_zero_cards(self):
        """Test that recognize_cards handles num_cards=0 gracefully."""
        recognizer = CardRecognizer(method="template")
        img = np.ones((100, 200, 3), dtype=np.uint8) * 255
        
        # Should not crash with division by zero
        result = recognizer.recognize_cards(img, num_cards=0)
        assert result == []
    
    def test_recognize_cards_with_negative_cards(self):
        """Test that recognize_cards handles negative num_cards gracefully."""
        recognizer = CardRecognizer(method="template")
        img = np.ones((100, 200, 3), dtype=np.uint8) * 255
        
        result = recognizer.recognize_cards(img, num_cards=-1)
        assert result == []
    
    def test_recognize_cards_with_none_image(self):
        """Test that recognize_cards handles None image gracefully."""
        recognizer = CardRecognizer(method="template")
        
        # Create an empty array to simulate None/empty image
        empty_img = np.array([])
        result = recognizer.recognize_cards(empty_img, num_cards=5)
        assert result == []
    
    def test_recognize_cards_with_valid_input(self):
        """Test that valid inputs still work correctly."""
        recognizer = CardRecognizer(method="template")
        img = np.ones((100, 200, 3), dtype=np.uint8) * 255
        
        # Should work normally with valid input
        result = recognizer.recognize_cards(img, num_cards=2)
        assert isinstance(result, list)
        assert len(result) == 2


class TestChatParserBugFixes:
    """Test bug fixes in ChatParser."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        mock = Mock(spec=OCREngine)
        mock.read_text.return_value = ""
        return mock
    
    @pytest.fixture
    def chat_parser(self, mock_ocr_engine):
        """Create a chat parser instance."""
        return ChatParser(mock_ocr_engine)
    
    def test_parse_amount_rejects_negative(self, chat_parser):
        """Test that negative amounts are rejected."""
        result = chat_parser._parse_amount("$-10")
        assert result is None
        
        result = chat_parser._parse_amount("-100.50")
        assert result is None
    
    def test_parse_amount_accepts_zero(self, chat_parser):
        """Test that zero amount is accepted."""
        result = chat_parser._parse_amount("$0")
        assert result == 0.0
        
        result = chat_parser._parse_amount("$0.00")
        assert result == 0.0
    
    def test_parse_amount_accepts_positive(self, chat_parser):
        """Test that positive amounts are accepted."""
        result = chat_parser._parse_amount("$10.50")
        assert result == 10.50
        
        result = chat_parser._parse_amount("$1,234.56")
        assert result == 1234.56
    
    def test_parse_cards_case_insensitive_suits(self, chat_parser):
        """Test that card parsing handles uppercase suits."""
        # Lowercase suits (original behavior)
        cards = chat_parser._parse_cards("Ah Kd")
        assert len(cards) == 2
        assert str(cards[0]) == "Ah"
        assert str(cards[1]) == "Kd"
        
        # Uppercase suits (should now work)
        cards = chat_parser._parse_cards("AH KD")
        assert len(cards) == 2
        assert str(cards[0]) == "Ah"
        assert str(cards[1]) == "Kd"
        
        # Mixed case suits
        cards = chat_parser._parse_cards("aH Kd Qs")
        assert len(cards) == 3
        assert str(cards[0]) == "Ah"
        assert str(cards[1]) == "Kd"
        assert str(cards[2]) == "Qs"


class TestEventFuserBugFixes:
    """Test bug fixes in EventFuser."""
    
    def test_create_vision_events_with_none_current_state(self):
        """Test that None current_state is handled gracefully."""
        fuser = EventFuser()
        
        prev_state = TableState(
            street=Street.PREFLOP,
            pot=10.0,
            board=[],
            players=[]
        )
        
        # Should not crash with None current_state
        result = fuser.create_vision_events_from_state(prev_state, None)
        assert result == []
    
    def test_create_vision_events_with_none_prev_state(self):
        """Test that None prev_state is handled gracefully."""
        fuser = EventFuser()
        
        current_state = TableState(
            street=Street.PREFLOP,
            pot=10.0,
            board=[],
            players=[]
        )
        
        # Should return empty list for first observation
        result = fuser.create_vision_events_from_state(None, current_state)
        assert result == []
    
    def test_create_vision_events_with_both_none(self):
        """Test that both None states are handled gracefully."""
        fuser = EventFuser()
        
        # Should handle gracefully
        result = fuser.create_vision_events_from_state(None, None)
        assert result == []


class TestOCREngineBugFixes:
    """Test bug fixes in OCREngine."""
    
    def test_extract_number_rejects_negative(self):
        """Test that negative numbers are rejected."""
        try:
            engine = OCREngine(backend="pytesseract")
        except Exception:
            pytest.skip("OCR backend not available")
        
        # Mock the read_text to return negative number
        engine.read_text = Mock(return_value="-100.50")
        
        result = engine.extract_number(np.zeros((10, 10)))
        assert result is None
    
    def test_extract_number_with_max_value(self):
        """Test that max_value validation works."""
        try:
            engine = OCREngine(backend="pytesseract")
        except Exception:
            pytest.skip("OCR backend not available")
        
        # Mock the read_text to return large number
        engine.read_text = Mock(return_value="999999999")
        
        # Should reject values above max_value
        result = engine.extract_number(np.zeros((10, 10)), max_value=10000.0)
        assert result is None
        
        # Should accept values below max_value
        engine.read_text = Mock(return_value="5000")
        result = engine.extract_number(np.zeros((10, 10)), max_value=10000.0)
        assert result == 5000.0
    
    def test_extract_number_accepts_zero(self):
        """Test that zero is accepted."""
        try:
            engine = OCREngine(backend="pytesseract")
        except Exception:
            pytest.skip("OCR backend not available")
        
        engine.read_text = Mock(return_value="0")
        result = engine.extract_number(np.zeros((10, 10)))
        assert result == 0.0
        
        engine.read_text = Mock(return_value="0.00")
        result = engine.extract_number(np.zeros((10, 10)))
        assert result == 0.0
    
    def test_extract_integer_with_max_value(self):
        """Test that extract_integer respects max_value."""
        try:
            engine = OCREngine(backend="pytesseract")
        except Exception:
            pytest.skip("OCR backend not available")
        
        engine.read_text = Mock(return_value="1000")
        
        # Should accept within bounds
        result = engine.extract_integer(np.zeros((10, 10)), max_value=5000)
        assert result == 1000
        
        # Should reject above bounds
        result = engine.extract_integer(np.zeros((10, 10)), max_value=500)
        assert result is None


class TestRegressionTests:
    """Tests to ensure fixes don't break existing functionality."""
    
    def test_card_recognizer_normal_operation(self):
        """Test that normal card recognition still works."""
        recognizer = CardRecognizer(method="template")
        img = np.ones((100, 350, 3), dtype=np.uint8) * 255
        
        # Should handle normal case
        result = recognizer.recognize_cards(img, num_cards=5)
        assert len(result) == 5
    
    def test_chat_parser_normal_operation(self):
        """Test that normal chat parsing still works."""
        mock_ocr = Mock()
        parser = ChatParser(mock_ocr)
        
        # Test normal parsing
        line = ChatLine(text="Player1 calls $10.50", timestamp=datetime.now())
        event = parser.parse_chat_line(line)
        
        assert event is not None
        assert event.amount == 10.50
    
    def test_event_fuser_normal_operation(self):
        """Test that normal event fusion still works."""
        fuser = EventFuser()
        
        prev_state = TableState(
            street=Street.PREFLOP,
            pot=10.0,
            board=[],
            players=[]
        )
        
        current_state = TableState(
            street=Street.FLOP,
            pot=15.0,
            board=[],
            players=[]
        )
        
        events = fuser.create_vision_events_from_state(prev_state, current_state)
        assert isinstance(events, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
