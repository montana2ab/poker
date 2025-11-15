"""Tests for safe click functionality."""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from holdem.control.safe_click import (
    safe_click_action_button,
    _analyze_button_pixels,
    safe_click_with_fallback
)


@pytest.fixture
def mock_screen_capture():
    """Mock screen capture that returns test images."""
    with patch('holdem.control.safe_click.ScreenCapture') as mock:
        yield mock


def create_light_button_image(width=60, height=30):
    """Create a mock image of a light-colored action button."""
    # Gray/light background (typical for action buttons)
    img = np.ones((height, width, 3), dtype=np.uint8) * 180  # Light gray
    return img


def create_checkbox_image(width=60, height=30):
    """Create a mock image with checkbox UI elements."""
    # Dark background with checkbox outline
    img = np.ones((height, width, 3), dtype=np.uint8) * 50  # Dark background
    
    # Add a dark checkbox square on the left side
    checkbox_x = int(width * 0.25)
    checkbox_y = height // 2
    checkbox_size = 5
    
    # Draw dark checkbox outline
    for i in range(-checkbox_size, checkbox_size):
        for j in range(-checkbox_size, checkbox_size):
            x = checkbox_x + i
            y = checkbox_y + j
            if 0 <= x < width and 0 <= y < height:
                img[y, x] = [30, 30, 30]  # Very dark
    
    return img


def create_dark_background_image(width=60, height=30):
    """Create a mock image with dark background (button not rendered yet)."""
    # Dark background
    img = np.ones((height, width, 3), dtype=np.uint8) * 40
    return img


class TestAnalyzeButtonPixels:
    """Tests for pixel analysis function."""
    
    def test_light_button_is_valid(self):
        """Test that a light button image is recognized as valid."""
        img = create_light_button_image()
        assert _analyze_button_pixels(img, 60, 30) is True
    
    def test_checkbox_is_invalid(self):
        """Test that a checkbox image is recognized as invalid."""
        img = create_checkbox_image()
        assert _analyze_button_pixels(img, 60, 30) is False
    
    def test_dark_background_is_invalid(self):
        """Test that a dark background is recognized as invalid."""
        img = create_dark_background_image()
        assert _analyze_button_pixels(img, 60, 30) is False
    
    def test_empty_image_is_invalid(self):
        """Test that an empty/None image is handled correctly."""
        assert _analyze_button_pixels(None, 60, 30) is False
        assert _analyze_button_pixels(np.array([]), 60, 30) is False
    
    def test_grayscale_image(self):
        """Test that grayscale images are handled correctly."""
        # Light grayscale image (valid button)
        gray_img = np.ones((30, 60), dtype=np.uint8) * 180
        assert _analyze_button_pixels(gray_img, 60, 30) is True
        
        # Dark grayscale image (invalid)
        dark_gray_img = np.ones((30, 60), dtype=np.uint8) * 40
        assert _analyze_button_pixels(dark_gray_img, 60, 30) is False
    
    def test_mixed_luminance(self):
        """Test images with mixed luminance values."""
        img = np.ones((30, 60, 3), dtype=np.uint8) * 150  # Medium-light gray
        
        # Add dark checkbox area on the left
        checkbox_x = int(60 * 0.25)
        img[:, :checkbox_x] = 30  # Dark left side
        
        # The center is medium-light (150/255 = 0.59), which is just above threshold (0.5)
        # So this should actually be accepted as valid (center is light enough)
        # The left is dark but the center passes the threshold
        assert _analyze_button_pixels(img, 60, 30) is True


