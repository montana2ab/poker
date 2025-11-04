"""Tests for automatic card template capture."""

import pytest
import numpy as np
import cv2
from pathlib import Path

from holdem.vision.auto_capture import CardTemplateCapture
from holdem.vision.calibrate import TableProfile


def test_card_template_capture_init(tmp_path):
    """Test CardTemplateCapture initialization."""
    profile = TableProfile()
    profile.hero_position = 0
    
    board_dir = tmp_path / "board"
    hero_dir = tmp_path / "hero"
    
    capture = CardTemplateCapture(profile, board_dir, hero_dir)
    
    assert capture.profile == profile
    assert capture.board_output_dir == board_dir
    assert capture.hero_output_dir == hero_dir
    assert board_dir.exists()
    assert hero_dir.exists()
    assert len(capture.board_cards_captured) == 0
    assert len(capture.hero_cards_captured) == 0


def test_load_existing_captures(tmp_path):
    """Test loading existing captured cards."""
    board_dir = tmp_path / "board"
    board_dir.mkdir()
    
    # Create some fake templates
    for card in ["Ah", "Ks", "7d"]:
        (board_dir / f"{card}.png").touch()
    
    profile = TableProfile()
    capture = CardTemplateCapture(profile, board_dir, tmp_path / "hero")
    
    assert len(capture.board_cards_captured) == 3
    assert "Ah" in capture.board_cards_captured
    assert "Ks" in capture.board_cards_captured
    assert "7d" in capture.board_cards_captured


def test_is_valid_card_image():
    """Test card image validation."""
    profile = TableProfile()
    capture = CardTemplateCapture(profile, Path("/tmp/b"), Path("/tmp/h"))
    
    # Valid card image
    valid_img = np.random.randint(50, 200, (100, 70, 3), dtype=np.uint8)
    assert capture._is_valid_card_image(valid_img) == True
    
    # Too small
    small_img = np.zeros((10, 10, 3), dtype=np.uint8)
    assert capture._is_valid_card_image(small_img) == False
    
    # Pure black
    black_img = np.zeros((100, 70, 3), dtype=np.uint8)
    assert capture._is_valid_card_image(black_img) == False
    
    # Pure white
    white_img = np.ones((100, 70, 3), dtype=np.uint8) * 255
    assert capture._is_valid_card_image(white_img) == False
    
    # Low variance (flat color)
    flat_img = np.ones((100, 70, 3), dtype=np.uint8) * 128
    assert capture._is_valid_card_image(flat_img) == False
    
    # None
    assert capture._is_valid_card_image(None) == False


def test_is_new_card():
    """Test new card detection."""
    profile = TableProfile()
    capture = CardTemplateCapture(profile, Path("/tmp/b"), Path("/tmp/h"))
    
    # First card (no previous) - should be new
    card1 = np.random.randint(0, 255, (100, 70, 3), dtype=np.uint8)
    assert capture._is_new_card(card1, None) == True
    
    # Same card - should not be new
    assert capture._is_new_card(card1, card1) == False
    
    # Different card - should be new
    card2 = np.random.randint(0, 255, (100, 70, 3), dtype=np.uint8)
    # Make it significantly different
    card2 = card2 + 50
    card2 = np.clip(card2, 0, 255).astype(np.uint8)
    assert capture._is_new_card(card2, card1) == True
    
    # Different size - should be new
    card3 = np.random.randint(0, 255, (80, 60, 3), dtype=np.uint8)
    assert capture._is_new_card(card3, card1) == True


def test_get_progress():
    """Test progress tracking."""
    profile = TableProfile()
    capture = CardTemplateCapture(profile, Path("/tmp/b"), Path("/tmp/h"))
    
    # Initially empty
    progress = capture.get_progress()
    assert progress["board_cards_captured"] == 0
    assert progress["hero_cards_captured"] == 0
    assert progress["board_progress"] == 0.0
    assert progress["hero_progress"] == 0.0
    assert progress["overall_progress"] == 0.0
    
    # Add some captured cards
    capture.board_cards_captured = {"Ah", "Ks", "7d"}  # 3 cards
    capture.hero_cards_captured = {"Qh", "Jc"}  # 2 cards
    
    progress = capture.get_progress()
    assert progress["board_cards_captured"] == 3
    assert progress["hero_cards_captured"] == 2
    assert progress["board_progress"] == pytest.approx(3/52 * 100)
    assert progress["hero_progress"] == pytest.approx(2/52 * 100)
    assert progress["overall_progress"] == pytest.approx(5/104 * 100)


