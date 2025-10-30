"""OCR for reading text (stacks, pot, bets)."""

import re
import cv2
import numpy as np
from typing import Optional
from holdem.utils.logging import get_logger

logger = get_logger("vision.ocr")


class OCREngine:
    """OCR engine with PaddleOCR primary and pytesseract fallback."""
    
    def __init__(self, backend: str = "paddleocr"):
        self.backend = backend.lower()
        self.paddle_ocr = None
        self.tesseract_available = False
        
        if self.backend == "paddleocr":
            try:
                from paddleocr import PaddleOCR
                self.paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                logger.info("PaddleOCR initialized")
            except ImportError:
                logger.warning("PaddleOCR not available, falling back to pytesseract")
                self.backend = "pytesseract"
        
        if self.backend == "pytesseract":
            try:
                import pytesseract
                self.tesseract_available = True
                logger.info("Pytesseract initialized")
            except ImportError:
                logger.error("Neither PaddleOCR nor pytesseract available")
    
    def read_text(self, img: np.ndarray, preprocess: bool = True) -> str:
        """Read text from image."""
        if preprocess:
            img = self._preprocess(img)
        
        if self.backend == "paddleocr" and self.paddle_ocr:
            return self._read_paddle(img)
        elif self.backend == "pytesseract" and self.tesseract_available:
            return self._read_tesseract(img)
        else:
            logger.error("No OCR backend available")
            return ""
    
    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR."""
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Increase contrast
        gray = cv2.equalizeHist(gray)
        
        # Threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(binary)
        
        return denoised
    
    def _read_paddle(self, img: np.ndarray) -> str:
        """Read using PaddleOCR."""
        try:
            result = self.paddle_ocr.ocr(img, cls=True)
            if result and len(result) > 0 and result[0]:
                texts = [line[1][0] for line in result[0]]
                return " ".join(texts)
        except Exception as e:
            logger.debug(f"PaddleOCR error: {e}")
        return ""
    
    def _read_tesseract(self, img: np.ndarray) -> str:
        """Read using pytesseract."""
        try:
            import pytesseract
            text = pytesseract.image_to_string(img, config='--psm 7')
            return text.strip()
        except Exception as e:
            logger.debug(f"Pytesseract error: {e}")
        return ""
    
    def extract_number(self, img: np.ndarray) -> Optional[float]:
        """Extract a number from image (for stacks, pot, bets)."""
        text = self.read_text(img)
        
        # Remove common currency symbols and commas
        text = text.replace('$', '').replace(',', '').replace('€', '')
        text = text.replace('£', '').replace('¥', '')
        
        # Extract first number found
        match = re.search(r'[\d.]+', text)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
        
        logger.debug(f"Could not extract number from: {text}")
        return None
    
    def extract_integer(self, img: np.ndarray) -> Optional[int]:
        """Extract an integer from image."""
        num = self.extract_number(img)
        if num is not None:
            return int(num)
        return None
