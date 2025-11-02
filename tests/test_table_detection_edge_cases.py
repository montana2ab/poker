"""Tests for table detection edge cases - empty matches, no features, etc."""

import pytest
import numpy as np
import cv2
from pathlib import Path
from holdem.vision.calibrate import TableProfile
from holdem.vision.detect_table import TableDetector


class TestTableDetectionEdgeCases:
    """Test edge cases in table detection that could cause crashes."""
    
    def test_detect_with_no_matches(self):
        """Test detection when there are no feature matches."""
        # Create a profile with a simple reference image
        profile = TableProfile()
        
        # Create a simple reference image with some features
        ref_img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        profile.reference_image = ref_img
        
        # Create detector and let it compute descriptors
        detector = TableDetector(profile, method="orb")
        
        # Create a completely different screenshot (no matching features)
        screenshot = np.zeros((200, 200, 3), dtype=np.uint8)  # Black image
        
        # This should not crash, even if there are no matches
        result = detector.detect(screenshot)
        
        # Should return the original screenshot when detection fails
        assert result is not None
        assert result.shape == screenshot.shape
    
    def test_detect_with_uniform_image(self):
        """Test detection with uniform images that have no features."""
        profile = TableProfile()
        
        # Create a uniform reference image (no features)
        ref_img = np.full((100, 100, 3), 128, dtype=np.uint8)
        profile.reference_image = ref_img
        
        # Create detector
        detector = TableDetector(profile, method="orb")
        
        # Create another uniform screenshot
        screenshot = np.full((100, 100, 3), 64, dtype=np.uint8)
        
        # Should handle gracefully
        result = detector.detect(screenshot)
        
        assert result is not None
    
    def test_get_transform_with_no_matches(self):
        """Test get_transform when there are no feature matches."""
        # Create a profile with a reference image
        profile = TableProfile()
        ref_img = np.random.randint(0, 255, (150, 150, 3), dtype=np.uint8)
        profile.reference_image = ref_img
        
        # Create detector
        detector = TableDetector(profile, method="orb")
        
        # Create a completely different screenshot
        screenshot = np.ones((150, 150, 3), dtype=np.uint8) * 200
        
        # Should return None when transform cannot be computed
        H = detector.get_transform(screenshot)
        
        # Transform should be None or we should not crash
        assert H is None or isinstance(H, np.ndarray)
    
    def test_detect_with_very_few_features(self):
        """Test detection when screenshot has very few features."""
        profile = TableProfile()
        
        # Create reference with some features
        ref_img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        profile.reference_image = ref_img
        
        detector = TableDetector(profile, method="orb")
        
        # Create screenshot with minimal features (mostly uniform)
        screenshot = np.full((200, 200, 3), 100, dtype=np.uint8)
        # Add just a tiny bit of variation
        screenshot[50:60, 50:60] = 150
        
        # Should not crash
        result = detector.detect(screenshot)
        assert result is not None
    
    def test_detect_with_none_descriptors(self):
        """Test detection when profile has None descriptors."""
        profile = TableProfile()
        profile.reference_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        profile.descriptors = None
        profile.keypoints = None
        
        # Create detector - should compute descriptors
        detector = TableDetector(profile, method="orb")
        
        # Even if ref_img has no features, should not crash
        screenshot = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = detector.detect(screenshot)
        
        assert result is not None
    
    def test_detect_with_empty_reference(self):
        """Test detection when reference image is None."""
        profile = TableProfile()
        profile.reference_image = None
        profile.descriptors = None
        
        detector = TableDetector(profile, method="orb")
        
        screenshot = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # Should return screenshot unmodified
        result = detector.detect(screenshot)
        assert result is not None
        assert np.array_equal(result, screenshot)
    
    def test_get_transform_with_empty_reference(self):
        """Test get_transform when reference is None."""
        profile = TableProfile()
        profile.reference_image = None
        profile.descriptors = None
        
        detector = TableDetector(profile, method="orb")
        
        screenshot = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # Should return None
        H = detector.get_transform(screenshot)
        assert H is None
    
    def test_detect_with_screenshot_having_no_features(self):
        """Test detection when screenshot has no detectable features."""
        profile = TableProfile()
        
        # Reference with features
        ref_img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        profile.reference_image = ref_img
        
        detector = TableDetector(profile, method="orb")
        
        # Screenshot with no features - pure white
        screenshot = np.full((200, 200, 3), 255, dtype=np.uint8)
        
        # Should handle gracefully
        result = detector.detect(screenshot)
        assert result is not None
        # Should return original screenshot
        assert np.array_equal(result, screenshot)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
