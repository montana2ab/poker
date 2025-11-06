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
    
    def __init__(self, templates_dir: Optional[Path] = None, method: str = "template", 
                 hero_templates_dir: Optional[Path] = None):
        self.method = method
        self.templates_dir = templates_dir
        self.hero_templates_dir = hero_templates_dir
        self.templates = {}  # Board card templates
        self.hero_templates = {}  # Hero card templates

        # Matching thresholds (overridable)
        self.board_match_threshold = 0.82
        self.hero_match_threshold = 0.65
        
        if method == "template":
            if templates_dir:
                self._load_templates()
            if hero_templates_dir:
                self._load_hero_templates()
    
    def _load_templates(self):
        """Load card templates from directory."""
        if not self.templates_dir or not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            return
        
        for rank in self.RANKS:
            for suit in self.SUITS:
                card_name = f"{rank}{suit}"
                template_path = self.templates_dir / f"{card_name}.png"
                if template_path.exists():
                    template = cv2.imread(str(template_path))
                    if template is not None:
                        self.templates[card_name] = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        
        logger.info(f"Loaded {len(self.templates)} board card templates")
    
    def _load_hero_templates(self):
        """Load hero card templates from separate directory."""
        if not self.hero_templates_dir or not self.hero_templates_dir.exists():
            logger.warning(f"Hero templates directory not found: {self.hero_templates_dir}")
            return
        
        for rank in self.RANKS:
            for suit in self.SUITS:
                card_name = f"{rank}{suit}"
                template_path = self.hero_templates_dir / f"{card_name}.png"
                if template_path.exists():
                    template = cv2.imread(str(template_path))
                    if template is not None:
                        self.hero_templates[card_name] = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        
        logger.info(f"Loaded {len(self.hero_templates)} hero card templates")
    
    def recognize_card(self, img: np.ndarray, confidence_threshold: Optional[float] = None, 
                      use_hero_templates: bool = False) -> Optional[Card]:
        """Recognize a single card from image.
        
        Args:
            img: Card image to recognize
            confidence_threshold: Minimum confidence score required
            use_hero_templates: If True, use hero templates instead of board templates
        """
        # Auto-pick default threshold if not provided
        if confidence_threshold is None:
            confidence_threshold = (
                self.hero_match_threshold if use_hero_templates else self.board_match_threshold
            )
        if self.method == "template":
            return self._recognize_template(img, confidence_threshold, use_hero_templates)
        elif self.method == "cnn":
            return self._recognize_cnn(img, confidence_threshold)
        else:
            raise ValueError(f"Unknown recognition method: {self.method}")
    
    def _recognize_template(self, img: np.ndarray, threshold: float, 
                           use_hero_templates: bool = False) -> Optional[Card]:
        """Template matching approach.
        
        Args:
            img: Card image to recognize
            threshold: Minimum confidence score required
            use_hero_templates: If True, use hero templates instead of board templates
        """
        # Select appropriate template set
        templates_to_use = self.hero_templates if use_hero_templates and self.hero_templates else self.templates
        
        if not templates_to_use:
            # Fall back to regular templates if hero templates not available
            if use_hero_templates and not self.hero_templates:
                logger.debug("Hero templates not available, falling back to board templates")
                templates_to_use = self.templates
            
            if not templates_to_use:
                logger.warning("No templates loaded")
                return None
        
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img

        # Dimensions
        h, w = gray.shape[:2]
        search = cv2.equalizeHist(gray)
  
        best_match = None
        best_score = 0.0
  
        for card_name, template in templates_to_use.items():
            # Normalize template
            t = cv2.equalizeHist(template)
            th, tw = t.shape[:2]
  
            # If template is bigger than ROI, scale it down proportionally
            if th > h or tw > w:
                scale = min(h / float(th), w / float(tw))
                if scale <= 0:
                    continue
                t = cv2.resize(t, (max(1, int(tw * scale)), max(1, int(th * scale))), interpolation=cv2.INTER_AREA)
                th, tw = t.shape[:2]
  
            # Skip degenerate or still-too-large templates
            if th <= 0 or tw <= 0 or th > h or tw > w:
                continue
  
            # Sliding search across the full ROI
            result = cv2.matchTemplate(search, t, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            if max_val > best_score:
                best_score = max_val
                best_match = card_name
  
        template_type = "hero" if use_hero_templates else "board"
        # Brief INFO summary of best score (helps when logger level is INFO)
        logger.info(f"{template_type} best={best_match} score={best_score:.3f} thr={threshold:.2f}")
  
        if best_score >= threshold and best_match:
            logger.debug(f"Recognized {template_type} card {best_match} with confidence {best_score:.3f}")
            return Card.from_string(best_match)
  
        # Log the best match even if below threshold
        best_info = f"{best_match} @ {best_score:.3f}" if best_match else "none"
        logger.debug(f"No {template_type} card match above threshold {threshold} (best: {best_info})")
        return None
    
    def _recognize_cnn(self, img: np.ndarray, threshold: float) -> Optional[Card]:
        """CNN-based recognition (placeholder for future implementation)."""
        logger.warning("CNN recognition not implemented, falling back to template matching")
        return self._recognize_template(img, threshold)
    
    def recognize_cards(self, img: np.ndarray, num_cards: int = 5, 
                       use_hero_templates: bool = False) -> List[Optional[Card]]:
        """Recognize multiple cards from image.
        
        Args:
            img: Image containing multiple cards
            num_cards: Number of cards to recognize
            use_hero_templates: If True, use hero templates instead of board templates
        """
        cards = []
        height, width = img.shape[:2]
        
        # If not specified, assume 2 hole cards for hero
        if use_hero_templates and num_cards == 5:
            num_cards = 2
        
        # Assume cards are horizontally aligned
        card_width = width // num_cards
        
        template_type = "hero" if use_hero_templates else "board"
        logger.debug(f"Recognizing {num_cards} {template_type} cards from image {width}x{height}")
        
        for i in range(num_cards):
            x1 = i * card_width
            x2 = (i + 1) * card_width
            card_img = img[:, x1:x2]
            
            card = self.recognize_card(card_img, use_hero_templates=use_hero_templates)
            cards.append(card)
            
            if card:
                logger.debug(f"Card {i}: {card}")
            else:
                logger.debug(f"Card {i}: not recognized")
        
        return cards


def create_mock_templates(output_dir: Path, for_hero: bool = False):
    """Create mock card templates for testing.
    
    Args:
        output_dir: Directory to save templates
        for_hero: If True, creates templates styled for hero cards (smaller, different appearance)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    ranks = CardRecognizer.RANKS
    suits = CardRecognizer.SUITS
    
    for rank in ranks:
        for suit in suits:
            # Create a simple colored rectangle as mock template
            # Hero cards might be smaller or have different styling
            if for_hero:
                # Hero cards - slightly different appearance with border
                img = np.ones((100, 70, 3), dtype=np.uint8) * 245
                # Add a border to distinguish hero cards
                cv2.rectangle(img, (2, 2), (68, 98), (200, 200, 200), 2)
            else:
                # Board cards - standard appearance
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
    
    template_type = "hero" if for_hero else "board"
    logger.info(f"Created {len(ranks) * len(suits)} mock {template_type} templates in {output_dir}")
