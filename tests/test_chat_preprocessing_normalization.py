"""Tests for chat preprocessing and normalization functions."""

import pytest
import numpy as np
import time
from PIL import Image
from unittest.mock import Mock
from datetime import datetime

from holdem.vision.chat_parser import (
    ChatParser, 
    preprocess_chat_image,
    normalize_dealer_line,
    correct_action_word,
    ChatLine
)
from holdem.vision.ocr import OCREngine


class TestPreprocessChatImage:
    """Test the preprocess_chat_image function."""
    
    def test_preprocess_with_pil_image(self):
        """Test preprocessing with PIL Image input."""
        # Create a sample chat image (100x400 pixels, typical chat size)
        img_array = np.random.randint(0, 255, (100, 400, 3), dtype=np.uint8)
        pil_img = Image.fromarray(img_array)
        
        result = preprocess_chat_image(pil_img)
        
        # Result should be a PIL Image
        assert isinstance(result, Image.Image)
        
        # Image should be upscaled by 1.5x
        assert result.size[0] == int(400 * 1.5)  # width
        assert result.size[1] == int(100 * 1.5)  # height
        
        # Result should be grayscale (mode 'L')
        assert result.mode == 'L'
    
    def test_preprocess_with_numpy_array(self):
        """Test preprocessing with numpy array input."""
        img_array = np.random.randint(0, 255, (100, 400, 3), dtype=np.uint8)
        
        result = preprocess_chat_image(img_array)
        
        # Result should be a PIL Image
        assert isinstance(result, Image.Image)
        
        # Image should be upscaled by 1.5x
        assert result.size[0] == int(400 * 1.5)  # width
        assert result.size[1] == int(100 * 1.5)  # height
    
    def test_preprocess_grayscale_input(self):
        """Test preprocessing with already grayscale input."""
        img_array = np.random.randint(0, 255, (100, 400), dtype=np.uint8)
        pil_img = Image.fromarray(img_array, mode='L')
        
        result = preprocess_chat_image(pil_img)
        
        # Should handle grayscale input without errors
        assert isinstance(result, Image.Image)
        assert result.size[0] == int(400 * 1.5)
        assert result.size[1] == int(100 * 1.5)
    
    def test_preprocess_performance(self):
        """Test that preprocessing stays under 10ms target."""
        # Create a typical chat image
        img_array = np.random.randint(0, 255, (100, 400, 3), dtype=np.uint8)
        pil_img = Image.fromarray(img_array)
        
        # Warm-up run
        for _ in range(3):
            preprocess_chat_image(pil_img)
        
        # Measure performance
        times = []
        for _ in range(20):
            start = time.perf_counter()
            preprocess_chat_image(pil_img)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        median_time = sorted(times)[len(times) // 2]
        p90_time = sorted(times)[int(len(times) * 0.9)]
        
        print(f"\nPreprocess performance: median={median_time:.2f}ms, 90th={p90_time:.2f}ms")
        
        # Should be under 10ms for 90th percentile
        assert p90_time < 10.0, f"Preprocessing too slow: {p90_time:.2f}ms"


class TestNormalizeDealerLine:
    """Test the normalize_dealer_line function."""
    
    def test_normalize_ealer_to_dealer(self):
        """Test correction of 'ealer:' to 'Dealer:'."""
        result = normalize_dealer_line("ealer: Player1 bets 100")
        assert result.startswith("Dealer:")
        assert "Player1 bets 100" in result
    
    def test_normalize_caler_to_dealer(self):
        """Test correction of 'caler:' to 'Dealer:'."""
        result = normalize_dealer_line("caler: Player2 calls 50")
        assert result.startswith("Dealer:")
    
    def test_normalize_ezler_to_dealer(self):
        """Test correction of 'ezler:' to 'Dealer:'."""
        result = normalize_dealer_line("ezler: Dealing Flop: [As Kd Qh]")
        assert result.startswith("Dealer:")
    
    def test_normalize_zealer_to_dealer(self):
        """Test correction of 'zealer:' to 'Dealer:'."""
        result = normalize_dealer_line("zealer: Player3 folds")
        assert result.startswith("Dealer:")
    
    def test_normalize_dzaler_to_dealer(self):
        """Test correction of 'Dzaler:' to 'Dealer:'."""
        result = normalize_dealer_line("Dzaler: Player4 raises to 200")
        assert result.startswith("Dealer:")
    
    def test_normalize_deaer_to_dealer(self):
        """Test correction of 'Deaer:' to 'Dealer:' (missing 'l')."""
        result = normalize_dealer_line("Deaer: Player5 checks")
        assert result.startswith("Dealer:")
    
    def test_normalize_deale_to_dealer(self):
        """Test correction of 'Deale:' to 'Dealer:' (missing 'r')."""
        result = normalize_dealer_line("Deale: Player6 calls 75")
        assert result.startswith("Dealer:")
    
    def test_normalize_whitespace(self):
        """Test that multiple spaces are normalized to single space."""
        result = normalize_dealer_line("Dealer:  Player1    bets   100")
        # Should have single spaces
        assert "  " not in result
        assert "Dealer: Player1 bets 100" == result
    
    def test_preserve_correct_dealer(self):
        """Test that correct 'Dealer:' is preserved."""
        result = normalize_dealer_line("Dealer: Player1 bets 100")
        assert result == "Dealer: Player1 bets 100"
    
    def test_empty_string(self):
        """Test handling of empty string."""
        result = normalize_dealer_line("")
        assert result == ""
    
    def test_none_input(self):
        """Test handling of None input."""
        result = normalize_dealer_line(None)
        assert result is None
    
    def test_case_insensitive(self):
        """Test that correction is case-insensitive."""
        result = normalize_dealer_line("EALER: Player1 bets 100")
        assert result.startswith("Dealer:")


class TestCorrectActionWord:
    """Test the correct_action_word function."""
    
    def test_correct_chtcks_to_checks(self):
        """Test correction of 'chtcks' to 'checks'."""
        result = correct_action_word("chtcks")
        assert result == "checks"
    
    def test_correct_chccks_to_checks(self):
        """Test correction of 'chccks' to 'checks'."""
        result = correct_action_word("chccks")
        assert result == "checks"
    
    def test_correct_chekcs_to_checks(self):
        """Test correction of 'chekcs' to 'checks'."""
        result = correct_action_word("chekcs")
        assert result == "checks"
    
    def test_correct_cals_to_calls(self):
        """Test correction of 'cals' to 'calls'."""
        result = correct_action_word("cals")
        assert result == "calls"
    
    def test_correct_calll_to_calls(self):
        """Test correction of 'calll' to 'calls'."""
        result = correct_action_word("calll")
        assert result == "calls"
    
    def test_correct_rauses_to_raises(self):
        """Test correction of 'rauses' to 'raises'."""
        result = correct_action_word("rauses")
        assert result == "raises"
    
    def test_correct_raies_to_raises(self):
        """Test correction of 'raies' to 'raises'."""
        result = correct_action_word("raies")
        assert result == "raises"
    
    def test_correct_fodls_to_folds(self):
        """Test correction of 'fodls' to 'folds'."""
        result = correct_action_word("fodls")
        assert result == "folds"
    
    def test_prefix_matching_che(self):
        """Test prefix matching for words starting with 'che'."""
        result = correct_action_word("checxs")
        assert result == "checks"
    
    def test_prefix_matching_cal(self):
        """Test prefix matching for words starting with 'cal'."""
        result = correct_action_word("calx")
        assert result == "calls"
    
    def test_prefix_matching_bet(self):
        """Test prefix matching for words starting with 'bet'."""
        result = correct_action_word("betx")
        assert result == "bets"
    
    def test_prefix_matching_rai(self):
        """Test prefix matching for words starting with 'rai'."""
        result = correct_action_word("raix")
        assert result == "raises"
    
    def test_prefix_matching_fol(self):
        """Test prefix matching for words starting with 'fol'."""
        result = correct_action_word("folx")
        assert result == "folds"
    
    def test_preserve_valid_actions(self):
        """Test that valid action words are preserved."""
        assert correct_action_word("checks") == "checks"
        assert correct_action_word("calls") == "calls"
        assert correct_action_word("bets") == "bets"
        assert correct_action_word("raises") == "raises"
        assert correct_action_word("folds") == "folds"
    
    def test_case_insensitive(self):
        """Test that correction is case-insensitive."""
        result = correct_action_word("CHTCKS")
        assert result == "checks"
    
    def test_empty_string(self):
        """Test handling of empty string."""
        result = correct_action_word("")
        assert result is None
    
    def test_none_input(self):
        """Test handling of None input."""
        result = correct_action_word(None)
        assert result is None


class TestChatParserIntegration:
    """Test integration of preprocessing and normalization in ChatParser."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        mock = Mock(spec=OCREngine)
        return mock
    
    @pytest.fixture
    def chat_parser(self, mock_ocr_engine):
        """Create a chat parser instance with preprocessing enabled."""
        return ChatParser(mock_ocr_engine, enable_preprocessing=True)
    
    @pytest.fixture
    def chat_parser_no_preprocessing(self, mock_ocr_engine):
        """Create a chat parser instance with preprocessing disabled."""
        return ChatParser(mock_ocr_engine, enable_preprocessing=False)
    
    def test_extract_chat_lines_with_preprocessing(self, chat_parser, mock_ocr_engine):
        """Test that extract_chat_lines applies preprocessing."""
        # Mock OCR to return text with dealer error
        mock_ocr_engine.read_text.return_value = "ealer: Player1 bets 100"
        
        # Create a sample chat region
        chat_region = np.random.randint(0, 255, (100, 400, 3), dtype=np.uint8)
        
        # Extract chat lines
        lines = chat_parser.extract_chat_lines(chat_region)
        
        # Should have normalized the dealer prefix
        assert len(lines) == 1
        assert lines[0].text.startswith("Dealer:")
        assert "Player1 bets 100" in lines[0].text
        
        # Raw text should be preserved
        assert lines[0].raw_text == "ealer: Player1 bets 100"
    
    def test_extract_chat_lines_without_preprocessing(self, chat_parser_no_preprocessing, mock_ocr_engine):
        """Test that preprocessing can be disabled."""
        # Mock OCR to return text
        mock_ocr_engine.read_text.return_value = "Dealer: Player1 bets 100"
        
        # Create a sample chat region
        chat_region = np.random.randint(0, 255, (100, 400, 3), dtype=np.uint8)
        
        # Extract chat lines
        lines = chat_parser_no_preprocessing.extract_chat_lines(chat_region)
        
        # Should work without preprocessing
        assert len(lines) == 1
        assert lines[0].text.startswith("Dealer:")
    
    def test_log_preprocess_time_flag(self, chat_parser, mock_ocr_engine, caplog):
        """Test that log_preprocess_time flag works."""
        import logging
        caplog.set_level(logging.INFO)
        
        mock_ocr_engine.read_text.return_value = "Dealer: Player1 bets 100"
        chat_region = np.random.randint(0, 255, (100, 400, 3), dtype=np.uint8)
        
        # Extract with logging enabled
        lines = chat_parser.extract_chat_lines(chat_region, log_preprocess_time=True)
        
        # Should have INFO level log with preprocess time
        assert any("[CHAT OCR FOCUS] Preprocess latency:" in record.message 
                   for record in caplog.records if record.levelname == "INFO")
    
    def test_multiple_lines_normalization(self, chat_parser, mock_ocr_engine):
        """Test normalization of multiple lines."""
        mock_ocr_engine.read_text.return_value = (
            "ealer: Player1 bets 100\n"
            "caler: Player2 calls 100\n"
            "Dealer: Player3 folds"
        )
        
        chat_region = np.random.randint(0, 255, (100, 400, 3), dtype=np.uint8)
        lines = chat_parser.extract_chat_lines(chat_region)
        
        # All lines should have normalized dealer prefix
        assert len(lines) == 3
        assert all(line.text.startswith("Dealer:") for line in lines)


class TestPerformanceRegression:
    """Test that new functionality doesn't cause performance regression."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        mock = Mock(spec=OCREngine)
        mock.read_text.return_value = "Dealer: Player1 bets 100\nDealer: Player2 calls 100"
        return mock
    
    def test_extract_chat_lines_performance(self, mock_ocr_engine):
        """Test that extract_chat_lines with preprocessing is reasonably fast."""
        chat_parser = ChatParser(mock_ocr_engine, enable_preprocessing=True)
        chat_region = np.random.randint(0, 255, (100, 400, 3), dtype=np.uint8)
        
        # Warm-up
        for _ in range(3):
            chat_parser.extract_chat_lines(chat_region)
        
        # Measure
        times = []
        for _ in range(10):
            start = time.perf_counter()
            chat_parser.extract_chat_lines(chat_region)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        median_time = sorted(times)[len(times) // 2]
        
        print(f"\nextract_chat_lines median time: {median_time:.2f}ms")
        
        # Should complete in reasonable time (excluding actual OCR which is mocked)
        # The overhead from preprocessing and normalization should be minimal
        assert median_time < 50.0, f"extract_chat_lines too slow: {median_time:.2f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
