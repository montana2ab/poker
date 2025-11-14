"""Tests for visual button detection using color-based detection."""

import pytest
import numpy as np
import cv2
from unittest.mock import Mock, MagicMock
from holdem.vision.button_detector import detect_button_by_color
from holdem.vision.calibrate import TableProfile


class TestVisualButtonDetection:
    """Tests for detect_button_by_color function."""
    
    def test_empty_frame(self):
        """Test with empty frame returns None."""
        profile = TableProfile()
        profile.player_regions = []
        
        result = detect_button_by_color(None, profile)
        assert result is None
        
        result = detect_button_by_color(np.array([]), profile)
        assert result is None
    
    def test_no_player_regions(self):
        """Test with no player regions returns None."""
        profile = TableProfile()
        profile.player_regions = []
        
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = detect_button_by_color(frame, profile)
        assert result is None
    
    def test_no_button_regions_defined(self):
        """Test when no button_region fields are defined."""
        profile = TableProfile()
        profile.player_regions = [
            {'position': 0, 'name_region': {'x': 10, 'y': 10, 'width': 50, 'height': 20}},
            {'position': 1, 'name_region': {'x': 10, 'y': 40, 'width': 50, 'height': 20}},
        ]
        
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = detect_button_by_color(frame, profile)
        assert result is None
    
    def test_single_gray_button_detected(self):
        """Test detection of single gray button with contrast."""
        profile = TableProfile()
        profile.player_regions = [
            {
                'position': 0,
                'button_region': {'x': 10, 'y': 10, 'width': 16, 'height': 16}
            },
            {
                'position': 1,
                'button_region': {'x': 10, 'y': 40, 'width': 16, 'height': 16}
            },
        ]
        
        # Create frame with one gray button at position 0
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        
        # Position 0: gray button (200, 200, 200) with darker center for "D"
        frame[10:26, 10:26] = [200, 200, 200]  # Light gray background
        frame[13:23, 13:23] = [80, 80, 80]     # Darker center (simulating "D")
        
        # Position 1: dark region (no button)
        frame[40:56, 10:26] = [50, 50, 50]
        
        result = detect_button_by_color(frame, profile)
        assert result == 0
    
    def test_multiple_candidates_returns_none(self):
        """Test that multiple candidates result in None (ambiguous)."""
        profile = TableProfile()
        profile.player_regions = [
            {
                'position': 0,
                'button_region': {'x': 10, 'y': 10, 'width': 16, 'height': 16}
            },
            {
                'position': 1,
                'button_region': {'x': 10, 'y': 40, 'width': 16, 'height': 16}
            },
        ]
        
        # Create frame with two gray buttons
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        
        # Position 0: gray button
        frame[10:26, 10:26] = [200, 200, 200]
        frame[13:23, 13:23] = [80, 80, 80]
        
        # Position 1: also gray button
        frame[40:56, 10:26] = [195, 195, 195]
        frame[43:53, 13:23] = [75, 75, 75]
        
        result = detect_button_by_color(frame, profile)
        # Should return None because ambiguous (2 candidates)
        assert result is None
    
    def test_color_out_of_range_not_detected(self):
        """Test that colors outside gray range are not detected."""
        profile = TableProfile()
        profile.player_regions = [
            {
                'position': 0,
                'button_region': {'x': 10, 'y': 10, 'width': 16, 'height': 16}
            },
        ]
        
        # Create frame with red region (not gray)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:26, 10:26] = [50, 50, 200]  # Red (BGR format)
        frame[13:23, 13:23] = [20, 20, 80]
        
        result = detect_button_by_color(frame, profile)
        assert result is None
    
    def test_insufficient_contrast_not_detected(self):
        """Test that uniform gray without contrast is not detected."""
        profile = TableProfile()
        profile.player_regions = [
            {
                'position': 0,
                'button_region': {'x': 10, 'y': 10, 'width': 16, 'height': 16}
            },
        ]
        
        # Create frame with uniform gray (no contrast for "D")
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:26, 10:26] = [200, 200, 200]  # Uniform gray, no darker "D"
        
        result = detect_button_by_color(frame, profile)
        # Should return None because insufficient contrast
        assert result is None
    
    def test_region_out_of_bounds(self):
        """Test that regions outside frame bounds are skipped."""
        profile = TableProfile()
        profile.player_regions = [
            {
                'position': 0,
                'button_region': {'x': 90, 'y': 90, 'width': 20, 'height': 20}  # Out of bounds
            },
            {
                'position': 1,
                'button_region': {'x': 10, 'y': 10, 'width': 16, 'height': 16}  # Valid
            },
        ]
        
        # Create 100x100 frame
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        
        # Position 1: gray button
        frame[10:26, 10:26] = [200, 200, 200]
        frame[13:23, 13:23] = [80, 80, 80]
        
        result = detect_button_by_color(frame, profile)
        assert result == 1  # Only position 1 is valid and detected
    
    def test_color_neutrality_check(self):
        """Test that non-neutral colors (R != G != B) are rejected."""
        profile = TableProfile()
        profile.player_regions = [
            {
                'position': 0,
                'button_region': {'x': 10, 'y': 10, 'width': 16, 'height': 16}
            },
        ]
        
        # Create frame with non-neutral gray (too much color variation)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:26, 10:26] = [180, 200, 200]  # B is too different from G and R
        frame[13:23, 13:23] = [70, 80, 80]
        
        result = detect_button_by_color(frame, profile)
        # Should return None because color is not neutral enough
        assert result is None
    
    def test_edge_case_values_at_boundary(self):
        """Test detection at boundary values (180 and 220)."""
        profile = TableProfile()
        profile.player_regions = [
            {
                'position': 0,
                'button_region': {'x': 10, 'y': 10, 'width': 16, 'height': 16}
            },
        ]
        
        # Create frame with values at lower boundary
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:26, 10:26] = [180, 180, 180]  # At minimum threshold
        frame[13:23, 13:23] = [60, 60, 60]     # Create contrast
        
        result = detect_button_by_color(frame, profile)
        assert result == 0  # Should be detected at boundary
    
    def test_six_max_table_multiple_seats(self):
        """Test with realistic 6-max table setup."""
        profile = TableProfile()
        profile.player_regions = [
            {'position': i, 'button_region': {'x': 10 + i * 30, 'y': 10, 'width': 16, 'height': 16}}
            for i in range(6)
        ]
        
        # Create frame with button at position 3
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        
        # All positions dark except position 3
        for i in range(6):
            x = 10 + i * 30
            if i == 3:
                # Position 3: gray button
                frame[10:26, x:x+16] = [195, 195, 195]
                frame[13:23, x+3:x+13] = [70, 70, 70]
            else:
                # Other positions: dark
                frame[10:26, x:x+16] = [40, 40, 40]
        
        result = detect_button_by_color(frame, profile)
        assert result == 3


class TestVisualButtonIntegration:
    """Integration tests with ChatEnabledStateParser."""
    
    def test_visual_detection_config_modes(self):
        """Test that different config modes work correctly."""
        from holdem.vision.vision_performance_config import VisionButtonDetectionConfig
        
        # Test default mode
        config = VisionButtonDetectionConfig()
        assert config.mode == "hybrid"
        assert config.min_stable_frames == 2
        
        # Test custom mode
        config = VisionButtonDetectionConfig(mode="visual_only", min_stable_frames=3)
        assert config.mode == "visual_only"
        assert config.min_stable_frames == 3
    
    def test_config_loading_from_dict(self):
        """Test loading button detection config from dict."""
        from holdem.vision.vision_performance_config import VisionPerformanceConfig
        
        config_dict = {
            'enable_caching': True,
            'vision_button_detection': {
                'mode': 'visual_only',
                'min_stable_frames': 3
            }
        }
        
        config = VisionPerformanceConfig.from_dict(config_dict)
        assert config.vision_button_detection.mode == 'visual_only'
        assert config.vision_button_detection.min_stable_frames == 3
