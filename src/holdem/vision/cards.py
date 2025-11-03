"""Card recognition using template matching and optional CNN."""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple
from holdem.types import Card
from holdem.utils.logging import get_logger

logger = get_logger("vision.cards")


class CardRecognizer:
    """Recognizes playing cards from images."""
    
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    SUITS = ['h', 'd', 'c', 's']  # hearts, diamonds, clubs, spades
    
    def __init__(self, templates_dir: Optional[Path] = None, method: str = "template"):
        self.method = method
        self.templates_dir = templates_dir
        self.templates = {}
        
        if method == "template" and templates_dir:
            self._load_templates()
    
    def _load_templates(self):
        """Load card templates from directory."""
        if not self.templates_dir or not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            logger.warning("Card recognition will not work without templates!")
            logger.warning("Run: python setup_assets.py to create card templates")
            return
        
        for rank in self.RANKS:
            for suit in self.SUITS:
                card_name = f"{rank}{suit}"
                template_path = self.templates_dir / f"{card_name}.png"
                if template_path.exists():
                    template = cv2.imread(str(template_path))
                    if template is not None:
                        self.templates[card_name] = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        
        if self.templates:
            logger.info(f"Loaded {len(self.templates)} card templates")
        else:
            logger.error("No card templates found! Card recognition will fail.")
            logger.error("Run: python setup_assets.py to create card templates")
    
    def recognize_card(self, img: np.ndarray, confidence_threshold: float = 0.7) -> Optional[Card]:
        """Recognize a single card from image."""
        if self.method == "template":
            return self._recognize_template(img, confidence_threshold)
        elif self.method == "cnn":
            return self._recognize_cnn(img, confidence_threshold)
        else:
            raise ValueError(f"Unknown recognition method: {self.method}")
    
    def _recognize_template(self, img: np.ndarray, threshold: float) -> Optional[Card]:
        """Template matching approach."""
        if not self.templates:
            logger.warning("No templates loaded")
            return None
        
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Resize to standard size
        gray = cv2.resize(gray, (70, 100))
        
        best_match = None
        best_score = 0.0
        
        for card_name, template in self.templates.items():
            # Resize template to match
            template_resized = cv2.resize(template, (70, 100))
            
            # Match using normalized correlation
            result = cv2.matchTemplate(gray, template_resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            
            if max_val > best_score:
                best_score = max_val
                best_match = card_name
        
        if best_score >= threshold and best_match:
            logger.debug(f"Recognized card {best_match} with confidence {best_score:.3f}")
            return Card.from_string(best_match)
        
        logger.debug(f"No card match above threshold {threshold} (best: {best_score:.3f})")
        return None
    
    def _recognize_cnn(self, img: np.ndarray, threshold: float) -> Optional[Card]:
        """CNN-based recognition (placeholder for future implementation)."""
        logger.warning("CNN recognition not implemented, falling back to template matching")
        return self._recognize_template(img, threshold)
    
    def recognize_cards(self, img: np.ndarray, num_cards: int = 5) -> List[Optional[Card]]:
        """Recognize multiple cards from image (community cards)."""
        cards = []
        height, width = img.shape[:2]
        
        # Assume cards are horizontally aligned
        card_width = width // num_cards
        
        logger.debug(f"Attempting to recognize {num_cards} cards from image of size {img.shape}")
        
        for i in range(num_cards):
            x1 = i * card_width
            x2 = (i + 1) * card_width
            card_img = img[:, x1:x2]
            
            if card_img.size == 0:
                logger.warning(f"Card {i}: Empty image region")
                cards.append(None)
                continue
            
            card = self.recognize_card(card_img)
            cards.append(card)
            
            if card is None:
                logger.debug(f"Card {i}: No match found")
        
        return cards


def create_mock_templates(output_dir: Path):
    """Create mock card templates for testing."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    ranks = CardRecognizer.RANKS
    suits = CardRecognizer.SUITS
    
    for rank in ranks:
        for suit in suits:
            # Create a simple colored rectangle as mock template
            img = np.ones((100, 70, 3), dtype=np.uint8) * 255
            
            # Add rank text
            cv2.putText(img, rank, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                       1.5, (0, 0, 0), 2)
            
            # Add suit symbol (simplified)
            suit_color = (0, 0, 255) if suit in ['h', 'd'] else (0, 0, 0)
            cv2.putText(img, suit, (25, 85), cv2.FONT_HERSHEY_SIMPLEX, 
                       1.0, suit_color, 2)
            
            filename = f"{rank}{suit}.png"
            cv2.imwrite(str(output_dir / filename), img)
    
    logger.info(f"Created {len(ranks) * len(suits)} mock templates in {output_dir}")
