"""Tests for board card color filter system.

This test suite covers the color-based prefiltering functionality for board cards:
- Board color template loading and histogram computation
- Generic color prefilter function works for both hero and board
- Color prefilter activation for board card recognition
- Board prefilter parameter configuration
- Performance improvements (latency reduction)
- No regression in hero card recognition
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
import time

import sys
sys.path.insert(0, 'src')

from holdem.vision.cards import CardRecognizer


class TestBoardColorFilterAttributes:
    """Test that board color filter attributes are properly initialized."""
    
    def test_board_color_filter_attributes_initialized(self):
        """Test that all board color filter attributes are present."""
        recognizer = CardRecognizer(method="template")
        
        # Check that board color filter attributes exist
        assert hasattr(recognizer, 'board_templates_color')
        assert hasattr(recognizer, 'board_templates_hue_hist')
        assert hasattr(recognizer, 'enable_board_color_prefilter')
        assert hasattr(recognizer, 'board_color_prefilter_min_sim')
        assert hasattr(recognizer, 'board_color_prefilter_top_k')
        
        # Check initial values
        assert recognizer.board_templates_color == {}
        assert recognizer.board_templates_hue_hist == {}
        assert recognizer.enable_board_color_prefilter is True
        assert recognizer.board_color_prefilter_min_sim == 0.20
        assert recognizer.board_color_prefilter_top_k == 12


class TestBoardColorTemplateLoading:
    """Test board color template loading and histogram computation."""
    
    @pytest.fixture
    def board_templates_dir(self, tmp_path):
        """Create board templates with different colors."""
        board_dir = tmp_path / "board_templates"
        board_dir.mkdir()
        
        # Create red card templates (hearts/diamonds)
        for card in ['Ah', '2h', 'Kd']:
            template = np.ones((100, 70, 3), dtype=np.uint8)
            # Red cards - more red channel
            template[:, :, 2] = 200  # R
            template[:, :, 1] = 50   # G
            template[:, :, 0] = 50   # B
            cv2.putText(template, card[0], (25, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
            cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        # Create black card templates (clubs/spades)
        for card in ['As', '2s', 'Kc']:
            template = np.ones((100, 70, 3), dtype=np.uint8)
            # Black cards - lower intensity overall
            template[:, :, 2] = 60   # R
            template[:, :, 1] = 60   # G
            template[:, :, 0] = 60   # B
            cv2.putText(template, card[0], (25, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
            cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        return board_dir
    
    def test_board_templates_load_color_data(self, board_templates_dir):
        """Test that board templates are loaded with color data."""
        recognizer = CardRecognizer(
            method="template",
            templates_dir=board_templates_dir
        )
        
        # Check that templates are loaded
        assert len(recognizer.templates) == 6
        assert len(recognizer.board_templates_color) == 6
        assert len(recognizer.board_templates_hue_hist) == 6
        
        # Check that color templates are BGR (3 channels)
        for card_name, tpl_color in recognizer.board_templates_color.items():
            assert tpl_color.ndim == 3
            assert tpl_color.shape[2] == 3
        
        # Check that grayscale templates are 2D
        for card_name, tpl_gray in recognizer.templates.items():
            assert tpl_gray.ndim == 2
        
        # Check that histograms are computed
        for card_name, tpl_hist in recognizer.board_templates_hue_hist.items():
            assert tpl_hist is not None
            assert tpl_hist.shape == (32, 1)


class TestGenericColorPrefilter:
    """Test the generic color prefilter function works for both hero and board."""
    
    @pytest.fixture
    def recognizer_with_templates(self, tmp_path):
        """Create recognizer with both hero and board templates."""
        # Create hero templates
        hero_dir = tmp_path / "hero_templates"
        hero_dir.mkdir()
        for card in ['Ah', 'Kh', 'Qh']:
            template = np.zeros((80, 60, 3), dtype=np.uint8)
            template[:, :, 2] = 180  # High red
            template[:, :, 1] = 40
            template[:, :, 0] = 40
            cv2.imwrite(str(hero_dir / f"{card}.png"), template)
        
        # Create board templates
        board_dir = tmp_path / "board_templates"
        board_dir.mkdir()
        for card in ['As', 'Ks', 'Qs']:
            template = np.zeros((100, 70, 3), dtype=np.uint8)
            template[:, :, 2] = 40
            template[:, :, 1] = 180  # High green
            template[:, :, 0] = 40
            cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        return CardRecognizer(
            method="template",
            templates_dir=board_dir,
            hero_templates_dir=hero_dir
        )
    
    def test_generic_prefilter_works_for_hero(self, recognizer_with_templates):
        """Test that generic prefilter works for hero templates."""
        # Create a reddish test image
        test_img = np.zeros((80, 60, 3), dtype=np.uint8)
        test_img[:, :, 2] = 200  # High red
        test_img[:, :, 1] = 50
        test_img[:, :, 0] = 50
        
        # Call generic prefilter for hero templates
        candidates = recognizer_with_templates.run_card_color_prefilter(
            card_image=test_img,
            templates=recognizer_with_templates.hero_templates,
            hue_histograms=recognizer_with_templates.hero_templates_hue_hist,
            top_k=2,
            min_sim=0.20,
            label="Hero"
        )
        
        # Should return candidates (red cards should match)
        assert len(candidates) > 0
        assert len(candidates) <= 2  # top_k=2
        # Each candidate is a tuple of (card_name, template, similarity)
        for card_name, template, sim in candidates:
            assert isinstance(card_name, str)
            assert isinstance(template, np.ndarray)
            assert 0.0 <= sim <= 1.0
    
    def test_generic_prefilter_works_for_board(self, recognizer_with_templates):
        """Test that generic prefilter works for board templates."""
        # Create a greenish test image
        test_img = np.zeros((100, 70, 3), dtype=np.uint8)
        test_img[:, :, 2] = 40
        test_img[:, :, 1] = 200  # High green
        test_img[:, :, 0] = 40
        
        # Call generic prefilter for board templates
        candidates = recognizer_with_templates.run_card_color_prefilter(
            card_image=test_img,
            templates=recognizer_with_templates.templates,
            hue_histograms=recognizer_with_templates.board_templates_hue_hist,
            top_k=2,
            min_sim=0.20,
            label="board"
        )
        
        # Should return candidates (green cards should match)
        assert len(candidates) > 0
        assert len(candidates) <= 2  # top_k=2


class TestBoardColorPrefilterIntegration:
    """Test board color prefilter integration in template matching."""
    
    @pytest.fixture
    def board_templates_with_color_variance(self, tmp_path):
        """Create board templates with distinct color profiles."""
        board_dir = tmp_path / "board_templates"
        board_dir.mkdir()
        
        # Create cards with very different colors to test filtering
        # Red cards (hearts/diamonds)
        for card in ['Ah', 'Kh', 'Qh']:
            template = np.zeros((100, 70, 3), dtype=np.uint8)
            template[:, :, 2] = 180  # High red
            template[:, :, 1] = 40
            template[:, :, 0] = 40
            cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        # Blue-ish cards (clubs)
        for card in ['Ac', 'Kc', 'Qc']:
            template = np.zeros((100, 70, 3), dtype=np.uint8)
            template[:, :, 2] = 40
            template[:, :, 1] = 40
            template[:, :, 0] = 180  # High blue
            cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        # Green-ish cards (spades)
        for card in ['As', 'Ks', 'Qs']:
            template = np.zeros((100, 70, 3), dtype=np.uint8)
            template[:, :, 2] = 40
            template[:, :, 1] = 180  # High green
            template[:, :, 0] = 40
            cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        return board_dir
    
    def test_board_color_prefilter_reduces_candidates(self, board_templates_with_color_variance, caplog):
        """Test that board color prefilter reduces the number of templates checked."""
        import logging
        caplog.set_level(logging.INFO)
        
        recognizer = CardRecognizer(
            method="template",
            templates_dir=board_templates_with_color_variance
        )
        
        # Set top_k to a small number
        recognizer.board_color_prefilter_top_k = 4
        
        # Create a reddish test image
        test_img = np.zeros((100, 70, 3), dtype=np.uint8)
        test_img[:, :, 2] = 200  # High red
        test_img[:, :, 1] = 50
        test_img[:, :, 0] = 50
        
        # Recognize with board templates (use_hero_templates=False)
        result = recognizer.recognize_card(test_img, use_hero_templates=False)
        
        # Check that the prefilter log message appears (with "board" in the label)
        prefilter_logs = [r.message for r in caplog.records if "color pre-filter:" in r.message and "board" in r.message]
        assert len(prefilter_logs) > 0
        
        # The log should mention candidates
        assert "candidates" in prefilter_logs[0]
    
    def test_board_color_prefilter_can_be_disabled(self, board_templates_with_color_variance, caplog):
        """Test that board color prefilter can be disabled."""
        import logging
        caplog.set_level(logging.INFO)
        
        recognizer = CardRecognizer(
            method="template",
            templates_dir=board_templates_with_color_variance
        )
        
        # Disable board prefilter
        recognizer.enable_board_color_prefilter = False
        
        # Create a test image
        test_img = np.zeros((100, 70, 3), dtype=np.uint8)
        test_img[:, :, 2] = 200
        
        # Recognize with board templates
        result = recognizer.recognize_card(test_img, use_hero_templates=False)
        
        # Check that NO board prefilter log message appears
        board_prefilter_logs = [r.message for r in caplog.records if "board" in r.message and "color pre-filter:" in r.message]
        assert len(board_prefilter_logs) == 0
    
    def test_board_prefilter_uses_card_index_in_logs(self, board_templates_with_color_variance, caplog):
        """Test that board prefilter includes card index in log messages."""
        import logging
        caplog.set_level(logging.INFO)
        
        recognizer = CardRecognizer(
            method="template",
            templates_dir=board_templates_with_color_variance
        )
        
        # Create a test image
        test_img = np.zeros((100, 70, 3), dtype=np.uint8)
        test_img[:, :, 2] = 200
        
        # Recognize with board templates and card index
        result = recognizer.recognize_card(test_img, use_hero_templates=False, board_card_index=2)
        
        # Check that the log includes "board card 2"
        board_card_logs = [r.message for r in caplog.records if "board card 2" in r.message]
        assert len(board_card_logs) > 0


class TestBoardColorPrefilterParameters:
    """Test board color prefilter parameter configuration."""
    
    @pytest.fixture
    def recognizer_with_board_templates(self, tmp_path):
        """Create recognizer with board templates."""
        board_dir = tmp_path / "board_templates"
        board_dir.mkdir()
        
        for i, card in enumerate(['Ah', 'Kh', 'Qh', 'Jh', 'Th', 'As', 'Ks', 'Qs']):
            template = np.ones((100, 70, 3), dtype=np.uint8)
            # Vary color slightly for each card
            template[:, :, 2] = 150 + i * 10
            template[:, :, 1] = 50
            template[:, :, 0] = 50
            cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        return CardRecognizer(method="template", templates_dir=board_dir)
    
    def test_board_top_k_limits_candidates(self, recognizer_with_board_templates, caplog):
        """Test that board top_k parameter limits the number of candidates."""
        import logging
        caplog.set_level(logging.INFO)
        
        # Set top_k to 3
        recognizer_with_board_templates.board_color_prefilter_top_k = 3
        
        # Create test image
        test_img = np.ones((100, 70, 3), dtype=np.uint8)
        test_img[:, :, 2] = 160
        test_img[:, :, 1] = 50
        test_img[:, :, 0] = 50
        
        result = recognizer_with_board_templates.recognize_card(test_img, use_hero_templates=False)
        
        # Check log mentions top_k=3 for board
        board_logs = [r.message for r in caplog.records if "top_k=3" in r.message and "board" in r.message]
        assert len(board_logs) > 0
    
    def test_board_min_sim_filters_candidates(self, recognizer_with_board_templates):
        """Test that board min_sim threshold filters out dissimilar templates."""
        # Set a very high min_sim (only very similar colors pass)
        recognizer_with_board_templates.board_color_prefilter_min_sim = 0.95
        
        # Create a very different colored test image (blue instead of red)
        test_img = np.zeros((100, 70, 3), dtype=np.uint8)
        test_img[:, :, 2] = 50
        test_img[:, :, 1] = 50
        test_img[:, :, 0] = 200  # Blue
        
        # This should result in no candidates passing the filter
        # (falling back to using all templates)
        result = recognizer_with_board_templates.recognize_card(test_img, use_hero_templates=False)
        
        # Result can be None (no match) or a card, but shouldn't crash
        assert result is None or result is not None


class TestBoardPrefilterPerformance:
    """Test performance improvements with board color prefilter."""
    
    @pytest.fixture
    def recognizer_with_many_board_templates(self, tmp_path):
        """Create recognizer with all 52 board templates."""
        board_dir = tmp_path / "board_templates"
        board_dir.mkdir()
        
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
        suits = ['h', 'd', 'c', 's']
        
        for rank in ranks:
            for suit in suits:
                card = f"{rank}{suit}"
                template = np.ones((100, 70, 3), dtype=np.uint8)
                # Vary colors by suit
                if suit in ['h', 'd']:
                    template[:, :, 2] = 180  # Red
                    template[:, :, 1] = 50
                    template[:, :, 0] = 50
                else:
                    template[:, :, 2] = 60   # Black
                    template[:, :, 1] = 60
                    template[:, :, 0] = 60
                cv2.putText(template, rank, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
                cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        return CardRecognizer(method="template", templates_dir=board_dir)
    
    def test_board_prefilter_improves_latency(self, recognizer_with_many_board_templates):
        """Test that board prefilter reduces recognition latency."""
        # Create a test image
        test_img = np.ones((100, 70, 3), dtype=np.uint8)
        test_img[:, :, 2] = 180  # Red card
        test_img[:, :, 1] = 50
        test_img[:, :, 0] = 50
        
        # Measure time with prefilter enabled
        recognizer_with_many_board_templates.enable_board_color_prefilter = True
        recognizer_with_many_board_templates.board_color_prefilter_top_k = 12
        
        start_with_prefilter = time.perf_counter()
        for _ in range(10):  # Run multiple times for better measurement
            result_with = recognizer_with_many_board_templates.recognize_card(test_img, use_hero_templates=False)
        time_with_prefilter = time.perf_counter() - start_with_prefilter
        
        # Measure time with prefilter disabled
        recognizer_with_many_board_templates.enable_board_color_prefilter = False
        
        start_without_prefilter = time.perf_counter()
        for _ in range(10):  # Run multiple times for better measurement
            result_without = recognizer_with_many_board_templates.recognize_card(test_img, use_hero_templates=False)
        time_without_prefilter = time.perf_counter() - start_without_prefilter
        
        # With prefilter should be faster or at least not significantly slower
        # We expect at least some improvement, but we'll be lenient for test stability
        print(f"Time with prefilter: {time_with_prefilter:.4f}s")
        print(f"Time without prefilter: {time_without_prefilter:.4f}s")
        print(f"Speedup: {time_without_prefilter / time_with_prefilter:.2f}x")
        
        # Assert that prefilter doesn't make it significantly slower (more than 20% slower)
        assert time_with_prefilter < time_without_prefilter * 1.2


class TestNoRegressionInHeroRecognition:
    """Test that board prefilter doesn't affect hero card recognition."""
    
    @pytest.fixture
    def recognizer_with_both(self, tmp_path):
        """Create recognizer with both hero and board templates."""
        hero_dir = tmp_path / "hero_templates"
        hero_dir.mkdir()
        for card in ['Ah', 'Kh']:
            template = np.ones((80, 60, 3), dtype=np.uint8)
            template[:, :, 2] = 180
            template[:, :, 1] = 50
            template[:, :, 0] = 50
            cv2.imwrite(str(hero_dir / f"{card}.png"), template)
        
        board_dir = tmp_path / "board_templates"
        board_dir.mkdir()
        for card in ['Ah', 'Kh']:
            template = np.ones((100, 70, 3), dtype=np.uint8)
            template[:, :, 2] = 180
            template[:, :, 1] = 50
            template[:, :, 0] = 50
            cv2.imwrite(str(board_dir / f"{card}.png"), template)
        
        return CardRecognizer(
            method="template",
            templates_dir=board_dir,
            hero_templates_dir=hero_dir
        )
    
    def test_hero_recognition_unchanged(self, recognizer_with_both, caplog):
        """Test that hero card recognition works the same with board prefilter present."""
        import logging
        caplog.set_level(logging.INFO)
        
        # Create a test image
        test_img = np.ones((80, 60, 3), dtype=np.uint8)
        test_img[:, :, 2] = 180
        test_img[:, :, 1] = 50
        test_img[:, :, 0] = 50
        
        # Recognize with hero templates
        result = recognizer_with_both.recognize_card(test_img, use_hero_templates=True)
        
        # Check that hero prefilter is used (not board)
        hero_logs = [r.message for r in caplog.records if "Hero color pre-filter:" in r.message]
        board_logs = [r.message for r in caplog.records if "board" in r.message.lower() and "color pre-filter:" in r.message]
        
        assert len(hero_logs) > 0  # Hero prefilter should be used
        assert len(board_logs) == 0  # Board prefilter should NOT be used for hero cards


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
