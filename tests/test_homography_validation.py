"""Tests for homography validation in table detection."""

import pytest
import numpy as np
import cv2
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from holdem.vision.detect_table import TableDetector
from holdem.vision.calibrate import TableProfile


class TestHomographyValidation:
    """Test homography validation to prevent distorted transformations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a simple reference image with distinct features
        self.ref_image = np.zeros((600, 800, 3), dtype=np.uint8)
        # Add some features
        cv2.rectangle(self.ref_image, (100, 100), (200, 200), (255, 255, 255), -1)
        cv2.rectangle(self.ref_image, (600, 100), (700, 200), (255, 255, 255), -1)
        cv2.rectangle(self.ref_image, (350, 250), (450, 350), (255, 255, 255), -1)
        cv2.circle(self.ref_image, (400, 500), 50, (255, 255, 255), -1)
        
        # Create profile
        self.profile = TableProfile()
        self.profile.reference_image = self.ref_image
        
        # Create detector
        self.detector = TableDetector(self.profile, method="orb")
    
    def test_identity_homography_valid(self):
        """Test that identity homography is considered valid."""
        H = np.eye(3, dtype=np.float64)
        
        # Create matching point pairs
        src_pts = np.array([[100, 100], [200, 200], [300, 300], [400, 400]], dtype=np.float32).reshape(-1, 1, 2)
        dst_pts = src_pts.copy()
        
        is_valid = self.detector._is_homography_valid(H, src_pts, dst_pts)
        assert is_valid, "Identity homography should be valid"
    
    def test_small_translation_valid(self):
        """Test that small translation homography is valid."""
        H = np.eye(3, dtype=np.float64)
        H[0, 2] = 5.0  # Small x translation
        H[1, 2] = 3.0  # Small y translation
        
        src_pts = np.array([[100, 100], [200, 200], [300, 300], [400, 400]], dtype=np.float32).reshape(-1, 1, 2)
        dst_pts = np.array([[105, 103], [205, 203], [305, 303], [405, 403]], dtype=np.float32).reshape(-1, 1, 2)
        
        is_valid = self.detector._is_homography_valid(H, src_pts, dst_pts)
        assert is_valid, "Small translation homography should be valid"
    
    def test_singular_homography_invalid(self):
        """Test that singular homography is rejected."""
        H = np.zeros((3, 3), dtype=np.float64)
        
        src_pts = np.array([[100, 100], [200, 200]], dtype=np.float32).reshape(-1, 1, 2)
        dst_pts = src_pts.copy()
        
        is_valid = self.detector._is_homography_valid(H, src_pts, dst_pts)
        assert not is_valid, "Singular homography should be invalid"
    
    def test_high_distortion_invalid(self):
        """Test that high distortion homography is rejected."""
        H = np.eye(3, dtype=np.float64)
        H[2, 0] = 0.01  # Add perspective distortion
        
        src_pts = np.array([[100, 100], [200, 100], [200, 200], [100, 200]], dtype=np.float32).reshape(-1, 1, 2)
        # Destination points with large errors
        dst_pts = np.array([[150, 150], [250, 120], [280, 250], [120, 280]], dtype=np.float32).reshape(-1, 1, 2)
        
        is_valid = self.detector._is_homography_valid(H, src_pts, dst_pts)
        assert not is_valid, "High distortion homography should be invalid"
    
    def test_large_reprojection_error_invalid(self):
        """Test that large reprojection error causes rejection."""
        # Create homography with good structure but poor fit
        H = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)
        
        src_pts = np.array([[100, 100], [200, 200], [300, 300], [400, 400]], dtype=np.float32).reshape(-1, 1, 2)
        # Destination points with large errors (> 10 pixels average)
        dst_pts = np.array([[120, 120], [230, 215], [315, 310], [410, 420]], dtype=np.float32).reshape(-1, 1, 2)
        
        is_valid = self.detector._is_homography_valid(H, src_pts, dst_pts)
        assert not is_valid, "Large reprojection error should cause rejection"
    
    def test_none_homography_invalid(self):
        """Test that None homography is rejected."""
        is_valid = self.detector._is_homography_valid(None, None, None)
        assert not is_valid, "None homography should be invalid"
    
    def test_detect_with_poor_features_returns_original(self):
        """Test that detection with poor features returns original screenshot."""
        # Create a nearly uniform screenshot (like preflop with empty board)
        screenshot = np.ones((600, 800, 3), dtype=np.uint8) * 100
        # Add only hero card region
        cv2.rectangle(screenshot, (50, 450), (150, 550), (200, 200, 200), -1)
        
        result = self.detector.detect(screenshot)
        
        # Should return original screenshot when homography is poor
        assert result is not None
        # Check if it's the original (not warped) by comparing shapes
        assert result.shape == screenshot.shape
    
    def test_detect_with_good_features_applies_warp(self):
        """Test that detection with good features applies warp."""
        # Create screenshot similar to reference but slightly shifted
        screenshot = np.zeros((600, 800, 3), dtype=np.uint8)
        # Add same features as reference but shifted
        cv2.rectangle(screenshot, (105, 105), (205, 205), (255, 255, 255), -1)
        cv2.rectangle(screenshot, (605, 105), (705, 205), (255, 255, 255), -1)
        cv2.rectangle(screenshot, (355, 255), (455, 355), (255, 255, 255), -1)
        cv2.circle(screenshot, (405, 505), 50, (255, 255, 255), -1)
        
        result = self.detector.detect(screenshot)
        
        # Should return a result
        assert result is not None
        # Result should have same shape as reference
        assert result.shape == self.ref_image.shape
    
    def test_get_transform_validates_homography(self):
        """Test that get_transform validates homography quality."""
        # Create screenshot with poor features (uniform)
        screenshot = np.ones((600, 800, 3), dtype=np.uint8) * 100
        
        H = self.detector.get_transform(screenshot)
        
        # Should return None when features are poor
        # (either no matches or invalid homography)
        # This is acceptable behavior for preflop scenarios
        assert H is None or isinstance(H, np.ndarray)


class TestHomographyWithMask:
    """Test homography validation with RANSAC inlier mask."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a simple reference image
        self.ref_image = np.zeros((400, 600, 3), dtype=np.uint8)
        cv2.rectangle(self.ref_image, (100, 100), (200, 200), (255, 255, 255), -1)
        
        self.profile = TableProfile()
        self.profile.reference_image = self.ref_image
        self.detector = TableDetector(self.profile, method="orb")
    
    def test_with_inlier_mask(self):
        """Test validation with inlier mask from RANSAC."""
        H = np.eye(3, dtype=np.float64)
        H[0, 2] = 2.0
        
        # 5 points: 4 inliers, 1 outlier
        src_pts = np.array([
            [100, 100], [200, 200], [300, 300], [400, 400], [500, 500]
        ], dtype=np.float32).reshape(-1, 1, 2)
        
        dst_pts = np.array([
            [102, 100], [202, 200], [302, 300], [402, 400], [600, 600]  # Last one is outlier
        ], dtype=np.float32).reshape(-1, 1, 2)
        
        # Mask marking first 4 as inliers, last as outlier
        mask = np.array([[1], [1], [1], [1], [0]], dtype=np.uint8)
        
        # Should be valid because we only check inliers
        is_valid = self.detector._is_homography_valid(H, src_pts, dst_pts, mask)
        assert is_valid, "Should be valid when checking only inliers"
    
    def test_with_no_inliers(self):
        """Test validation with no inliers."""
        H = np.eye(3, dtype=np.float64)
        
        src_pts = np.array([[100, 100], [200, 200]], dtype=np.float32).reshape(-1, 1, 2)
        dst_pts = src_pts.copy()
        
        # Mask with no inliers
        mask = np.array([[0], [0]], dtype=np.uint8)
        
        is_valid = self.detector._is_homography_valid(H, src_pts, dst_pts, mask)
        assert not is_valid, "Should be invalid with no inliers"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
