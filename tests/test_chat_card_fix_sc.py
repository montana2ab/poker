"""Tests for fix_chat_card function with S->5 correction."""

import pytest
from unittest.mock import Mock
from datetime import datetime

from holdem.vision.chat_parser import ChatParser, ChatLine
from holdem.vision.ocr import OCREngine


class TestFixChatCardSCorrection:
    """Test that 'S' is corrected to '5' (not '8') in chat board cards."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        return Mock(spec=OCREngine)
    
    @pytest.fixture
    def chat_parser(self, mock_ocr_engine):
        """Create a chat parser instance."""
        return ChatParser(mock_ocr_engine)
    
    def test_sc_corrects_to_5c_not_8c(self, chat_parser):
        """Test that 'Sc' is corrected to '5c' (not '8c')."""
        result = chat_parser.fix_chat_card('Sc')
        assert result == '5c', f"Expected '5c' but got '{result}'"
    
    def test_lowercase_sc_corrects_to_5c(self, chat_parser):
        """Test that 'sc' (lowercase) is also corrected to '5c'."""
        result = chat_parser.fix_chat_card('sc')
        assert result == '5c', f"Expected '5c' but got '{result}'"
    
    def test_dollar_c_corrects_to_5c(self, chat_parser):
        """Test that '$c' is corrected to '5c'."""
        result = chat_parser.fix_chat_card('$c')
        assert result == '5c', f"Expected '5c' but got '{result}'"
    
    def test_s_with_all_suits(self, chat_parser):
        """Test that 'S' corrects to '5' with all suits."""
        assert chat_parser.fix_chat_card('Sc') == '5c'
        assert chat_parser.fix_chat_card('Sd') == '5d'
        assert chat_parser.fix_chat_card('Sh') == '5h'
        assert chat_parser.fix_chat_card('Ss') == '5s'
    
    def test_valid_5c_unchanged(self, chat_parser):
        """Test that valid '5c' is returned unchanged."""
        result = chat_parser.fix_chat_card('5c')
        assert result == '5c'
    
    def test_valid_8c_unchanged(self, chat_parser):
        """Test that valid '8c' is returned unchanged."""
        result = chat_parser.fix_chat_card('8c')
        assert result == '8c'
    
    def test_dealing_flop_with_sc(self, chat_parser):
        """Test parsing 'Dealing Flop: [Sc 9h Kd]' produces ['5c', '9h', 'Kd']."""
        chat_line = ChatLine(
            text="Dealing Flop: [Sc 9h Kd]",
            timestamp=datetime.now()
        )
        
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "board_update"
        assert event.street == "FLOP"
        assert len(event.cards) == 3
        
        # Check cards are parsed correctly with Sc -> 5c correction
        cards_str = [str(c) for c in event.cards]
        assert cards_str == ['5c', '9h', 'Kd'], f"Expected ['5c', '9h', 'Kd'] but got {cards_str}"
    
    def test_dealing_river_sc(self, chat_parser):
        """Test parsing 'Dealing River: [Sc]' produces ['5c']."""
        chat_line = ChatLine(
            text="Dealing River: [Sc]",
            timestamp=datetime.now()
        )
        
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "board_update"
        assert event.street == "RIVER"
        assert len(event.cards) == 1
        
        # Check card is corrected from Sc to 5c
        assert str(event.cards[0]) == "5c"
    
    def test_multiple_s_cards(self, chat_parser):
        """Test parsing multiple cards with 'S' -> '5' correction."""
        chat_line = ChatLine(
            text="Dealing Flop: [Sc Sd Sh]",
            timestamp=datetime.now()
        )
        
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        event = events[0]
        cards_str = [str(c) for c in event.cards]
        assert cards_str == ['5c', '5d', '5h']
    
    def test_fallback_to_general_fix_card(self, chat_parser):
        """Test that general fix_card logic is used for non-S corrections."""
        # 'B' should still be corrected to '8' using fallback logic
        result = chat_parser.fix_chat_card('Bd')
        assert result == '8d', f"Expected '8d' but got '{result}'"
        
        # 'Z' should still be corrected to '7' using fallback logic
        result = chat_parser.fix_chat_card('Zh')
        assert result == '7h', f"Expected '7h' but got '{result}'"
    
    def test_logging_on_correction(self, chat_parser, caplog):
        """Test that corrections are logged with [CHAT CARD FIX]."""
        import logging
        caplog.set_level(logging.INFO)
        
        result = chat_parser.fix_chat_card('Sc')
        
        # Check that a log was created for the correction
        assert any('[CHAT CARD FIX]' in record.message for record in caplog.records)
        assert any("Accepted corrected card '5c' (original: 'Sc')" in record.message 
                   for record in caplog.records)
    
    def test_no_logging_for_valid_cards(self, chat_parser, caplog):
        """Test that no correction log is generated for already valid cards."""
        import logging
        caplog.set_level(logging.INFO)
        
        result = chat_parser.fix_chat_card('5c')
        
        # Should not log correction for already valid card
        correction_logs = [r for r in caplog.records if '[CHAT CARD FIX]' in r.message and 'Accepted' in r.message]
        assert len(correction_logs) == 0


class TestBackwardCompatibility:
    """Ensure fix_chat_card doesn't break existing functionality."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        return Mock(spec=OCREngine)
    
    @pytest.fixture
    def chat_parser(self, mock_ocr_engine):
        """Create a chat parser instance."""
        return ChatParser(mock_ocr_engine)
    
    def test_all_valid_cards_still_work(self, chat_parser):
        """Test that all valid cards are recognized."""
        valid_cards = [
            'As', 'Kh', 'Qd', 'Jc', 'Ts',
            '9h', '8d', '7c', '6s', '5h',
            '4d', '3c', '2s', 'Ah', 'Kd'
        ]
        
        for card in valid_cards:
            result = chat_parser.fix_chat_card(card)
            assert result == card, f"Valid card '{card}' was changed to '{result}'"
    
    def test_existing_corrections_still_work(self, chat_parser):
        """Test that existing correction logic still works."""
        # Test some existing corrections
        test_cases = [
            ('Bd', '8d'),  # B -> 8
            ('&s', '8s'),  # & -> 8
            ('0s', 'Ts'),  # 0 -> T
            ('Zh', '7h'),  # Z -> 7
            ('Os', 'Qs'),  # O -> Q
        ]
        
        for input_card, expected in test_cases:
            result = chat_parser.fix_chat_card(input_card)
            assert result == expected, f"Expected '{expected}' for '{input_card}' but got '{result}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
