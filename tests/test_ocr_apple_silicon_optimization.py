"""Tests for Apple Silicon OCR memory optimization."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Mock dependencies that might not be available in test environment
sys.modules['cv2'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['paddleocr'] = MagicMock()

from holdem.vision.ocr import OCREngine, _is_apple_silicon


class TestAppleSiliconOptimization:
    """Test Apple Silicon-specific OCR memory optimizations."""
    
    def test_is_apple_silicon_detection(self):
        """Test Apple Silicon detection function."""
        # Just verify the function can be called without error
        result = _is_apple_silicon()
        assert isinstance(result, bool)
    
    @patch('holdem.vision.ocr._is_apple_silicon')
    @patch('paddleocr.PaddleOCR')
    def test_ocr_init_apple_silicon_optimizations(self, mock_paddle_ocr, mock_is_apple_silicon):
        """Test that OCR engine uses optimized settings on Apple Silicon."""
        mock_is_apple_silicon.return_value = True
        mock_paddle_instance = MagicMock()
        mock_paddle_ocr.return_value = mock_paddle_instance
        
        engine = OCREngine(backend="paddleocr")
        
        # Verify PaddleOCR was called with Apple Silicon optimizations
        mock_paddle_ocr.assert_called_once()
        call_kwargs = mock_paddle_ocr.call_args[1]
        
        # Check ultra-low memory settings for Apple Silicon
        assert call_kwargs['use_angle_cls'] is False, "Angle classification should be disabled"
        assert call_kwargs['use_gpu'] is False, "GPU should be disabled"
        assert call_kwargs['enable_mkldnn'] is False, "MKL-DNN should be disabled"
        assert call_kwargs['use_space_char'] is False, "Space char should be disabled"
        assert call_kwargs['rec_batch_num'] == 1, "Batch size should be 1"
        assert call_kwargs['det_limit_side_len'] == 640, "Detection limit should be 640"
        assert call_kwargs['use_mp'] is False, "Multiprocessing should be disabled"
        
        # Verify the engine was configured correctly
        assert engine.backend == "paddleocr"
        assert engine.paddle_ocr is mock_paddle_instance
        assert engine.use_angle_cls is False
    
    @patch('holdem.vision.ocr._is_apple_silicon')
    @patch('paddleocr.PaddleOCR')
    def test_ocr_init_non_apple_silicon(self, mock_paddle_ocr, mock_is_apple_silicon):
        """Test that OCR engine uses standard settings on non-Apple Silicon."""
        mock_is_apple_silicon.return_value = False
        mock_paddle_instance = MagicMock()
        mock_paddle_ocr.return_value = mock_paddle_instance
        
        engine = OCREngine(backend="paddleocr")
        
        # Verify PaddleOCR was called with standard resource-friendly settings
        mock_paddle_ocr.assert_called_once()
        call_kwargs = mock_paddle_ocr.call_args[1]
        
        # Check standard settings (still memory-friendly but less aggressive)
        assert call_kwargs['use_angle_cls'] is False, "Angle classification should be disabled"
        assert call_kwargs['use_gpu'] is False, "GPU should be disabled"
        assert call_kwargs['enable_mkldnn'] is False, "MKL-DNN should be disabled"
        assert call_kwargs['use_mp'] is False, "Multiprocessing should be disabled"
        
        # Apple Silicon-specific settings should not be present
        assert 'use_space_char' not in call_kwargs or call_kwargs.get('use_space_char') is not False
        assert 'rec_batch_num' not in call_kwargs or call_kwargs.get('rec_batch_num') != 1
        assert 'det_limit_side_len' not in call_kwargs or call_kwargs.get('det_limit_side_len') != 640
        
        assert engine.backend == "paddleocr"
        assert engine.paddle_ocr is mock_paddle_instance
    
    @patch('holdem.vision.ocr._is_apple_silicon')
    @patch('paddleocr.PaddleOCR')
    def test_ocr_fallback_on_paddleocr_failure(self, mock_paddle_ocr, mock_is_apple_silicon):
        """Test that OCR engine falls back to pytesseract if PaddleOCR fails."""
        mock_is_apple_silicon.return_value = True
        mock_paddle_ocr.side_effect = Exception("PaddleOCR initialization failed")
        
        engine = OCREngine(backend="paddleocr")
        
        # Should have fallen back to pytesseract
        assert engine.backend == "pytesseract"
        assert engine.paddle_ocr is None
    
    @patch('holdem.vision.ocr._is_apple_silicon')
    @patch('paddleocr.PaddleOCR')
    def test_read_paddle_with_angle_cls_disabled(self, mock_paddle_ocr, mock_is_apple_silicon):
        """Test that _read_paddle uses cls=False when angle classification is disabled."""
        mock_is_apple_silicon.return_value = True
        mock_paddle_instance = MagicMock()
        mock_paddle_ocr.return_value = mock_paddle_instance
        
        # Setup mock OCR result
        mock_paddle_instance.ocr.return_value = [[
            [[[0, 0], [100, 0], [100, 50], [0, 50]], ("$123.45", 0.95)]
        ]]
        
        engine = OCREngine(backend="paddleocr")
        
        # Create a dummy image
        import numpy as np
        img = np.zeros((100, 100), dtype=np.uint8)
        
        # Call _read_paddle
        text = engine._read_paddle(img)
        
        # Verify OCR was called with cls=False (since use_angle_cls=False)
        mock_paddle_instance.ocr.assert_called_once()
        call_args = mock_paddle_instance.ocr.call_args
        assert call_args[1]['cls'] is False, "cls parameter should be False"
        
        # Verify text was extracted correctly
        assert text == "$123.45"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