class TestSafeClickActionButton:
    """Tests for safe_click_action_button function."""
    
    def test_valid_button_click(self, mock_screen_capture):
        """Test that a valid button is clicked successfully."""
        # Mock screen capture to return a light button image
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = create_light_button_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result = safe_click_action_button(x=300, y=400, width=80, height=40, label="Call")
            
            assert result is True
            mock_pyautogui.click.assert_called_once_with(300, 400)
    
    def test_checkbox_detection_prevents_click(self, mock_screen_capture):
        """Test that checkbox detection prevents clicking."""
        # Mock screen capture to return a checkbox image
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = create_checkbox_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result = safe_click_action_button(x=300, y=400, width=80, height=40, label="Call")
            
            assert result is False
            mock_pyautogui.click.assert_not_called()
    
    def test_dark_background_prevents_click(self, mock_screen_capture):
        """Test that dark background prevents clicking."""
        # Mock screen capture to return a dark background image
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = create_dark_background_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result = safe_click_action_button(x=300, y=400, width=80, height=40, label="Fold")
            
            assert result is False
            mock_pyautogui.click.assert_not_called()
    
    def test_capture_failure_prevents_click(self, mock_screen_capture):
        """Test that capture failure is handled gracefully."""
        # Mock screen capture to return None (capture failed)
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = None
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result = safe_click_action_button(x=300, y=400, width=80, height=40)
            
            assert result is False
            mock_pyautogui.click.assert_not_called()
    
    def test_exception_handling(self, mock_screen_capture):
        """Test that exceptions are handled gracefully."""
        # Mock screen capture to raise an exception
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.side_effect = Exception("Screen capture failed")
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result = safe_click_action_button(x=300, y=400, width=80, height=40)
            
            assert result is False
            mock_pyautogui.click.assert_not_called()
    
    def test_custom_click_delay(self, mock_screen_capture):
        """Test that custom click delay is used."""
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = create_light_button_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            with patch('holdem.control.safe_click.time.sleep') as mock_sleep:
                result = safe_click_action_button(
                    x=300, y=400, width=80, height=40, 
                    label="Raise", click_delay=0.25
                )
                
                assert result is True
                mock_pyautogui.click.assert_called_once()
                mock_sleep.assert_called_once_with(0.25)
    
    def test_region_calculation(self, mock_screen_capture):
        """Test that capture region is calculated correctly."""
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = create_light_button_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            safe_click_action_button(x=300, y=400, width=80, height=40)
            
            # Should capture a region larger than the button
            call_args = mock_instance.capture_region.call_args[0]
            captured_width = call_args[2]
            captured_height = call_args[3]
            
            assert captured_width >= 60  # Minimum width
            assert captured_height >= 30  # Minimum height
            assert captured_width >= 80   # At least button width
            assert captured_height >= 40  # At least button height


class TestSafeClickWithFallback:
    """Tests for safe_click_with_fallback function."""
    
    def test_safe_click_enabled(self, mock_screen_capture):
        """Test behavior when safe click is enabled."""
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = create_light_button_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result = safe_click_with_fallback(
                x=300, y=400, width=80, height=40,
                label="Call", enable_safe_click=True
            )
            
            assert result is True
            mock_pyautogui.click.assert_called_once()
    
    def test_safe_click_disabled(self):
        """Test behavior when safe click is disabled (legacy mode)."""
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            with patch('holdem.control.safe_click.time.sleep'):
                result = safe_click_with_fallback(
                    x=300, y=400, width=80, height=40,
                    label="Fold", enable_safe_click=False
                )
                
                assert result is True
                # Should click directly without verification
                mock_pyautogui.click.assert_called_once_with(300, 400)
    
    def test_safe_click_rejects_checkbox(self, mock_screen_capture):
        """Test that safe click rejects checkbox when enabled."""
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = create_checkbox_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result = safe_click_with_fallback(
                x=300, y=400, width=80, height=40,
                label="Call", enable_safe_click=True
            )
            
            assert result is False
            mock_pyautogui.click.assert_not_called()


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""
    
    def test_fold_button_ready(self, mock_screen_capture):
        """Test clicking Fold button when it's ready."""
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = create_light_button_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result = safe_click_action_button(
                x=140, y=320, width=80, height=40, label="Fold"
            )
            
            assert result is True
            mock_pyautogui.click.assert_called_once_with(140, 320)
    
    def test_call_button_with_checkbox_overlay(self, mock_screen_capture):
        """Test that Call button click is prevented when checkbox is visible."""
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = create_checkbox_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result = safe_click_action_button(
                x=240, y=320, width=80, height=40, label="Call"
            )
            
            assert result is False
            mock_pyautogui.click.assert_not_called()
    
    def test_pot_button_not_yet_rendered(self, mock_screen_capture):
        """Test that Pot button click is prevented when not yet rendered."""
        mock_instance = mock_screen_capture.return_value
        mock_instance.capture_region.return_value = create_dark_background_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result = safe_click_action_button(
                x=340, y=320, width=80, height=40, label="Pot"
            )
            
            assert result is False
            mock_pyautogui.click.assert_not_called()
    
    def test_multiple_buttons_sequence(self, mock_screen_capture):
        """Test clicking multiple buttons in sequence."""
        mock_instance = mock_screen_capture.return_value
        
        # First call: checkbox visible (should fail)
        mock_instance.capture_region.return_value = create_checkbox_image()
        
        with patch('holdem.control.safe_click._get_pyautogui') as mock_get_pyautogui:
            mock_pyautogui = Mock()
            mock_get_pyautogui.return_value = mock_pyautogui
            
            result1 = safe_click_action_button(
                x=240, y=320, width=80, height=40, label="Call"
            )
            assert result1 is False
            
            # Second call: button ready (should succeed)
            mock_instance.capture_region.return_value = create_light_button_image()
            result2 = safe_click_action_button(
                x=240, y=320, width=80, height=40, label="Call"
            )
            assert result2 is True
            
            # Should have clicked only once (second attempt)
            assert mock_pyautogui.click.call_count == 1
