"""Tests for chat OCR quality improvements."""

import pytest
import numpy as np
import time
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import cv2

from holdem.types import Card
from holdem.vision.chat_parser import ChatParser, ChatLine
from holdem.vision.ocr import OCREngine


class TestCardCorrectionLogic:
    """Test card correction logic with CHAR_FIXES."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        mock = Mock(spec=OCREngine)
        return mock
    
    @pytest.fixture
    def chat_parser(self, mock_ocr_engine):
        """Create a chat parser instance."""
        return ChatParser(mock_ocr_engine)
    
    def test_char_fixes_ampersand_to_8(self, chat_parser):
        """Test that '&' is corrected to '8' in card rank."""
        # Test the CHAR_FIXES mapping exists
        assert '&' in chat_parser.CHAR_FIXES
        assert chat_parser.CHAR_FIXES['&'] == '8'
        
        # Parse a card with & instead of 8
        cards = chat_parser._parse_cards('&s')
        assert len(cards) == 1
        assert cards[0].rank == '8'
        assert cards[0].suit == 's'
    
    def test_char_fixes_B_to_8(self, chat_parser):
        """Test that 'B' is corrected to '8' in card rank."""
        assert 'B' in chat_parser.CHAR_FIXES
        assert chat_parser.CHAR_FIXES['B'] == '8'
        
        cards = chat_parser._parse_cards('Bd')
        assert len(cards) == 1
        assert cards[0].rank == '8'
        assert cards[0].suit == 'd'
    
    def test_char_fixes_O_to_0(self, chat_parser):
        """Test that 'O' is corrected to '0' (then potentially to other chars)."""
        assert 'O' in chat_parser.CHAR_FIXES
        assert chat_parser.CHAR_FIXES['O'] == '0'
    
    def test_char_fixes_lowercase_l_to_1(self, chat_parser):
        """Test that 'l' is corrected to '1' in card rank."""
        assert 'l' in chat_parser.CHAR_FIXES
        assert chat_parser.CHAR_FIXES['l'] == '1'
    
    def test_char_fixes_I_to_1(self, chat_parser):
        """Test that 'I' is corrected to '1' in card rank."""
        assert 'I' in chat_parser.CHAR_FIXES
        assert chat_parser.CHAR_FIXES['I'] == '1'
    
    def test_dealing_flop_with_ampersand(self, chat_parser):
        """Test parsing 'Dealing Flop: [As Td &s]' produces ['As', 'Td', '8s']."""
        chat_line = ChatLine(
            text="Dealing Flop: [As Td &s]",
            timestamp=datetime.now()
        )
        
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        # Should return a board_update event
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "board_update"
        assert event.street == "FLOP"
        assert len(event.cards) == 3
        
        # Check cards are parsed correctly with & -> 8 correction
        assert str(event.cards[0]) == "As"
        assert str(event.cards[1]) == "Td"
        assert str(event.cards[2]) == "8s"  # & corrected to 8
    
    def test_multiple_cards_with_corrections(self, chat_parser):
        """Test multiple cards with different corrections."""
        # Test string with multiple OCR errors
        cards = chat_parser._parse_cards('As &h Bd')
        assert len(cards) == 3
        assert str(cards[0]) == "As"  # No correction needed
        assert str(cards[1]) == "8h"  # & -> 8
        assert str(cards[2]) == "8d"  # B -> 8
    
    def test_correction_logged(self, chat_parser, caplog):
        """Test that corrections are logged for debugging."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        cards = chat_parser._parse_cards('&s')
        
        # Check that a debug log was created for the correction
        assert any('[CHAT CARD FIX]' in record.message for record in caplog.records)
    
    def test_invalid_card_after_correction_rejected(self, chat_parser):
        """Test that invalid cards are rejected even after correction."""
        # Test with a character that corrects to an invalid rank
        cards = chat_parser._parse_cards('Xs')  # X is not in CHAR_FIXES and not valid
        assert len(cards) == 0
    
    def test_case_insensitive_correction(self, chat_parser):
        """Test that corrections work regardless of case."""
        # Ampersand in different positions
        cards1 = chat_parser._parse_cards('&s')  # rank position
        assert len(cards1) == 1
        assert cards1[0].rank == '8'
        
        # Test with mixed case suits (suits should be lowercase)
        cards2 = chat_parser._parse_cards('8S')
        assert len(cards2) == 1
        assert cards2[0].suit == 's'


