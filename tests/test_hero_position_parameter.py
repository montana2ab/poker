"""Tests for fixed hero position parameter in StateParser and ChatEnabledStateParser."""

import pytest
import numpy as np
from unittest.mock import Mock
from holdem.vision.parse_state import StateParser
from holdem.vision.chat_enabled_parser import ChatEnabledStateParser
from holdem.vision.calibrate import TableProfile


class TestHeroPositionParameter:
    """Test cases for hero_position parameter functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock profile WITHOUT hero_position set
        self.profile = TableProfile()
        self.profile.hero_position = None  # Not set in config
        self.profile.card_regions = [{'x': 100, 'y': 100, 'width': 310, 'height': 82}]
        self.profile.pot_region = {'x': 100, 'y': 100, 'width': 100, 'height': 20}
        self.profile.player_regions = [
            {
                'position': 0,
                'name_region': {'x': 0, 'y': 0, 'width': 100, 'height': 20},
                'stack_region': {'x': 0, 'y': 20, 'width': 100, 'height': 20},
                'bet_region': {'x': 0, 'y': 40, 'width': 100, 'height': 20},
                'card_region': {'x': 0, 'y': 60, 'width': 80, 'height': 60}
            },
            {
                'position': 1,
                'name_region': {'x': 200, 'y': 0, 'width': 100, 'height': 20},
                'stack_region': {'x': 200, 'y': 20, 'width': 100, 'height': 20},
                'bet_region': {'x': 200, 'y': 40, 'width': 100, 'height': 20},
                'card_region': {'x': 200, 'y': 60, 'width': 80, 'height': 60}
            },
            {
                'position': 2,
                'name_region': {'x': 400, 'y': 0, 'width': 100, 'height': 20},
                'stack_region': {'x': 400, 'y': 20, 'width': 100, 'height': 20},
                'bet_region': {'x': 400, 'y': 40, 'width': 100, 'height': 20},
                'card_region': {'x': 400, 'y': 60, 'width': 80, 'height': 60}
            }
        ]
        
        # Create mock card recognizer and OCR engine
        self.card_recognizer = Mock()
        self.card_recognizer.recognize_cards = Mock(return_value=[None, None])
        
        self.ocr_engine = Mock()
        self.ocr_engine.extract_number = Mock(return_value=100.0)
        self.ocr_engine.read_text = Mock(return_value="Player")
    
    def test_state_parser_without_hero_position(self):
        """Test StateParser with no hero position specified (backward compatibility)."""
        parser = StateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine
        )
        
        # Should use profile.hero_position (None in this case)
        assert parser.fixed_hero_position is None
        
        # Create dummy screenshot
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        state = parser.parse(screenshot)
        
        assert state is not None
        assert state.hero_position is None  # No hero position set
    
    def test_state_parser_with_cli_hero_position(self):
        """Test StateParser with CLI hero position override."""
        parser = StateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine,
            hero_position=2  # CLI override to position 2
        )
        
        # Should use CLI-provided value
        assert parser.fixed_hero_position == 2
        
        # Create dummy screenshot
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        state = parser.parse(screenshot)
        
        assert state is not None
        assert state.hero_position == 2  # Should use CLI override
    
    def test_state_parser_with_config_hero_position(self):
        """Test StateParser with config hero position."""
        # Set hero position in profile
        self.profile.hero_position = 1
        
        parser = StateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine
        )
        
        # Should use None (no CLI override) but profile value will be used in parse
        assert parser.fixed_hero_position is None
        
        # Create dummy screenshot
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        state = parser.parse(screenshot)
        
        assert state is not None
        assert state.hero_position == 1  # Should use profile value
    
    def test_state_parser_cli_overrides_config(self):
        """Test that CLI hero position overrides config."""
        # Set hero position in profile
        self.profile.hero_position = 1
        
        parser = StateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine,
            hero_position=2  # CLI override
        )
        
        # Should use CLI value
        assert parser.fixed_hero_position == 2
        
        # Create dummy screenshot
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        state = parser.parse(screenshot)
        
        assert state is not None
        assert state.hero_position == 2  # CLI should override config
    
    def test_chat_enabled_parser_with_hero_position(self):
        """Test ChatEnabledStateParser with hero position parameter."""
        parser = ChatEnabledStateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine,
            enable_chat_parsing=False,
            hero_position=2
        )
        
        # Should pass hero position to underlying StateParser
        assert parser.hero_pos == 2
        assert parser.state_parser.fixed_hero_position == 2
        
        # Create dummy screenshot
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        state = parser.parse(screenshot)
        
        assert state is not None
        assert state.hero_position == 2
    
    def test_chat_enabled_parser_uses_config_when_no_cli(self):
        """Test ChatEnabledStateParser uses config value when no CLI override."""
        # Set hero position in profile
        self.profile.hero_position = 1
        
        parser = ChatEnabledStateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine,
            enable_chat_parsing=False
        )
        
        # Should use config value
        assert parser.hero_pos == 1
        
        # Create dummy screenshot
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        state = parser.parse(screenshot)
        
        assert state is not None
        assert state.hero_position == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
