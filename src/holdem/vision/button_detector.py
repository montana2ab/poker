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
