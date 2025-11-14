"""Tests for button inference from blinds logic."""

import pytest
from holdem.vision.parse_state import StateParser
from holdem.vision.calibrate import TableProfile
from holdem.types import PlayerState, ActionType
from unittest.mock import Mock


class TestButtonInference:
    """Test cases for _infer_button_from_blinds functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock profile
        self.profile = TableProfile()
        self.profile.hero_position = 0
        self.profile.card_regions = []
        self.profile.pot_region = {'x': 100, 'y': 100, 'width': 100, 'height': 20}
        self.profile.player_regions = []
        
        # Create mock card recognizer and OCR engine
        self.card_recognizer = Mock()
        self.ocr_engine = Mock()
        
        # Create parser
        self.parser = StateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine
        )
    
    def test_simple_6max_sb_at_position_1(self):
        """Test button inference in 6-max with SB at position 1."""
        players = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=0.0),  # BTN
            PlayerState(name="Player1", stack=100.0, position=1, bet_this_round=0.5),  # SB
            PlayerState(name="Player2", stack=100.0, position=2, bet_this_round=1.0),  # BB
            PlayerState(name="Player3", stack=100.0, position=3, bet_this_round=0.0),
            PlayerState(name="Player4", stack=100.0, position=4, bet_this_round=0.0),
            PlayerState(name="Player5", stack=100.0, position=5, bet_this_round=0.0),
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        assert button_pos == 0, f"Expected button at position 0, got {button_pos}"
    
    def test_simple_6max_sb_at_position_3(self):
        """Test button inference in 6-max with SB at position 3."""
        players = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=0.0),
            PlayerState(name="Player1", stack=100.0, position=1, bet_this_round=0.0),
            PlayerState(name="Player2", stack=100.0, position=2, bet_this_round=0.0),  # BTN
            PlayerState(name="Player3", stack=100.0, position=3, bet_this_round=0.5),  # SB
            PlayerState(name="Player4", stack=100.0, position=4, bet_this_round=1.0),  # BB
            PlayerState(name="Player5", stack=100.0, position=5, bet_this_round=0.0),
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        assert button_pos == 2, f"Expected button at position 2, got {button_pos}"
    
    def test_wrap_around_sb_at_position_0(self):
        """Test button inference when SB wraps around to position 0."""
        players = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=0.5),  # SB
            PlayerState(name="Player1", stack=100.0, position=1, bet_this_round=1.0),  # BB
            PlayerState(name="Player2", stack=100.0, position=2, bet_this_round=0.0),
            PlayerState(name="Player3", stack=100.0, position=3, bet_this_round=0.0),
            PlayerState(name="Player4", stack=100.0, position=4, bet_this_round=0.0),
            PlayerState(name="Player5", stack=100.0, position=5, bet_this_round=0.0),  # BTN
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        assert button_pos == 5, f"Expected button at position 5, got {button_pos}"
    
    def test_heads_up(self):
        """Test button inference in heads-up game."""
        # In heads-up, button is also small blind
        players = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=0.5),  # BTN/SB
            PlayerState(name="Player1", stack=100.0, position=1, bet_this_round=1.0),  # BB
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        # In heads-up, button posts SB, so button should be at the SB position (0)
        assert button_pos == 0, f"Expected button at position 0 (heads-up), got {button_pos}"
    
    def test_no_blinds_posted(self):
        """Test when no blinds are posted (should return None)."""
        players = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=0.0),
            PlayerState(name="Player1", stack=100.0, position=1, bet_this_round=0.0),
            PlayerState(name="Player2", stack=100.0, position=2, bet_this_round=0.0),
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        assert button_pos is None, f"Expected None when no blinds, got {button_pos}"
    
    def test_only_one_bet(self):
        """Test when only one player has bet (should return None)."""
        players = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=0.0),
            PlayerState(name="Player1", stack=100.0, position=1, bet_this_round=0.5),
            PlayerState(name="Player2", stack=100.0, position=2, bet_this_round=0.0),
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        assert button_pos is None, f"Expected None when only one bet, got {button_pos}"
    
    def test_non_standard_blind_ratio(self):
        """Test with non-standard blind ratio (should return None)."""
        # BB is not ~2x SB
        players = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=0.0),
            PlayerState(name="Player1", stack=100.0, position=1, bet_this_round=0.5),   # SB
            PlayerState(name="Player2", stack=100.0, position=2, bet_this_round=5.0),   # Not standard BB
            PlayerState(name="Player3", stack=100.0, position=3, bet_this_round=0.0),
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        assert button_pos is None, f"Expected None for non-standard blinds, got {button_pos}"
    
    def test_with_raises(self):
        """Test button inference when there are raises beyond blinds."""
        # Even with raises, the two smallest bets should still be SB and BB
        players = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=0.0),  # BTN (folded)
            PlayerState(name="Player1", stack=100.0, position=1, bet_this_round=0.5),  # SB
            PlayerState(name="Player2", stack=100.0, position=2, bet_this_round=1.0),  # BB
            PlayerState(name="Player3", stack=100.0, position=3, bet_this_round=3.0),  # Raised
            PlayerState(name="Player4", stack=100.0, position=4, bet_this_round=0.0),  # Folded
            PlayerState(name="Player5", stack=100.0, position=5, bet_this_round=0.0),  # Folded
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        assert button_pos == 0, f"Expected button at position 0, got {button_pos}"
    
    def test_tolerance_for_rounding(self):
        """Test that small deviations from 2x ratio are tolerated."""
        # BB is 1.9x SB (within tolerance)
        players = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=0.0),
            PlayerState(name="Player1", stack=100.0, position=1, bet_this_round=0.5),  # SB
            PlayerState(name="Player2", stack=100.0, position=2, bet_this_round=0.95), # BB (1.9x)
            PlayerState(name="Player3", stack=100.0, position=3, bet_this_round=0.0),
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        assert button_pos == 0, f"Expected button at position 0, got {button_pos}"
    
    def test_empty_player_list(self):
        """Test with empty player list (should return None)."""
        players = []
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        assert button_pos is None, f"Expected None for empty players, got {button_pos}"
    
    def test_single_player(self):
        """Test with only one player (should return None)."""
        players = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=1.0),
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players)
        
        assert button_pos is None, f"Expected None for single player, got {button_pos}"
    
    def test_different_blind_sizes(self):
        """Test with different blind sizes (1/2, 5/10, etc.)."""
        # Test with 1/2 blinds
        players_1_2 = [
            PlayerState(name="Player0", stack=100.0, position=0, bet_this_round=0.0),
            PlayerState(name="Player1", stack=100.0, position=1, bet_this_round=1.0),  # SB
            PlayerState(name="Player2", stack=100.0, position=2, bet_this_round=2.0),  # BB
            PlayerState(name="Player3", stack=100.0, position=3, bet_this_round=0.0),
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players_1_2)
        assert button_pos == 0, f"Expected button at position 0 for 1/2 blinds, got {button_pos}"
        
        # Test with 5/10 blinds
        players_5_10 = [
            PlayerState(name="Player0", stack=1000.0, position=0, bet_this_round=0.0),
            PlayerState(name="Player1", stack=1000.0, position=1, bet_this_round=0.0),
            PlayerState(name="Player2", stack=1000.0, position=2, bet_this_round=0.0),
            PlayerState(name="Player3", stack=1000.0, position=3, bet_this_round=5.0),   # SB
            PlayerState(name="Player4", stack=1000.0, position=4, bet_this_round=10.0),  # BB
            PlayerState(name="Player5", stack=1000.0, position=5, bet_this_round=0.0),
        ]
        
        button_pos = self.parser._infer_button_from_blinds(players_5_10)
        assert button_pos == 2, f"Expected button at position 2 for 5/10 blinds, got {button_pos}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
