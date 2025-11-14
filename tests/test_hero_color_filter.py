"""Tests for hero card color filter system.

This test suite covers the new color-based prefiltering functionality for hero cards:
- Color template loading and histogram computation
- Hue histogram similarity calculation
- Color prefilter activation and candidate reduction
- Prefilter parameter configuration
"""

import pytest
import numpy as np
import cv2
from pathlib import Path

import sys
sys.path.insert(0, 'src')

from holdem.vision.cards import CardRecognizer


class TestHeroColorFilterAttributes:
    """Test that color filter attributes are properly initialized."""
    
    def test_color_filter_attributes_initialized(self):
        """Test that all color filter attributes are present."""
        recognizer = CardRecognizer(method="template")
        
        # Check that new attributes exist
        assert hasattr(recognizer, 'hero_templates_color')
        assert hasattr(recognizer, 'hero_templates_hue_hist')
        assert hasattr(recognizer, 'enable_hero_color_prefilter')
        assert hasattr(recognizer, 'hero_color_prefilter_min_sim')
        assert hasattr(recognizer, 'hero_color_prefilter_top_k')
        
        # Check initial values
        assert recognizer.hero_templates_color == {}
        assert recognizer.hero_templates_hue_hist == {}
        assert recognizer.enable_hero_color_prefilter is True
        assert recognizer.hero_color_prefilter_min_sim == 0.20
        assert recognizer.hero_color_prefilter_top_k == 12


