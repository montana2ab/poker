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
                logger.info("PaddleOCR initialized successfully")
            except ImportError:
                logger.warning("PaddleOCR not available, falling back to pytesseract")
                logger.warning("Install PaddleOCR with: pip install paddleocr")
                self.backend = "pytesseract"
        
        if self.backend == "pytesseract":
            try:
                import pytesseract
                # Test if tesseract is actually available
                try:
                    pytesseract.get_tesseract_version()
                    self.tesseract_available = True
                    logger.info("Pytesseract initialized successfully")
                except (OSError, RuntimeError):
                    logger.error("Tesseract is not installed or not in PATH")
                    logger.error("Install tesseract: https://github.com/tesseract-ocr/tesseract")
                    logger.error("  - macOS: brew install tesseract")
                    logger.error("  - Ubuntu: sudo apt install tesseract-ocr")
                    logger.error("  - Windows: Download from GitHub releases")
            except ImportError:
                logger.error("Pytesseract package not installed")
                logger.error("Install with: pip install pytesseract")
        
        if not self.paddle_ocr and not self.tesseract_available:
            logger.error("No OCR backend available! Text recognition will not work.")
            logger.error("Install at least one of: paddleocr OR pytesseract+tesseract")
    
    def read_text(self, img: np.ndarray, preprocess: bool = True) -> str:
        """Read text from image."""
        if img is None or img.size == 0:
            logger.debug("Cannot read text from empty image")
            return ""
        
        if preprocess:
            img = self._preprocess(img)
        
        if self.backend == "paddleocr" and self.paddle_ocr:
            return self._read_paddle(img)
        elif self.backend == "pytesseract" and self.tesseract_available:
            return self._read_tesseract(img)
        else:
            logger.debug("No OCR backend available for text reading")
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
