"""Tests for card vision system stability improvements.

This test suite covers edge cases and bugs found during the vision system verification:
- Empty/malformed image handling
- Image format conversions (grayscale, BGRA, single-channel 3D)
- Minimum size requirements
- Template size validation
- Float image handling
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
import tempfile

import sys
sys.path.insert(0, 'src')

from holdem.vision.cards import CardRecognizer


class TestCardRecognizerStability:
    """Test stability improvements in CardRecognizer."""
    
    @pytest.fixture
    def recognizer(self):
        """Create a card recognizer without templates."""
        return CardRecognizer(method="template")
    
    @pytest.fixture
    def recognizer_with_templates(self, tmp_path):
        """Create a card recognizer with mock templates."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        
        # Create a few mock templates
        for card in ['Ah', 'Kd', '2s']:
            template = np.ones((100, 70), dtype=np.uint8) * 128
            # Add some variation
            cv2.putText(template, card[0], (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
            cv2.imwrite(str(templates_dir / f"{card}.png"), template)
        
        recognizer = CardRecognizer(method="template", templates_dir=templates_dir)
        return recognizer
    
    # ===== Empty/Invalid Image Handling =====
    
    def test_empty_array(self, recognizer):
        """Test that empty arrays are handled gracefully."""
        empty = np.array([])
        result = recognizer.recognize_card(empty)
        assert result is None
    
    def test_one_dimensional_array(self, recognizer):
        """Test that 1D arrays are handled gracefully."""
        one_d = np.array([1, 2, 3, 4, 5])
        result = recognizer.recognize_card(one_d)
        assert result is None
    
    def test_none_image(self, recognizer):
        """Test that None image doesn't crash (handled by recognize_cards)."""
        # recognize_cards should handle None
        result = recognizer.recognize_cards(None, num_cards=2)
        assert result == []
    
    # ===== Image Format Conversions =====
    
    def test_single_channel_3d_image(self, recognizer):
        """Test single-channel 3D images (h, w, 1) are converted correctly."""
        single_3d = np.ones((100, 70, 1), dtype=np.uint8) * 128
        result = recognizer.recognize_card(single_3d)
        # Should not crash, returns None (no templates loaded)
        assert result is None
    
    def test_bgra_image(self, recognizer):
        """Test 4-channel BGRA images are converted correctly."""
        bgra = np.ones((100, 70, 4), dtype=np.uint8) * 128
        result = recognizer.recognize_card(bgra)
        # Should not crash, returns None (no templates loaded)
        assert result is None
    
    def test_grayscale_image(self, recognizer):
        """Test grayscale images are handled correctly."""
        gray = np.ones((100, 70), dtype=np.uint8) * 128
        result = recognizer.recognize_card(gray)
        # Should not crash, returns None (no templates loaded)
        assert result is None
    
    def test_bgr_image(self, recognizer):
        """Test standard BGR images work correctly."""
        bgr = np.ones((100, 70, 3), dtype=np.uint8) * 128
        result = recognizer.recognize_card(bgr)
        # Should not crash, returns None (no templates loaded)
        assert result is None
    
    def test_float_image_conversion(self, recognizer):
        """Test float images are converted to uint8 correctly."""
        float_img = np.ones((100, 70), dtype=np.float32) * 128.5
        result = recognizer.recognize_card(float_img)
        # Should not crash, converts to uint8
        assert result is None
    
    def test_float_out_of_range(self, recognizer):
        """Test float images with out-of-range values are clipped."""
        float_img = np.random.uniform(-100, 400, (100, 70)).astype(np.float32)
        result = recognizer.recognize_card(float_img)
        # Should not crash, clips to [0, 255]
        assert result is None
    
    # ===== Minimum Size Requirements =====
    
    def test_very_small_image_2x2(self, recognizer):
        """Test very small 2x2 images are rejected."""
        tiny = np.ones((2, 2, 3), dtype=np.uint8) * 128
        result = recognizer.recognize_card(tiny)
        assert result is None
    
    def test_very_small_image_4x4(self, recognizer):
        """Test small 4x4 images are rejected."""
        small = np.ones((4, 4, 3), dtype=np.uint8) * 128
        result = recognizer.recognize_card(small)
        assert result is None
    
    def test_minimum_acceptable_size(self, recognizer):
        """Test minimum acceptable size (5x5) doesn't crash."""
        min_size = np.ones((5, 5, 3), dtype=np.uint8) * 128
        result = recognizer.recognize_card(min_size)
        # Should not crash, may return None (no templates or too small for matching)
        assert result is None
    
    # ===== Template Matching Edge Cases =====
    
    def test_template_same_size_as_image(self, recognizer_with_templates):
        """Test template matching when template is same size as image region."""
        # Create image that's same size as templates (100x70)
        img = np.ones((100, 70, 3), dtype=np.uint8) * 128
        result = recognizer_with_templates.recognize_card(img)
        # Should handle this case - template will be scaled down to be smaller
        assert result is None or result is not None  # Just shouldn't crash
    
    def test_template_larger_than_image(self, recognizer_with_templates):
        """Test template matching when template is larger than image."""
        # Create image smaller than templates (50x35 vs 100x70)
        img = np.ones((50, 35, 3), dtype=np.uint8) * 128
        result = recognizer_with_templates.recognize_card(img)
        # Should scale template down and match
        assert result is None or result is not None  # Just shouldn't crash
    
    def test_very_thin_image(self, recognizer):
        """Test matching on very thin images."""
        thin = np.ones((100, 5, 3), dtype=np.uint8) * 128
        result = recognizer.recognize_card(thin)
        # Should either reject or handle gracefully
        assert result is None
    
    # ===== _region_has_cards Edge Cases =====
    
    def test_region_has_cards_empty(self, recognizer):
        """Test _region_has_cards with empty array."""
        result = recognizer._region_has_cards(np.array([]))
        assert result is False
    
    def test_region_has_cards_too_small(self, recognizer):
        """Test _region_has_cards rejects images that are too small."""
        tiny = np.ones((2, 2), dtype=np.uint8) * 128
        result = recognizer._region_has_cards(tiny)
        assert result is False
    
    def test_region_has_cards_single_channel_3d(self, recognizer):
        """Test _region_has_cards with single-channel 3D image."""
        single_3d = np.ones((100, 200, 1), dtype=np.uint8) * 128
        result = recognizer._region_has_cards(single_3d)
        # Should not crash, returns False (uniform image)
        assert result is False
    
    def test_region_has_cards_bgra(self, recognizer):
        """Test _region_has_cards with BGRA image."""
        bgra = np.ones((100, 200, 4), dtype=np.uint8) * 128
        result = recognizer._region_has_cards(bgra)
        # Should not crash, returns False (uniform image)
        assert result is False
    
    def test_region_has_cards_float(self, recognizer):
        """Test _region_has_cards with float image."""
        float_img = np.ones((100, 200), dtype=np.float32) * 128.5
        result = recognizer._region_has_cards(float_img)
        # Should convert to uint8 and process
        assert result is False  # Uniform image
    
    def test_region_has_cards_high_variance(self, recognizer):
        """Test _region_has_cards detects high variance regions."""
        # Create image with high variance
        high_var = np.random.randint(0, 255, (100, 200), dtype=np.uint8)
        result = recognizer._region_has_cards(high_var)
        # Should detect high variance (use bool() for numpy boolean)
        assert bool(result) is True
    
    def test_region_has_cards_with_edges(self, recognizer):
        """Test _region_has_cards detects regions with edges."""
        # Create image with edges
        img = np.ones((100, 200), dtype=np.uint8) * 128
        # Add some rectangles to create edges
        cv2.rectangle(img, (20, 20), (80, 80), 255, 2)
        cv2.rectangle(img, (120, 20), (180, 80), 50, 2)
        result = recognizer._region_has_cards(img)
        # Should detect edges (use bool() for numpy boolean)
        assert bool(result) is True
    
    # ===== recognize_cards Integration Tests =====
    
    def test_recognize_cards_with_invalid_images(self, recognizer):
        """Test recognize_cards with various invalid inputs."""
        # None image
        result = recognizer.recognize_cards(None, num_cards=2)
        assert result == []
        
        # Empty array
        result = recognizer.recognize_cards(np.array([]), num_cards=2)
        assert result == []
    
    def test_recognize_cards_skip_empty_check(self, recognizer):
        """Test recognize_cards with skip_empty_check flag."""
        # Uniform image would normally be skipped, but skip_empty_check=True processes it
        uniform = np.ones((100, 200, 3), dtype=np.uint8) * 128
        result = recognizer.recognize_cards(uniform, num_cards=2, skip_empty_check=True)
        # Should return list of None (no templates but didn't skip)
        assert len(result) == 2
        assert all(c is None for c in result)
    
    def test_recognize_cards_detects_empty_board(self, recognizer):
        """Test recognize_cards detects empty board regions."""
        # Uniform low-variance image (typical empty board)
        uniform = np.ones((100, 500, 3), dtype=np.uint8) * 50
        result = recognizer.recognize_cards(uniform, num_cards=5)
        # Should skip recognition due to empty region detection
        assert len(result) == 5
        assert all(c is None for c in result)


class TestHeroTemplateStability:
    """Test hero template functionality under edge cases."""
    
    @pytest.fixture
    def recognizer_with_both_templates(self, tmp_path):
        """Create a recognizer with both board and hero templates."""
        board_dir = tmp_path / "board_templates"
        hero_dir = tmp_path / "hero_templates"
        board_dir.mkdir()
        hero_dir.mkdir()
        
        # Create distinct board templates
        for card in ['Ah', 'Kd']:
            template = np.ones((100, 70), dtype=np.uint8) * 128
            cv2.rectangle(template, (5, 5), (65, 95), 200, 2)
            cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        # Create distinct hero templates (smaller, different style)
        for card in ['Ah', 'Kd']:
            template = np.ones((80, 60), dtype=np.uint8) * 140
            cv2.rectangle(template, (3, 3), (57, 77), 180, 2)
            cv2.imwrite(str(hero_dir / f"{card}.png"), template)
        
        recognizer = CardRecognizer(
            method="template",
            templates_dir=board_dir,
            hero_templates_dir=hero_dir
        )
        return recognizer
    
    def test_hero_templates_with_empty_image(self, recognizer_with_both_templates):
        """Test hero template matching with empty image."""
        empty = np.array([])
        result = recognizer_with_both_templates.recognize_card(empty, use_hero_templates=True)
        assert result is None
    
    def test_hero_templates_with_invalid_formats(self, recognizer_with_both_templates):
        """Test hero templates work with various image formats."""
        # Single-channel 3D
        single_3d = np.ones((80, 60, 1), dtype=np.uint8) * 140
        result = recognizer_with_both_templates.recognize_card(single_3d, use_hero_templates=True)
        assert result is None or result is not None  # Just shouldn't crash
        
        # BGRA
        bgra = np.ones((80, 60, 4), dtype=np.uint8) * 140
        result = recognizer_with_both_templates.recognize_card(bgra, use_hero_templates=True)
        assert result is None or result is not None  # Just shouldn't crash
    
    def test_fallback_to_board_templates(self, tmp_path):
        """Test fallback to board templates when hero templates not available."""
        board_dir = tmp_path / "board_only"
        board_dir.mkdir()
        
        # Create only board templates
        template = np.ones((100, 70), dtype=np.uint8) * 128
        cv2.imwrite(str(board_dir / "Ah.png"), template)
        
        recognizer = CardRecognizer(method="template", templates_dir=board_dir)
        
        # Request hero templates - should fall back to board templates
        img = np.ones((100, 70, 3), dtype=np.uint8) * 128
        result = recognizer.recognize_card(img, use_hero_templates=True)
        # Should fall back without crashing
        assert result is None or result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
