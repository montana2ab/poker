"""Parse complete game state from vision."""

import cv2
import numpy as np
import time
from pathlib import Path
from typing import Optional, List, Tuple
import re
from decimal import Decimal
from dataclasses import dataclass, field
from holdem.types import TableState, PlayerState, Street, Card
from holdem.vision.calibrate import TableProfile
from holdem.vision.cards import CardRecognizer
from holdem.vision.ocr import OCREngine
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
        vision_metrics: Optional['VisionMetrics'] = None
    ):
        self.profile = profile
        self.card_recognizer = card_recognizer
        self.ocr_engine = ocr_engine
        self.debug_dir = debug_dir
        self.vision_metrics = vision_metrics
        self._debug_counter = 0
        self.hero_cards_tracker = HeroCardsTracker()  # Track stable hero cards
        self._last_pot = 0.0  # Track pot for regression detection
    
    def parse(self, screenshot: np.ndarray) -> Optional[TableState]:
        """Parse table state from screenshot."""
        try:
            # Track parse latency if metrics are enabled
            parse_start = time.time() if self.vision_metrics else None
            
            # Increment debug counter for each parse call
            if self.debug_dir:
                self._debug_counter += 1
            
            # Extract community cards
            board = self._parse_board(screenshot)
            
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
            pot = self._parse_pot(screenshot)
            
            # Parse button position (dealer button)
            button_position = self._parse_button_position(screenshot)
            
            # Extract player states and check for showdown labels
            players, has_showdown_label = self._parse_players(screenshot)
            
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
            
            # Get hero position from profile
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
                self.vision_metrics.record_parse_latency(parse_latency_ms)
            
            logger.debug(f"Parsed state: {street.name}, pot={pot}, current_bet={current_bet}, "
                        f"button={button_position}, hero_pos={hero_position}, is_IP={is_in_position}, "
                        f"to_call={to_call:.2f}, eff_stack={effective_stack:.2f}, SPR={spr:.2f}, "
                        f"{len(players)} players")
            return state
            
        except Exception as e:
            logger.error(f"Error parsing state: {e}")
            return None
    
    def _parse_board(self, img: np.ndarray) -> list:
        """Parse community cards from image."""
        if not self.profile.card_regions:
            logger.warning("No card regions defined in profile")
            return [None] * 5
        
        region = self.profile.card_regions[0]
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h <= img.shape[0] and x + w <= img.shape[1]:
            card_region = img[y:y+h, x:x+w]
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
            
            cards = self.card_recognizer.recognize_cards(card_region, num_cards=5)
            
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
        else:
            logger.error(f"Card region ({x},{y},{w},{h}) out of bounds for image shape {img.shape}")
        
        return [None] * 5
    
    def _parse_pot(self, img: np.ndarray) -> float:
        """Parse pot amount from image."""
        if not self.profile.pot_region:
            return 0.0
        
        region = self.profile.pot_region
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h <= img.shape[0] and x + w <= img.shape[1]:
            pot_region = img[y:y+h, x:x+w]
            pot = self.ocr_engine.extract_number(pot_region)
            
            # Track OCR and amount metrics if enabled
            if self.vision_metrics and pot is not None:
                self.vision_metrics.record_amount(
                    detected_amount=pot,
                    expected_amount=None,  # No ground truth in production
                    category="pot"
                )
            
            return pot if pot is not None else 0.0
        
        return 0.0
    
    def _parse_players(self, img: np.ndarray) -> Tuple[list, bool]:
        """Parse player states from image.
        
        Returns:
            Tuple of (players list, has_showdown_label boolean)
        """
        players = []
        has_showdown_label = False  # Track if any showdown label detected
        parse_opp = getattr(self.profile, "parse_opponent_cards", False)
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
                parsed_stack = self.ocr_engine.extract_number(stack_img)
                if parsed_stack is None:
                    # Fallback: OCR raw text then parse locale-aware
                    raw_txt = self.ocr_engine.read_text(stack_img) or ""
                    parsed_stack = _parse_amount_from_text(raw_txt)
                if parsed_stack is not None:
                    stack = parsed_stack
                    logger.info(f"Player {table_position} stack OCR: {stack:.2f}")
                    
                    # Track amount metrics if enabled
                    if self.vision_metrics:
                        self.vision_metrics.record_amount(
                            detected_amount=stack,
                            expected_amount=None,  # No ground truth in production
                            category="stack"
                        )

            # Extract name
            name_reg = player_region.get('name_region', {})
            x, y, w, h = name_reg.get('x', 0), name_reg.get('y', 0), \
                         name_reg.get('width', 0), name_reg.get('height', 0)

            name = f"Player{table_position}"
            if y + h <= img.shape[0] and x + w <= img.shape[1] and w > 0 and h > 0:
                name_img = img[y:y+h, x:x+w]
                parsed_name = self.ocr_engine.read_text(name_img)
                if parsed_name:
                    parsed_name_stripped = parsed_name.strip()
                    # Check if this is a showdown "Won X,XXX" label
                    if is_showdown_won_label(parsed_name_stripped):
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
                parsed_bet = self.ocr_engine.extract_number(bet_img)
                if parsed_bet is None:
                    # Fallback: OCR raw text then parse locale-aware
                    raw_txt = self.ocr_engine.read_text(bet_img) or ""
                    parsed_bet = _parse_amount_from_text(raw_txt)
                if parsed_bet is not None:
                    # Only record bet if this is not a showdown label in the name region
                    # (prevents "Won 5,249" from being treated as a bet)
                    if not is_showdown_won_label(name):
                        bet_this_round = parsed_bet
                        logger.info(f"Player {table_position} bet OCR: {bet_this_round:.2f}")
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
                hole_cards = self._parse_player_cards(img, player_region, is_hero=True)
            elif parse_opp:
                logger.info(f"Parsing opponent cards at position {table_position}")
                # Templates héros et joueurs identiques -> on réutilise la même reco
                hole_cards = self._parse_player_cards(img, player_region, is_hero=False)

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
    
    def _parse_player_cards(self, img: np.ndarray, player_region: dict, is_hero: bool = False) -> Optional[List[Card]]:
        """Parse hole cards for a specific player.
        
        Args:
            img: Full table image
            player_region: Region definition for this player
            is_hero: True if parsing hero cards (enables sticky tracking)
        """
        card_reg = player_region.get('card_region', {})
        x, y, w, h = card_reg.get('x', 0), card_reg.get('y', 0), \
                    card_reg.get('width', 0), card_reg.get('height', 0)
        
        player_pos = player_region.get('position', 'unknown')
        logger.debug(f"Extracting player cards for position {player_pos} from region ({x},{y},{w},{h})")
        
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
            cards = self.card_recognizer.recognize_cards(card_region, num_cards=2, use_hero_templates=True, skip_empty_check=True)
            
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