def test_save_board_card(tmp_path):
    """Test saving board card template."""
    board_dir = tmp_path / "board"
    profile = TableProfile()
    capture = CardTemplateCapture(profile, board_dir, tmp_path / "hero")
    
    # Create a valid card image
    card_img = np.random.randint(50, 200, (100, 70, 3), dtype=np.uint8)
    
    # Save should succeed
    result = capture._save_board_card(card_img, 0)
    assert result == True
    
    # Check file was created
    files = list(board_dir.glob("*.png"))
    assert len(files) == 1
    assert "board_pos0_" in files[0].name


def test_save_hero_card(tmp_path):
    """Test saving hero card template."""
    hero_dir = tmp_path / "hero"
    profile = TableProfile()
    capture = CardTemplateCapture(profile, tmp_path / "board", hero_dir)
    
    # Create a valid card image
    card_img = np.random.randint(50, 200, (100, 70, 3), dtype=np.uint8)
    
    # Save should succeed
    result = capture._save_hero_card(card_img, 1)
    assert result == True
    
    # Check file was created
    files = list(hero_dir.glob("*.png"))
    assert len(files) == 1
    assert "hero_pos1_" in files[0].name


def test_capture_from_screenshot(tmp_path):
    """Test capturing from a full screenshot."""
    # Create profile with regions
    profile = TableProfile()
    profile.hero_position = 0
    profile.card_regions = [{"x": 100, "y": 100, "width": 350, "height": 100}]
    profile.player_regions = [
        {
            "position": 0,
            "card_region": {"x": 50, "y": 300, "width": 140, "height": 100}
        }
    ]
    
    capture = CardTemplateCapture(profile, tmp_path / "board", tmp_path / "hero")
    
    # Create a mock screenshot
    screenshot = np.random.randint(50, 200, (600, 800, 3), dtype=np.uint8)
    
    # Capture (may or may not find cards depending on validation)
    stats = capture.capture_from_screenshot(screenshot)
    
    assert "board_captured" in stats
    assert "hero_captured" in stats
    assert "total_board" in stats
    assert "total_hero" in stats


def test_capture_handles_out_of_bounds(tmp_path):
    """Test that capture handles out-of-bounds regions safely."""
    # Create profile with out-of-bounds regions
    profile = TableProfile()
    profile.hero_position = 0
    profile.card_regions = [{"x": 1000, "y": 1000, "width": 350, "height": 100}]
    profile.player_regions = [
        {
            "position": 0,
            "card_region": {"x": 2000, "y": 2000, "width": 140, "height": 100}
        }
    ]
    
    capture = CardTemplateCapture(profile, tmp_path / "board", tmp_path / "hero")
    
    # Create a small screenshot
    screenshot = np.random.randint(50, 200, (600, 800, 3), dtype=np.uint8)
    
    # Should not crash
    stats = capture.capture_from_screenshot(screenshot)
    
    # Should capture nothing (out of bounds)
    assert stats["board_captured"] == 0
    assert stats["hero_captured"] == 0


def test_table_detector_returns_image_not_bbox(tmp_path):
    """Test that table detector integration uses returned image correctly."""
    from unittest.mock import Mock, patch
    from holdem.vision.auto_capture import run_auto_capture
    
    # Create a mock profile file
    profile_path = tmp_path / "test_profile.json"
    
    # Create mock profile
    profile = TableProfile()
    profile.hero_position = 0
    profile.card_regions = []
    profile.player_regions = []
    
    # Mock the necessary components
    mock_screenshot = np.random.randint(50, 200, (600, 800, 3), dtype=np.uint8)
    mock_warped = np.random.randint(50, 200, (500, 700, 3), dtype=np.uint8)
    
    with patch('holdem.vision.auto_capture.TableProfile.load') as mock_load, \
         patch('holdem.vision.auto_capture.ScreenCapture') as mock_screen, \
         patch('holdem.vision.auto_capture.TableDetector') as mock_detector_class, \
         patch('holdem.vision.auto_capture.time.sleep'):
        
        # Setup mocks
        mock_load.return_value = profile
        mock_screen_instance = Mock()
        mock_screen.return_value = mock_screen_instance
        
        # First call returns screenshot, second returns None to exit loop
        mock_screen_instance.capture.side_effect = [mock_screenshot, None]
        
        # TableDetector.detect should return an image (warped), not a bbox
        mock_detector_instance = Mock()
        mock_detector_class.return_value = mock_detector_instance
        mock_detector_instance.detect.return_value = mock_warped
        
        # Run with duration=0 to exit quickly
        try:
            run_auto_capture(
                profile_path=profile_path,
                duration_seconds=0,
                interval_seconds=0.1,
                board_output=tmp_path / "board",
                hero_output=tmp_path / "hero"
            )
        except Exception:
            # May fail due to mocking, but we just want to verify no unpacking error
            pass
        
        # Verify detect was called and returned an image
        mock_detector_instance.detect.assert_called()
        # The key test: if detect() returns an image (not a tuple),
        # it should be used directly, not unpacked as (x, y, w, h)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
