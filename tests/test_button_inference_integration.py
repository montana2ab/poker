"""Integration test for button inference in parse() method."""

import pytest
import numpy as np
from unittest.mock import Mock
from holdem.vision.parse_state import StateParser
from holdem.vision.calibrate import TableProfile
from holdem.types import PlayerState, Street


class TestButtonInferenceIntegration:
    """Test button inference integrated into the parse() method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock profile
        self.profile = TableProfile()
        self.profile.hero_position = 0
        self.profile.card_regions = [{'x': 0, 'y': 0, 'width': 200, 'height': 100}]
        self.profile.pot_region = {'x': 100, 'y': 100, 'width': 100, 'height': 20}
        self.profile.player_regions = [
            {
                'position': i,
                'name_region': {'x': i*100, 'y': 0, 'width': 100, 'height': 20},
                'stack_region': {'x': i*100, 'y': 20, 'width': 100, 'height': 20},
                'bet_region': {'x': i*100, 'y': 40, 'width': 100, 'height': 20},
                'card_region': {'x': i*100, 'y': 60, 'width': 80, 'height': 60}
            }
            for i in range(6)
        ]
        
        # Create mock card recognizer and OCR engine
        self.card_recognizer = Mock()
        self.card_recognizer.recognize_cards = Mock(return_value=[None] * 5)
        self.card_recognizer.last_confidence_scores = []
        
        self.ocr_engine = Mock()
        self.ocr_engine.read_text = Mock(return_value="Player")
        
        # Create parser
        self.parser = StateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine
        )
    
    def test_button_inference_in_parse_6max(self):
        """Test that button is correctly inferred during parse() in 6-max."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Mock OCR to return specific values:
        # pot, then for each player: stack, bet
        # Button should be at position 2 (since SB=pos3, BB=pos4)
        ocr_values = [
            10.0,   # pot
            100.0, 0.0,   # Player 0: stack, bet
            100.0, 0.0,   # Player 1: stack, bet
            100.0, 0.0,   # Player 2: stack, bet (BTN)
            100.0, 0.5,   # Player 3: stack, bet (SB)
            100.0, 1.0,   # Player 4: stack, bet (BB)
            100.0, 0.0,   # Player 5: stack, bet
        ]
        
        def mock_extract_number(img):
            if ocr_values:
                return ocr_values.pop(0)
            return 0.0
        
        self.ocr_engine.extract_number = mock_extract_number
        
        # Parse
        state = self.parser.parse(screenshot)
        
        assert state is not None, "Parse should succeed"
        assert state.button_position == 2, f"Expected button at position 2, got {state.button_position}"
        assert len(state.players) == 6, "Should have 6 players"
        
        # Verify player bets
        assert state.players[3].bet_this_round == 0.5, "SB should have 0.5 bet"
        assert state.players[4].bet_this_round == 1.0, "BB should have 1.0 bet"
    
    def test_button_inference_fallback_when_no_blinds(self):
        """Test that button falls back to default when blinds can't be inferred."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Mock OCR to return no bets (all zeros)
        ocr_values = [
            10.0,   # pot
            100.0, 0.0,   # Player 0
            100.0, 0.0,   # Player 1
            100.0, 0.0,   # Player 2
            100.0, 0.0,   # Player 3
            100.0, 0.0,   # Player 4
            100.0, 0.0,   # Player 5
        ]
        
        def mock_extract_number(img):
            if ocr_values:
                return ocr_values.pop(0)
            return 0.0
        
        self.ocr_engine.extract_number = mock_extract_number
        
        # Mock _parse_button_position to return 0 (default)
        self.parser._parse_button_position = Mock(return_value=0)
        
        # Parse
        state = self.parser.parse(screenshot)
        
        assert state is not None, "Parse should succeed even without blind inference"
        # Should fall back to _parse_button_position result (0)
        assert state.button_position == 0, f"Expected fallback button at position 0, got {state.button_position}"
    
    def test_button_inference_with_raises(self):
        """Test button inference when players have raised beyond blinds."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Player 3 raised to 3.0 after blinds
        ocr_values = [
            10.0,   # pot
            100.0, 0.0,   # Player 0: folded
            100.0, 0.0,   # Player 1: folded
            100.0, 0.0,   # Player 2: folded (BTN)
            100.0, 0.5,   # Player 3: SB (still shows 0.5 from initial bet)
            100.0, 1.0,   # Player 4: BB (still shows 1.0 from initial bet)
            100.0, 3.0,   # Player 5: raised to 3.0
        ]
        
        def mock_extract_number(img):
            if ocr_values:
                return ocr_values.pop(0)
            return 0.0
        
        self.ocr_engine.extract_number = mock_extract_number
        
        # Parse
        state = self.parser.parse(screenshot)
        
        assert state is not None, "Parse should succeed"
        # Button should still be correctly inferred as position 2 (before SB at pos 3)
        assert state.button_position == 2, f"Expected button at position 2 despite raise, got {state.button_position}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
