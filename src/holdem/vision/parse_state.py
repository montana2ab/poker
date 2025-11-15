"""Parse complete game state from vision."""

import cv2
import numpy as np
import time
from pathlib import Path
from typing import Optional, List, Tuple, Dict
import re
from decimal import Decimal
from dataclasses import dataclass, field
from holdem.types import TableState, PlayerState, Street, Card
from holdem.vision.calibrate import TableProfile
from holdem.vision.cards import CardRecognizer
from holdem.vision.ocr import OCREngine
from holdem.vision.vision_performance_config import VisionPerformanceConfig
from holdem.vision.vision_cache import BoardCache, HeroCache, OcrCacheManager
from holdem.utils.logging import get_logger

logger = get_logger("vision.parse_state")

# Import VisionMetrics if available
try:
    from holdem.vision.vision_metrics import VisionMetrics
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False
    VisionMetrics = None


# Helper to robustly parse stack/amounts from OCR text (locale-aware)
def _parse_amount_from_text(txt: str) -> Optional[float]:
    """Parse amounts like '1,234.50', '€12,50', '$0.25' into float."""
    if not txt:
        return None
    s = txt.strip()
    # Keep only digits, separators, spaces, and currency signs
    s = re.sub(r"[^\d,.\s]", "", s)
    s = s.strip()
    if not s:
        return None
    # Normalize decimal separators:
    # - if both ',' and '.' are present, assume '.' is decimal (remove commas as thousands)
    # - else, treat ',' as decimal
    if ("," in s) and ("." in s):
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(Decimal(s))
    except Exception:
        return None


def is_button_label(name: str) -> bool:
    """
    Return True if 'name' looks like a button label (Raise, Call, Bet, Fold, Check, All-in)
    rather than a player name.
    
    These labels appear from OCR reading action buttons and should never be
    interpreted as player names in action events.
    
    Args:
        name: The OCR name to check
        
    Returns:
        True if it's a button label, False otherwise
    
    Examples:
        >>> is_button_label("Raise")
        True
        >>> is_button_label("Call")
        True
        >>> is_button_label("call")
        True
        >>> is_button_label("ALL-IN")
        True
        >>> is_button_label("Player123")
        False
        >>> is_button_label("guyeast")
        False
    """
    if not name:
        return False
    
    cleaned = name.strip().lower()
    button_words = {
        "raise",
        "call",
        "bet",
        "fold",
        "check",
        "all-in",
        "all in",
        "allin",
    }
    
    is_button = cleaned in button_words
    if is_button:
        logger.debug(f"[VISION] Detected button label: '{name}'")
    
    return is_button


def is_showdown_won_label(name: str) -> bool:
    """
    Retourne True si le nom OCR correspond à un label de type 'Won 5,249'
    et non à un pseudo de joueur.
    
    Ces labels apparaissent lors du showdown quand un joueur gagne le pot,
    et ne doivent jamais être interprétés comme des actions de mise (BET).
    
    Args:
        name: Le nom OCR à vérifier
        
    Returns:
        True si c'est un label de showdown, False sinon
    
    Examples:
        >>> is_showdown_won_label("Won 5,249")
        True
        >>> is_showdown_won_label("Won 2,467")
        True
        >>> is_showdown_won_label("Player123")
        False
        >>> is_showdown_won_label("Won")
        False
    """
    if not name:
        return False
    
    # Regex pattern: "Won" followed by whitespace and numbers with optional separators
    # ^Won\s+[0-9,.\s]+$
    pattern = r'^Won\s+[0-9,.\s]+$'
    
    if re.match(pattern, name.strip(), re.IGNORECASE):
        logger.debug(f"[SHOWDOWN] Detected showdown label: '{name}'")
        return True
    
    return False


@dataclass
class HeroCardsTracker:
    """Tracker for hero cards to ensure stability across frames.
    
    This prevents card recognition from degrading when one card's confidence
    temporarily drops (e.g., Kd 9s → Kd alone) by requiring multiple consistent
    frames before accepting new cards.
    """
    confirmed_cards: Optional[List[Card]] = None  # Validated cards for current hand
    current_candidate: Optional[List[Card]] = None  # Latest candidate from OCR
    current_scores: Optional[List[float]] = None  # Confidence scores for candidate
    frames_stable: int = 0  # Number of consecutive frames with same candidate
    stability_threshold: int = 2  # Number of frames needed to confirm new cards
    
    def update(self, cards: Optional[List[Card]], scores: Optional[List[float]]) -> Optional[List[Card]]:
        """Update tracker with new OCR reading and return best cards to use.
        
        Args:
            cards: Newly detected cards (may be None or partial)
            scores: Confidence scores for detected cards
            
        Returns:
            Best cards to use (confirmed or candidate)
        """
        # If no cards detected, keep existing confirmed cards
        if not cards or len(cards) == 0:
            logger.debug("[HERO CARDS] No cards detected, keeping confirmed cards")
            return self.confirmed_cards
        
        # CRITICAL: Once we have 2 confirmed cards, never downgrade to fewer cards
        if self.confirmed_cards and len(self.confirmed_cards) == 2:
            # If new detection has fewer than 2 cards, ignore it and keep confirmed cards
            if len(cards) < 2:
                logger.debug(
                    f"[HERO CARDS] Ignoring downgrade from 2 confirmed cards to {len(cards)} card(s). "
                    f"Keeping confirmed: {self._cards_str(self.confirmed_cards)}"
                )
                return self.confirmed_cards
            
            # If new detection has 2 cards but they're different, require stability before replacing
            if not self._cards_match(cards, self.confirmed_cards):
                logger.debug(
                    f"[HERO CARDS] Detected different 2-card hand while already confirmed. "
                    f"Confirmed: {self._cards_str(self.confirmed_cards)}, "
                    f"New: {self._cards_str(cards)}"
                )
                # This might indicate a new hand - allow it but require stability
                # Fall through to normal candidate tracking
        
        # Check if this matches our current candidate
        if self._cards_match(cards, self.current_candidate):
            self.frames_stable += 1
            logger.debug(f"[HERO CARDS] Candidate stable for {self.frames_stable} frames: {self._cards_str(cards)}")
        else:
            # New candidate detected
            self.current_candidate = cards
            self.current_scores = scores
            self.frames_stable = 1
            logger.debug(f"[HERO CARDS] New candidate detected: {self._cards_str(cards)}")
        
        # If candidate is stable enough, confirm it
        if self.frames_stable >= self.stability_threshold:
            if not self._cards_match(self.confirmed_cards, self.current_candidate):
                # Special log message when confirming 2 cards for the first time
                if len(self.current_candidate) == 2 and (not self.confirmed_cards or len(self.confirmed_cards) < 2):
                    logger.info(f"[HERO CARDS] Confirmed hero cards for current hand: {self._cards_str(self.current_candidate)}")
                else:
                    logger.info(f"[HERO CARDS] Confirming stable cards: {self._cards_str(self.current_candidate)}")
                self.confirmed_cards = self.current_candidate
        
        # Return best available cards
        return self.confirmed_cards if self.confirmed_cards else self.current_candidate
    
    def reset(self):
        """Reset tracker for new hand."""
        logger.debug("[HERO CARDS] Resetting tracker for new hand")
        self.confirmed_cards = None
        self.current_candidate = None
        self.current_scores = None
        self.frames_stable = 0
    
    def _cards_match(self, cards1: Optional[List[Card]], cards2: Optional[List[Card]]) -> bool:
        """Check if two card lists match."""
        if cards1 is None or cards2 is None:
            return cards1 is cards2
        if len(cards1) != len(cards2):
            return False
        return all(str(c1) == str(c2) for c1, c2 in zip(cards1, cards2))
    
    def _cards_str(self, cards: Optional[List[Card]]) -> str:
        """Convert cards to string for logging."""
        if not cards:
            return "None"
        return ", ".join(str(c) for c in cards)


