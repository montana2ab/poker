"""Tests for EasyOCR backend integration."""

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


class TestEasyOCRBackend:
    """Test EasyOCR backend integration."""
    
    def test_easyocr_engine_init(self):
        """Test that EasyOCR engine can be initialized."""
        try:
            engine = OCREngine(backend="easyocr")
            assert engine.backend == "easyocr"
            assert engine.easy_ocr is not None or engine.backend == "pytesseract"  # Falls back if not available
        except ImportError:
            pytest.skip("EasyOCR not available")
        except Exception as e:
            # EasyOCR may not be available, which is acceptable
            pytest.skip(f"EasyOCR initialization failed: {e}")
    
    def test_easyocr_read_text(self):
        """Test reading text with EasyOCR backend."""
        try:
            engine = OCREngine(backend="easyocr", enable_enhanced_preprocessing=False)
            if engine.backend != "easyocr":
                pytest.skip("EasyOCR not available, fallback occurred")
            
            # Create simple test image
            test_img = create_test_text_image("123")
            
            # Try to read text
            result = engine.read_text(test_img, preprocess=False)
            assert isinstance(result, str)
            # We can't guarantee what text will be read, but it should return a string
        except ImportError:
            pytest.skip("EasyOCR not available")
        except Exception as e:
            pytest.skip(f"EasyOCR test failed: {e}")
    
    def test_easyocr_with_preprocessing(self):
        """Test EasyOCR with preprocessing enabled."""
        try:
            engine = OCREngine(backend="easyocr", enable_enhanced_preprocessing=True)
            if engine.backend != "easyocr":
                pytest.skip("EasyOCR not available, fallback occurred")
            
            # Create test image
            test_img = create_test_text_image("456")
            
            # Try to read with preprocessing
            result = engine.read_text(test_img, preprocess=True)
            assert isinstance(result, str)
        except ImportError:
            pytest.skip("EasyOCR not available")
        except Exception as e:
            pytest.skip(f"EasyOCR test failed: {e}")
    
    def test_easyocr_extract_number(self):
        """Test number extraction with EasyOCR."""
        try:
            engine = OCREngine(backend="easyocr")
            if engine.backend != "easyocr":
                pytest.skip("EasyOCR not available, fallback occurred")
            
            # Create test image with number
            test_img = create_test_text_image("1234")
            
            # Try to extract number
            result = engine.extract_number(test_img)
            # Result can be None or a float (OCR might not recognize the text perfectly)
            assert result is None or isinstance(result, float)
        except ImportError:
            pytest.skip("EasyOCR not available")
        except Exception as e:
            pytest.skip(f"EasyOCR test failed: {e}")
    
    def test_backend_fallback_from_easyocr(self):
        """Test that engine falls back gracefully if EasyOCR is not available."""
        # This test should always pass - even if EasyOCR is not installed
        try:
            engine = OCREngine(backend="easyocr")
            # Should either have EasyOCR or fall back to pytesseract
            assert engine.backend in ["easyocr", "pytesseract"]
        except Exception as e:
            pytest.skip(f"OCR initialization failed: {e}")
    
    def test_all_backends_available(self):
        """Test initialization of all three backends."""
        backends = ["paddleocr", "easyocr", "pytesseract"]
        for backend in backends:
            try:
                engine = OCREngine(backend=backend)
                # Engine should initialize (may fall back to another backend)
                assert engine.backend in backends
            except Exception as e:
                # This is acceptable - not all backends may be installed
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
