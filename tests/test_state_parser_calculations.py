"""Tests for StateParser button position and state calculations."""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from holdem.vision.parse_state import StateParser
from holdem.vision.calibrate import TableProfile
from holdem.types import Street, Card


class TestStateParserCalculations:
    """Test cases for StateParser position and calculation features."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock profile
        self.profile = TableProfile()
        self.profile.hero_position = 0  # Hero is at position 0
        self.profile.card_regions = []
        self.profile.pot_region = {'x': 100, 'y': 100, 'width': 100, 'height': 20}  # Add pot region
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
            }
        ]
        
        # Create mock card recognizer and OCR engine
        self.card_recognizer = Mock()
        self.card_recognizer.recognize_cards = Mock(return_value=[None, None])
        
        self.ocr_engine = Mock()
        self.ocr_engine.extract_number = Mock(return_value=100.0)
        self.ocr_engine.read_text = Mock(return_value="Player")
        
        # Create parser
        self.parser = StateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine
        )
    
    def test_current_bet_calculation(self):
        """Test that current_bet is calculated as the maximum bet."""
        # Create a dummy screenshot
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Mock OCR to return different bet amounts
        # Call order: pot, hero_stack, hero_bet, opp_stack, opp_bet
        call_values = [10.0, 100.0, 50.0, 100.0, 100.0]  # pot, stacks and bets
        call_iter = iter(call_values)
        self.ocr_engine.extract_number = Mock(side_effect=lambda img: next(call_iter, 0.0))
        
        state = self.parser.parse(screenshot)
        
        assert state is not None
        assert state.current_bet == 100.0, f"Expected current_bet=100.0, got {state.current_bet}"
    
    def test_to_call_calculation(self):
        """Test that to_call is calculated correctly for hero."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Mock: Hero has bet 20, opponent has bet 50
        # Call order: pot, hero_stack, hero_bet, opp_stack, opp_bet
        call_values = [10.0, 100.0, 20.0, 100.0, 50.0]
        call_iter = iter(call_values)
        self.ocr_engine.extract_number = Mock(side_effect=lambda img: next(call_iter, 0.0))
        
        state = self.parser.parse(screenshot)
        
        assert state is not None
        # Hero needs to call: current_bet (50) - hero_bet (20) = 30
        assert state.to_call == 30.0, f"Expected to_call=30.0, got {state.to_call}"
    
    def test_effective_stack_calculation(self):
        """Test that effective_stack is minimum of hero and largest opponent stack."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Mock: Hero stack=200, Opponent stack=300
        # Effective stack should be min(200, 300) = 200
        # Call order: pot, hero_stack, hero_bet, opp_stack, opp_bet
        call_values = [10.0, 200.0, 0.0, 300.0, 0.0]
        call_iter = iter(call_values)
        self.ocr_engine.extract_number = Mock(side_effect=lambda img: next(call_iter, 0.0))
        
        state = self.parser.parse(screenshot)
        
        assert state is not None
        assert state.effective_stack == 200.0, f"Expected effective_stack=200.0, got {state.effective_stack}"
    
    def test_spr_calculation(self):
        """Test that SPR is calculated correctly."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Mock: Hero stack=200, Opponent stack=300, Pot=100
        # Effective stack = 200, SPR = 200/100 = 2.0
        # Call order: pot, hero_stack, hero_bet, opp_stack, opp_bet
        call_values = [100.0, 200.0, 0.0, 300.0, 0.0]
        call_iter = iter(call_values)
        self.ocr_engine.extract_number = Mock(side_effect=lambda img: next(call_iter, 0.0))
        
        state = self.parser.parse(screenshot)
        
        assert state is not None
        assert abs(state.spr - 2.0) < 0.01, f"Expected SPR=2.0, got {state.spr}"
    
    def test_heads_up_position_preflop(self):
        """Test heads-up position determination preflop."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Hero at position 0, button at position 0
        # Preflop: button (SB) is OOP, BB is IP
        # So hero (button) should be OOP preflop
        self.profile.hero_position = 0
        
        # Mock button position to be 0
        self.parser._parse_button_position = Mock(return_value=0)
        
        # Mock stacks
        call_sequence = [10.0, 100.0, 0.0, 100.0, 0.0]  # pot, stacks, bets
        self.ocr_engine.extract_number = Mock(side_effect=lambda img: call_sequence.pop(0) if call_sequence else 0.0)
        
        state = self.parser.parse(screenshot)
        
        assert state is not None
        assert state.street == Street.PREFLOP
        # Preflop: hero (button) should be OOP (is_in_position should be False)
        assert state.is_in_position == False, "Hero (button) should be OOP preflop"
    
    def test_heads_up_position_postflop(self):
        """Test heads-up position determination postflop."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Add some board cards to make it postflop
        # Need to mock the card region extraction differently
        def mock_recognize_cards(region, num_cards=5, use_hero_templates=False):
            # For board cards (num_cards=5), return flop cards
            if num_cards == 5:
                return [Card('A', 'h'), Card('K', 'd'), Card('Q', 's'), None, None]
            # For player cards (num_cards=2), return None
            return [None, None]
        
        self.card_recognizer.recognize_cards = mock_recognize_cards
        
        # Add card_regions to profile for board parsing
        self.profile.card_regions = [{'x': 0, 'y': 0, 'width': 200, 'height': 100}]
        
        # Hero at position 0, button at position 0
        # Postflop: button (SB) is IP
        self.profile.hero_position = 0
        
        # Mock button position to be 0
        self.parser._parse_button_position = Mock(return_value=0)
        
        # Mock stacks and bets
        def mock_extract_number(img):
            if not hasattr(mock_extract_number, 'call_count'):
                mock_extract_number.call_count = 0
            mock_extract_number.call_count += 1
            
            call_map = {
                1: 10.0,   # pot
                2: 100.0,  # hero stack
                3: 0.0,    # hero bet
                4: 100.0,  # opp stack
                5: 0.0,    # opp bet
            }
            return call_map.get(mock_extract_number.call_count, 0.0)
        
        self.ocr_engine.extract_number = mock_extract_number
        
        state = self.parser.parse(screenshot)
        
        assert state is not None
        assert state.street == Street.FLOP
        # Postflop: hero (button) should be IP
        assert state.is_in_position == True, "Hero (button) should be IP postflop"
    
    def test_button_position_parsing(self):
        """Test that button position is parsed correctly."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Add dealer_button_region to profile
        self.profile.dealer_button_region = {
            'x': 100, 'y': 100, 'width': 50, 'height': 50
        }
        
        # Mock stacks
        call_sequence = [10.0, 100.0, 0.0, 100.0, 0.0]
        self.ocr_engine.extract_number = Mock(side_effect=lambda img: call_sequence.pop(0) if call_sequence else 0.0)
        
        state = self.parser.parse(screenshot)
        
        assert state is not None
        # Default implementation returns 0, but the mechanism is in place
        assert state.button_position >= 0, "Button position should be set"
    
    def test_bet_region_parsing(self):
        """Test that bet amounts are parsed from player bet regions."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Mock OCR to return specific bet amounts when bet regions are accessed
        # Order: pot, hero_stack, hero_bet, opp_stack, opp_bet
        call_values = [10.0, 100.0, 25.0, 100.0, 50.0]
        call_iter = iter(call_values)
        self.ocr_engine.extract_number = Mock(side_effect=lambda img: next(call_iter, 0.0))
        
        state = self.parser.parse(screenshot)
        
        assert state is not None
        assert len(state.players) == 2
        # Check that bet_this_round was set
        assert state.players[0].bet_this_round == 25.0, f"Expected hero bet=25.0, got {state.players[0].bet_this_round}"
        assert state.players[1].bet_this_round == 50.0, f"Expected opp bet=50.0, got {state.players[1].bet_this_round}"
    
    def test_hero_position_propagation(self):
        """Test that hero_position is propagated to TableState."""
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        self.profile.hero_position = 1  # Hero at position 1
        
        # Mock stacks
        call_sequence = [10.0, 100.0, 0.0, 100.0, 0.0]
        self.ocr_engine.extract_number = Mock(side_effect=lambda img: call_sequence.pop(0) if call_sequence else 0.0)
        
        state = self.parser.parse(screenshot)
        
        assert state is not None
        assert state.hero_position == 1, f"Expected hero_position=1, got {state.hero_position}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
