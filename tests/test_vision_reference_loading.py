"""Tests for vision reference loading from file paths."""

import pytest
import tempfile
import numpy as np
import cv2
from pathlib import Path
from holdem.vision.calibrate import TableProfile
from holdem.vision.detect_table import TableDetector, _load_refs_from_paths


class TestReferenceLoading:
    """Test loading reference images and descriptors from paths."""
    
    def test_load_refs_from_paths_with_image(self):
        """Test loading reference image from path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create a dummy image
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img_path = tmpdir / "test_image.png"
            cv2.imwrite(str(img_path), img)
            
            # Create profile with image path
            profile = TableProfile()
            profile.reference_image = str(img_path)
            
            # Load references
            _load_refs_from_paths(profile, tmpdir / "dummy.json")
            
            # Check that image was loaded
            assert isinstance(profile.reference_image, np.ndarray)
            assert profile.reference_image.shape == (100, 100, 3)
    
    def test_load_refs_from_paths_with_relative_path(self):
        """Test loading with relative paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create subdirectory and image
            subdir = tmpdir / "refs"
            subdir.mkdir()
            img = np.zeros((50, 50, 3), dtype=np.uint8)
            img_path = subdir / "ref.png"
            cv2.imwrite(str(img_path), img)
            
            # Create profile with relative path
            profile = TableProfile()
            profile.reference_image = "refs/ref.png"
            
            # Load references with base directory
            _load_refs_from_paths(profile, tmpdir / "profile.json")
            
            # Check that image was loaded
            assert isinstance(profile.reference_image, np.ndarray)
    
    def test_load_refs_from_paths_with_descriptors_npy(self):
        """Test loading descriptors from .npy file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create dummy descriptors with proper uint8 values
            descriptors = np.random.randint(0, 256, size=(100, 32), dtype=np.uint8)
            desc_path = tmpdir / "descriptors.npy"
            np.save(desc_path, descriptors)
            
            # Create profile with descriptors path
            profile = TableProfile()
            profile.descriptors = str(desc_path)
            
            # Load references
            _load_refs_from_paths(profile, tmpdir / "dummy.json")
            
            # Check that descriptors were loaded
            assert isinstance(profile.descriptors, np.ndarray)
            assert profile.descriptors.shape == (100, 32)
    
    def test_load_refs_from_paths_with_descriptors_npz(self):
        """Test loading descriptors from .npz file with 'des' key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create dummy descriptors in npz format with proper uint8 values
            descriptors = np.random.randint(0, 256, size=(50, 64), dtype=np.uint8)
            desc_path = tmpdir / "descriptors.npz"
            np.savez(desc_path, des=descriptors)
            
            # Create profile with descriptors path
            profile = TableProfile()
            profile.descriptors = str(desc_path)
            
            # Load references
            _load_refs_from_paths(profile, tmpdir / "dummy.json")
            
            # Check that descriptors were loaded
            assert isinstance(profile.descriptors, np.ndarray)
            assert profile.descriptors.shape == (50, 64)
    
    def test_load_refs_from_paths_with_descriptors_npz_alt_key(self):
        """Test loading descriptors from .npz file with 'descriptors' key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create dummy descriptors with alternative key and proper uint8 values
            descriptors = np.random.randint(0, 256, size=(30, 128), dtype=np.uint8)
            desc_path = tmpdir / "descriptors.npz"
            np.savez(desc_path, descriptors=descriptors)
            
            # Create profile with descriptors path
            profile = TableProfile()
            profile.descriptors = str(desc_path)
            
            # Load references
            _load_refs_from_paths(profile, tmpdir / "dummy.json")
            
            # Check that descriptors were loaded
            assert isinstance(profile.descriptors, np.ndarray)
            assert profile.descriptors.shape == (30, 128)
    
    def test_load_refs_nonexistent_path(self):
        """Test handling of nonexistent file paths."""
        profile = TableProfile()
        profile.reference_image = "/nonexistent/path/to/image.png"
        profile.descriptors = "/nonexistent/path/to/descriptors.npz"
        
        # Should not crash, just set to None
        _load_refs_from_paths(profile, Path("/tmp/dummy.json"))
        
        assert profile.reference_image is None
        assert profile.descriptors is None
    
    def test_load_refs_with_ndarray_already_loaded(self):
        """Test that already-loaded ndarrays are not processed."""
        profile = TableProfile()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        descriptors = np.random.randint(0, 256, size=(50, 32), dtype=np.uint8)
        
        profile.reference_image = img
        profile.descriptors = descriptors
        
        # Load should not change anything
        _load_refs_from_paths(profile, Path("/tmp/dummy.json"))
        
        assert np.array_equal(profile.reference_image, img)
        assert np.array_equal(profile.descriptors, descriptors)


class TestTableDetectorWithReferences:
    """Test TableDetector with reference loading."""
    
    def test_detector_loads_references_from_paths(self):
        """Test that TableDetector loads references during initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create dummy reference image and descriptors with proper uint8 values
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img_path = tmpdir / "ref.png"
            cv2.imwrite(str(img_path), img)
            
            descriptors = np.random.randint(0, 256, size=(50, 32), dtype=np.uint8)
            desc_path = tmpdir / "desc.npz"
            np.savez(desc_path, des=descriptors)
            
            # Create profile with paths
            profile = TableProfile()
            profile.reference_image = str(img_path)
            profile.descriptors = str(desc_path)
            
            profile_path = tmpdir / "profile.json"
            
            # Create detector - should load references
            detector = TableDetector(profile, method="orb", profile_path=profile_path)
            
            # Check that references were loaded
            assert isinstance(detector.profile.reference_image, np.ndarray)
            assert isinstance(detector.profile.descriptors, np.ndarray)
    
    def test_detector_computes_descriptors_if_missing(self):
        """Test that detector computes descriptors if only image is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create dummy reference image (with some features)
            img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
            img_path = tmpdir / "ref.png"
            cv2.imwrite(str(img_path), img)
            
            # Create profile with only image path
            profile = TableProfile()
            profile.reference_image = str(img_path)
            profile.descriptors = None
            
            profile_path = tmpdir / "profile.json"
            
            # Create detector - should load image and compute descriptors
            detector = TableDetector(profile, method="orb", profile_path=profile_path)
            
            # Check that image was loaded and descriptors computed
            assert isinstance(detector.profile.reference_image, np.ndarray)
            assert detector.profile.descriptors is not None


class TestProfileLoadingSaveWithReferences:
    """Test TableProfile save/load with reference paths."""
    
    def test_profile_save_and_load_with_owner_name(self):
        """Test saving and loading profile with owner_name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create profile
            profile = TableProfile()
            profile.window_title = "Hold'em Table"
            profile.owner_name = "PokerStars"
            profile.screen_region = (100, 100, 800, 600)
            
            # Save profile
            profile_path = tmpdir / "test_profile.json"
            profile.save(profile_path)
            
            # Load profile
            loaded = TableProfile.load(profile_path)
            
            assert loaded.window_title == "Hold'em Table"
            assert loaded.owner_name == "PokerStars"
            assert loaded.screen_region == (100, 100, 800, 600)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
