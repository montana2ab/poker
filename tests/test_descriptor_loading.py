"""Test for loading descriptors from file paths."""

import pytest
import numpy as np
import cv2
from pathlib import Path
import tempfile
import json
from holdem.vision.calibrate import TableProfile
from holdem.vision.detect_table import TableDetector


class TestDescriptorLoading:
    """Test that keypoints are properly computed when descriptors are loaded from a path."""
    
    def test_keypoints_computed_when_descriptors_loaded_from_path(self):
        """Test that keypoints are computed when descriptors are loaded from a file path.
        
        This test reproduces the bug where descriptors are loaded from a file
        but keypoints remain empty, causing "list index out of range" errors.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create a reference image with some features
            ref_img = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8)
            # Add some strong features
            ref_img[50:100, 50:100] = 255
            ref_img[150:200, 150:200] = 0
            ref_img[200:250, 100:150] = 128
            
            # Save reference image
            ref_img_path = tmpdir / "ref.png"
            cv2.imwrite(str(ref_img_path), ref_img)
            
            # Compute and save descriptors using ORB
            orb = cv2.ORB_create(nfeatures=1000)
            gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
            kp, des = orb.detectAndCompute(gray, None)
            
            # Save descriptors to file
            desc_path = tmpdir / "descriptors.npz"
            np.savez(str(desc_path), des=des)
            
            # Create a profile JSON that references these paths
            profile_data = {
                "window_title": "Test Table",
                "reference_image": str(ref_img_path),
                "descriptors": str(desc_path),
                "card_regions": [],
                "player_regions": [],
                "pot_region": None,
                "bet_regions": [],
                "button_regions": {}
            }
            
            profile_path = tmpdir / "profile.json"
            with open(profile_path, 'w') as f:
                json.dump(profile_data, f)
            
            # Load the profile
            profile = TableProfile.load(profile_path)
            
            # Verify that reference_image and descriptors are paths (strings)
            assert isinstance(profile.reference_image, str)
            assert isinstance(profile.descriptors, str)
            assert profile.keypoints == []  # Should be empty list initially
            
            # Create detector - this should load the paths and compute keypoints
            detector = TableDetector(profile, method="orb", profile_path=profile_path)
            
            # Verify that keypoints have been computed
            assert profile.keypoints is not None
            assert len(profile.keypoints) > 0, "Keypoints should be computed from reference image"
            assert profile.reference_image is not None
            assert isinstance(profile.reference_image, np.ndarray), "Reference image should be loaded as ndarray"
            assert profile.descriptors is not None
            assert isinstance(profile.descriptors, np.ndarray), "Descriptors should be loaded as ndarray"
            
            # Now test detection with a slightly modified screenshot
            # This would previously crash with "list index out of range"
            screenshot = ref_img.copy()
            screenshot[100:150, 100:150] = 200  # Modify slightly
            
            # This should NOT crash
            result = detector.detect(screenshot)
            
            assert result is not None
            assert result.shape == screenshot.shape
    
    def test_keypoints_with_relative_paths(self):
        """Test that relative paths work correctly for reference_image and descriptors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create assets subdirectory
            assets_dir = tmpdir / "assets"
            assets_dir.mkdir()
            
            # Create a reference image
            ref_img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
            ref_img[25:75, 25:75] = 255
            
            # Save reference image
            ref_img_path = assets_dir / "table_ref.png"
            cv2.imwrite(str(ref_img_path), ref_img)
            
            # Compute and save descriptors
            orb = cv2.ORB_create(nfeatures=1000)
            gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
            kp, des = orb.detectAndCompute(gray, None)
            
            desc_path = assets_dir / "descriptors.npy"
            np.save(str(desc_path), des)
            
            # Create profile with RELATIVE paths
            profile_data = {
                "window_title": "Test Table",
                "reference_image": "assets/table_ref.png",  # Relative path
                "descriptors": "assets/descriptors.npy",    # Relative path
                "card_regions": [],
                "player_regions": [],
                "pot_region": None,
                "bet_regions": [],
                "button_regions": {}
            }
            
            profile_path = tmpdir / "profile.json"
            with open(profile_path, 'w') as f:
                json.dump(profile_data, f)
            
            # Load the profile
            profile = TableProfile.load(profile_path)
            
            # Create detector with profile_path so it can resolve relative paths
            detector = TableDetector(profile, method="orb", profile_path=profile_path)
            
            # Verify keypoints computed
            assert profile.keypoints is not None
            assert len(profile.keypoints) > 0
            assert isinstance(profile.reference_image, np.ndarray)
            assert isinstance(profile.descriptors, np.ndarray)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
