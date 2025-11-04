#!/usr/bin/env python3
"""
Demonstration of the improved player/hero card debug functionality.

This script shows how debug images are now saved for player cards in addition
to board cards, making it easier to diagnose card recognition issues.
"""

import sys
from pathlib import Path
import numpy as np
import cv2
from tempfile import TemporaryDirectory

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from holdem.vision.calibrate import TableProfile
from holdem.vision.parse_state import StateParser
from holdem.vision.cards import CardRecognizer, create_mock_templates
from holdem.vision.ocr import OCREngine


def main():
    print("=" * 70)
    print("Demo: Improved Player/Hero Card Debug Functionality")
    print("=" * 70)
    
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create templates
        print("\n1. Creating mock card templates...")
        board_templates = tmpdir / "board_templates"
        hero_templates = tmpdir / "hero_templates"
        create_mock_templates(board_templates, for_hero=False)
        create_mock_templates(hero_templates, for_hero=True)
        print(f"   - Board templates: {board_templates}")
        print(f"   - Hero templates: {hero_templates}")
        
        # Create debug directory
        debug_dir = tmpdir / "debug_output"
        debug_dir.mkdir()
        print(f"\n2. Debug images will be saved to: {debug_dir}")
        
        # Create a table profile
        print("\n3. Setting up table profile...")
        profile = TableProfile()
        profile.hero_position = 0  # First player is the hero
        profile.card_regions = [{"x": 400, "y": 320, "width": 400, "height": 120}]
        profile.player_regions = [
            {
                "position": 0,
                "name_region": {"x": 150, "y": 650, "width": 120, "height": 25},
                "stack_region": {"x": 150, "y": 675, "width": 120, "height": 25},
                "card_region": {"x": 130, "y": 700, "width": 160, "height": 100}
            },
            {
                "position": 5,
                "name_region": {"x": 950, "y": 650, "width": 120, "height": 25},
                "stack_region": {"x": 950, "y": 675, "width": 120, "height": 25},
                "card_region": {"x": 930, "y": 700, "width": 160, "height": 100}
            }
        ]
        profile.pot_region = {"x": 450, "y": 380, "width": 200, "height": 80}
        print(f"   - Hero position: {profile.hero_position}")
        print(f"   - Total players: {len(profile.player_regions)}")
        
        # Create parser with debug enabled
        print("\n4. Creating parser with debug enabled...")
        card_recognizer = CardRecognizer(board_templates, method="template",
                                        hero_templates_dir=hero_templates)
        ocr_engine = OCREngine(backend="pytesseract")
        parser = StateParser(profile, card_recognizer, ocr_engine, debug_dir=debug_dir)
        
        # Create a mock screenshot
        print("\n5. Parsing mock screenshot...")
        img = np.ones((900, 1200, 3), dtype=np.uint8) * 255
        
        # Parse the state
        state = parser.parse(img)
        
        # Show what was saved
        print("\n6. Debug images saved:")
        debug_files = sorted(debug_dir.glob("*.png"))
        for f in debug_files:
            size = f.stat().st_size
            print(f"   - {f.name} ({size} bytes)")
        
        print("\n" + "=" * 70)
        print("Summary of improvements:")
        print("=" * 70)
        print("✓ Board cards debug: board_region_XXXX.png (ALREADY EXISTED)")
        print("✓ Hero cards debug:  player_0_cards_XXXX.png (NEW!)")
        print("✓ Detailed logging for card recognition (NEW!)")
        print("\nBefore: Only board cards had debug output")
        print("After:  Both board AND player cards have debug output")
        print("\nThis makes it much easier to diagnose card recognition issues!")
        print("=" * 70)


if __name__ == "__main__":
    main()