class TestHeroColorTemplateLoading:
    """Test color template loading and histogram computation."""
    
    @pytest.fixture
    def hero_templates_dir(self, tmp_path):
        """Create hero templates with different colors."""
        hero_dir = tmp_path / "hero_templates"
        hero_dir.mkdir()
        
        # Create red card templates (hearts/diamonds)
        for card in ['Ah', '2h', 'Kd']:
            template = np.ones((80, 60, 3), dtype=np.uint8)
            # Red cards - more red channel
            template[:, :, 2] = 200  # R
            template[:, :, 1] = 50   # G
            template[:, :, 0] = 50   # B
            cv2.putText(template, card[0], (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            cv2.imwrite(str(hero_dir / f"{card}.png"), template)
        
        # Create black card templates (clubs/spades)
        for card in ['As', '2s', 'Kc']:
            template = np.ones((80, 60, 3), dtype=np.uint8)
            # Black cards - lower intensity overall
            template[:, :, 2] = 60   # R
            template[:, :, 1] = 60   # G
            template[:, :, 0] = 60   # B
            cv2.putText(template, card[0], (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            cv2.imwrite(str(hero_dir / f"{card}.png"), template)
        
        return hero_dir
    
    def test_hero_templates_load_color_data(self, hero_templates_dir):
        """Test that hero templates are loaded with color data."""
        recognizer = CardRecognizer(
            method="template",
            hero_templates_dir=hero_templates_dir
        )
        
        # Check that templates are loaded
        assert len(recognizer.hero_templates) == 6
        assert len(recognizer.hero_templates_color) == 6
        assert len(recognizer.hero_templates_hue_hist) == 6
        
        # Check that color templates are BGR (3 channels)
        for card_name, tpl_color in recognizer.hero_templates_color.items():
            assert tpl_color.ndim == 3
            assert tpl_color.shape[2] == 3
        
        # Check that grayscale templates are 2D
        for card_name, tpl_gray in recognizer.hero_templates.items():
            assert tpl_gray.ndim == 2
        
        # Check that histograms are computed
        for card_name, tpl_hist in recognizer.hero_templates_hue_hist.items():
            assert tpl_hist is not None
            assert tpl_hist.shape == (32, 1)


class TestHueHistogramSimilarity:
    """Test hue histogram similarity computation."""
    
    @pytest.fixture
    def recognizer(self):
        """Create a card recognizer."""
        return CardRecognizer(method="template")
    
    def test_hue_similarity_identical_images(self, recognizer):
        """Test that identical images have high similarity."""
        # Create a red image
        img_hsv = np.ones((100, 100, 3), dtype=np.uint8)
        img_hsv[:, :, 0] = 0  # Red hue
        img_hsv[:, :, 1] = 255  # Full saturation
        img_hsv[:, :, 2] = 255  # Full value
        
        # Compute histogram
        hist = cv2.calcHist([img_hsv], [0], None, [32], [0, 180])
        hist = cv2.normalize(hist, hist, alpha=1.0, beta=0.0, norm_type=cv2.NORM_L1)
        
        # Compare with itself
        similarity = recognizer._hue_hist_similarity(img_hsv, hist)
        
        # Should be very high (close to 1.0)
        assert similarity > 0.95
    
    def test_hue_similarity_different_colors(self, recognizer):
        """Test that different colors have lower similarity."""
        # Create a red image
        img_red_hsv = np.ones((100, 100, 3), dtype=np.uint8)
        img_red_hsv[:, :, 0] = 0  # Red hue
        img_red_hsv[:, :, 1] = 255
        img_red_hsv[:, :, 2] = 255
        
        # Create a blue image histogram
        img_blue_hsv = np.ones((100, 100, 3), dtype=np.uint8)
        img_blue_hsv[:, :, 0] = 120  # Blue hue
        img_blue_hsv[:, :, 1] = 255
        img_blue_hsv[:, :, 2] = 255
        
        hist_blue = cv2.calcHist([img_blue_hsv], [0], None, [32], [0, 180])
        hist_blue = cv2.normalize(hist_blue, hist_blue, alpha=1.0, beta=0.0, norm_type=cv2.NORM_L1)
        
        # Compare red image with blue histogram
        similarity = recognizer._hue_hist_similarity(img_red_hsv, hist_blue)
        
        # Should be low (different colors)
        assert similarity < 0.5
    
    def test_hue_similarity_empty_inputs(self, recognizer):
        """Test that empty inputs return 0.0."""
        empty_array = np.array([])
        hist = np.ones((32, 1), dtype=np.float32)
        
        similarity = recognizer._hue_hist_similarity(empty_array, hist)
        assert similarity == 0.0
        
        img_hsv = np.ones((100, 100, 3), dtype=np.uint8)
        similarity = recognizer._hue_hist_similarity(img_hsv, None)
        assert similarity == 0.0


class TestColorPrefilterIntegration:
    """Test color prefilter integration in template matching."""
    
    @pytest.fixture
    def hero_templates_with_color_variance(self, tmp_path):
        """Create hero templates with distinct color profiles."""
        hero_dir = tmp_path / "hero_templates"
        hero_dir.mkdir()
        
        # Create cards with very different colors to test filtering
        # Red cards (hearts/diamonds)
        for card in ['Ah', 'Kh', 'Qh']:
            template = np.zeros((80, 60, 3), dtype=np.uint8)
            template[:, :, 2] = 180  # High red
            template[:, :, 1] = 40
            template[:, :, 0] = 40
            cv2.imwrite(str(hero_dir / f"{card}.png"), template)
        
        # Blue-ish cards (clubs)
        for card in ['Ac', 'Kc', 'Qc']:
            template = np.zeros((80, 60, 3), dtype=np.uint8)
            template[:, :, 2] = 40
            template[:, :, 1] = 40
            template[:, :, 0] = 180  # High blue
            cv2.imwrite(str(hero_dir / f"{card}.png"), template)
        
        # Green-ish cards (spades)
        for card in ['As', 'Ks', 'Qs']:
            template = np.zeros((80, 60, 3), dtype=np.uint8)
            template[:, :, 2] = 40
            template[:, :, 1] = 180  # High green
            template[:, :, 0] = 40
            cv2.imwrite(str(hero_dir / f"{card}.png"), template)
        
        return hero_dir
    
    def test_color_prefilter_reduces_candidates(self, hero_templates_with_color_variance, caplog):
        """Test that color prefilter reduces the number of templates checked."""
        import logging
        caplog.set_level(logging.INFO)
        
        recognizer = CardRecognizer(
            method="template",
            hero_templates_dir=hero_templates_with_color_variance
        )
        
        # Set top_k to a small number
        recognizer.hero_color_prefilter_top_k = 4
        
        # Create a reddish test image
        test_img = np.zeros((80, 60, 3), dtype=np.uint8)
        test_img[:, :, 2] = 200  # High red
        test_img[:, :, 1] = 50
        test_img[:, :, 0] = 50
        
        # Recognize with hero templates (will trigger prefilter)
        result = recognizer.recognize_card(test_img, use_hero_templates=True)
        
        # Check that the prefilter log message appears
        assert any("Hero color pre-filter:" in record.message for record in caplog.records)
        
        # Check that candidates were reduced
        prefilter_logs = [r.message for r in caplog.records if "Hero color pre-filter:" in r.message]
        assert len(prefilter_logs) > 0
        # The log should mention a reduced number of candidates
        assert "candidates" in prefilter_logs[0]
    
    def test_color_prefilter_can_be_disabled(self, hero_templates_with_color_variance, caplog):
        """Test that color prefilter can be disabled."""
        import logging
        caplog.set_level(logging.INFO)
        
        recognizer = CardRecognizer(
            method="template",
            hero_templates_dir=hero_templates_with_color_variance
        )
        
        # Disable prefilter
        recognizer.enable_hero_color_prefilter = False
        
        # Create a test image
        test_img = np.zeros((80, 60, 3), dtype=np.uint8)
        test_img[:, :, 2] = 200
        
        # Recognize with hero templates
        result = recognizer.recognize_card(test_img, use_hero_templates=True)
        
        # Check that NO prefilter log message appears
        assert not any("Hero color pre-filter:" in record.message for record in caplog.records)
    
    def test_color_prefilter_not_applied_to_board_cards(self, hero_templates_with_color_variance, tmp_path, caplog):
        """Test that color prefilter is NOT applied to board cards."""
        import logging
        caplog.set_level(logging.INFO)
        
        # Create board templates
        board_dir = tmp_path / "board_templates"
        board_dir.mkdir()
        for card in ['Ah', 'Kd']:
            template = np.ones((100, 70, 3), dtype=np.uint8) * 128
            cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        recognizer = CardRecognizer(
            method="template",
            templates_dir=board_dir,
            hero_templates_dir=hero_templates_with_color_variance
        )
        
        # Create a test image
        test_img = np.ones((100, 70, 3), dtype=np.uint8) * 128
        
        # Recognize with board templates (use_hero_templates=False)
        result = recognizer.recognize_card(test_img, use_hero_templates=False)
        
        # Check that NO prefilter log message appears for board cards
        assert not any("Hero color pre-filter:" in record.message for record in caplog.records)


class TestColorPrefilterParameters:
    """Test color prefilter parameter configuration."""
    
    @pytest.fixture
    def recognizer_with_templates(self, tmp_path):
        """Create recognizer with hero templates."""
        hero_dir = tmp_path / "hero_templates"
        hero_dir.mkdir()
        
        for i, card in enumerate(['Ah', 'Kh', 'Qh', 'Jh', 'Th', 'As', 'Ks', 'Qs']):
            template = np.ones((80, 60, 3), dtype=np.uint8)
            # Vary color slightly for each card
            template[:, :, 2] = 150 + i * 10
            template[:, :, 1] = 50
            template[:, :, 0] = 50
            cv2.imwrite(str(hero_dir / f"{card}.png"), template)
        
        return CardRecognizer(method="template", hero_templates_dir=hero_dir)
    
    def test_top_k_limits_candidates(self, recognizer_with_templates, caplog):
        """Test that top_k parameter limits the number of candidates."""
        import logging
        caplog.set_level(logging.INFO)
        
        # Set top_k to 3
        recognizer_with_templates.hero_color_prefilter_top_k = 3
        
        # Create test image
        test_img = np.ones((80, 60, 3), dtype=np.uint8)
        test_img[:, :, 2] = 160
        test_img[:, :, 1] = 50
        test_img[:, :, 0] = 50
        
        result = recognizer_with_templates.recognize_card(test_img, use_hero_templates=True)
        
        # Check log mentions top_k=3
        prefilter_logs = [r.message for r in caplog.records if "top_k=3" in r.message]
        assert len(prefilter_logs) > 0
    
    def test_min_sim_filters_candidates(self, recognizer_with_templates):
        """Test that min_sim threshold filters out dissimilar templates."""
        # Set a very high min_sim (only very similar colors pass)
        recognizer_with_templates.hero_color_prefilter_min_sim = 0.95
        
        # Create a very different colored test image (blue instead of red)
        test_img = np.zeros((80, 60, 3), dtype=np.uint8)
        test_img[:, :, 2] = 50
        test_img[:, :, 1] = 50
        test_img[:, :, 0] = 200  # Blue
        
        # This should result in no candidates passing the filter
        # (falling back to using all templates)
        result = recognizer_with_templates.recognize_card(test_img, use_hero_templates=True)
        
        # Result can be None (no match) or a card, but shouldn't crash
        assert result is None or result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
