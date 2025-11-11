"""Visual overlay for displaying game state information on screen."""

import cv2
import numpy as np
from typing import Optional, Tuple, List
from holdem.types import TableState, PlayerState, ActionType
from holdem.vision.calibrate import TableProfile
from holdem.utils.logging import get_logger

logger = get_logger("vision.overlay")


class GameOverlay:
    """Manages visual overlays for displaying game state information."""
    
    def __init__(self, profile: TableProfile, alpha: float = 0.7):
        """Initialize overlay manager.
        
        Args:
            profile: TableProfile with region definitions
            alpha: Transparency for overlay (0.0 = transparent, 1.0 = opaque)
        """
        self.profile = profile
        self.alpha = alpha
        
        # Color scheme
        self.colors = {
            'background': (0, 0, 0),
            'text': (255, 255, 255),
            'action_call': (100, 200, 100),
            'action_bet': (200, 100, 100),
            'action_raise': (200, 100, 100),
            'action_check': (100, 150, 200),
            'action_fold': (150, 150, 150),
            'action_allin': (255, 100, 100),
            'highlight': (255, 200, 0),
        }
    
    def draw_state(self, img: np.ndarray, state: TableState) -> np.ndarray:
        """Draw complete game state overlay on image.
        
        Args:
            img: Input image (will not be modified)
            state: TableState to display
            
        Returns:
            New image with overlay drawn
        """
        # Create a copy to avoid modifying original
        overlay_img = img.copy()
        
        # Draw player information
        for player in state.players:
            self._draw_player_info(overlay_img, player)
        
        # Draw pot information
        self._draw_pot(overlay_img, state.pot)
        
        # Draw dealer button highlight
        if state.button_position is not None:
            self._draw_button_highlight(overlay_img, state.button_position)
        
        # Draw board cards info (street name)
        self._draw_street_info(overlay_img, state)
        
        return overlay_img
    
    def _draw_player_info(self, img: np.ndarray, player: PlayerState) -> None:
        """Draw player information overlay.
        
        Displays action and bet information aligned with player name region.
        """
        if player.position >= len(self.profile.player_regions):
            return
        
        player_region = self.profile.player_regions[player.position]
        name_region = player_region.get('name_region', {})
        
        # Get center point of name region for alignment
        center_x = name_region.get('x', 0) + name_region.get('width', 0) // 2
        center_y = name_region.get('y', 0) + name_region.get('height', 0) // 2
        
        # Draw action if available
        if player.last_action:
            action_text = self._format_action(player.last_action, player.bet_this_round)
            color = self._get_action_color(player.last_action)
            
            # Draw action text above name region
            self._draw_text_with_background(
                img, 
                action_text, 
                (center_x, center_y - 25),
                color=color,
                center_align=True
            )
        
        # Draw bet amount if any
        if player.bet_this_round > 0:
            bet_text = f"${player.bet_this_round:.2f}"
            
            # Draw bet below name region
            self._draw_text_with_background(
                img,
                bet_text,
                (center_x, center_y + 25),
                color=self.colors['highlight'],
                center_align=True
            )
    
    def _draw_pot(self, img: np.ndarray, pot: float) -> None:
        """Draw pot information."""
        if not self.profile.pot_region:
            return
        
        region = self.profile.pot_region
        center_x = region.get('x', 0) + region.get('width', 0) // 2
        center_y = region.get('y', 0) + region.get('height', 0) // 2
        
        # Draw pot label above the pot region
        self._draw_text_with_background(
            img,
            f"Pot: ${pot:.2f}",
            (center_x, center_y - 20),
            color=self.colors['highlight'],
            center_align=True
        )
    
    def _draw_button_highlight(self, img: np.ndarray, button_position: int) -> None:
        """Highlight the dealer button position."""
        if button_position >= len(self.profile.player_regions):
            return
        
        player_region = self.profile.player_regions[button_position]
        name_region = player_region.get('name_region', {})
        
        if not name_region:
            return
        
        x = name_region.get('x', 0)
        y = name_region.get('y', 0)
        w = name_region.get('width', 0)
        h = name_region.get('height', 0)
        
        # Draw a circle or "D" marker near the player
        marker_x = x - 15
        marker_y = y + h // 2
        
        # Draw circle
        cv2.circle(img, (marker_x, marker_y), 8, self.colors['highlight'], 2)
        # Draw "D" in the circle
        self._draw_text_with_background(
            img,
            "D",
            (marker_x, marker_y),
            color=self.colors['highlight'],
            center_align=True,
            font_scale=0.4
        )
    
    def _draw_street_info(self, img: np.ndarray, state: TableState) -> None:
        """Draw street information (PREFLOP, FLOP, TURN, RIVER)."""
        street_name = state.street.name
        
        # Draw in top-left corner
        self._draw_text_with_background(
            img,
            street_name,
            (10, 20),
            color=self.colors['text'],
            center_align=False
        )
    
    def _draw_text_with_background(
        self, 
        img: np.ndarray, 
        text: str, 
        position: Tuple[int, int],
        color: Tuple[int, int, int] = (255, 255, 255),
        center_align: bool = False,
        font_scale: float = 0.5,
        thickness: int = 1
    ) -> None:
        """Draw text with semi-transparent background.
        
        Args:
            img: Image to draw on
            text: Text to draw
            position: (x, y) position
            color: Text color (BGR)
            center_align: If True, center text at position
            font_scale: Font size scale
            thickness: Text thickness
        """
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Get text size
        (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        
        # Calculate position
        x, y = position
        if center_align:
            x = x - text_w // 2
            y = y + text_h // 2
        
        # Draw background rectangle with transparency
        padding = 4
        bg_pt1 = (x - padding, y - text_h - padding)
        bg_pt2 = (x + text_w + padding, y + baseline + padding)
        
        # Create overlay for transparency
        overlay = img.copy()
        cv2.rectangle(overlay, bg_pt1, bg_pt2, self.colors['background'], -1)
        cv2.addWeighted(overlay, self.alpha, img, 1 - self.alpha, 0, img)
        
        # Draw text
        cv2.putText(img, text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)
    
    def _format_action(self, action: ActionType, amount: float = 0.0) -> str:
        """Format action for display."""
        action_str = action.value.upper()
        if amount > 0 and action in [ActionType.BET, ActionType.RAISE, ActionType.CALL]:
            return f"{action_str} ${amount:.2f}"
        return action_str
    
    def _get_action_color(self, action: ActionType) -> Tuple[int, int, int]:
        """Get color for action type."""
        color_map = {
            ActionType.CALL: self.colors['action_call'],
            ActionType.CHECK: self.colors['action_check'],
            ActionType.BET: self.colors['action_bet'],
            ActionType.RAISE: self.colors['action_raise'],
            ActionType.FOLD: self.colors['action_fold'],
            ActionType.ALLIN: self.colors['action_allin'],
        }
        return color_map.get(action, self.colors['text'])