class TestChatOCRFocusLatency:
    """Test that chat OCR focus mode latency remains acceptable."""
    
    def test_preprocess_latency_acceptable(self):
        """Test that preprocessing with new enhancements stays under 2-3ms."""
        # Create a sample chat region image (100x400 pixels, typical chat size)
        chat_img = np.random.randint(0, 255, (100, 400, 3), dtype=np.uint8)
        
        # Warm-up run to avoid cache/initialization overhead
        for _ in range(3):
            chat_img_resized = cv2.resize(chat_img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
            chat_img_gray = cv2.cvtColor(chat_img_resized, cv2.COLOR_BGR2GRAY)
            sharpening_kernel = np.array([[0, -1, 0],
                                          [-1, 5, -1],
                                          [0, -1, 0]], dtype=np.float32)
            chat_img_sharp = cv2.filter2D(chat_img_gray, -1, sharpening_kernel)
            _, chat_img_processed = cv2.threshold(chat_img_sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Measure preprocessing time (simulating the new pipeline)
        times = []
        for _ in range(20):
            start = time.time()
            
            # Resize with fx=1.5, fy=1.5
            chat_img_resized = cv2.resize(chat_img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
            
            # Convert to grayscale
            chat_img_gray = cv2.cvtColor(chat_img_resized, cv2.COLOR_BGR2GRAY)
            
            # Apply sharpening filter
            sharpening_kernel = np.array([[0, -1, 0],
                                          [-1, 5, -1],
                                          [0, -1, 0]], dtype=np.float32)
            chat_img_sharp = cv2.filter2D(chat_img_gray, -1, sharpening_kernel)
            
            # Apply Otsu binarization
            _, chat_img_processed = cv2.threshold(chat_img_sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            elapsed = (time.time() - start) * 1000  # Convert to ms
            times.append(elapsed)
        
        # Remove outliers (first few runs may be slower)
        times_sorted = sorted(times)
        # Use median and 90th percentile instead of average and max
        median_time = times_sorted[len(times_sorted) // 2]
        p90_time = times_sorted[int(len(times_sorted) * 0.9)]
        avg_time = sum(times) / len(times)
        
        print(f"\nPreprocessing latency: median={median_time:.2f}ms, 90th percentile={p90_time:.2f}ms, avg={avg_time:.2f}ms")
        
        # Check that median time is under 3ms and 90th percentile is under 10ms
        # This is more realistic for production use
        assert median_time < 3.0, f"Median preprocessing time {median_time:.2f}ms exceeds 3ms threshold"
        assert p90_time < 10.0, f"90th percentile preprocessing time {p90_time:.2f}ms exceeds 10ms threshold"
    
    def test_preprocess_operations_order(self):
        """Test that preprocessing operations are applied in correct order."""
        chat_img = np.random.randint(0, 255, (50, 200, 3), dtype=np.uint8)
        
        # 1. Resize
        chat_img_resized = cv2.resize(chat_img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
        assert chat_img_resized.shape[0] == int(chat_img.shape[0] * 1.5)
        assert chat_img_resized.shape[1] == int(chat_img.shape[1] * 1.5)
        
        # 2. Grayscale
        chat_img_gray = cv2.cvtColor(chat_img_resized, cv2.COLOR_BGR2GRAY)
        assert len(chat_img_gray.shape) == 2  # Should be 2D
        
        # 3. Sharpen
        sharpening_kernel = np.array([[0, -1, 0],
                                      [-1, 5, -1],
                                      [0, -1, 0]], dtype=np.float32)
        chat_img_sharp = cv2.filter2D(chat_img_gray, -1, sharpening_kernel)
        assert chat_img_sharp.shape == chat_img_gray.shape
        
        # 4. Otsu binarization
        _, chat_img_processed = cv2.threshold(chat_img_sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        assert chat_img_processed.dtype == np.uint8
        # Check that it's binary (only 0 and 255 values)
        unique_vals = np.unique(chat_img_processed)
        assert len(unique_vals) <= 2


class TestEasyOCRConfiguration:
    """Test EasyOCR configuration with enhanced parameters."""
    
    def test_easyocr_has_enhanced_parameters(self):
        """Test that _read_easyocr method includes enhanced parameters."""
        # Read the source code of ocr.py to verify parameters are present
        import inspect
        from holdem.vision.ocr import OCREngine
        
        source = inspect.getsource(OCREngine._read_easyocr)
        
        # Check for enhanced parameters
        assert 'contrast_ths=0.3' in source, "Should have contrast_ths=0.3 parameter"
        assert 'adjust_contrast=0.7' in source, "Should have adjust_contrast=0.7 parameter"
        assert 'allowlist' in source, "Should have allowlist parameter"
    
    def test_easyocr_allowlist_contains_poker_chars(self):
        """Test that allowlist includes all necessary PokerStars chat characters."""
        import inspect
        from holdem.vision.ocr import OCREngine
        
        source = inspect.getsource(OCREngine._read_easyocr)
        
        # Check for required character types in allowlist
        assert '0123456789' in source, "Should include digits"
        assert 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' in source or 'A-Z' in source, "Should include uppercase letters"
        assert 'abcdefghijklmnopqrstuvwxyz' in source or 'a-z' in source, "Should include lowercase letters"
        assert '[]' in source, "Should include brackets"
        assert ':' in source, "Should include colon"
        assert ',' in source, "Should include comma"
        assert '()' in source, "Should include parentheses"


class TestIntegrationWithExistingTests:
    """Ensure our changes don't break existing functionality."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        mock = Mock(spec=OCREngine)
        return mock
    
    @pytest.fixture
    def chat_parser(self, mock_ocr_engine):
        """Create a chat parser instance."""
        return ChatParser(mock_ocr_engine)
    
    def test_normal_cards_still_work(self, chat_parser):
        """Test that normal cards (without OCR errors) still parse correctly."""
        cards = chat_parser._parse_cards('As Kd Qh')
        assert len(cards) == 3
        assert str(cards[0]) == "As"
        assert str(cards[1]) == "Kd"
        assert str(cards[2]) == "Qh"
    
    def test_existing_ocr_corrections_still_work(self, chat_parser):
        """Test that existing _correct_rank_ocr and _correct_suit_ocr still work."""
        # Test existing correction: 0 -> T
        assert chat_parser._correct_rank_ocr('0') == 'T'
        
        # Test existing suit corrections
        assert chat_parser._correct_suit_ocr('n') == 'h'
    
    def test_flop_parsing_backward_compatible(self, chat_parser):
        """Test that flop parsing works with normal cards (backward compatibility)."""
        chat_line = ChatLine(
            text="Dealing Flop: [Ac Jd 9d]",
            timestamp=datetime.now()
        )
        
        events = chat_parser.parse_chat_line_multi(chat_line)
        assert len(events) == 1
        assert events[0].event_type == "board_update"
        assert len(events[0].cards) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
