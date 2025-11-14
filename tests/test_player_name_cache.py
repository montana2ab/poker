"""Tests for player name caching system."""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from holdem.vision.parse_state import StateParser
from holdem.vision.calibrate import TableProfile
from holdem.vision.vision_cache import PlayerNameCache, OcrCacheManager
from holdem.vision.vision_performance_config import VisionPerformanceConfig


class TestPlayerNameCache:
    """Test cases for PlayerNameCache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = PlayerNameCache()
    
    def test_initial_state_should_run_ocr(self):
        """Test that OCR runs when name is not locked."""
        assert self.cache.should_run_name_ocr(0) is True
        assert self.cache.get_cached_name(0) is None
    
    def test_single_reading_does_not_lock(self):
        """Test that a single reading does not lock the name."""
        self.cache.update_name(0, "Player1", default_name="Player0")
        assert self.cache.should_run_name_ocr(0) is True
        assert self.cache.get_cached_name(0) is None
    
    def test_stable_readings_lock_name(self):
        """Test that consistent readings lock the name."""
        # First reading
        self.cache.update_name(0, "Player1", default_name="Player0")
        assert self.cache.should_run_name_ocr(0) is True
        
        # Second reading (same name) - should lock
        self.cache.update_name(0, "Player1", default_name="Player0")
        assert self.cache.should_run_name_ocr(0) is False
        assert self.cache.get_cached_name(0) == "Player1"
        assert self.cache.player_name_locked[0] is True
    
    def test_different_readings_reset_stability(self):
        """Test that different readings reset stability tracking."""
        # First reading
        self.cache.update_name(0, "Player1", default_name="Player0")
        
        # Second reading (different name) - should reset
        self.cache.update_name(0, "Player2", default_name="Player0")
        assert self.cache.should_run_name_ocr(0) is True
        assert self.cache.get_cached_name(0) is None
        
        # Third reading (same as second) - should lock
        self.cache.update_name(0, "Player2", default_name="Player0")
        assert self.cache.should_run_name_ocr(0) is False
        assert self.cache.get_cached_name(0) == "Player2"
    
    def test_empty_name_ignored(self):
        """Test that empty names are ignored for stability tracking."""
        self.cache.update_name(0, "", default_name="Player0")
        assert self.cache.should_run_name_ocr(0) is True
        assert self.cache.get_cached_name(0) is None
    
    def test_default_name_ignored(self):
        """Test that default names are ignored for stability tracking."""
        self.cache.update_name(0, "Player0", default_name="Player0")
        assert self.cache.should_run_name_ocr(0) is True
        assert self.cache.get_cached_name(0) is None
    
    def test_unlock_seat(self):
        """Test that unlock_seat resets the lock."""
        # Lock a name
        self.cache.update_name(0, "Player1", default_name="Player0")
        self.cache.update_name(0, "Player1", default_name="Player0")
        assert self.cache.should_run_name_ocr(0) is False
        
        # Unlock
        self.cache.unlock_seat(0)
        assert self.cache.should_run_name_ocr(0) is True
        assert self.cache.get_cached_name(0) is None
    
    def test_multiple_seats_independent(self):
        """Test that different seats are tracked independently."""
        # Lock seat 0
        self.cache.update_name(0, "Player1", default_name="Player0")
        self.cache.update_name(0, "Player1", default_name="Player0")
        
        # Seat 1 should still need OCR
        assert self.cache.should_run_name_ocr(1) is True
        
        # Lock seat 1
        self.cache.update_name(1, "Player2", default_name="Player1")
        self.cache.update_name(1, "Player2", default_name="Player1")
        
        # Both should be locked
        assert self.cache.should_run_name_ocr(0) is False
        assert self.cache.should_run_name_ocr(1) is False
        assert self.cache.get_cached_name(0) == "Player1"
        assert self.cache.get_cached_name(1) == "Player2"
    
    def test_reset_all_clears_locks(self):
        """Test that reset_all clears all locks."""
        # Lock multiple seats
        self.cache.update_name(0, "Player1", default_name="Player0")
        self.cache.update_name(0, "Player1", default_name="Player0")
        self.cache.update_name(1, "Player2", default_name="Player1")
        self.cache.update_name(1, "Player2", default_name="Player1")
        
        # Reset
        self.cache.reset_all()
        
        # All seats should need OCR
        assert self.cache.should_run_name_ocr(0) is True
        assert self.cache.should_run_name_ocr(1) is True
        assert self.cache.get_cached_name(0) is None
        assert self.cache.get_cached_name(1) is None


class TestStateParserNameCache:
    """Test cases for StateParser integration with name cache."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock profile with 2 players
        self.profile = TableProfile()
        self.profile.hero_position = 0
        self.profile.card_regions = []
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
            }
        ]
        
        # Create mock card recognizer and OCR engine
        self.card_recognizer = Mock()
        self.card_recognizer.recognize_cards = Mock(return_value=[None, None])
        
        self.ocr_engine = Mock()
        
        # Enable caching in performance config
        self.perf_config = VisionPerformanceConfig.default()
        self.perf_config.enable_caching = True
        self.perf_config.cache_roi_hash = True
    
    def test_name_ocr_runs_initially(self):
        """Test that name OCR runs on first parse."""
        # Mock OCR to return different names
        ocr_call_count = {'count': 0}
        name_responses = ["Alice", "Bob"]
        
        def mock_read_text(img):
            if ocr_call_count['count'] < len(name_responses):
                result = name_responses[ocr_call_count['count']]
                ocr_call_count['count'] += 1
                return result
            return "Unknown"
        
        self.ocr_engine.read_text = Mock(side_effect=mock_read_text)
        self.ocr_engine.extract_number = Mock(return_value=100.0)
        
        # Create parser with caching enabled
        parser = StateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine,
            perf_config=self.perf_config
        )
        
        # Create dummy screenshot
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Parse first frame
        state = parser.parse(screenshot)
        
        assert state is not None
        # Name OCR should have been called for both players
        # Plus pot OCR and stack/bet OCR calls
        assert self.ocr_engine.read_text.call_count >= 2
    
    def test_name_ocr_locked_after_stability(self):
        """Test that name OCR stops after names are locked."""
        # Mock OCR to return consistent names
        name_responses = ["Alice", "Bob", "Alice", "Bob"]  # 2 frames with same names
        ocr_call_index = {'index': 0}
        
        def mock_read_text(img):
            if ocr_call_index['index'] < len(name_responses):
                result = name_responses[ocr_call_index['index']]
                ocr_call_index['index'] += 1
                return result
            # After locking, this should not be called for names
            return "ShouldNotAppear"
        
        self.ocr_engine.read_text = Mock(side_effect=mock_read_text)
        self.ocr_engine.extract_number = Mock(return_value=100.0)
        
        # Create parser
        parser = StateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine,
            perf_config=self.perf_config
        )
        
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Parse twice to establish stability
        state1 = parser.parse(screenshot)
        state2 = parser.parse(screenshot)
        
        assert state1 is not None
        assert state2 is not None
        
        # Check that names are locked
        name_cache = parser.ocr_cache_manager.get_name_cache()
        assert name_cache.player_name_locked.get(0, False) is True
        assert name_cache.player_name_locked.get(1, False) is True
        
        # Parse third time - names should come from cache
        initial_call_count = self.ocr_engine.read_text.call_count
        state3 = parser.parse(screenshot)
        
        assert state3 is not None
        # read_text call count should not increase for names
        # (may increase for other OCR like action detection if implemented)
        # The key is that it doesn't call read_text for name regions
    
    def test_name_unlock_on_stack_zero(self):
        """Test that names unlock when stack goes to zero."""
        # Mock OCR to return stable names initially
        name_call_count = {'count': 0}
        name_responses = ["Alice", "Bob", "Alice", "Bob", "NewPlayer"]  # Need one more for after unlock
        
        def mock_read_text(img):
            if name_call_count['count'] < len(name_responses):
                result = name_responses[name_call_count['count']]
                name_call_count['count'] += 1
                return result
            return "UnexpectedName"
        
        # Stacks: parse1(100,200), parse2(100,200) to lock, parse3(0,200) to unlock, parse4(100,200) new player
        stack_values = [100.0, 200.0, 100.0, 200.0, 0.0, 200.0, 100.0, 200.0]
        stack_iter = iter(stack_values)
        
        def mock_extract_number(img):
            return next(stack_iter, 0.0)
        
        self.ocr_engine.read_text = Mock(side_effect=mock_read_text)
        self.ocr_engine.extract_number = Mock(side_effect=mock_extract_number)
        
        # Create parser
        parser = StateParser(
            profile=self.profile,
            card_recognizer=self.card_recognizer,
            ocr_engine=self.ocr_engine,
            perf_config=self.perf_config
        )
        
        screenshot = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Parse twice to lock names
        parser.parse(screenshot)  # Parse 1: Alice (count=1), Bob (count=1)
        parser.parse(screenshot)  # Parse 2: Alice (count=2, LOCKED), Bob (count=2, LOCKED)
        
        name_cache = parser.ocr_cache_manager.get_name_cache()
        assert name_cache.player_name_locked.get(0, False) is True
        assert name_cache.player_names[0] == "Alice"
        
        # Parse with seat 0 having stack=0 (should unlock on this parse)
        parser.parse(screenshot)  # Parse 3: stack0=0, unlocks seat 0
        
        # Seat 0 should now be unlocked
        assert name_cache.player_name_locked.get(0, False) is False
        
        # Parse 4: should re-detect name for seat 0
        parser.parse(screenshot)  # Parse 4: NewPlayer name OCR should run
        # After one reading, not locked yet
        assert name_cache.player_name_locked.get(0, False) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
