"""Automatic button (dealer) position detection using chat events and player names.

This module provides button position inference without requiring additional OCR
or screenshot captures. It uses only:
- Blind posting events from chat (POST_SB, POST_BB)
- name_to_seat mapping from vision_cache
- active_seats list (players still in the hand)

Performance: O(n) where n = number of players
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from holdem.utils.logging import get_logger

logger = get_logger("vision.button_detector")


@dataclass
class ButtonInferenceResult:
    """Result of button position inference.
    
    Attributes:
        button_seat: Seat index of the button (dealer), or None if couldn't infer
        sb_seat: Seat index of small blind, or None if not found
        bb_seat: Seat index of big blind, or None if not found
    """
    button_seat: Optional[int]
    sb_seat: Optional[int]
    bb_seat: Optional[int]


class ButtonDetector:
    """Detect button position from blind posting events and player seating.
    
    The button position in poker follows these rules:
    - For 3+ players: button is the seat immediately before SB in seating order
    - For 2 players (heads-up): button IS the small blind (BTN = SB)
    
    This detector requires:
    1. Blind posting events from chat (event_type="post_small_blind", "post_big_blind")
    2. name_to_seat mapping (player name -> seat index)
    3. active_seats list (seats of players still in the hand)
    """
    
    def __init__(self, num_seats: int):
        """Initialize button detector.
        
        Args:
            num_seats: Total number of seats at the table (e.g., 6 for 6-max)
        """
        self.num_seats = num_seats
    
    def _find_sb_bb_seats(
        self,
        events: List,
        name_to_seat: Dict[str, int],
    ) -> tuple[Optional[int], Optional[int]]:
        """Find SB and BB seat indices from blind posting events.
        
        Args:
            events: List of game events (expects events with event_type attribute)
            name_to_seat: Mapping from player name to seat index
            
        Returns:
            Tuple of (sb_seat, bb_seat), either may be None if not found
        """
        sb_seat = None
        bb_seat = None
        
        for ev in events:
            # Check for post_small_blind event
            if getattr(ev, 'event_type', None) == 'post_small_blind':
                player_name = getattr(ev, 'player', None)
                if player_name and player_name in name_to_seat:
                    sb_seat = name_to_seat[player_name]
                    logger.debug(f"[BUTTON] Found SB at seat {sb_seat} (player: {player_name})")
            
            # Check for post_big_blind event
            elif getattr(ev, 'event_type', None) == 'post_big_blind':
                player_name = getattr(ev, 'player', None)
                if player_name and player_name in name_to_seat:
                    bb_seat = name_to_seat[player_name]
                    logger.debug(f"[BUTTON] Found BB at seat {bb_seat} (player: {player_name})")
        
        return sb_seat, bb_seat
    
    def infer_button(
        self,
        events: List,
        name_to_seat: Dict[str, int],
        active_seats: List[int],
    ) -> ButtonInferenceResult:
        """Infer button position from blind events and active seats.
        
        Algorithm:
        1. Find SB and BB seats from blind posting events
        2. If SB found and is active:
           - For 2 players (heads-up): button = SB
           - For 3+ players: button = seat before SB in circular order
        3. Return ButtonInferenceResult with inferred positions
        
        Complexity: O(n) where n = len(events) + len(active_seats)
        
        Args:
            events: List of game events (must have event_type, player attributes)
            name_to_seat: Mapping from player name to seat index
            active_seats: List of seat indices still active in the hand (ordered)
            
        Returns:
            ButtonInferenceResult with inferred button_seat, sb_seat, bb_seat
        """
        # Find SB and BB from events
        sb_seat, bb_seat = self._find_sb_bb_seats(events, name_to_seat)
        
        button_seat: Optional[int] = None
        
        # Can only infer button if we found SB and it's active
        if sb_seat is not None and sb_seat in active_seats:
            num_active = len(active_seats)
            
            if num_active == 2:
                # Heads-up: button IS small blind
                button_seat = sb_seat
                logger.info(f"[BUTTON] Heads-up detected: button_seat={button_seat} (BTN=SB)")
            
            elif num_active >= 3:
                # Multi-way: button is seat before SB in circular order
                try:
                    idx = active_seats.index(sb_seat)
                    btn_idx = (idx - 1) % num_active
                    button_seat = active_seats[btn_idx]
                    logger.info(
                        f"[BUTTON] Multi-way detected ({num_active} players): "
                        f"button_seat={button_seat}, sb_seat={sb_seat}, bb_seat={bb_seat}"
                    )
                except ValueError:
                    logger.warning(f"[BUTTON] SB seat {sb_seat} not found in active_seats {active_seats}")
        else:
            if sb_seat is None:
                logger.debug("[BUTTON] Could not infer button: SB seat not found in events")
            elif sb_seat not in active_seats:
                logger.debug(f"[BUTTON] Could not infer button: SB seat {sb_seat} not in active seats {active_seats}")
        
        return ButtonInferenceResult(
            button_seat=button_seat,
            sb_seat=sb_seat,
            bb_seat=bb_seat,
        )


def assign_positions_for_6max(
    button_seat: int,
    active_seats: List[int],
) -> Dict[int, str]:
    """Assign position labels (BTN, SB, BB, UTG, MP, CO) based on button seat.
    
    This function calculates the distance from each active seat to the button
    and assigns standard poker position names.
    
    Position order (clockwise from button):
    - Distance 0: BTN (Button)
    - Distance 1: SB (Small Blind)
    - Distance 2: BB (Big Blind)
    - Distance 3: UTG (Under The Gun)
    - Distance 4: MP (Middle Position)
    - Distance 5: CO (Cutoff)
    
    For fewer players, some positions may not exist (e.g., in 3-handed,
    only BTN, SB, BB exist).
    
    Args:
        button_seat: Seat index of the button
        active_seats: List of seat indices of active players
        
    Returns:
        Dictionary mapping seat index to position label string
        (e.g., {0: "BTN", 1: "SB", 2: "BB", ...})
    """
    from holdem.types import Position
    
    num_active = len(active_seats)
    
    # Position labels in order of distance from button
    # For 6-max, this is the full lineup
    positions_order_6max = [
        Position.BTN,  # distance 0
        Position.SB,   # distance 1
        Position.BB,   # distance 2
        Position.UTG,  # distance 3
        Position.MP,   # distance 4
        Position.CO,   # distance 5
    ]
    
    pos_by_seat: Dict[int, str] = {}
    
    for seat in active_seats:
        # Calculate circular distance from button
        dist = (seat - button_seat) % num_active
        
        # Assign position based on distance (if position exists for this player count)
        if dist < len(positions_order_6max):
            position = positions_order_6max[dist]
            pos_by_seat[seat] = position.name
        else:
            # Shouldn't happen for 6-max or less, but handle gracefully
            pos_by_seat[seat] = f"SEAT{dist}"
            logger.warning(
                f"[POSITIONS] Unexpected distance {dist} for seat {seat} "
                f"with {num_active} active players"
            )
    
    logger.debug(f"[POSITIONS] Assigned positions: {pos_by_seat}")
    return pos_by_seat


def detect_button_by_color(
    frame,
    table_profile,
    state_cache=None
) -> Optional[int]:
    """Detect button position using visual color detection on button_region patches.
    
    This function provides ultra-cheap visual detection of the dealer button by analyzing
    small color patches at each seat position. It looks for the characteristic gray button
    with "D" that appears on PokerStars tables.
    
    Performance: O(n) where n = number of seats, optimized with numpy vectorized operations.
    Expected cost: < 1ms for 6-max table.
    
    Algorithm:
    1. For each seat with a button_region defined:
       - Extract small patch (typically 16x16)
       - Downsample to 4x4 or 8x8 for speed
       - Calculate mean RGB values
       - Check if matches gray button criteria (180-220 RGB, low color variance)
       - Check for contrast (darker "D" in center)
    2. Return seat index if exactly one seat matches criteria
    3. Return None if 0 or multiple seats match (ambiguous)
    
    Args:
        frame: Current screenshot as numpy array (BGR format from OpenCV)
        table_profile: TableProfile with player_regions containing optional button_region fields
        state_cache: Optional cache for stabilization across frames (not used in v1)
        
    Returns:
        Seat index (int) of button position, or None if not detected/ambiguous
        
    Examples:
        >>> profile = TableProfile.load("pokerstars_6max.json")
        >>> button_seat = detect_button_by_color(screenshot, profile)
        >>> if button_seat is not None:
        ...     print(f"Button detected at seat {button_seat}")
    """
    import cv2
    import numpy as np
    
    if frame is None or frame.size == 0:
        logger.debug("[BUTTON VISUAL] Empty frame, cannot detect")
        return None
    
    if not hasattr(table_profile, 'player_regions') or not table_profile.player_regions:
        logger.debug("[BUTTON VISUAL] No player_regions in profile")
        return None
    
    # Criteria for gray button detection (PokerStars dealer button)
    # These values are tuned for the light gray button with black "D"
    MIN_GRAY_VALUE = 180
    MAX_GRAY_VALUE = 220
    MAX_COLOR_DIFF = 15  # Max difference between R, G, B for "gray" detection
    MIN_VARIANCE = 100   # Minimum variance to detect the darker "D" letter
    
    candidates = []  # List of (seat_idx, confidence) tuples
    
    for player_region in table_profile.player_regions:
        seat_idx = player_region.get('position', -1)
        button_region = player_region.get('button_region')
        
        if button_region is None or seat_idx < 0:
            continue
        
        # Extract region coordinates
        x = button_region.get('x', 0)
        y = button_region.get('y', 0)
        w = button_region.get('width', 16)
        h = button_region.get('height', 16)
        
        # Validate region bounds
        if y + h > frame.shape[0] or x + w > frame.shape[1] or w <= 0 or h <= 0:
            logger.debug(f"[BUTTON VISUAL] Seat {seat_idx}: region out of bounds")
            continue
        
        # Extract patch
        patch = frame[y:y+h, x:x+w].copy()
        
        if patch.size == 0:
            continue
        
        # Convert to grayscale for easier analysis
        gray_patch = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        
        # Strategy: Check if patch has BOTH light gray regions AND darker regions (the "D")
        # This is more reliable than downsampling which mixes them together
        
        # Calculate statistics
        mean_gray = np.mean(gray_patch)
        max_gray = np.max(gray_patch)
        min_gray = np.min(gray_patch)
        variance = np.var(gray_patch)
        
        # Check 1: Maximum value should be in light gray range (the button background)
        # This indicates presence of light gray, even if dark "D" brings down the average
        if not (MIN_GRAY_VALUE <= max_gray <= MAX_GRAY_VALUE):
            logger.debug(
                f"[BUTTON VISUAL] Seat {seat_idx}: max brightness out of range "
                f"(max: {max_gray:.1f}, expected: {MIN_GRAY_VALUE}-{MAX_GRAY_VALUE})"
            )
            continue
        
        # Check 2: Should have sufficient contrast (variance) indicating "D" letter
        if variance < MIN_VARIANCE:
            logger.debug(
                f"[BUTTON VISUAL] Seat {seat_idx}: insufficient contrast "
                f"(variance: {variance:.1f}, min: {MIN_VARIANCE})"
            )
            continue
        
        # Check 3: Color neutrality check on the lighter pixels (button background)
        # Sample the brightest 25% of pixels to check if they're gray
        bright_threshold = np.percentile(gray_patch, 75)
        bright_mask = gray_patch >= bright_threshold
        
        if np.any(bright_mask):
            # Get RGB values of bright pixels only
            bright_pixels_bgr = patch[bright_mask]
            if len(bright_pixels_bgr) > 0:
                mean_b = np.mean(bright_pixels_bgr[:, 0])
                mean_g = np.mean(bright_pixels_bgr[:, 1])
                mean_r = np.mean(bright_pixels_bgr[:, 2])
                
                # Check color neutrality
                max_diff = max(abs(mean_r - mean_g), abs(mean_r - mean_b), abs(mean_g - mean_b))
                if max_diff > MAX_COLOR_DIFF:
                    logger.debug(
                        f"[BUTTON VISUAL] Seat {seat_idx}: bright pixels not neutral gray "
                        f"(BGR: {mean_b:.1f}, {mean_g:.1f}, {mean_r:.1f}, max_diff: {max_diff:.1f})"
                    )
                    continue
                
                # Check that bright pixels are in valid range
                if not (MIN_GRAY_VALUE <= mean_r <= MAX_GRAY_VALUE and
                       MIN_GRAY_VALUE <= mean_g <= MAX_GRAY_VALUE and
                       MIN_GRAY_VALUE <= mean_b <= MAX_GRAY_VALUE):
                    logger.debug(
                        f"[BUTTON VISUAL] Seat {seat_idx}: bright pixels out of gray range "
                        f"(BGR: {mean_b:.1f}, {mean_g:.1f}, {mean_r:.1f})"
                    )
                    continue
        else:
            # No bright pixels found
            logger.debug(f"[BUTTON VISUAL] Seat {seat_idx}: no bright pixels found")
            continue
        
        # This seat is a candidate!
        # Calculate confidence based on variance (higher variance = clearer "D")
        # and how well max brightness matches ideal gray (200)
        ideal_gray = 200.0
        brightness_score = 1.0 - abs(max_gray - ideal_gray) / 100.0
        variance_score = min(variance / 5000.0, 1.0)  # Normalize variance
        confidence = (brightness_score + variance_score) / 2.0
        confidence = max(0.0, min(1.0, confidence))
        
        candidates.append((seat_idx, confidence))
        logger.debug(
            f"[BUTTON VISUAL] Seat {seat_idx}: CANDIDATE "
            f"(max_gray: {max_gray:.1f}, variance: {variance:.1f}, confidence: {confidence:.2f})"
        )
    
    # Decision logic: return seat only if exactly one candidate
    if len(candidates) == 0:
        logger.debug("[BUTTON VISUAL] No candidates found")
        return None
    elif len(candidates) == 1:
        seat_idx, confidence = candidates[0]
        logger.info(f"[BUTTON VISUAL] Detected button at seat {seat_idx} (confidence: {confidence:.2f})")
        return seat_idx
    else:
        # Multiple candidates - ambiguous, don't decide
        seats_str = ", ".join(f"{s}({c:.2f})" for s, c in candidates)
        logger.debug(f"[BUTTON VISUAL] Multiple candidates, ambiguous: {seats_str}")
        return None
