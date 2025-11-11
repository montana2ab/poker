"""Demo: Real-time Action Detection and Visual Overlay

This script demonstrates the new real-time action detection and overlay features:
- Player action detection (CALL, CHECK, BET, RAISE, FOLD, ALL-IN)
- Dealer button position detection
- Visual overlay showing actions, bets, and game state

Usage:
    python demo_action_detection.py --profile assets/table_profiles/pokerstars.json

The script will:
1. Capture screenshots from the poker table
2. Detect player actions and dealer button position
3. Display visual overlay with detected information
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import argparse
import time
import cv2
import numpy as np
from holdem.vision.screen import ScreenCapture
from holdem.vision.calibrate import TableProfile
from holdem.vision.detect_table import TableDetector, _load_refs_from_paths
from holdem.vision.cards import CardRecognizer
from holdem.vision.ocr import OCREngine
from holdem.vision.parse_state import StateParser
from holdem.vision.overlay import GameOverlay
from holdem.utils.logging import setup_logger

logger = setup_logger("demo_action_detection")


def main():
    parser = argparse.ArgumentParser(
        description="Demo: Real-time Action Detection and Visual Overlay"
    )
    parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Table profile JSON file"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Capture interval in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--save-images",
        type=Path,
        help="Directory to save overlay images (optional)"
    )
    parser.add_argument(
        "--max-captures",
        type=int,
        default=10,
        help="Maximum number of captures (default: 10, 0 = unlimited)"
    )
    
    args = parser.parse_args()
    
    # Load profile
    logger.info(f"Loading table profile from {args.profile}")
    profile = TableProfile.load(args.profile)
    _load_refs_from_paths(profile, args.profile)
    
    # Setup components
    screen_capture = ScreenCapture()
    table_detector = TableDetector(profile)
    
    # Setup card recognizer
    hero_templates_dir = None
    if profile.hero_templates_dir:
        hero_templates_dir = Path(profile.hero_templates_dir)
    
    card_recognizer = CardRecognizer(
        templates_dir=Path("assets/templates"),
        hero_templates_dir=hero_templates_dir,
        method="template"
    )
    
    ocr_engine = OCREngine()
    state_parser = StateParser(profile, card_recognizer, ocr_engine)
    overlay_manager = GameOverlay(profile, alpha=0.7)
    
    # Create save directory if needed
    if args.save_images:
        args.save_images.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving overlay images to {args.save_images}")
    
    logger.info("Starting action detection demo...")
    logger.info(f"Capture interval: {args.interval}s")
    logger.info("Press Ctrl+C to stop")
    
    capture_count = 0
    
    try:
        while True:
            # Check max captures
            if args.max_captures > 0 and capture_count >= args.max_captures:
                logger.info(f"Reached maximum captures ({args.max_captures})")
                break
            
            capture_count += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"Capture #{capture_count}")
            logger.info(f"{'='*60}")
            
            # Capture screen
            screenshot = screen_capture.capture(profile.window_title, profile.owner_name)
            
            if screenshot is None:
                logger.warning("Failed to capture screenshot")
                time.sleep(args.interval)
                continue
            
            # Detect table
            warped = table_detector.detect_and_warp(screenshot)
            
            if warped is None:
                logger.warning("Table not detected")
                time.sleep(args.interval)
                continue
            
            logger.info(f"Table detected, size: {warped.shape}")
            
            # Parse state
            state = state_parser.parse(warped)
            
            if state is None:
                logger.warning("Failed to parse game state")
                time.sleep(args.interval)
                continue
            
            # Display detected information
            logger.info(f"\n📊 Game State:")
            logger.info(f"  Street: {state.street.name}")
            logger.info(f"  Pot: ${state.pot:.2f}")
            logger.info(f"  Button Position: {state.button_position}")
            logger.info(f"  Current Bet: ${state.current_bet:.2f}")
            
            logger.info(f"\n👥 Players ({len(state.players)}):")
            for player in state.players:
                action_str = ""
                if player.last_action:
                    action_str = f" | Action: {player.last_action.value.upper()}"
                
                bet_str = ""
                if player.bet_this_round > 0:
                    bet_str = f" | Bet: ${player.bet_this_round:.2f}"
                
                status_str = ""
                if player.folded:
                    status_str = " [FOLDED]"
                elif player.all_in:
                    status_str = " [ALL-IN]"
                
                logger.info(
                    f"  Pos {player.position}: {player.name} "
                    f"(${player.stack:.2f}){action_str}{bet_str}{status_str}"
                )
            
            # Create overlay
            overlay_img = overlay_manager.draw_state(warped, state)
            
            # Save image if requested
            if args.save_images:
                filename = f"overlay_{capture_count:04d}.png"
                filepath = args.save_images / filename
                cv2.imwrite(str(filepath), overlay_img)
                logger.info(f"💾 Saved overlay to {filepath}")
            
            # Display summary of detected actions
            actions_detected = [
                p for p in state.players 
                if p.last_action is not None
            ]
            if actions_detected:
                logger.info(f"\n🎯 Actions Detected:")
                for player in actions_detected:
                    logger.info(
                        f"  {player.name}: {player.last_action.value.upper()}"
                    )
            else:
                logger.info(f"\n⚠️  No actions detected in this frame")
            
            # Wait for next capture
            time.sleep(args.interval)
    
    except KeyboardInterrupt:
        logger.info("\n\nDemo stopped by user")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Demo completed: {capture_count} captures processed")
    if args.save_images:
        logger.info(f"Overlay images saved to: {args.save_images}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
