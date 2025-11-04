"""
Auto-capture module for generating card templates automatically.

This module captures card images during actual gameplay and saves them
as templates for improved recognition accuracy.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Set, Tuple, Dict, List
from datetime import datetime
import time

from holdem.vision.calibrate import TableProfile
from holdem.vision.screen import ScreenCapture
from holdem.vision.detect_table import TableDetector
from holdem.utils.logging import get_logger

logger = get_logger("vision.auto_capture")


class CardTemplateCapture:
    """Automatically captures card templates during gameplay."""
    
    def __init__(
        self,
        profile: TableProfile,
        board_output_dir: Path,
        hero_output_dir: Path,
        min_card_confidence: float = 0.8
    ):
        """
        Initialize template capture system.
        
        Args:
            profile: Table profile with region definitions
            board_output_dir: Directory to save board card templates
            hero_output_dir: Directory to save hero card templates
            min_card_confidence: Minimum confidence to consider card valid
        """
        self.profile = profile
        self.board_output_dir = Path(board_output_dir)
        self.hero_output_dir = Path(hero_output_dir)
        self.min_card_confidence = min_card_confidence
        
        # Create output directories
        self.board_output_dir.mkdir(parents=True, exist_ok=True)
        self.hero_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Track captured cards
        self.board_cards_captured: Set[str] = set()
        self.hero_cards_captured: Set[str] = set()
        
        # Load existing templates to avoid re-capturing
        self._load_existing_captures()
        
        # State tracking
        self.last_board_state: List[Optional[np.ndarray]] = [None] * 5
        self.last_hero_state: List[Optional[np.ndarray]] = [None] * 2
        
        logger.info("CardTemplateCapture initialized")
        logger.info(f"Board templates: {len(self.board_cards_captured)}/52 captured")
        logger.info(f"Hero templates: {len(self.hero_cards_captured)}/52 captured")
    
    def _load_existing_captures(self):
        """Load list of already captured cards."""
        # Check board templates
        for template_file in self.board_output_dir.glob("*.png"):
            card_name = template_file.stem
            if len(card_name) == 2:  # e.g., "Ah", "Ks"
                self.board_cards_captured.add(card_name)
        
        # Check hero templates
        for template_file in self.hero_output_dir.glob("*.png"):
            card_name = template_file.stem
            if len(card_name) == 2:
                self.hero_cards_captured.add(card_name)
    
    def capture_from_screenshot(self, screenshot: np.ndarray) -> Dict[str, int]:
        """
        Process a screenshot and capture any new cards.
        
        Args:
            screenshot: Full screenshot image
            
        Returns:
            Dictionary with capture statistics
        """
        stats = {
            "board_captured": 0,
            "hero_captured": 0,
            "total_board": len(self.board_cards_captured),
            "total_hero": len(self.hero_cards_captured)
        }
        
        # Capture board cards
        board_stats = self._capture_board_cards(screenshot)
        stats["board_captured"] = board_stats
        
        # Capture hero cards
        hero_stats = self._capture_hero_cards(screenshot)
        stats["hero_captured"] = hero_stats
        
        stats["total_board"] = len(self.board_cards_captured)
        stats["total_hero"] = len(self.hero_cards_captured)
        
        return stats
    
    def _capture_board_cards(self, screenshot: np.ndarray) -> int:
        """
        Capture board cards from screenshot.
        
        Returns:
            Number of new cards captured
        """
        if not self.profile.card_regions:
            return 0
        
        captured_count = 0
        region = self.profile.card_regions[0]
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        # Extract board region
        if y + h > screenshot.shape[0] or x + w > screenshot.shape[1]:
            return 0
        
        board_region = screenshot[y:y+h, x:x+w]
        
        # Split into individual cards (5 cards on board)
        card_width = w // 5
        
        for i in range(5):
            x1 = i * card_width
            x2 = (i + 1) * card_width
            card_img = board_region[:, x1:x2]
            
            # Check if this card is new (different from last state)
            if self._is_new_card(card_img, self.last_board_state[i]):
                # Try to save the card
                if self._save_board_card(card_img, i):
                    captured_count += 1
                    self.last_board_state[i] = card_img.copy()
        
        return captured_count
    
    def _capture_hero_cards(self, screenshot: np.ndarray) -> int:
        """
        Capture hero cards from screenshot.
        
        Returns:
            Number of new cards captured
        """
        if self.profile.hero_position is None:
            return 0
        
        if self.profile.hero_position >= len(self.profile.player_regions):
            return 0
        
        captured_count = 0
        player_region = self.profile.player_regions[self.profile.hero_position]
        card_reg = player_region.get('card_region', {})
        
        x, y, w, h = card_reg.get('x', 0), card_reg.get('y', 0), \
                    card_reg.get('width', 0), card_reg.get('height', 0)
        
        if w == 0 or h == 0:
            return 0
        
        # Extract hero card region
        if y + h > screenshot.shape[0] or x + w > screenshot.shape[1]:
            return 0
        
        hero_region = screenshot[y:y+h, x:x+w]
        
        # Split into individual cards (2 hole cards)
        card_width = w // 2
        
        for i in range(2):
            x1 = i * card_width
            x2 = (i + 1) * card_width
            card_img = hero_region[:, x1:x2]
            
            # Check if this card is new
            if self._is_new_card(card_img, self.last_hero_state[i]):
                # Try to save the card
                if self._save_hero_card(card_img, i):
                    captured_count += 1
                    self.last_hero_state[i] = card_img.copy()
        
        return captured_count
    
    def _is_new_card(self, card_img: np.ndarray, last_card: Optional[np.ndarray]) -> bool:
        """
        Check if card image is different from last captured state.
        
        Args:
            card_img: Current card image
            last_card: Previous card image (or None)
            
        Returns:
            True if card is new/different
        """
        if last_card is None:
            return True
        
        # Resize both to same size for comparison
        if card_img.shape != last_card.shape:
            return True
        
        # Compare images using structural similarity
        diff = cv2.absdiff(card_img, last_card)
        diff_score = np.mean(diff)
        
        # If difference is significant, it's a new card
        return diff_score > 10.0  # Threshold for detecting change
    
    def _save_board_card(self, card_img: np.ndarray, position: int) -> bool:
        """
        Save a board card template.
        
        Args:
            card_img: Card image to save
            position: Position on board (0-4)
            
        Returns:
            True if saved successfully
        """
        # Validate card image quality
        if not self._is_valid_card_image(card_img):
            logger.debug(f"Invalid board card image at position {position}")
            return False
        
        # Generate filename with timestamp to capture multiple examples
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"board_pos{position}_{timestamp}.png"
        filepath = self.board_output_dir / filename
        
        # Save the image
        cv2.imwrite(str(filepath), card_img)
        logger.info(f"Captured board card at position {position}: {filepath}")
        
        return True
    
    def _save_hero_card(self, card_img: np.ndarray, position: int) -> bool:
        """
        Save a hero card template.
        
        Args:
            card_img: Card image to save
            position: Position in hand (0-1)
            
        Returns:
            True if saved successfully
        """
        # Validate card image quality
        if not self._is_valid_card_image(card_img):
            logger.debug(f"Invalid hero card image at position {position}")
            return False
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hero_pos{position}_{timestamp}.png"
        filepath = self.hero_output_dir / filename
        
        # Save the image
        cv2.imwrite(str(filepath), card_img)
        logger.info(f"Captured hero card at position {position}: {filepath}")
        
        return True
    
    def _is_valid_card_image(self, card_img: np.ndarray) -> bool:
        """
        Validate that an image looks like a card.
        
        Args:
            card_img: Card image to validate
            
        Returns:
            True if image appears to be a valid card
        """
        if card_img is None or card_img.size == 0:
            return False
        
        # Check minimum size
        if card_img.shape[0] < 20 or card_img.shape[1] < 20:
            return False
        
        # Check if image is not mostly black or white
        gray = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY) if len(card_img.shape) == 3 else card_img
        mean_intensity = np.mean(gray)
        
        # Card should have moderate intensity (not pure black/white)
        if mean_intensity < 20 or mean_intensity > 235:
            return False
        
        # Check variance (card should have details, not flat color)
        variance = np.var(gray)
        if variance < 100:
            return False
        
        return True
    
    def get_progress(self) -> Dict[str, any]:
        """
        Get current capture progress.
        
        Returns:
            Dictionary with progress information
        """
        total_cards = 52
        
        return {
            "board_cards_captured": len(self.board_cards_captured),
            "board_cards_total": total_cards,
            "board_progress": (len(self.board_cards_captured) / total_cards) * 100,
            "hero_cards_captured": len(self.hero_cards_captured),
            "hero_cards_total": total_cards,
            "hero_progress": (len(self.hero_cards_captured) / total_cards) * 100,
            "overall_progress": ((len(self.board_cards_captured) + len(self.hero_cards_captured)) / (total_cards * 2)) * 100
        }
    
    def organize_templates(self):
        """
        Organize captured templates by card identity.
        
        This method should be run after capture session to:
        1. Group similar cards together
        2. Select best quality image for each card
        3. Rename to standard format (e.g., "Ah.png")
        
        Note: This requires manual or AI-based card identification.
        """
        logger.warning("Template organization requires manual card identification")
        logger.info("Use the organize_captured_templates.py script to label and organize captures")


def run_auto_capture(
    profile_path: Path,
    duration_seconds: Optional[int] = None,
    interval_seconds: float = 1.0,
    board_output: Path = Path("assets/templates_captured/board"),
    hero_output: Path = Path("assets/templates_captured/hero")
):
    """
    Run automatic template capture session.
    
    Args:
        profile_path: Path to table profile
        duration_seconds: How long to run (None = run until stopped)
        interval_seconds: Seconds between captures
        board_output: Output directory for board templates
        hero_output: Output directory for hero templates
    """
    # Load profile
    logger.info(f"Loading profile from {profile_path}")
    profile = TableProfile.load(profile_path)
    
    # Initialize capture system
    capture = CardTemplateCapture(profile, board_output, hero_output)
    
    # Initialize screen capture
    screen_capture = ScreenCapture()
    table_detector = TableDetector(profile)
    
    logger.info("Starting auto-capture session")
    logger.info(f"Capturing every {interval_seconds} seconds")
    if duration_seconds:
        logger.info(f"Will run for {duration_seconds} seconds")
    else:
        logger.info("Press Ctrl+C to stop")
    
    start_time = time.time()
    capture_count = 0
    
    try:
        while True:
            # Check if we should stop
            if duration_seconds and (time.time() - start_time) > duration_seconds:
                break
            
            # Capture screenshot
            screenshot = screen_capture.capture()
            if screenshot is None:
                logger.warning("Failed to capture screenshot")
                time.sleep(interval_seconds)
                continue
            
            # Detect table
            table_region = table_detector.detect(screenshot)
            if table_region is None:
                logger.debug("Table not detected")
                time.sleep(interval_seconds)
                continue
            
            # Extract table region
            x, y, w, h = table_region
            table_img = screenshot[y:y+h, x:x+w]
            
            # Capture cards
            stats = capture.capture_from_screenshot(table_img)
            
            if stats["board_captured"] > 0 or stats["hero_captured"] > 0:
                capture_count += 1
                logger.info(f"Capture #{capture_count}: "
                          f"Board +{stats['board_captured']} (total: {stats['total_board']}), "
                          f"Hero +{stats['hero_captured']} (total: {stats['total_hero']})")
                
                # Show progress
                progress = capture.get_progress()
                logger.info(f"Overall progress: {progress['overall_progress']:.1f}%")
            
            # Wait before next capture
            time.sleep(interval_seconds)
    
    except KeyboardInterrupt:
        logger.info("Capture stopped by user")
    
    # Show final stats
    progress = capture.get_progress()
    logger.info("=" * 60)
    logger.info("Capture session complete!")
    logger.info(f"Board cards: {progress['board_cards_captured']}/52 ({progress['board_progress']:.1f}%)")
    logger.info(f"Hero cards: {progress['hero_cards_captured']}/52 ({progress['hero_progress']:.1f}%)")
    logger.info(f"Templates saved to:")
    logger.info(f"  Board: {board_output}")
    logger.info(f"  Hero: {hero_output}")
    logger.info("=" * 60)
    logger.info("Next steps:")
    logger.info("1. Review captured images and identify each card")
    logger.info("2. Rename files to standard format (e.g., 'Ah.png', 'Ks.png')")
    logger.info("3. Select best quality image for each card")
    logger.info("4. Move final templates to assets/templates/ and assets/hero_templates/")
