"""Tests for the vision system fix when board is empty (preflop)."""

import pytest
import numpy as np
from pathlib import Path
from holdem.vision.cards import CardRecognizer, create_mock_templates
from holdem.vision.parse_state import StateParser
from holdem.vision.calibrate import TableProfile
from holdem.vision.ocr import OCREngine
from holdem.types import Street
from unittest.mock import Mock


class TestEmptyBoardFix:
    """Test that empty board detection works correctly."""
    
    def test_region_has_cards_with_empty_region(self):
        """Test that empty region is correctly identified."""
        recognizer = CardRecognizer(method="template")
        
        # Create a uniform empty region (like empty table background)
        empty_img = np.ones((100, 350, 3), dtype=np.uint8) * 128
        
        assert not recognizer._region_has_cards(empty_img)
    
    def test_region_has_cards_with_card_present(self):
        """Test that region with card is correctly identified."""
        recognizer = CardRecognizer(method="template")
        
        # Create an image with high variance (simulating a card)
        card_img = np.random.randint(0, 255, (100, 350, 3), dtype=np.uint8)
        
        assert recognizer._region_has_cards(card_img)
    
    def test_region_has_cards_with_edges(self):
        """Test that region with edges is correctly identified as having cards."""
        recognizer = CardRecognizer(method="template")
        
        # Create an image with distinct edges (simulating card borders)
        img = np.ones((100, 350, 3), dtype=np.uint8) * 200
        # Add some rectangles to simulate card edges
        img[20:80, 50:100] = 255
        img[20:80, 150:200] = 255
        
        assert recognizer._region_has_cards(img)
    
    def test_recognize_cards_skips_empty_board(self):
        """Test that recognize_cards returns None for empty board regions."""
        recognizer = CardRecognizer(method="template")
        
        # Create an empty region
        empty_img = np.ones((100, 350, 3), dtype=np.uint8) * 128
        
        # Recognize board cards (use_hero_templates=False)
        cards = recognizer.recognize_cards(empty_img, num_cards=5, use_hero_templates=False)
        
        # Should return list of None values
        assert len(cards) == 5
        assert all(card is None for card in cards)
    
    def test_recognize_cards_hero_cards_not_skipped(self):
        """Test that hero card recognition is not skipped even if region appears empty."""
        recognizer = CardRecognizer(method="template")
        
        # Create an empty region
        empty_img = np.ones((100, 140, 3), dtype=np.uint8) * 128
        
        # Recognize hero cards with skip_empty_check=True
        cards = recognizer.recognize_cards(empty_img, num_cards=2, use_hero_templates=True, skip_empty_check=True)
        
        # Should still attempt recognition (returns 2 cards, may be None due to no templates)
        assert len(cards) == 2
    
    def test_recognize_cards_with_skip_empty_check_false(self):
        """Test that recognition is skipped when skip_empty_check=False and region is empty."""
        recognizer = CardRecognizer(method="template")
        
        # Create an empty region
        empty_img = np.ones((100, 350, 3), dtype=np.uint8) * 128
        
        # Recognize with skip_empty_check=False (default for board cards)
        cards = recognizer.recognize_cards(empty_img, num_cards=5, skip_empty_check=False)
        
        # Should return None for all positions
        assert len(cards) == 5
        assert all(card is None for card in cards)


class TestPreflopBoardParsing:
    """Test that preflop board parsing works correctly with the fix."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        mock = Mock(spec=OCREngine)
        mock.extract_number.return_value = 10.0
        mock.read_text.return_value = "Player"
        mock.detect_action.return_value = None
        return mock
    
    @pytest.fixture
    def mock_card_recognizer(self):
        """Create a mock card recognizer that simulates empty board check."""
        mock = Mock(spec=CardRecognizer)
        
        def mock_recognize_cards(img, num_cards=5, use_hero_templates=False, skip_empty_check=False):
            # Simulate empty board detection for board cards
            if not use_hero_templates and not skip_empty_check:
                # Check if image is "empty" (uniform)
                if len(img.shape) == 3:
                    gray = img[:, :, 0]  # Just use first channel for simplicity
                else:
                    gray = img
                variance = np.var(gray)
                if variance < 100:
                    return [None] * num_cards
            
            # Otherwise return None cards (no templates loaded)
            return [None] * num_cards
        
        mock.recognize_cards = Mock(side_effect=mock_recognize_cards)
        return mock
    
    @pytest.fixture
    def test_profile(self):
        """Create a minimal test profile."""
        profile = TableProfile()
        profile.window_title = "Test"
        profile.hero_position = 0
        profile.player_regions = [
            {
                'position': 0,
                'stack_region': {'x': 0, 'y': 0, 'width': 10, 'height': 10},
                'name_region': {'x': 0, 'y': 0, 'width': 10, 'height': 10},
                'bet_region': {'x': 0, 'y': 0, 'width': 10, 'height': 10},
                'card_region': {'x': 0, 'y': 0, 'width': 10, 'height': 10},
                'action_region': {'x': 0, 'y': 0, 'width': 10, 'height': 10}
            }
        ]
        profile.card_regions = [
            {'x': 100, 'y': 100, 'width': 350, 'height': 100}
        ]
        profile.pot_region = {'x': 0, 'y': 0, 'width': 10, 'height': 10}
        return profile
    
    def test_parse_preflop_with_empty_board(self, test_profile, mock_ocr_engine, mock_card_recognizer):
        """Test that parsing preflop state with empty board works correctly."""
        parser = StateParser(
            profile=test_profile,
            card_recognizer=mock_card_recognizer,
            ocr_engine=mock_ocr_engine
        )
        
        # Create a test screenshot with uniform board region (empty)
        screenshot = np.ones((500, 800, 3), dtype=np.uint8) * 128
        
        state = parser.parse(screenshot)
        
        # Should successfully parse state
        assert state is not None
        
        # Should be preflop (0 board cards)
        assert state.street == Street.PREFLOP
        assert len(state.board) == 0
        
        # Verify that board card recognition was called
        assert mock_card_recognizer.recognize_cards.called


class TestVarianceCalculation:
    """Test the variance-based card detection."""
    
    def test_low_variance_uniform_image(self):
        """Test that uniform images have low variance."""
        recognizer = CardRecognizer(method="template")
        
        # Uniform gray image
        img = np.ones((100, 350, 3), dtype=np.uint8) * 128
        
        assert not recognizer._region_has_cards(img, min_variance=100.0)
    
    def test_high_variance_noisy_image(self):
        """Test that noisy/card images have high variance."""
        recognizer = CardRecognizer(method="template")
        
        # Random noisy image (simulating card with details)
        img = np.random.randint(50, 200, (100, 350, 3), dtype=np.uint8)
        
        assert recognizer._region_has_cards(img, min_variance=100.0)
    
    def test_edge_detection_works(self):
        """Test that edge detection identifies card boundaries."""
        recognizer = CardRecognizer(method="template")
        
        # Image with distinct edges
        img = np.ones((100, 350, 3), dtype=np.uint8) * 200
        # Draw rectangles to simulate card edges
        img[10:90, 20:90] = 255
        img[10:90, 100:170] = 255
        img[10:90, 180:250] = 255
        
        assert recognizer._region_has_cards(img)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
