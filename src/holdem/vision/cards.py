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

        # Board card templates in color (for color-based prefilter)
        self.board_templates_color = {}  # type: dict[str, np.ndarray]
        
        # Precomputed hue histograms (H channel, 32 bins) for board templates
        self.board_templates_hue_hist = {}  # type: dict[str, np.ndarray]
        
        # Enable/disable board color prefilter (before template matching)
        self.enable_board_color_prefilter = True
        
        # Minimum similarity (in [0,1]) to keep a board template as color candidate
        self.board_color_prefilter_min_sim = 0.20
        
        # Maximum number of board templates to keep after color prefilter
        self.board_color_prefilter_top_k = 12

        # Hero card templates in color (for color-based prefilter)
        self.hero_templates_color = {}  # type: dict[str, np.ndarray]

        # Precomputed hue histograms (H channel, 32 bins) for hero templates
        self.hero_templates_hue_hist = {}  # type: dict[str, np.ndarray]

        # Enable/disable hero color prefilter (before template matching)
        self.enable_hero_color_prefilter = True

        # Minimum similarity (in [0,1]) to keep a hero template as color candidate
        # Très bas pour filtrer juste les cas totalement aberrants
        self.hero_color_prefilter_min_sim = 0.20

        # Maximum number of hero templates to keep after color prefilter
        self.hero_color_prefilter_top_k = 12

        # Matching thresholds (overridable)
        self.board_match_threshold = 0.70
        self.hero_match_threshold = 0.65
        
        # Track last confidence scores for metrics
        self.last_confidence_scores: List[float] = []
        
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
                if not template_path.exists():
                    continue
                
                tpl_bgr = cv2.imread(str(template_path))
                if tpl_bgr is None or tpl_bgr.size == 0:
                    logger.warning(f"Failed to load board template for {card_name} from {template_path}")
                    continue
                
                # Store color template for this board card
                self.board_templates_color[card_name] = tpl_bgr
                
                # Store grayscale template for matching
                tpl_gray = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
                self.templates[card_name] = tpl_gray
                
                # Precompute hue histogram (H in HSV, 32 bins)
                tpl_hsv = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2HSV)
                tpl_hist = cv2.calcHist([tpl_hsv], [0], None, [32], [0, 180])
                tpl_hist = cv2.normalize(tpl_hist, tpl_hist, alpha=1.0, beta=0.0,
                                         norm_type=cv2.NORM_L1)
                self.board_templates_hue_hist[card_name] = tpl_hist
        
        logger.info(
            f"Loaded {len(self.templates)} board card templates "
            f"(with color data and hue histograms)"
        )
    
    def _load_hero_templates(self):
        """Load hero card templates from separate directory."""
        if not self.hero_templates_dir or not self.hero_templates_dir.exists():
            logger.warning(f"Hero templates directory not found: {self.hero_templates_dir}")
            return
        
        for rank in self.RANKS:
            for suit in self.SUITS:
                card_name = f"{rank}{suit}"
                template_path = self.hero_templates_dir / f"{card_name}.png"
                if not template_path.exists():
                    continue

                tpl_bgr = cv2.imread(str(template_path))
                if tpl_bgr is None or tpl_bgr.size == 0:
                    logger.warning(f"Failed to load hero template for {card_name} from {template_path}")
                    continue

                # Store color template for this hero card
                self.hero_templates_color[card_name] = tpl_bgr

                # Store grayscale template for matching
                tpl_gray = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
                self.hero_templates[card_name] = tpl_gray

                # Precompute hue histogram (H in HSV, 32 bins)
                tpl_hsv = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2HSV)
                tpl_hist = cv2.calcHist([tpl_hsv], [0], None, [32], [0, 180])
                tpl_hist = cv2.normalize(tpl_hist, tpl_hist, alpha=1.0, beta=0.0,
                                         norm_type=cv2.NORM_L1)
                self.hero_templates_hue_hist[card_name] = tpl_hist

        logger.info(
            f"Loaded {len(self.hero_templates)} hero card templates "
            f"(with color data and hue histograms)"
        )
    
    def run_card_color_prefilter(
        self,
        card_image: np.ndarray,
        templates: dict[str, np.ndarray],
        hue_histograms: dict[str, np.ndarray],
        top_k: int,
        min_sim: float,
        label: str
    ) -> List[Tuple[str, np.ndarray, float]]:
        """
        Generic color-based prefilter for card recognition.
        
        Computes color similarity between card_image and all templates,
        returns the top-K candidates above min_sim threshold.
        
        Args:
            card_image: The card image to match (BGR or grayscale, will be converted to BGR if needed)
            templates: Dictionary of card_name -> grayscale template
            hue_histograms: Dictionary of card_name -> precomputed hue histogram
            top_k: Maximum number of candidates to return
            min_sim: Minimum similarity threshold (0.0 to 1.0)
            label: Label for logging (e.g., "Hero", "board")
            
        Returns:
            List of (card_name, grayscale_template, similarity_score) tuples,
            sorted by similarity in descending order, limited to top_k
        """
        # Ensure card_image is 3-channel BGR
        color_img = card_image
        if len(color_img.shape) == 2:
            color_img = cv2.cvtColor(color_img, cv2.COLOR_GRAY2BGR)
        elif len(color_img.shape) == 3 and color_img.shape[2] == 1:
            color_img = cv2.cvtColor(color_img, cv2.COLOR_GRAY2BGR)
        
        roi_hsv = cv2.cvtColor(color_img, cv2.COLOR_BGR2HSV)
        
        candidates = []
        for card_name, tpl_gray in templates.items():
            tpl_hist = hue_histograms.get(card_name)
            if tpl_hist is None:
                continue
            
            sim = self._hue_hist_similarity(roi_hsv, tpl_hist)
            # Keep only templates above the minimum similarity threshold
            if sim >= min_sim:
                candidates.append((card_name, tpl_gray, sim))
        
        # Sort candidates by similarity in descending order
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        # Limit to top-K candidates
        if top_k > 0:
            candidates = candidates[:top_k]
        
        logger.info(
            f"{label} color pre-filter: {len(candidates)} candidates "
            f"(top_k={top_k}, min_sim={min_sim:.2f})"
        )
        
        return candidates
    
    def recognize_card(self, img: np.ndarray, confidence_threshold: Optional[float] = None, 
                      use_hero_templates: bool = False, board_card_index: Optional[int] = None) -> Optional[Card]:
        """Recognize a single card from image.
        
        Args:
            img: Card image to recognize
            confidence_threshold: Minimum confidence score required
            use_hero_templates: If True, use hero templates instead of board templates
            board_card_index: For board cards, the index (0-4) for logging purposes
        """
        # Auto-pick default threshold if not provided
        if confidence_threshold is None:
            confidence_threshold = (
                self.hero_match_threshold if use_hero_templates else self.board_match_threshold
            )
        if self.method == "template":
            return self._recognize_template(img, confidence_threshold, use_hero_templates, board_card_index)
        elif self.method == "cnn":
            return self._recognize_cnn(img, confidence_threshold)
        else:
            raise ValueError(f"Unknown recognition method: {self.method}")
    
    def _hue_hist_similarity(self, roi_hsv: np.ndarray, tpl_hist: np.ndarray) -> float:
        """
        Compare l'histogramme de teinte H du ROI avec l'histogramme H d'un template héros.
        Renvoie un score entre 0.0 et 1.0, en mappant la corrélation [-1,1] vers [0,1].
        """
        if roi_hsv is None or roi_hsv.size == 0 or tpl_hist is None or tpl_hist.size == 0:
            return 0.0

        roi_hist = cv2.calcHist([roi_hsv], [0], None, [32], [0, 180])
        roi_hist = cv2.normalize(roi_hist, roi_hist, alpha=1.0, beta=0.0,
                                 norm_type=cv2.NORM_L1)

        score = cv2.compareHist(roi_hist, tpl_hist, cv2.HISTCMP_CORREL)
        sim = max(0.0, (score + 1.0) / 2.0)
        return sim
    
    def _recognize_template(self, img: np.ndarray, threshold: float, 
                           use_hero_templates: bool = False, board_card_index: Optional[int] = None) -> Optional[Card]:
        """Template matching approach.
        
        Args:
            img: Card image to recognize
            threshold: Minimum confidence score required
            use_hero_templates: If True, use hero templates instead of board templates
            board_card_index: For board cards, the index (0-4) for logging purposes
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
        
        # Validate image shape
        if img.size == 0 or len(img.shape) < 2:
            logger.warning("Invalid image shape for card recognition")
            return None
        
        # Optional hero color pre-filter to reduce the number of templates
        if use_hero_templates and self.enable_hero_color_prefilter:
            candidates = self.run_card_color_prefilter(
                card_image=img,
                templates=self.hero_templates,
                hue_histograms=self.hero_templates_hue_hist,
                top_k=self.hero_color_prefilter_top_k,
                min_sim=self.hero_color_prefilter_min_sim,
                label="Hero"
            )
            
            if candidates:
                # Reconstruct templates_to_use from candidates
                templates_to_use = {name: tpl for (name, tpl, _) in candidates}
            else:
                logger.info(
                    "Hero color pre-filter: no candidate above min_sim, "
                    "using all hero templates"
                )
        
        # Optional board color pre-filter to reduce the number of templates
        if not use_hero_templates and self.enable_board_color_prefilter:
            # Determine label for logging (include card index if provided)
            if board_card_index is not None:
                label = f"board card {board_card_index}"
            else:
                label = "board"
            
            candidates = self.run_card_color_prefilter(
                card_image=img,
                templates=self.templates,
                hue_histograms=self.board_templates_hue_hist,
                top_k=self.board_color_prefilter_top_k,
                min_sim=self.board_color_prefilter_min_sim,
                label=label
            )
            
            if candidates:
                # Reconstruct templates_to_use from candidates
                templates_to_use = {name: tpl for (name, tpl, _) in candidates}
            else:
                logger.info(
                    f"{label} color pre-filter: no candidate above min_sim, "
                    "using all board templates"
                )
        
        # Convert to grayscale
        if len(img.shape) == 3:
            # Handle single-channel images with 3D shape (h, w, 1)
            if img.shape[2] == 1:
                gray = img[:, :, 0]
            # Handle 4-channel images (BGRA) - convert from BGRA
            elif img.shape[2] == 4:
                gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            # Standard 3-channel BGR
            else:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img

        # Dimensions - validate we have at least 2D
        if len(gray.shape) < 2:
            logger.warning("Grayscale conversion resulted in invalid shape")
            return None
        
        h, w = gray.shape[:2]
        
        # Minimum size check - need reasonable dimensions for matching
        if h < 5 or w < 5:
            logger.debug(f"Image too small for reliable matching: {h}x{w}")
            return None
        
        # Ensure image is uint8 for histogram equalization
        if gray.dtype != np.uint8:
            gray = np.clip(gray, 0, 255).astype(np.uint8)
        
        search = cv2.equalizeHist(gray)
  
        best_match = None
        best_score = 0.0
  
        for card_name, template in templates_to_use.items():
            # Validate template
            if template is None or template.size == 0:
                logger.debug(f"Skipping invalid template: {card_name}")
                continue
            
            # Ensure template is uint8 for histogram equalization
            if template.dtype != np.uint8:
                template = np.clip(template, 0, 255).astype(np.uint8)
            
            # Normalize template
            t = cv2.equalizeHist(template)
            th, tw = t.shape[:2]
  
            # Template must be at least 3 pixels smaller in both dimensions for reliable matching
            # This ensures we get a meaningful match result grid (at least 3x3)
            min_margin = 3
            target_h = h - min_margin
            target_w = w - min_margin
            
            # If template is bigger than target size, scale it down proportionally
            if th > target_h or tw > target_w:
                scale = min(target_h / float(th), target_w / float(tw))
                if scale <= 0:
                    logger.debug(f"Cannot scale template {card_name} to fit image")
                    continue
                t = cv2.resize(t, (max(1, int(tw * scale)), max(1, int(th * scale))), interpolation=cv2.INTER_AREA)
                th, tw = t.shape[:2]
  
            # Skip degenerate templates or templates that are still too large
            # Ensure template is smaller than image by at least 1 pixel in each dimension
            if th <= 0 or tw <= 0 or th >= h or tw >= w:
                logger.debug(f"Skipping template {card_name}: size {th}x{tw} vs image {h}x{w}")
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
            # Store confidence for metrics tracking
            self.last_confidence_scores.append(best_score)
            return Card.from_string(best_match)
  
        # Log the best match even if below threshold
        best_info = f"{best_match} @ {best_score:.3f}" if best_match else "none"
        logger.debug(f"No {template_type} card match above threshold {threshold} (best: {best_info})")
        return None
    
    def _recognize_cnn(self, img: np.ndarray, threshold: float) -> Optional[Card]:
        """CNN-based recognition (placeholder for future implementation)."""
        logger.warning("CNN recognition not implemented, falling back to template matching")
        return self._recognize_template(img, threshold)
    
    def _region_has_cards(self, img: np.ndarray, min_variance: float = 100.0) -> bool:
        """Check if a region likely contains cards based on image variance.
        
        Args:
            img: Image region to check
            min_variance: Minimum variance threshold to consider region as containing cards
            
        Returns:
            True if the region likely contains cards, False otherwise
        """
        if img is None or img.size == 0:
            return False
        
        # Validate shape
        if len(img.shape) < 2:
            return False
        
        # Minimum size check
        h, w = img.shape[:2]
        if h < 5 or w < 5:
            logger.debug(f"Region too small for card detection: {h}x{w}")
            return False
            
        # Convert to grayscale if needed
        if len(img.shape) == 3:
            if img.shape[2] == 1:
                gray = img[:, :, 0]
            elif img.shape[2] == 4:
                gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            else:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Ensure uint8 type
        if gray.dtype != np.uint8:
            gray = np.clip(gray, 0, 255).astype(np.uint8)
            
        # Calculate variance - empty/uniform regions have low variance
        variance = np.var(gray)
        
        # Check if there are edges (cards have distinct edges)
        # Canny requires at least some minimal size
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.count_nonzero(edges) / edges.size
        
        has_cards = variance >= min_variance or edge_ratio > 0.01
        
        if not has_cards:
            logger.debug(f"Region appears empty (variance={variance:.1f}, edge_ratio={edge_ratio:.4f})")
        
        return has_cards
    
    def recognize_cards(self, img: np.ndarray, num_cards: int = 5, 
                       use_hero_templates: bool = False, 
                       skip_empty_check: bool = False,
                       card_spacing: int = 0) -> List[Optional[Card]]:
        """Recognize multiple cards from image.
        
        Args:
            img: Image containing multiple cards
            num_cards: Number of cards to recognize
            use_hero_templates: If True, use hero templates instead of board templates
            skip_empty_check: If True, skip checking if region contains cards (for hero cards)
            card_spacing: Pixels of spacing/overlap between cards (negative for overlap, positive for spacing)
            
        Returns:
            List of recognized cards (None for unrecognized positions)
        """
        cards = []
        
        # Clear confidence scores before recognition
        self.last_confidence_scores = []
        
        # Validate input
        if img is None or img.size == 0:
            logger.warning("Empty or None image provided to recognize_cards")
            return cards
        
        # Check if region likely contains cards (skip if requested or for hero templates by default)
        if not skip_empty_check:
            if not self._region_has_cards(img):
                logger.info("Board region appears empty (likely preflop), skipping card recognition")
                return [None] * num_cards
        
        height, width = img.shape[:2]
        
        # If not specified, assume 2 hole cards for hero
        if use_hero_templates and num_cards == 5:
            num_cards = 2
        
        # Validate num_cards to prevent division by zero
        if num_cards <= 0:
            logger.warning(f"Invalid num_cards={num_cards}, must be > 0")
            return cards
        
        template_type = "hero" if use_hero_templates else "board"
        logger.debug(f"Recognizing {num_cards} {template_type} cards from image {width}x{height}, spacing={card_spacing}")
        
        # Calculate card width accounting for spacing between cards
        # Total width = (num_cards * card_width) + ((num_cards - 1) * spacing)
        # Solving for card_width: card_width = (width - (num_cards - 1) * spacing) / num_cards
        total_spacing = (num_cards - 1) * card_spacing
        available_width = width - total_spacing
        
        # Use integer division for base card width, but distribute remainder pixels
        base_card_width = available_width // num_cards
        remainder = available_width % num_cards
        
        logger.debug(f"Card extraction: base_width={base_card_width}, remainder={remainder}, total_spacing={total_spacing}")
        
        current_x = 0
        for i in range(num_cards):
            # Give extra pixels to later cards to use full width
            # This ensures the last card gets any remainder pixels
            extra_pixels = 1 if i >= (num_cards - remainder) else 0
            card_width = base_card_width + extra_pixels
            
            x1 = current_x
            x2 = current_x + card_width
            
            # Ensure we don't go out of bounds
            x2 = min(x2, width)
            
            # Log extraction details for debugging
            logger.debug(f"Extracting card {i}: x=[{x1}:{x2}], width={x2-x1}")
            
            card_img = img[:, x1:x2]
            
            # Validate extracted region
            if card_img.size == 0 or card_img.shape[1] < 5:
                logger.warning(f"Card {i} region too small or empty: shape={card_img.shape}")
                cards.append(None)
            else:
                # For board cards, pass the card index for better logging
                board_index = i if not use_hero_templates else None
                card = self.recognize_card(card_img, use_hero_templates=use_hero_templates, board_card_index=board_index)
                cards.append(card)
                
                if card:
                    conf_str = f"{self.last_confidence_scores[-1]:.3f}" if self.last_confidence_scores else "N/A"
                    logger.info(f"{template_type.capitalize()} card {i}: {card} (confidence: {conf_str})")
                else:
                    logger.warning(f"{template_type.capitalize()} card {i}: NOT RECOGNIZED (region: {x1}-{x2}, width: {x2-x1})")
            
            # Move to next card position (card width + spacing)
            current_x = x2 + card_spacing
        
        # Log summary
        recognized_count = len([c for c in cards if c is not None])
        logger.info(f"Card recognition summary: {recognized_count}/{num_cards} {template_type} cards recognized")
        
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
