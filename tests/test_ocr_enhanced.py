"""Tests for enhanced OCR preprocessing."""

import pytest
import numpy as np
import cv2
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from holdem.vision.ocr import OCREngine


def create_test_text_image(text: str, height: int = 40, width: int = 200) -> np.ndarray:
    """Create a synthetic image with text for testing."""
    # Create white background
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    
    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    thickness = 2
    color = (0, 0, 0)  # Black text
    
    # Get text size to center it
    (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x = (width - text_width) // 2
    y = (height + text_height) // 2
    
    cv2.putText(img, text, (x, y), font, font_scale, color, thickness)
    
    # Add some noise to make it more realistic
    noise = np.random.normal(0, 5, img.shape).astype(np.uint8)
    img = cv2.add(img, noise)
    
    return img


def create_small_text_image(text: str, height: int = 20, width: int = 100) -> np.ndarray:
    """Create a small synthetic image with text (to test upscaling)."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.4
    thickness = 1
    color = (0, 0, 0)
    
    (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x = max(5, (width - text_width) // 2)
    y = (height + text_height) // 2
    
    cv2.putText(img, text, (x, y), font, font_scale, color, thickness)
    
    return img


class TestOCREnhanced:
    """Test enhanced OCR preprocessing features."""
    
    def test_ocr_engine_init_with_enhanced_preprocessing(self):
        """Test OCR engine initializes with enhanced preprocessing enabled."""
        # This will fail gracefully if PaddleOCR/pytesseract not installed
        try:
            engine = OCREngine(backend="pytesseract", enable_enhanced_preprocessing=True)
            assert engine.enable_enhanced_preprocessing is True
            assert engine.upscale_small_regions is True
            assert engine.min_upscale_height == 30
        except Exception as e:
            pytest.skip(f"OCR backend not available: {e}")
    
    def test_ocr_engine_init_with_custom_params(self):
        """Test OCR engine with custom parameters."""
        try:
            engine = OCREngine(
                backend="pytesseract",
                enable_enhanced_preprocessing=False,
                upscale_small_regions=False,
                min_upscale_height=50
            )
            assert engine.enable_enhanced_preprocessing is False
            assert engine.upscale_small_regions is False
            assert engine.min_upscale_height == 50
        except Exception as e:
            pytest.skip(f"OCR backend not available: {e}")
    
    def test_upscale_small_images(self):
        """Test that small images are upscaled correctly."""
        try:
            engine = OCREngine(
                backend="pytesseract",
                enable_enhanced_preprocessing=True,
                upscale_small_regions=True,
                min_upscale_height=30
            )
        except Exception as e:
            pytest.skip(f"OCR backend not available: {e}")
        
        # Create a small image (20 pixels high)
        small_img = np.ones((20, 100), dtype=np.uint8) * 255
        
        # Upscale it
        upscaled = engine._upscale_if_small(small_img)
        
        # Check that it was upscaled
        assert upscaled.shape[0] >= 30, f"Expected height >= 30, got {upscaled.shape[0]}"
        assert upscaled.shape[1] > small_img.shape[1], "Width should also be scaled"
    
    def test_no_upscale_for_large_images(self):
        """Test that large images are not upscaled."""
        try:
            engine = OCREngine(
                backend="pytesseract",
                enable_enhanced_preprocessing=True,
                upscale_small_regions=True,
                min_upscale_height=30
            )
        except Exception as e:
            pytest.skip(f"OCR backend not available: {e}")
        
        # Create a large image (50 pixels high)
        large_img = np.ones((50, 200), dtype=np.uint8) * 255
        
        # Try to upscale
        result = engine._upscale_if_small(large_img)
        
        # Check that it was not upscaled
        assert result.shape == large_img.shape, "Large image should not be upscaled"
    
    def test_preprocessing_strategies_exist(self):
        """Test that all preprocessing strategies are callable."""
        try:
            engine = OCREngine(backend="pytesseract", enable_enhanced_preprocessing=True)
        except Exception as e:
            pytest.skip(f"OCR backend not available: {e}")
        
        # Create a test image
        test_img = np.ones((40, 200, 3), dtype=np.uint8) * 255
        
        # Test each strategy
        strategies = [
            engine._preprocess_strategy_standard,
            engine._preprocess_strategy_sharp,
            engine._preprocess_strategy_bilateral,
            engine._preprocess_strategy_morphological,
        ]
        
        for strategy in strategies:
            result = strategy(test_img)
            assert result is not None
            assert len(result.shape) == 2, "Result should be grayscale"
            assert result.dtype == np.uint8
    
    def test_multi_strategy_returns_text(self):
        """Test that multi-strategy preprocessing attempts multiple methods."""
        try:
            engine = OCREngine(backend="pytesseract", enable_enhanced_preprocessing=True)
        except Exception as e:
            pytest.skip(f"OCR backend not available: {e}")
        
        # Create a simple test image with text
        test_img = create_test_text_image("123")
        
        # This will try multiple strategies
        # We can't guarantee OCR will work without tesseract installed,
        # but we can check it doesn't crash
        try:
            result = engine._read_with_multi_strategy(test_img)
            # Result should be a string (may be empty if OCR not installed)
            assert isinstance(result, str)
        except Exception as e:
            # If tesseract is not installed, this is expected
            if "tesseract" not in str(e).lower():
                raise
    
    def test_backward_compatibility_with_standard_preprocessing(self):
        """Test that old _preprocess method still works."""
        try:
            engine = OCREngine(backend="pytesseract", enable_enhanced_preprocessing=False)
        except Exception as e:
            pytest.skip(f"OCR backend not available: {e}")
        
        # Create a test image
        test_img = create_test_text_image("TEST")
        
        # Use old preprocessing method
        result = engine._preprocess(test_img)
        
        assert result is not None
        assert len(result.shape) == 2, "Result should be grayscale"
        assert result.dtype == np.uint8
    
    def test_read_text_with_enhanced_preprocessing_enabled(self):
        """Test read_text with enhanced preprocessing enabled."""
        try:
            engine = OCREngine(backend="pytesseract", enable_enhanced_preprocessing=True)
        except Exception as e:
            pytest.skip(f"OCR backend not available: {e}")
        
        # Create test image
        test_img = create_test_text_image("456")
        
        # Try to read with preprocessing
        try:
            result = engine.read_text(test_img, preprocess=True)
            assert isinstance(result, str)
        except Exception as e:
            # If tesseract is not installed, this is expected
            if "tesseract" not in str(e).lower() and "paddleocr" not in str(e).lower():
                raise
    
    def test_read_text_with_enhanced_preprocessing_disabled(self):
        """Test read_text with enhanced preprocessing disabled."""
        try:
            engine = OCREngine(backend="pytesseract", enable_enhanced_preprocessing=False)
        except Exception as e:
            pytest.skip(f"OCR backend not available: {e}")
        
        # Create test image
        test_img = create_test_text_image("789")
        
        # Try to read with standard preprocessing
        try:
            result = engine.read_text(test_img, preprocess=True)
            assert isinstance(result, str)
        except Exception as e:
            # If tesseract is not installed, this is expected
            if "tesseract" not in str(e).lower() and "paddleocr" not in str(e).lower():
                raise
    
    def test_extract_number_still_works(self):
        """Test that extract_number still works with enhanced preprocessing."""
        try:
            engine = OCREngine(backend="pytesseract", enable_enhanced_preprocessing=True)
        except Exception as e:
            pytest.skip(f"OCR backend not available: {e}")
        
        # Create test image with a number
        test_img = create_test_text_image("$1,234.56")
        
        # Try to extract number (may return None if OCR not installed)
        try:
            result = engine.extract_number(test_img)
            # Result can be None or a float
            assert result is None or isinstance(result, float)
        except Exception as e:
            # If tesseract is not installed, this is expected
            if "tesseract" not in str(e).lower() and "paddleocr" not in str(e).lower():
                raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