class StateParser:
    """Parse complete table state from screenshot."""
    
    def __init__(
        self, 
        profile: TableProfile,
        card_recognizer: CardRecognizer,
        ocr_engine: OCREngine,
        debug_dir: Optional[Path] = None,
        vision_metrics: Optional['VisionMetrics'] = None,
        perf_config: Optional[VisionPerformanceConfig] = None,
        hero_position: Optional[int] = None
    ):
        self.profile = profile
        self.card_recognizer = card_recognizer
        self.ocr_engine = ocr_engine
        self.debug_dir = debug_dir
        self.vision_metrics = vision_metrics
        self._debug_counter = 0
        self.hero_cards_tracker = HeroCardsTracker()  # Track stable hero cards
        self._last_pot = 0.0  # Track pot for regression detection
        
        # Store fixed hero position if provided (takes precedence over profile.hero_position)
        self.fixed_hero_position = hero_position
        
        # Performance optimization config
        self.perf_config = perf_config or VisionPerformanceConfig.default()
        
        # Caching for performance
        self.board_cache = BoardCache(
            stability_threshold=self.perf_config.board_cache.stability_threshold
        ) if self.perf_config.enable_caching and self.perf_config.board_cache.enabled else None
        
        self.hero_cache = HeroCache(
            stability_threshold=self.perf_config.hero_cache.stability_threshold
        ) if self.perf_config.enable_caching and self.perf_config.hero_cache.enabled else None
        
        # OCR amount cache with enable_amount_cache flag
        self.ocr_cache_manager = OcrCacheManager() if (
            self.perf_config.enable_caching and 
            self.perf_config.cache_roi_hash and 
            self.perf_config.enable_amount_cache
        ) else None
        
        # Track previous stacks for unlock detection
        self._previous_stacks: Dict[int, float] = {}
        
        # Health check for disabled homography (track recent parse validity)
        self._recent_parse_health: list = []  # List of booleans indicating parse health
        self._health_check_window = perf_config.detect_table.health_check_window if perf_config else 20
    
    def parse(self, screenshot: np.ndarray, frame_index: int = 0) -> Optional[TableState]:
        """Parse table state from screenshot.
        
        Args:
            screenshot: Screenshot image to parse
            frame_index: Frame number for light parse logic (0 = always full parse)
            
        Returns:
            TableState or None if parsing failed
        """
        try:
            # Track parse latency if metrics are enabled
            parse_start = time.time() if self.vision_metrics else None
            
            # Increment debug counter for each parse call
            if self.debug_dir:
                self._debug_counter += 1
            
            # Determine if this is a full parse or light parse
            is_full_parse = True
            if self.perf_config.enable_light_parse and frame_index > 0:
                is_full_parse = (frame_index % self.perf_config.light_parse_interval == 0)
                if not is_full_parse:
                    logger.debug(f"[LIGHT PARSE] Frame {frame_index} - skipping heavy OCR")
            
            # Determine street based on existing board cache or quick check
            # We need to know the street before deciding whether to parse board
            initial_street = self._determine_initial_street()
            
            # Extract community cards - SKIP IN PREFLOP (optimization)
            board = []
            if initial_street == Street.PREFLOP:
                # In PREFLOP, board is always empty - no need to parse
                board = [None] * 5
                logger.debug("[PREFLOP OPTIMIZATION] Skipping board card recognition (no board in preflop)")
            else:
                # Parse board for FLOP/TURN/RIVER, passing initial_street hint for optimization
                board = self._parse_board(screenshot, is_full_parse=is_full_parse, current_street=initial_street)
            
            # Determine street based on board cards
            num_board_cards = len([c for c in board if c is not None])
            if num_board_cards == 0:
                street = Street.PREFLOP
            elif num_board_cards == 3:
                street = Street.FLOP
            elif num_board_cards == 4:
                street = Street.TURN
            elif num_board_cards == 5:
                street = Street.RIVER
            else:
                street = Street.PREFLOP
            
            # Extract pot
            pot = self._parse_pot(screenshot, is_full_parse=is_full_parse)
            
            # Detect new hand and reset caches if needed
            # New hand signals:
            # 1. PREFLOP with empty board
            # 2. Pot reset to blind levels (or small value)
            is_new_hand = self._detect_new_hand(street, num_board_cards, pot)
            
            if is_new_hand:
                logger.info("[NEW HAND] Detected new hand, resetting board and hero caches")
                if self.board_cache:
                    self.board_cache.reset_for_new_hand()
                if self.hero_cache:
                    self.hero_cache.reset()
                    self.hero_cards_tracker.reset()
            
            # Parse button position (dealer button)
            button_position = self._parse_button_position(screenshot)
            
            # Extract player states and check for showdown labels
            players, has_showdown_label = self._parse_players(screenshot, is_full_parse=is_full_parse)
            
            # Health check for disabled homography
            self._check_parse_health(pot, players)
            
            # Try to infer button position from blinds (if vision-based detection didn't work)
            inferred_button = self._infer_button_from_blinds(players)
            if inferred_button is not None:
                button_position = inferred_button
            
            # Detect pot regression (inconsistent state)
            state_inconsistent = False
            if self._last_pot > 0 and pot < self._last_pot and abs(pot - self._last_pot) > 0.01:
                # Pot decreased without apparent reason (no new hand detected yet)
                # This could be a timing issue, OCR error, or actual end of hand
                logger.warning(f"[STATE] Pot decreased from {self._last_pot:.2f} to {pot:.2f} - marking state as inconsistent")
                state_inconsistent = True
            
            # Update last pot
            self._last_pot = pot
            
            # Calculate current_bet (highest bet this round)
            current_bet = max([p.bet_this_round for p in players], default=0.0)
            
            # Get hero position - use fixed position if provided, otherwise use profile
            if self.fixed_hero_position is not None:
                hero_position = self.fixed_hero_position
            else:
                hero_position = self.profile.hero_position
            
            # Calculate hero-specific values if hero is known
            is_in_position = False
            to_call = 0.0
            effective_stack = 0.0
            spr = 0.0
            
            if hero_position is not None and 0 <= hero_position < len(players):
                hero = players[hero_position]
                
                # Calculate to_call (amount hero needs to call)
                to_call = max(0.0, current_bet - hero.bet_this_round)
                
                # Calculate is_in_position for heads-up (2 players)
                # In HU: Button (BTN) is Small Blind (SB) and has position postflop
                # Big Blind (BB) is out of position postflop
                num_active = len([p for p in players if not p.folded])
                if num_active == 2:
                    # Heads-up position logic
                    if street == Street.PREFLOP:
                        # Preflop: BB has position (acts last), BTN (SB) is OOP
                        is_in_position = (hero_position != button_position)
                    else:
                        # Postflop: BTN (SB) has position, BB is OOP
                        is_in_position = (hero_position == button_position)
                else:
                    # Multi-way: need to determine based on button and active players
                    # For simplicity, assume hero is IP if acting after most players postflop
                    # This is a simplification and may need refinement for 6-max
                    is_in_position = self._calculate_multiway_position(hero_position, button_position, players, street)
                
                # Calculate effective_stack (min of hero stack and largest opponent stack)
                opponent_stacks = [p.stack for p in players if p.position != hero_position and not p.folded]
                max_opponent_stack = max(opponent_stacks, default=0.0)
                effective_stack = min(hero.stack, max_opponent_stack)
                
                # Calculate SPR (stack-to-pot ratio)
                # Use small epsilon to avoid division by zero while minimizing impact on calculation
                spr = effective_stack / max(pot, 0.01)
            
            # Create table state
            state = TableState(
                street=street,
                pot=pot,
                board=[c for c in board if c is not None],
                players=players,
                current_bet=current_bet,
                small_blind=1.0,
                big_blind=2.0,
                button_position=button_position,
                hero_position=hero_position,
                is_in_position=is_in_position,
                to_call=to_call,
                effective_stack=effective_stack,
                spr=spr,
                frame_has_showdown_label=has_showdown_label,
                state_inconsistent=state_inconsistent,
                last_pot=self._last_pot
            )
            
            # Record parse latency if metrics are enabled
            if self.vision_metrics and parse_start is not None:
                parse_latency_ms = (time.time() - parse_start) * 1000
                self.vision_metrics.record_parse_latency(parse_latency_ms, is_full_parse=is_full_parse)
            
            logger.debug(f"Parsed state: {street.name}, pot={pot}, current_bet={current_bet}, "
                        f"button={button_position}, hero_pos={hero_position}, is_IP={is_in_position}, "
                        f"to_call={to_call:.2f}, eff_stack={effective_stack:.2f}, SPR={spr:.2f}, "
                        f"{len(players)} players")
            logger.info(f"Parsed state: {street.name}, pot={pot:.2f}, current_bet={current_bet:.2f}, "
                       f"button={button_position}, hero_pos={hero_position}, {len(players)} players")
            return state
            
        except Exception as e:
            logger.error(f"Error parsing state: {e}")
            return None
    
    def _parse_board(self, img: np.ndarray, is_full_parse: bool = True, current_street: Optional[Street] = None) -> list:
        """Parse community cards from image with caching and zone-based detection.
        
        Args:
            img: Screenshot image
            is_full_parse: Whether to perform full recognition or use cache
            current_street: Current street (PREFLOP/FLOP/TURN/RIVER) for optimization
            
        Returns:
            List of 5 cards (some may be None)
        """
        # PREFLOP: Skip board detection entirely
        if current_street == Street.PREFLOP:
            logger.debug("[BOARD] Skipping board detection in PREFLOP")
            if self.board_cache:
                # Return existing cards if any (should be empty)
                return self.board_cache.cards
            return [None] * 5
        
        # Check if board_cache is available
        if not self.board_cache:
            # Fall back to old behavior if cache not enabled
            return self._parse_board_legacy(img, is_full_parse)
        
        # Use zone-based detection if board_regions is configured
        if self.profile.has_board_regions():
            return self._parse_board_zones(img, is_full_parse, current_street)
        else:
            # Fall back to legacy single-region detection
            return self._parse_board_legacy(img, is_full_parse)
    
    def _parse_board_zones(self, img: np.ndarray, is_full_parse: bool, current_street: Optional[Street]) -> list:
        """Parse board cards using zone-based detection (flop/turn/river).
        
        Args:
            img: Screenshot image
            is_full_parse: Whether to perform full recognition or use cache
            current_street: Current street hint (may be None)
            
        Returns:
            List of 5 cards (some may be None)
        """
        # If all zones are detected, return cached cards
        if self.board_cache.has_river():
            logger.debug("[BOARD ZONES] River complete, using cached cards")
            return self.board_cache.cards
        
        # Scan flop zone if not yet detected
        if self.board_cache.should_scan_flop():
            flop_region = self.profile.get_flop_region()
            if flop_region:
                flop_cards = self._scan_board_zone(img, flop_region, 3, "flop")
                if flop_cards and len([c for c in flop_cards if c is not None]) == 3:
                    # Check stability before locking
                    self.board_cache.flop_stability_frames += 1
                    if self.board_cache.flop_stability_frames >= self.board_cache.stability_threshold:
                        self.board_cache.mark_flop(flop_cards)
                    else:
                        logger.debug(f"[BOARD ZONES] Flop stability: {self.board_cache.flop_stability_frames}/{self.board_cache.stability_threshold}")
                else:
                    self.board_cache.flop_stability_frames = 0
        
        # Scan turn zone if flop is detected and turn is not
        if self.board_cache.should_scan_turn():
            turn_region = self.profile.get_turn_region()
            if turn_region:
                turn_card = self._scan_board_zone(img, turn_region, 1, "turn")
                if turn_card and turn_card[0] is not None:
                    # Check stability before locking
                    self.board_cache.turn_stability_frames += 1
                    if self.board_cache.turn_stability_frames >= self.board_cache.stability_threshold:
                        self.board_cache.mark_turn(turn_card[0])
                    else:
                        logger.debug(f"[BOARD ZONES] Turn stability: {self.board_cache.turn_stability_frames}/{self.board_cache.stability_threshold}")
                else:
                    self.board_cache.turn_stability_frames = 0
        
        # Scan river zone if turn is detected and river is not
        if self.board_cache.should_scan_river():
            river_region = self.profile.get_river_region()
            if river_region:
                river_card = self._scan_board_zone(img, river_region, 1, "river")
                if river_card and river_card[0] is not None:
                    # Check stability before locking
                    self.board_cache.river_stability_frames += 1
                    if self.board_cache.river_stability_frames >= self.board_cache.stability_threshold:
                        self.board_cache.mark_river(river_card[0])
                    else:
                        logger.debug(f"[BOARD ZONES] River stability: {self.board_cache.river_stability_frames}/{self.board_cache.stability_threshold}")
                else:
                    self.board_cache.river_stability_frames = 0
        
        return self.board_cache.cards
    
    def _scan_board_zone(self, img: np.ndarray, region: Dict[str, int], num_cards: int, zone_name: str) -> List[Optional[Card]]:
        """Scan a specific board zone for cards.
        
        Args:
            img: Screenshot image
            region: Region dict with x, y, width, height
            num_cards: Expected number of cards in zone
            zone_name: Name of zone for logging (flop/turn/river)
            
        Returns:
            List of recognized cards (or None)
        """
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h > img.shape[0] or x + w > img.shape[1]:
            logger.error(f"[BOARD ZONES] {zone_name} region ({x},{y},{w},{h}) out of bounds for image shape {img.shape}")
            return [None] * num_cards
        
        card_region = img[y:y+h, x:x+w]
        
        logger.debug(f"[BOARD ZONES] Scanning {zone_name} region ({x},{y},{w},{h})")
        
        # Save debug image if debug mode is enabled
        if self.debug_dir:
            debug_path = self.debug_dir / f"board_{zone_name}_{self._debug_counter:04d}.png"
            try:
                success = cv2.imwrite(str(debug_path), card_region)
                if success:
                    logger.debug(f"Saved {zone_name} region to {debug_path}")
            except Exception as e:
                logger.warning(f"Error saving debug image: {e}")
        
        cards = self.card_recognizer.recognize_cards(
            card_region,
            num_cards=num_cards,
            card_spacing=getattr(self.profile, 'card_spacing', 0)
        )
        
        # Track card recognition metrics if enabled
        if self.vision_metrics and cards:
            confidences = self.card_recognizer.last_confidence_scores
            for i, card in enumerate(cards):
                if card is not None:
                    confidence = confidences[i] if i < len(confidences) else 0.0
                    self.vision_metrics.record_card_recognition(
                        detected_card=str(card),
                        expected_card=None,
                        confidence=confidence
                    )
        
        # Log the result
        if cards:
            cards_str = ", ".join(str(c) for c in cards if c is not None)
            if cards_str:
                logger.info(f"[BOARD ZONES] Detected {zone_name}: {cards_str}")
        
        return cards
    
    def _parse_board_legacy(self, img: np.ndarray, is_full_parse: bool = True) -> list:
        """Parse community cards using legacy single-region detection.
        
        Args:
            img: Screenshot image
            is_full_parse: Whether to perform full recognition or use cache
            
        Returns:
            List of 5 cards (some may be None)
        """
        if not self.profile.card_regions:
            logger.warning("No card regions defined in profile")
            return [None] * 5
        
        region = self.profile.card_regions[0]
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h > img.shape[0] or x + w > img.shape[1]:
            logger.error(f"Card region ({x},{y},{w},{h}) out of bounds for image shape {img.shape}")
            return [None] * 5
        
        card_region = img[y:y+h, x:x+w]
        
        # Try to use board cache if enabled
        if self.board_cache and not is_full_parse:
            # Check if cache is stable - if so, use it
            cached_cards = self.board_cache.get_cached_cards()
            if cached_cards is not None:
                logger.debug(f"[BOARD CACHE] Using cached board cards")
                return cached_cards
        
        # Need to run recognition
        logger.debug(f"Extracting board cards from region ({x},{y},{w},{h})")
        
        # Save debug image if debug mode is enabled
        if self.debug_dir:
            debug_path = self.debug_dir / f"board_region_{self._debug_counter:04d}.png"
            try:
                success = cv2.imwrite(str(debug_path), card_region)
                if success:
                    logger.debug(f"Saved board region to {debug_path}")
                else:
                    logger.warning(f"Failed to save debug image to {debug_path}")
            except Exception as e:
                logger.warning(f"Error saving debug image: {e}")
        
        cards = self.card_recognizer.recognize_cards(
            card_region, 
            num_cards=5,
            card_spacing=getattr(self.profile, 'card_spacing', 0)
        )
        
        # Determine street from cards
        num_board_cards = len([c for c in cards if c is not None])
        if num_board_cards == 0:
            current_street = Street.PREFLOP
        elif num_board_cards == 3:
            current_street = Street.FLOP
        elif num_board_cards == 4:
            current_street = Street.TURN
        elif num_board_cards == 5:
            current_street = Street.RIVER
        else:
            current_street = Street.PREFLOP
        
        # Update board cache if enabled
        if self.board_cache:
            self.board_cache.update(current_street, cards)
        
        # Track card recognition metrics if enabled
        if self.vision_metrics:
            # Get confidence scores from card recognizer
            confidences = self.card_recognizer.last_confidence_scores
            for i, card in enumerate(cards):
                if card is not None:
                    # Get confidence for this card (if available)
                    confidence = confidences[i] if i < len(confidences) else 0.0
                    self.vision_metrics.record_card_recognition(
                        detected_card=str(card),
                        expected_card=None,
                        confidence=confidence
                    )
        
        # Log the result
        cards_str = ", ".join(str(c) for c in cards if c is not None)
        if cards_str:
            num_recognized = len([c for c in cards if c is not None])
            logger.info(f"Recognized {num_recognized} board card(s): {cards_str}")
        else:
            logger.warning("No board cards recognized - check card templates and region coordinates")
        
        return cards
    
    def _parse_pot(self, img: np.ndarray, is_full_parse: bool = True) -> float:
        """Parse pot amount from image with OCR caching.
        
        Args:
            img: Screenshot image
            is_full_parse: Whether to perform OCR or use cache
            
        Returns:
            Pot amount as float
        """
        if not self.profile.pot_region:
            return 0.0
        
        region = self.profile.pot_region
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h > img.shape[0] or x + w > img.shape[1]:
            return 0.0
        
        pot_region = img[y:y+h, x:x+w]
        
        # Check if we should run OCR based on cache
        should_run_ocr = True
        if self.ocr_cache_manager:
            pot_cache = self.ocr_cache_manager.get_pot_cache()
            # Always compute hash to check/update cache, even on full parse
            should_run_ocr = pot_cache.should_run_ocr(pot_region)
            
            # On light parse, we can skip OCR if cache is valid
            if not is_full_parse and not should_run_ocr:
                cached_pot = pot_cache.get_cached_value()
                if cached_pot is not None:
                    logger.info(f"[VISION] Reusing cached pot (hash unchanged): {cached_pot:.2f}")
                    self.ocr_cache_manager.record_cache_hit("pot")
                    return cached_pot
        
        # Downscale ROI if needed
        if self.perf_config.downscale_ocr_rois:
            pot_region = self._downscale_roi(pot_region)
        
        # Run OCR
        logger.info("[VISION] OCR pot (image changed)")
        pot = self.ocr_engine.extract_number(pot_region)
        pot_value = pot if pot is not None else 0.0
        
        # Update cache if enabled
        if self.ocr_cache_manager:
            pot_cache = self.ocr_cache_manager.get_pot_cache()
            pot_cache.update_value(pot_value, confidence=None)  # OCR engine doesn't provide confidence yet
            self.ocr_cache_manager.record_ocr_call("pot")
        
        # Track OCR and amount metrics if enabled
        if self.vision_metrics and pot is not None:
            self.vision_metrics.record_amount(
                detected_amount=pot,
                expected_amount=None,  # No ground truth in production
                category="pot"
            )
        
        return pot_value
    
    def _downscale_roi(self, roi: np.ndarray) -> np.ndarray:
        """Downscale ROI if it exceeds maximum dimension.
        
        Args:
            roi: Region of interest image
            
        Returns:
            Downscaled ROI or original if small enough
        """
        h, w = roi.shape[:2]
        max_side = max(h, w)
        max_dim = self.perf_config.max_roi_dimension
        
        if max_side > max_dim:
            scale = max_dim / max_side
            new_w = int(w * scale)
            new_h = int(h * scale)
            roi = cv2.resize(roi, (new_w, new_h), interpolation=cv2.INTER_AREA)
            logger.debug(f"[OCR OPTIMIZATION] Downscaled ROI from {w}x{h} to {new_w}x{new_h}")
        
        return roi
    
    def _parse_players(self, img: np.ndarray, is_full_parse: bool = True) -> Tuple[list, bool]:
        """Parse player states from image.
        
        Returns:
            Tuple of (players list, has_showdown_label boolean)
        """
        players = []
        has_showdown_label = False  # Track if any showdown label detected
        parse_opp = getattr(self.profile, "parse_opponent_cards", False)
        
        # Use fixed hero position if provided, otherwise fallback to profile
        if self.fixed_hero_position is not None:
            hero_pos = self.fixed_hero_position
        else:
            hero_pos = getattr(self.profile, "hero_position", None)
        
        for i, player_region in enumerate(self.profile.player_regions):
            table_position = player_region.get('position', i)
            # Extract stack
            stack_reg = player_region.get('stack_region', {})
            x, y, w, h = stack_reg.get('x', 0), stack_reg.get('y', 0), \
                         stack_reg.get('width', 0), stack_reg.get('height', 0)

            stack = 1000.0  # Default
            if y + h <= img.shape[0] and x + w <= img.shape[1] and w > 0 and h > 0:
                stack_img = img[y:y+h, x:x+w]
                
                # Determine if we should run OCR (hero always updates, opponents can use cache on light parse)
                should_run_ocr_decision = is_full_parse or (table_position == hero_pos)
                should_run_ocr = should_run_ocr_decision
                
                if self.ocr_cache_manager:
                    stack_cache = self.ocr_cache_manager.get_stack_cache(table_position)
                    # Always compute hash to check/update cache
                    cache_says_unchanged = not stack_cache.should_run_ocr(stack_img)
                    
                    # On light parse for non-hero, we can skip OCR if cache is valid
                    if not should_run_ocr_decision and cache_says_unchanged:
                        cached_stack = stack_cache.get_cached_value()
                        if cached_stack is not None:
                            stack = cached_stack
                            logger.info(f"[VISION] Reusing cached stack for seat {table_position} (hash unchanged): {stack:.2f}")
                            self.ocr_cache_manager.record_cache_hit("stack")
                            should_run_ocr = False
                
                if should_run_ocr:
                    # Downscale ROI if needed
                    stack_img_processed = self._downscale_roi(stack_img) if self.perf_config.downscale_ocr_rois else stack_img
                    
                    logger.info(f"[VISION] OCR stack for seat {table_position} (image changed)")
                    parsed_stack = self.ocr_engine.extract_number(stack_img_processed)
                    if parsed_stack is None:
                        # Fallback: OCR raw text then parse locale-aware
                        raw_txt = self.ocr_engine.read_text(stack_img_processed) or ""
                        parsed_stack = _parse_amount_from_text(raw_txt)
                    if parsed_stack is not None:
                        stack = parsed_stack
                        logger.info(f"Player {table_position} stack OCR result: {stack:.2f}")
                        
                        # Update cache if enabled
                        if self.ocr_cache_manager:
                            stack_cache = self.ocr_cache_manager.get_stack_cache(table_position)
                            stack_cache.update_value(stack, confidence=None)
                            self.ocr_cache_manager.record_ocr_call("stack")
                        
                        # Track amount metrics if enabled
                        if self.vision_metrics:
                            self.vision_metrics.record_amount(
                                detected_amount=stack,
                                expected_amount=None,  # No ground truth in production
                                category="stack"
                            )
            
            # Check for player leaving (stack went to 0) and unlock name if needed
            # This must happen BEFORE name OCR so unlocked seats can be re-detected
            if self.ocr_cache_manager:
                name_cache = self.ocr_cache_manager.get_name_cache()
                previous_stack = self._previous_stacks.get(table_position, 0.0)
                
                # Unlock if stack went to 0 and name was locked
                if stack <= 0.01 and previous_stack > 0.01:
                    if name_cache.player_name_locked.get(table_position, False):
                        logger.info(f"[PLAYER NAME CACHE] Unlocking seat {table_position} due to stack=0")
                        name_cache.unlock_seat(table_position)
                
                # Update previous stack
                self._previous_stacks[table_position] = stack

            # Extract name
            name_reg = player_region.get('name_region', {})
            x, y, w, h = name_reg.get('x', 0), name_reg.get('y', 0), \
                         name_reg.get('width', 0), name_reg.get('height', 0)

            name = f"Player{table_position}"
            
            # Check if name is locked in cache
            if self.ocr_cache_manager:
                name_cache = self.ocr_cache_manager.get_name_cache()
                cached_name = name_cache.get_cached_name(table_position)
                if cached_name:
                    # Use cached locked name
                    name = cached_name
                    logger.debug(f"[PLAYER NAME CACHE] seat={table_position} name={name} (locked)")
                elif y + h <= img.shape[0] and x + w <= img.shape[1] and w > 0 and h > 0:
                    # Name not locked - run OCR
                    name_img = img[y:y+h, x:x+w]
                    parsed_name = self.ocr_engine.read_text(name_img)
                    if parsed_name:
                        parsed_name_stripped = parsed_name.strip()
                        
                        # Check if this is a button label (Raise, Call, Bet, Fold, Check, All-in)
                        if is_button_label(parsed_name_stripped):
                            logger.info(f"[VISION] Ignoring button label as player name at position {table_position}: {parsed_name_stripped}")
                            # Keep default player name instead of button label
                            # This prevents the button label from being treated as a real player
                        # Check if this is a showdown "Won X,XXX" label
                        elif is_showdown_won_label(parsed_name_stripped):
                            logger.info(f"[SHOWDOWN] Ignoring 'Won X,XXX' label as player name at position {table_position}: {parsed_name_stripped}")
                            has_showdown_label = True  # Mark that we found a showdown label
                            # Keep default player name instead of showdown label
                            # This prevents the showdown label from being treated as a real player
                        else:
                            name = parsed_name_stripped
                            logger.info(f"Player {table_position} name OCR: {name}")
                            # Update name cache for stability tracking and potential locking
                            name_cache.update_name(table_position, name, default_name=f"Player{table_position}")
            elif y + h <= img.shape[0] and x + w <= img.shape[1] and w > 0 and h > 0:
                # No cache manager - use original logic
                name_img = img[y:y+h, x:x+w]
                parsed_name = self.ocr_engine.read_text(name_img)
                if parsed_name:
                    parsed_name_stripped = parsed_name.strip()
                    
                    # Check if this is a button label (Raise, Call, Bet, Fold, Check, All-in)
                    if is_button_label(parsed_name_stripped):
                        logger.info(f"[VISION] Ignoring button label as player name at position {table_position}: {parsed_name_stripped}")
                        # Keep default player name instead of button label
                        # This prevents the button label from being treated as a real player
                    # Check if this is a showdown "Won X,XXX" label
                    elif is_showdown_won_label(parsed_name_stripped):
                        logger.info(f"[SHOWDOWN] Ignoring 'Won X,XXX' label as player name at position {table_position}: {parsed_name_stripped}")
                        has_showdown_label = True  # Mark that we found a showdown label
                        # Keep default player name instead of showdown label
                        # This prevents the showdown label from being treated as a real player
                    else:
                        name = parsed_name_stripped
                        logger.info(f"Player {table_position} name OCR: {name}")

            # Extract bet amount for this round
            bet_this_round = 0.0
            bet_reg = player_region.get('bet_region', {})
            x, y, w, h = bet_reg.get('x', 0), bet_reg.get('y', 0), \
                         bet_reg.get('width', 0), bet_reg.get('height', 0)
            if y + h <= img.shape[0] and x + w <= img.shape[1] and w > 0 and h > 0:
                bet_img = img[y:y+h, x:x+w]
                
                # Determine if we should run OCR
                should_run_ocr_decision = is_full_parse
                should_run_ocr = should_run_ocr_decision
                
                if self.ocr_cache_manager:
                    bet_cache = self.ocr_cache_manager.get_bet_cache(table_position)
                    # Always compute hash to check/update cache
                    cache_says_unchanged = not bet_cache.should_run_ocr(bet_img)
                    
                    # On light parse, we can skip OCR if cache is valid
                    if not should_run_ocr_decision and cache_says_unchanged:
                        cached_bet = bet_cache.get_cached_value()
                        if cached_bet is not None:
                            bet_this_round = cached_bet
                            logger.info(f"[VISION] Reusing cached bet for seat {table_position} (hash unchanged): {bet_this_round:.2f}")
                            self.ocr_cache_manager.record_cache_hit("bet")
                            should_run_ocr = False
                
                if should_run_ocr:
                    # Downscale ROI if needed
                    bet_img_processed = self._downscale_roi(bet_img) if self.perf_config.downscale_ocr_rois else bet_img
                    
                    logger.info(f"[VISION] OCR bet for seat {table_position} (image changed)")
                    parsed_bet = self.ocr_engine.extract_number(bet_img_processed)
                    if parsed_bet is None:
                        # Fallback: OCR raw text then parse locale-aware
                        raw_txt = self.ocr_engine.read_text(bet_img_processed) or ""
                        parsed_bet = _parse_amount_from_text(raw_txt)
                    if parsed_bet is not None:
                        # Only record bet if this is not a showdown label in the name region
                        # (prevents "Won 5,249" from being treated as a bet)
                        if not is_showdown_won_label(name):
                            bet_this_round = parsed_bet
                            logger.info(f"Player {table_position} bet OCR result: {bet_this_round:.2f}")
                            
                            # Update cache if enabled
                            if self.ocr_cache_manager:
                                bet_cache = self.ocr_cache_manager.get_bet_cache(table_position)
                                bet_cache.update_value(bet_this_round, confidence=None)
                                self.ocr_cache_manager.record_ocr_call("bet")
                        else:
                            logger.debug(f"[SHOWDOWN] Ignoring bet amount for showdown label at position {table_position}")

            # Extract player action (CALL, CHECK, BET, RAISE, FOLD, ALL-IN)
            last_action = None
            action_reg = player_region.get('action_region', {})
            x, y, w, h = action_reg.get('x', 0), action_reg.get('y', 0), \
                         action_reg.get('width', 0), action_reg.get('height', 0)
            if y + h <= img.shape[0] and x + w <= img.shape[1] and w > 0 and h > 0:
                action_img = img[y:y+h, x:x+w]
                detected_action = self.ocr_engine.detect_action(action_img)
                if detected_action:
                    # Map detected action string to ActionType enum
                    from holdem.types import ActionType
                    action_map = {
                        'FOLD': ActionType.FOLD,
                        'CHECK': ActionType.CHECK,
                        'CALL': ActionType.CALL,
                        'BET': ActionType.BET,
                        'RAISE': ActionType.RAISE,
                        'ALL-IN': ActionType.ALLIN,
                    }
                    last_action = action_map.get(detected_action)
                    if last_action:
                        logger.info(f"Player {table_position} action detected: {detected_action}")

            # Extract hole cards
            hole_cards = None
            if hero_pos is not None and table_position == hero_pos:
                logger.info(f"Parsing hero cards at position {table_position}")
                hole_cards = self._parse_player_cards(img, player_region, is_hero=True, is_full_parse=is_full_parse)
            elif parse_opp:
                logger.info(f"Parsing opponent cards at position {table_position}")
                # Templates héros et joueurs identiques -> on réutilise la même reco
                hole_cards = self._parse_player_cards(img, player_region, is_hero=False, is_full_parse=is_full_parse)

            player = PlayerState(
                name=name,
                stack=stack,
                position=table_position,
                bet_this_round=bet_this_round,
                folded=(last_action == ActionType.FOLD if last_action else False),
                all_in=(last_action == ActionType.ALLIN if last_action else False),
                hole_cards=hole_cards,
                last_action=last_action
            )
            players.append(player)

        return players, has_showdown_label
    
    def _parse_player_cards(self, img: np.ndarray, player_region: dict, is_hero: bool = False, is_full_parse: bool = True) -> Optional[List[Card]]:
        """Parse hole cards for a specific player.
        
        Args:
            img: Full table image
            player_region: Region definition for this player
            is_hero: True if parsing hero cards (enables sticky tracking and caching)
            is_full_parse: Whether to perform full recognition or use cache
        """
        card_reg = player_region.get('card_region', {})
        x, y, w, h = card_reg.get('x', 0), card_reg.get('y', 0), \
                    card_reg.get('width', 0), card_reg.get('height', 0)
        
        player_pos = player_region.get('position', 'unknown')
        logger.debug(f"Extracting player cards for position {player_pos} from region ({x},{y},{w},{h})")
        
        # Try to use hero cache if enabled - check if cards are stable
        if is_hero and self.hero_cache:
            cached_cards = self.hero_cache.get_cached_cards()
            if cached_cards and len(cached_cards) == 2:
                # Hero cache is stable - reuse cards without re-recognition
                logger.debug(f"[HERO CACHE] Hero cards reuse from cache: {', '.join(str(c) for c in cached_cards)} (no reparse needed)")
                return cached_cards
        
        if y + h <= img.shape[0] and x + w <= img.shape[1] and w > 0 and h > 0:
            card_region = img[y:y+h, x:x+w]
            
            # Save debug image if debug mode is enabled
            if self.debug_dir:
                debug_path = self.debug_dir / f"player_{player_pos}_cards_{self._debug_counter:04d}.png"
                try:
                    success = cv2.imwrite(str(debug_path), card_region)
                    if success:
                        logger.debug(f"Saved player {player_pos} card region to {debug_path}")
                    else:
                        logger.warning(f"Failed to save player {player_pos} debug image to {debug_path}")
                except Exception as e:
                    logger.warning(f"Error saving player {player_pos} debug image: {e}")
            
            # Hole cards are 2 cards - use hero templates
            # Skip empty check for hero cards as they should always be present when visible
            cards = self.card_recognizer.recognize_cards(
                card_region, 
                num_cards=2, 
                use_hero_templates=True, 
                skip_empty_check=True,
                card_spacing=getattr(self.profile, 'card_spacing', 0)
            )
            
            # Get confidence scores
            confidences = self.card_recognizer.last_confidence_scores if hasattr(self.card_recognizer, 'last_confidence_scores') else []
            
            # Track card recognition metrics if enabled
            if self.vision_metrics:
                for i, card in enumerate(cards):
                    if card is not None:
                        # Get confidence for this card (if available)
                        confidence = confidences[i] if i < len(confidences) else 0.0
                        self.vision_metrics.record_card_recognition(
                            detected_card=str(card),
                            expected_card=None,
                            confidence=confidence,
                            street="preflop",  # Hero cards are shown preflop
                            seat_position=player_pos
                        )
            
            # Filter out None values
            valid_cards = [c for c in cards if c is not None]
            
            # For hero cards, use sticky tracker to prevent degradation
            if is_hero and len(valid_cards) > 0:
                tracked_cards = self.hero_cards_tracker.update(valid_cards, confidences)
                
                # Update hero cache if enabled and we have 2 stable cards
                if self.hero_cache and tracked_cards and len(tracked_cards) == 2:
                    # Check if tracker has marked cards as stable
                    if self.hero_cards_tracker.confirmed_cards and len(self.hero_cards_tracker.confirmed_cards) == 2:
                        # Create hand_id for cache (simple but effective)
                        hand_id = int(self._last_pot * 100)
                        self.hero_cache.update(hand_id, tracked_cards)
                
                if tracked_cards:
                    cards_str = ", ".join(str(c) for c in tracked_cards)
                    logger.info(f"Hero cards (tracked): {cards_str}")
                    return tracked_cards
            
            # Log the result
            if len(valid_cards) > 0:
                cards_str = ", ".join(str(c) for c in valid_cards)
                logger.info(f"Recognized {len(valid_cards)} card(s) for player {player_pos}: {cards_str}")
                return valid_cards
            else:
                # For hero cards with tracker, return confirmed cards if available
                if is_hero:
                    tracked_cards = self.hero_cards_tracker.update(None, None)
                    if tracked_cards:
                        cards_str = ", ".join(str(c) for c in tracked_cards)
                        logger.info(f"Hero cards (from tracker, no new detection): {cards_str}")
                        return tracked_cards
                logger.warning(f"No cards recognized for player {player_pos} - check card templates and region coordinates")
        else:
            logger.error(f"Player {player_pos} card region ({x},{y},{w},{h}) out of bounds for image shape {img.shape}")
        
        return None
    
    def _parse_button_position(self, img: np.ndarray) -> int:
        """Parse dealer button position from image.
        
        Supports two detection modes:
        1. dealer_button_regions (list): Check each player position for button presence
        2. dealer_button_region (single): Use OCR/template matching on button area
        
        Returns:
            Position index (0-based) of the player with the dealer button.
        """
        # Mode 1: Check dealer_button_regions (list of regions, one per player)
        if hasattr(self.profile, 'dealer_button_regions') and self.profile.dealer_button_regions:
            button_positions = self.profile.dealer_button_regions
            best_score = 0.0
            best_position = 0
            
            for pos_idx, btn_region in enumerate(button_positions):
                if not btn_region:
                    continue
                    
                x = btn_region.get('x', 0)
                y = btn_region.get('y', 0)
                w = btn_region.get('width', 0)
                h = btn_region.get('height', 0)
                
                if y + h <= img.shape[0] and x + w <= img.shape[1] and w > 0 and h > 0:
                    btn_img = img[y:y+h, x:x+w]
                    
                    # Check for button presence using multiple methods
                    score = self._detect_button_presence(btn_img)
                    
                    if score > best_score:
                        best_score = score
                        best_position = pos_idx
            
            if best_score > 0.3:  # Threshold for confidence
                logger.info(f"Detected dealer button at position {best_position} (score: {best_score:.2f})")
                return best_position
            else:
                logger.debug(f"No dealer button detected with confidence (best score: {best_score:.2f})")
        
        # Mode 2: Single dealer_button_region (legacy support)
        if hasattr(self.profile, 'dealer_button_region') and self.profile.dealer_button_region:
            region = self.profile.dealer_button_region
            x, y, w, h = region.get('x', 0), region.get('y', 0), \
                         region.get('width', 0), region.get('height', 0)
            
            if y + h <= img.shape[0] and x + w <= img.shape[1] and w > 0 and h > 0:
                button_region = img[y:y+h, x:x+w]
                
                # Try OCR to detect "D" or "DEALER" text
                text = self.ocr_engine.read_text(button_region)
                if text and ('D' in text.upper() or 'DEALER' in text.upper()):
                    logger.info(f"Detected dealer button via OCR: {text}")
                    return 0  # Single region doesn't specify position
        
        logger.debug("No dealer_button_regions or dealer_button_region defined, defaulting to position 0")
        return 0
    
    def _detect_button_presence(self, img: np.ndarray) -> float:
        """Detect presence of dealer button in image region.
        
        Uses multiple heuristics to detect button:
        - Color-based detection (dealer buttons are often bright/distinctive)
        - Shape detection (circular buttons)
        - OCR for "D" or "DEALER" text
        
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if img.size == 0:
            return 0.0
        
        score = 0.0
        
        # Method 1: OCR for "D" or "DEALER" text
        try:
            text = self.ocr_engine.read_text(img, preprocess=False)
            text_upper = text.upper() if text else ""
            if 'D' in text_upper or 'DEALER' in text_upper or 'BTN' in text_upper:
                score += 0.6
                logger.debug(f"Button OCR match: {text}")
        except Exception as e:
            logger.debug(f"OCR error in button detection: {e}")
        
        # Method 2: Color-based detection (bright/distinctive colors)
        try:
            # Convert to HSV for better color detection
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            # Check for bright regions (dealer button is often bright)
            mean_intensity = np.mean(gray)
            if mean_intensity > 150:  # Bright region
                score += 0.2
                logger.debug(f"Button brightness match: {mean_intensity:.1f}")
            
            # Check for high contrast (button vs background)
            std_intensity = np.std(gray)
            if std_intensity > 30:  # High contrast
                score += 0.2
                logger.debug(f"Button contrast match: {std_intensity:.1f}")
        except Exception as e:
            logger.debug(f"Image processing error in button detection: {e}")
        
        return min(score, 1.0)
    
    def _infer_button_from_blinds(self, players: List[PlayerState]) -> Optional[int]:
        """Infer dealer button position from blind structure.
        
        In standard poker, the button is immediately before the small blind
        in the order of seats. This function identifies SB and BB by their
        bet amounts and calculates the button position.
        
        Args:
            players: List of PlayerState objects with bet_this_round populated
            
        Returns:
            Button position (0-based seat index) if successfully inferred,
            None if blind pattern is unclear or cannot be determined
            
        Algorithm:
            1. Collect all non-zero bets from bet_this_round
            2. Identify smallest bet as SB, next smallest as BB
            3. Find positions of players with SB and BB bets
            4. Calculate button as (SB_position - 1) mod num_players
            5. Handle edge cases (no blinds, heads-up, etc.)
        """
        if not players or len(players) < 2:
            logger.debug("[BUTTON] Not enough players to infer button from blinds")
            return None
        
        # Collect non-zero bets with their positions
        bets_with_positions = []
        for player in players:
            if player.bet_this_round > 0.01:  # Ignore zero or very small bets
                bets_with_positions.append((player.bet_this_round, player.position))
        
        if len(bets_with_positions) < 2:
            logger.debug("[BUTTON] Not enough non-zero bets to infer blinds")
            return None
        
        # Sort by bet amount to find SB (smallest) and BB (second smallest)
        bets_with_positions.sort(key=lambda x: x[0])
        
        # Get the two smallest bets
        sb_bet, sb_pos = bets_with_positions[0]
        bb_bet, bb_pos = bets_with_positions[1]
        
        # Validate that BB is roughly 2x SB (standard blind structure)
        # Allow some tolerance for rounding or non-standard structures
        expected_bb = sb_bet * 2
        if bb_bet < expected_bb * 0.8 or bb_bet > expected_bb * 1.3:
            logger.debug(
                f"[BUTTON] Blind structure unclear: SB={sb_bet:.2f}, BB={bb_bet:.2f} "
                f"(expected BB ~{expected_bb:.2f})"
            )
            return None
        
        # Button is immediately before SB in seat order
        # Special case for heads-up: button IS the small blind
        # In a 6-max game with positions 0-5:
        # If SB is at position 1, button is at position 0
        # If SB is at position 0, button is at position 5 (wraps around)
        num_players = len(players)
        
        if num_players == 2:
            # Heads-up: button posts the small blind
            button_pos = sb_pos
        else:
            # Multi-way: button is one seat before SB
            button_pos = (sb_pos - 1) % num_players
        
        logger.info(
            f"[BUTTON] Inferred from blinds: position={button_pos}, "
            f"SB_pos={sb_pos} (bet={sb_bet:.2f}), BB_pos={bb_pos} (bet={bb_bet:.2f})"
        )
        
        return button_pos
    
    def _calculate_multiway_position(
        self, 
        hero_pos: int, 
        button_pos: int, 
        players: List, 
        street: Street
    ) -> bool:
        """Calculate if hero is in position in a multiway pot.
        
        Args:
            hero_pos: Hero's position index
            button_pos: Button position index
            players: List of PlayerState objects
            street: Current street
            
        Returns:
            True if hero is in position, False otherwise
        """
        # For multiway pots, hero is in position if:
        # - Hero is on the button, OR
        # - Hero acts after most active players
        
        # Simplification: Consider hero IP if hero is button or within 2 positions of button
        # This is a heuristic and may need refinement based on actual table dynamics
        
        num_players = len(players)
        if num_players == 0:
            return False
        
        # Normalize positions (button is position 0 in action order postflop)
        # Calculate relative position from button
        relative_pos = (hero_pos - button_pos) % num_players
        
        if street == Street.PREFLOP:
            # Preflop: later positions have advantage (closer to button has position)
            # Hero is IP if in late position (within last 1/3 of players)
            return relative_pos >= (num_players * 2 // 3)
        else:
            # Postflop: button acts last, so earlier relative positions are better
            # Hero is IP if within first 1/3 of players after button
            return relative_pos <= (num_players // 3)
    
    def _determine_initial_street(self) -> Street:
        """Determine initial street based on board cache or assume PREFLOP.
        
        Returns:
            Street enum value for initial street determination
        """
        # Check if we have a cached board to infer street
        if self.board_cache and self.board_cache.street:
            return self.board_cache.street
        
        # No cached board info - assume PREFLOP to skip board parsing
        # This is safe because:
        # 1. Most frames are PREFLOP (longest phase)
        # 2. If we're wrong, next frame will correct it
        # 3. PREFLOP board is always empty anyway
        return Street.PREFLOP
    
    def _detect_new_hand(self, street: Street, num_board_cards: int, pot: float) -> bool:
        """Detect if a new hand has started.
        
        Args:
            street: Current street
            num_board_cards: Number of board cards detected
            pot: Current pot value
            
        Returns:
            True if new hand detected, False otherwise
        """
        # Signal 1: PREFLOP with empty board
        if street != Street.PREFLOP or num_board_cards != 0:
            return False
        
        # Signal 2: Pot reset to blind levels
        # Compare with last pot - if pot decreased significantly, it's a new hand
        if self._last_pot > 0:
            # If pot dropped from a high value to blind level, new hand
            if self._last_pot > 50.0 and pot <= 10.0:
                logger.debug(f"[NEW HAND] Pot reset detected: {self._last_pot:.2f} -> {pot:.2f}")
                return True
        
        # Signal 3: Board was full (river) and now empty
        if self.board_cache:
            if self.board_cache.has_river() and num_board_cards == 0:
                logger.debug("[NEW HAND] Board reset from river to empty")
                return True
        
        return False
    
    def _check_parse_health(self, pot: float, players: list):
        """Check parse health when homography is disabled.
        
        Tracks recent parse validity and logs warning if consistently invalid.
        This helps detect table layout changes when homography is disabled.
        
        Args:
            pot: Parsed pot value
            players: List of PlayerState objects
        """
        # Only check if homography is disabled via performance config
        if not self.perf_config or self.perf_config.detect_table.enable_homography:
            return
        
        # Determine if this parse looks valid
        # Valid = has pot > 0 OR at least one player with stack > 0
        has_valid_pot = pot > 0.01
        has_valid_stack = any(p.stack > 0.01 for p in players)
        parse_valid = has_valid_pot or has_valid_stack
        
        # Track recent parse health
        self._recent_parse_health.append(parse_valid)
        
        # Keep only the last N parses
        if len(self._recent_parse_health) > self._health_check_window:
            self._recent_parse_health.pop(0)
        
        # Check if we have enough data and all recent parses are invalid
        if len(self._recent_parse_health) >= self._health_check_window:
            if not any(self._recent_parse_health):
                logger.warning(
                    "[HOMOGRAPHY DISABLED] Table layout may have changed - "
                    f"no valid stacks or pot detected in last {self._health_check_window} parses. "
                    "Consider re-enabling homography or recalibrating regions."
                )
                # Reset health tracking to avoid spamming warnings
                self._recent_parse_health = []
    
    def get_cache_metrics(self) -> Optional[dict]:
        """Get OCR cache metrics.
        
        Returns:
            Dictionary with cache statistics, or None if caching is disabled
        """
        if self.ocr_cache_manager:
            return self.ocr_cache_manager.get_metrics()
        return None
    
    def reset_cache_metrics(self):
        """Reset cache metrics counters."""
        if self.ocr_cache_manager:
            self.ocr_cache_manager.reset_metrics()
    
    def log_cache_metrics(self):
        """Log cache metrics summary."""
        metrics = self.get_cache_metrics()
        if metrics:
            logger.info("=" * 60)
            logger.info("OCR CACHE METRICS SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total OCR calls: {metrics['total_ocr_calls']}")
            logger.info(f"Total cache hits: {metrics['total_cache_hits']}")
            logger.info(f"Total checks: {metrics['total_checks']}")
            logger.info(f"Cache hit rate: {metrics['cache_hit_rate_percent']:.1f}%")
            logger.info("")
            logger.info("By type:")
            for cache_type, type_metrics in metrics['by_type'].items():
                logger.info(f"  {cache_type.upper()}:")
                logger.info(f"    OCR calls: {type_metrics['ocr_calls']}")
                logger.info(f"    Cache hits: {type_metrics['cache_hits']}")
                logger.info(f"    Hit rate: {type_metrics['hit_rate_percent']:.1f}%")
            logger.info("=" * 60)
