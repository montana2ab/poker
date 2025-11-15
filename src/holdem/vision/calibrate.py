"""Table calibration utilities."""

import json
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from holdem.utils.logging import get_logger

logger = get_logger("vision.calibrate")


class TableProfile:
    """Stores calibration data for a poker table."""
    
    def __init__(self):
        self.window_title: str = ""
        self.owner_name: Optional[str] = None  # Application owner (e.g., "PokerStars")
        self.screen_region: Optional[Tuple[int, int, int, int]] = None
        self.card_regions: List[Dict[str, int]] = []  # Regions where cards appear
        self.player_regions: List[Dict[str, any]] = []  # Player info regions
        self.pot_region: Optional[Dict[str, int]] = None
        self.bet_regions: List[Dict[str, int]] = []
        self.button_regions: Dict[str, Dict[str, int]] = {}  # Fold, Call, Raise, etc.
        self.dealer_button_region: Optional[Dict[str, int]] = None  # Single region (legacy)
        self.dealer_button_regions: List[Dict[str, int]] = []  # One region per player position
        self.chat_region: Optional[Dict[str, int]] = None  # Chat/history region for event parsing
        self.board_regions: Optional[Dict[str, Dict[str, int]]] = None  # Optional flop/turn/river zones
        self.reference_image: Optional[np.ndarray] = None
        self.keypoints: List = []
        self.descriptors: Optional[np.ndarray] = None
        self.hero_position: Optional[int] = None  # Index of hero player in player_regions
        self.hero_templates_dir: Optional[str] = None  # Directory for hero card templates
        self.card_spacing: int = 0  # Spacing between cards in pixels (negative for overlap)
    
    def save(self, path: Path):
        """Save profile to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "window_title": self.window_title,
            "owner_name": self.owner_name,
            "screen_region": self.screen_region,
            "card_regions": self.card_regions,
            "player_regions": self.player_regions,
            "pot_region": self.pot_region,
            "bet_regions": self.bet_regions,
            "button_regions": self.button_regions,
            "dealer_button_region": self.dealer_button_region,
            "dealer_button_regions": self.dealer_button_regions,
            "chat_region": self.chat_region,
            "board_regions": self.board_regions,
            "hero_position": self.hero_position,
            "hero_templates_dir": self.hero_templates_dir,
            "card_spacing": self.card_spacing,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved table profile to {path}")
        
        # Save reference image and features separately
        if self.reference_image is not None:
            ref_path = path.parent / f"{path.stem}_reference.npy"
            np.save(ref_path, self.reference_image)
            
            if self.descriptors is not None:
                desc_path = path.parent / f"{path.stem}_descriptors.npy"
                np.save(desc_path, self.descriptors)
    
    @classmethod
    def load(cls, path: Path) -> "TableProfile":
        """Load profile from JSON."""
        with open(path, 'r') as f:
            data = json.load(f)
        
        profile = cls()
        profile.window_title = data.get("window_title", "")
        profile.owner_name = data.get("owner_name")
        profile.screen_region = tuple(data["screen_region"]) if data.get("screen_region") else None
        profile.card_regions = data.get("card_regions", [])
        profile.player_regions = data.get("player_regions", [])
        profile.pot_region = data.get("pot_region")
        profile.bet_regions = data.get("bet_regions", [])
        profile.button_regions = data.get("button_regions", {})
        profile.dealer_button_region = data.get("dealer_button_region")
        profile.dealer_button_regions = data.get("dealer_button_regions", [])
        profile.chat_region = data.get("chat_region")
        profile.board_regions = data.get("board_regions")  # Optional board zones
        profile.hero_position = data.get("hero_position")
        profile.hero_templates_dir = data.get("hero_templates_dir")
        profile.card_spacing = data.get("card_spacing", 0)
        
        # Handle reference_image - can be path or loaded from .npy file
        ref_image_data = data.get("reference_image")
        if ref_image_data:
            if isinstance(ref_image_data, str):
                # It's a path - store it, will be loaded by TableDetector
                profile.reference_image = ref_image_data
            else:
                # Try loading from default .npy file
                ref_path = path.parent / f"{path.stem}_reference.npy"
                if ref_path.exists():
                    profile.reference_image = np.load(ref_path)
        else:
            # No reference_image in JSON, try default .npy file
            ref_path = path.parent / f"{path.stem}_reference.npy"
            if ref_path.exists():
                profile.reference_image = np.load(ref_path)
        
        # Handle descriptors - can be path or loaded from .npy/.npz file
        desc_data = data.get("descriptors") or data.get("reference_descriptors")
        if desc_data:
            if isinstance(desc_data, str):
                # It's a path - store it, will be loaded by TableDetector
                profile.descriptors = desc_data
            else:
                # Try loading from default .npy file
                desc_path = path.parent / f"{path.stem}_descriptors.npy"
                if desc_path.exists():
                    profile.descriptors = np.load(desc_path)
        else:
            # No descriptors in JSON, try default .npy file
            desc_path = path.parent / f"{path.stem}_descriptors.npy"
            if desc_path.exists():
                profile.descriptors = np.load(desc_path)
        
        logger.info(f"Loaded table profile from {path}")
        return profile
    
    def has_board_regions(self) -> bool:
        """Check if board_regions is configured.
        
        Returns:
            True if board_regions with flop/turn/river zones is configured
        """
        if not self.board_regions:
            return False
        return all(zone in self.board_regions for zone in ["flop", "turn", "river"])
    
    def get_flop_region(self) -> Optional[Dict[str, int]]:
        """Get flop region if configured.
        
        Returns:
            Flop region dict with x, y, width, height or None
        """
        if self.board_regions and "flop" in self.board_regions:
            return self.board_regions["flop"]
        return None
    
    def get_turn_region(self) -> Optional[Dict[str, int]]:
        """Get turn region if configured.
        
        Returns:
            Turn region dict with x, y, width, height or None
        """
        if self.board_regions and "turn" in self.board_regions:
            return self.board_regions["turn"]
        return None
    
    def get_river_region(self) -> Optional[Dict[str, int]]:
        """Get river region if configured.
        
        Returns:
            River region dict with x, y, width, height or None
        """
        if self.board_regions and "river" in self.board_regions:
            return self.board_regions["river"]
        return None


def calibrate_interactive(screenshot: np.ndarray, window_title: str, seats: int = 9) -> TableProfile:
    """Interactive calibration (simplified version for automation).
    
    Args:
        screenshot: Screenshot of the poker table
        window_title: Window title for identification
        seats: Number of seats at the table (6 or 9, default: 9)
    """
    profile = TableProfile()
    profile.window_title = window_title
    profile.reference_image = screenshot
    
    # Auto-detect features for table detection
    gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=1000)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    profile.keypoints = keypoints
    profile.descriptors = descriptors
    
    # Default regions (placeholder - would be interactive in real implementation)
    height, width = screenshot.shape[:2]
    
    # Community cards region (center top)
    profile.card_regions = [{
        "x": int(width * 0.35),
        "y": int(height * 0.35),
        "width": int(width * 0.3),
        "height": int(height * 0.15)
    }]
    
    # Player regions - support both 6-max and 9-max tables
    # Arrange players in circular layout around the table
    # For 9-max: positions 0-8 at 40° intervals (360°/9)
    # For 6-max: positions 0-5 at 60° intervals (360°/6)
    angle_step = 360 / seats
    for i in range(seats):
        angle = i * angle_step
        cx = width // 2 + int(width * 0.35 * np.cos(np.radians(angle)))
        cy = height // 2 + int(height * 0.35 * np.sin(np.radians(angle)))
        profile.player_regions.append({
            "position": i,
            "name_region": {"x": cx - 50, "y": cy - 30, "width": 100, "height": 20},
            "stack_region": {"x": cx - 50, "y": cy, "width": 100, "height": 20},
            "card_region": {"x": cx - 40, "y": cy + 20, "width": 80, "height": 60}
        })
    
    # Pot region (center)
    profile.pot_region = {
        "x": int(width * 0.4),
        "y": int(height * 0.25),
        "width": int(width * 0.2),
        "height": int(height * 0.1)
    }
    
    # Action buttons (bottom center)
    button_y = int(height * 0.85)
    profile.button_regions = {
        "fold": {"x": int(width * 0.25), "y": button_y, "width": 100, "height": 40},
        "check": {"x": int(width * 0.40), "y": button_y, "width": 100, "height": 40},
        "call": {"x": int(width * 0.40), "y": button_y, "width": 100, "height": 40},
        "bet": {"x": int(width * 0.55), "y": button_y, "width": 100, "height": 40},
        "raise": {"x": int(width * 0.55), "y": button_y, "width": 100, "height": 40},
        "allin": {"x": int(width * 0.70), "y": button_y, "width": 100, "height": 40},
    }
    
    logger.info(f"Calibration complete (automated regions for {seats}-max table)")
    return profile
