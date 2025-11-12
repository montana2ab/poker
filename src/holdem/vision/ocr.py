"""OCR for reading text (stacks, pot, bets)."""

import re
import cv2
import numpy as np
from typing import Optional
from holdem.utils.logging import get_logger

logger = get_logger("vision.ocr")


class OCREngine:
    """OCR engine with PaddleOCR primary and pytesseract fallback.

    Enhanced with advanced preprocessing techniques for improved accuracy:
    - Adaptive upscaling for small text regions
    - Multiple preprocessing strategies (contrast, bilateral, morphological)
    - Sharpening and denoising
    - Best-result selection from multiple attempts
    """

    def __init__(self, backend: str = "paddleocr", enable_enhanced_preprocessing: bool = True,
                 upscale_small_regions: bool = True, min_upscale_height: int = 30):
        """Initialize OCR engine.

        Args:
            backend: OCR backend to use ("paddleocr" or "pytesseract")
            enable_enhanced_preprocessing: Enable advanced multi-strategy preprocessing
            upscale_small_regions: Upscale small text regions before OCR
            min_upscale_height: Minimum height (in pixels) below which to upscale
        """
        self.backend = backend.lower()
        self.paddle_ocr = None
        self.tesseract_available = False
        self.enable_enhanced_preprocessing = enable_enhanced_preprocessing
        self.upscale_small_regions = upscale_small_regions
        self.min_upscale_height = min_upscale_height

        if self.backend == "paddleocr":
            try:
                from paddleocr import PaddleOCR
                self.paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                logger.info("PaddleOCR initialized with enhanced preprocessing")
            except ImportError:
                logger.warning("PaddleOCR not available, falling back to pytesseract")
                self.backend = "pytesseract"

        if self.backend == "pytesseract":
            try:
                import pytesseract
                self.tesseract_available = True
                logger.info("Pytesseract initialized with enhanced preprocessing")
            except ImportError:
                logger.error("Neither PaddleOCR nor pytesseract available")

    def read_text(self, img: np.ndarray, preprocess: bool = True) -> str:
        """Read text from image with optional enhanced preprocessing.

        Args:
            img: Input image (BGR or grayscale)
            preprocess: Whether to apply preprocessing

        Returns:
            Extracted text string
        """
        if not preprocess:
            # No preprocessing, use image as-is
            if self.backend == "paddleocr" and self.paddle_ocr:
                return self._read_paddle(img)
            elif self.backend == "pytesseract" and self.tesseract_available:
                return self._read_tesseract(img)
            else:
                logger.error("No OCR backend available")
                return ""

        # Apply preprocessing based on configuration
        if self.enable_enhanced_preprocessing:
            return self._read_with_multi_strategy(img)
        else:
            preprocessed = self._preprocess(img)
            if self.backend == "paddleocr" and self.paddle_ocr:
                return self._read_paddle(preprocessed)
            elif self.backend == "pytesseract" and self.tesseract_available:
                return self._read_tesseract(preprocessed)
            else:
                logger.error("No OCR backend available")
                return ""

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        """Standard preprocessing for OCR - kept for backward compatibility.

        This is the original preprocessing method. For better results,
        use enable_enhanced_preprocessing=True in the constructor.
        """
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

    def _upscale_if_small(self, img: np.ndarray) -> np.ndarray:
        """Upscale image if it's too small for good OCR.

        Small text regions benefit from upscaling. This uses a high-quality
        interpolation method (INTER_CUBIC) to preserve text clarity.

        Args:
            img: Input image

        Returns:
            Upscaled image if needed, otherwise original
        """
        if not self.upscale_small_regions:
            return img

        height = img.shape[0]
        if height < self.min_upscale_height:
            # Calculate scale factor to reach target height
            scale = max(2.0, self.min_upscale_height / height)
            new_width = int(img.shape[1] * scale)
            new_height = int(height * scale)
            upscaled = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            logger.debug(f"Upscaled image from {img.shape[:2]} to {upscaled.shape[:2]}")
            return upscaled
        return img

    def _preprocess_strategy_standard(self, img: np.ndarray) -> np.ndarray:
        """Standard preprocessing strategy: contrast + threshold + denoise."""
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Upscale if needed
        gray = self._upscale_if_small(gray)

        # Enhance contrast with CLAHE (better than simple histogram equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Threshold
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Denoise
        denoised = cv2.fastNlMeansDenoising(binary, h=10)

        return denoised

    def _preprocess_strategy_sharp(self, img: np.ndarray) -> np.ndarray:
        """Sharpening strategy: sharpen + contrast + threshold."""
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Upscale if needed
        gray = self._upscale_if_small(gray)

        # Apply sharpening kernel
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(gray, -1, kernel)

        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(sharpened)

        # Threshold
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return binary

    def _preprocess_strategy_bilateral(self, img: np.ndarray) -> np.ndarray:
        """Bilateral filter strategy: preserve edges while smoothing."""
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Upscale if needed
        gray = self._upscale_if_small(gray)

        # Bilateral filter preserves edges while reducing noise
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)

        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(filtered)

        # Threshold
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return binary

    def _preprocess_strategy_morphological(self, img: np.ndarray) -> np.ndarray:
        """Morphological operations strategy: enhance character shapes."""
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Upscale if needed
        gray = self._upscale_if_small(gray)

        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Threshold
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Morphological operations to improve character shapes
        # Use a small kernel to connect broken characters
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # Remove small noise
        kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        cleaned = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel2)

        return cleaned

    def _read_with_multi_strategy(self, img: np.ndarray) -> str:
        """Try multiple preprocessing strategies and return best result.

        This method applies different preprocessing strategies and selects
        the result with the highest confidence (longest non-empty text).

        Args:
            img: Input image

        Returns:
            Best OCR result from all strategies
        """
        strategies = [
            ("standard", self._preprocess_strategy_standard),
            ("sharp", self._preprocess_strategy_sharp),
            ("bilateral", self._preprocess_strategy_bilateral),
            ("morphological", self._preprocess_strategy_morphological),
        ]

        results = []
        for name, strategy_func in strategies:
            try:
                preprocessed = strategy_func(img)
                if self.backend == "paddleocr" and self.paddle_ocr:
                    text = self._read_paddle(preprocessed)
                elif self.backend == "pytesseract" and self.tesseract_available:
                    text = self._read_tesseract(preprocessed)
                else:
                    text = ""

                # Score based on text length and character variety
                # Prefer results with actual content
                score = len(text.strip()) if text else 0
                results.append((score, text, name))
                logger.debug(f"Strategy '{name}': '{text}' (score: {score})")
            except Exception as e:
                logger.debug(f"Strategy '{name}' failed: {e}")
                continue

        if not results:
            logger.warning("All preprocessing strategies failed")
            return ""

        # Sort by score (descending) and return best result
        results.sort(reverse=True, key=lambda x: x[0])
        best_score, best_text, best_strategy = results[0]

        if best_score > 0:
            logger.debug(f"Best strategy: '{best_strategy}' with text: '{best_text}'")

        return best_text

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

    def detect_action(self, img: np.ndarray) -> Optional[str]:
        """Detect player action from image (CALL, CHECK, BET, RAISE, FOLD, ALL-IN).

        Returns:
            Action string in uppercase (e.g., "CALL", "RAISE") or None if not detected
        """
        text = self.read_text(img, preprocess=True)
        if not text:
            return None

        # Normalize text: uppercase and remove extra spaces
        text_norm = text.upper().strip()

        # Define action keywords and their variations
        action_keywords = {
            'FOLD': ['FOLD', 'FOLDED', 'FOLDS'],
            'CHECK': ['CHECK', 'CHECKS', 'CHECKED'],
            'CALL': ['CALL', 'CALLS', 'CALLED'],
            'BET': ['BET', 'BETS', 'BETTING'],
            'RAISE': ['RAISE', 'RAISES', 'RAISED'],
            'ALL-IN': ['ALL-IN', 'ALLIN', 'ALL IN', 'ALL_IN'],
        }

        # Try to match action keywords
        for action, variations in action_keywords.items():
            for keyword in variations:
                if keyword in text_norm:
                    logger.debug(f"Detected action '{action}' from text: {text}")
                    return action

        # Check for partial matches (at least 4 characters matching)
        for action, variations in action_keywords.items():
            for keyword in variations:
                if len(keyword) >= 4 and keyword[:4] in text_norm:
                    logger.debug(f"Partial match: detected action '{action}' from text: {text}")
                    return action

        logger.debug(f"No action detected from text: {text}")
        return None
