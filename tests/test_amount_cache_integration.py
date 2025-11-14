"""Integration tests for amount cache system."""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from holdem.vision.vision_performance_config import VisionPerformanceConfig
from holdem.vision.parse_state import StateParser
from holdem.vision.calibrate import TableProfile
from holdem.vision.cards import CardRecognizer
from holdem.vision.ocr import OCREngine


class TestAmountCacheIntegration:
    """Integration tests for amount cache with enable_amount_cache flag."""
    
    def test_cache_disabled_when_flag_false(self):
        """Test that cache is disabled when enable_amount_cache is False."""
        # Create config with caching disabled
        config = VisionPerformanceConfig(
            enable_caching=True,
            cache_roi_hash=True,
            enable_amount_cache=False  # Disable amount cache
        )
        
        # Create mock dependencies
        profile = Mock(spec=TableProfile)
        profile.card_regions = []
        profile.player_regions = []
        profile.pot_region = None
        profile.hero_position = None
        
        card_recognizer = Mock(spec=CardRecognizer)
        ocr_engine = Mock(spec=OCREngine)
        
        # Create parser with disabled cache
        parser = StateParser(
            profile=profile,
            card_recognizer=card_recognizer,
            ocr_engine=ocr_engine,
            perf_config=config
        )
        
        # Verify cache manager is None
        assert parser.ocr_cache_manager is None
    
    def test_cache_enabled_when_flag_true(self):
        """Test that cache is enabled when enable_amount_cache is True."""
        # Create config with caching enabled
        config = VisionPerformanceConfig(
            enable_caching=True,
            cache_roi_hash=True,
            enable_amount_cache=True  # Enable amount cache
        )
        
        # Create mock dependencies
        profile = Mock(spec=TableProfile)
        profile.card_regions = []
        profile.player_regions = []
        profile.pot_region = None
        profile.hero_position = None
        
        card_recognizer = Mock(spec=CardRecognizer)
        ocr_engine = Mock(spec=OCREngine)
        
        # Create parser with enabled cache
        parser = StateParser(
            profile=profile,
            card_recognizer=card_recognizer,
            ocr_engine=ocr_engine,
            perf_config=config
        )
        
        # Verify cache manager is created
        assert parser.ocr_cache_manager is not None
    
    def test_cache_metrics_tracking(self):
        """Test that cache metrics are tracked correctly during parsing."""
        # Create config with caching enabled
        config = VisionPerformanceConfig(
            enable_caching=True,
            cache_roi_hash=True,
            enable_amount_cache=True,
            enable_light_parse=True,
            light_parse_interval=2  # Full parse every 2 frames
        )
        
        # Create mock profile with minimal regions
        profile = Mock(spec=TableProfile)
        profile.card_regions = [{
            'x': 100, 'y': 100, 'width': 200, 'height': 50
        }]
        profile.player_regions = []
        profile.pot_region = {
            'x': 300, 'y': 50, 'width': 100, 'height': 30
        }
        profile.hero_position = None
        
        card_recognizer = Mock(spec=CardRecognizer)
        card_recognizer.recognize_cards.return_value = [None] * 5
        card_recognizer.last_confidence_scores = []
        
        ocr_engine = Mock(spec=OCREngine)
        ocr_engine.extract_number.return_value = 100.0
        
        # Create parser
        parser = StateParser(
            profile=profile,
            card_recognizer=card_recognizer,
            ocr_engine=ocr_engine,
            perf_config=config
        )
        
        # Create test image (consistent data)
        img = np.zeros((600, 800, 3), dtype=np.uint8)
        
        # First parse - frame 0 is always full parse, should run OCR
        print("=== FIRST PARSE (frame 0, full parse) ===")
        state1 = parser.parse(img, frame_index=0)
        
        # Verify metrics show OCR call
        metrics = parser.get_cache_metrics()
        print(f"After frame 0: OCR calls={metrics['total_ocr_calls']}, cache hits={metrics['total_cache_hits']}")
        assert metrics is not None
        assert metrics['total_ocr_calls'] > 0
        initial_ocr_calls = metrics['total_ocr_calls']
        
        # Second parse - frame 1 is light parse (1 % 2 = 1, not 0), should use cache
        print("\n=== SECOND PARSE (frame 1, light parse) ===")
        state2 = parser.parse(img, frame_index=1)
        
        # Verify metrics show cache hit
        metrics = parser.get_cache_metrics()
        print(f"After frame 1: OCR calls={metrics['total_ocr_calls']}, cache hits={metrics['total_cache_hits']}")
        print(f"Cache hit rate: {metrics['cache_hit_rate_percent']:.1f}%")
        
        # At minimum, pot should have been cached (1 cache hit)
        assert metrics['total_cache_hits'] > 0, "Expected at least one cache hit on second parse"
        assert metrics['cache_hit_rate_percent'] > 0
    
    def test_cache_invalidation_on_image_change(self):
        """Test that cache is invalidated when image changes."""
        # Create config with caching enabled
        config = VisionPerformanceConfig(
            enable_caching=True,
            cache_roi_hash=True,
            enable_amount_cache=True
        )
        
        # Create mock profile
        profile = Mock(spec=TableProfile)
        profile.card_regions = [{
            'x': 100, 'y': 100, 'width': 200, 'height': 50
        }]
        profile.player_regions = []
        profile.pot_region = {
            'x': 300, 'y': 50, 'width': 100, 'height': 30
        }
        profile.hero_position = None
        
        card_recognizer = Mock(spec=CardRecognizer)
        card_recognizer.recognize_cards.return_value = [None] * 5
        card_recognizer.last_confidence_scores = []
        
        ocr_engine = Mock(spec=OCREngine)
        ocr_engine.extract_number.side_effect = [100.0, 150.0]  # Different values
        
        # Create parser
        parser = StateParser(
            profile=profile,
            card_recognizer=card_recognizer,
            ocr_engine=ocr_engine,
            perf_config=config
        )
        
        # First parse with image 1
        img1 = np.zeros((600, 800, 3), dtype=np.uint8)
        state1 = parser.parse(img1, frame_index=0)
        
        # Get initial metrics
        metrics1 = parser.get_cache_metrics()
        initial_ocr_calls = metrics1['total_ocr_calls']
        
        # Second parse with different image - should invalidate cache
        img2 = np.ones((600, 800, 3), dtype=np.uint8) * 255
        state2 = parser.parse(img2, frame_index=0)
        
        # Verify new OCR call was made
        metrics2 = parser.get_cache_metrics()
        assert metrics2['total_ocr_calls'] > initial_ocr_calls
    
    def test_metrics_reset(self):
        """Test that metrics can be reset."""
        config = VisionPerformanceConfig(
            enable_caching=True,
            cache_roi_hash=True,
            enable_amount_cache=True
        )
        
        profile = Mock(spec=TableProfile)
        profile.card_regions = []
        profile.player_regions = []
        profile.pot_region = None
        profile.hero_position = None
        
        card_recognizer = Mock(spec=CardRecognizer)
        ocr_engine = Mock(spec=OCREngine)
        
        parser = StateParser(
            profile=profile,
            card_recognizer=card_recognizer,
            ocr_engine=ocr_engine,
            perf_config=config
        )
        
        # Simulate some cache activity
        parser.ocr_cache_manager.record_ocr_call("pot")
        parser.ocr_cache_manager.record_cache_hit("pot")
        
        # Verify metrics exist
        metrics = parser.get_cache_metrics()
        assert metrics['total_ocr_calls'] > 0
        
        # Reset metrics
        parser.reset_cache_metrics()
        
        # Verify metrics are cleared
        metrics = parser.get_cache_metrics()
        assert metrics['total_ocr_calls'] == 0
        assert metrics['total_cache_hits'] == 0
    
    def test_config_from_yaml_includes_amount_cache(self):
        """Test that enable_amount_cache is loaded from YAML config."""
        # Create test config dict
        config_dict = {
            "enable_caching": True,
            "cache_roi_hash": True,
            "enable_amount_cache": False,  # Explicitly disable
            "board_cache": {"enabled": True},
            "hero_cache": {"enabled": True}
        }
        
        # Load config
        config = VisionPerformanceConfig.from_dict(config_dict)
        
        # Verify flag is loaded correctly
        assert config.enable_amount_cache is False
        
        # Test with enabled
        config_dict["enable_amount_cache"] = True
        config = VisionPerformanceConfig.from_dict(config_dict)
        assert config.enable_amount_cache is True
    
    def test_default_config_has_amount_cache_enabled(self):
        """Test that default config has amount cache enabled."""
        config = VisionPerformanceConfig.default()
        
        # Verify default is enabled
        assert config.enable_amount_cache is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
