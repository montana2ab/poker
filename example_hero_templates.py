#!/usr/bin/env python
"""
Example script showing how to use separate templates for board and hero cards.

This demonstrates the solution to card recognition issues where hero cards
and board cards have different visual characteristics.
"""

from pathlib import Path
from holdem.vision.cards import CardRecognizer, create_mock_templates
from holdem.vision.calibrate import TableProfile
from holdem.vision.parse_state import StateParser
from holdem.vision.ocr import OCREngine
import cv2
import numpy as np


def setup_templates_example():
    """
    Example 1: Setting up separate templates for board and hero cards.
    """
    print("=" * 60)
    print("Example 1: Setting up separate templates")
    print("=" * 60)
    
    # Define template directories
    board_templates_dir = Path("assets/templates")
    hero_templates_dir = Path("assets/hero_templates")
    
    # Create mock templates for testing
    # In production, replace these with actual card images from your poker client
    print("\nCreating mock board templates...")
    create_mock_templates(board_templates_dir, for_hero=False)
    
    print("Creating mock hero templates...")
    create_mock_templates(hero_templates_dir, for_hero=True)
    
    print(f"\nBoard templates saved to: {board_templates_dir}")
    print(f"Hero templates saved to: {hero_templates_dir}")
    print("\nNote: Replace mock templates with real card images for production use!")


def create_recognizer_example():
    """
    Example 2: Creating a CardRecognizer with separate template sets.
    """
    print("\n" + "=" * 60)
    print("Example 2: Creating CardRecognizer with separate templates")
    print("=" * 60)
    
    board_templates_dir = Path("assets/templates")
    hero_templates_dir = Path("assets/hero_templates")
    
    # Create recognizer with both template sets
    recognizer = CardRecognizer(
        templates_dir=board_templates_dir,
        hero_templates_dir=hero_templates_dir,
        method="template"
    )
    
    print(f"\nLoaded {len(recognizer.templates)} board card templates")
    print(f"Loaded {len(recognizer.hero_templates)} hero card templates")
    
    # Example: Recognize a board card
    print("\nRecognizing board cards:")
    print("  card = recognizer.recognize_card(board_card_img, use_hero_templates=False)")
    
    # Example: Recognize a hero card
    print("\nRecognizing hero cards:")
    print("  card = recognizer.recognize_card(hero_card_img, use_hero_templates=True)")
    
    return recognizer


def configure_table_profile_example():
    """
    Example 3: Configuring a TableProfile with hero templates.
    """
    print("\n" + "=" * 60)
    print("Example 3: Configuring TableProfile with hero templates")
    print("=" * 60)
    
    # Create a table profile
    profile = TableProfile()
    profile.window_title = "PokerStars - Hold'em No Limit"
    
    # Set hero position (0-based index in player_regions)
    profile.hero_position = 0  # Hero is at position 0
    
    # Set hero templates directory
    profile.hero_templates_dir = "assets/hero_templates"
    
    # Configure card regions
    profile.card_regions = [
        {"x": 400, "y": 320, "width": 400, "height": 120}  # Board cards region
    ]
    
    # Configure player regions (including hero)
    profile.player_regions = [
        {
            "position": 0,  # Hero position
            "name_region": {"x": 150, "y": 650, "width": 120, "height": 25},
            "stack_region": {"x": 150, "y": 675, "width": 120, "height": 25},
            "card_region": {"x": 130, "y": 700, "width": 160, "height": 100}  # Hero cards
        },
        # Add other player regions as needed...
    ]
    
    profile.pot_region = {"x": 450, "y": 380, "width": 200, "height": 80}
    
    # Save the profile
    profile_path = Path("assets/table_profiles/my_custom_profile.json")
    profile.save(profile_path)
    print(f"\nProfile saved to: {profile_path}")
    
    # Load it back
    loaded_profile = TableProfile.load(profile_path)
    print(f"Profile loaded successfully!")
    print(f"  Hero position: {loaded_profile.hero_position}")
    print(f"  Hero templates dir: {loaded_profile.hero_templates_dir}")
    
    return profile


def parse_with_hero_templates_example(profile):
    """
    Example 4: Parsing game state with separate hero templates.
    """
    print("\n" + "=" * 60)
    print("Example 4: Parsing game state with hero templates")
    print("=" * 60)
    
    # Create recognizer with both template sets
    board_templates_dir = Path("assets/templates")
    hero_templates_dir = Path(profile.hero_templates_dir or "assets/hero_templates")
    
    card_recognizer = CardRecognizer(
        templates_dir=board_templates_dir,
        hero_templates_dir=hero_templates_dir,
        method="template"
    )
    
    # Create OCR engine
    ocr_engine = OCREngine(backend="pytesseract")
    
    # Create state parser
    parser = StateParser(profile, card_recognizer, ocr_engine)
    
    print("\nStateParser configured with:")
    print(f"  Board templates: {board_templates_dir}")
    print(f"  Hero templates: {hero_templates_dir}")
    
    # When you capture a screenshot:
    # screenshot = capture_screenshot()  # Your screenshot capture method
    # state = parser.parse(screenshot)
    
    print("\nWhen parsing:")
    print("  - Board cards will use templates from 'assets/templates'")
    print("  - Hero cards will use templates from 'assets/hero_templates'")
    print("  - This improves recognition accuracy!")
    
    return parser


def how_to_create_real_templates():
    """
    Example 5: Guide for creating real templates from screenshots.
    """
    print("\n" + "=" * 60)
    print("Example 5: Creating real templates from screenshots")
    print("=" * 60)
    
    print("""
To create high-quality templates for production use:

1. BOARD CARD TEMPLATES:
   - Start a poker game and deal cards on the board
   - Take a screenshot showing all 5 board cards clearly
   - Crop each individual card (Ah, Kd, Qc, Js, Ts, etc.)
   - Save to 'assets/templates/' with names like 'Ah.png', 'Kd.png', etc.
   - Repeat for all 52 cards (13 ranks × 4 suits)

2. HERO CARD TEMPLATES:
   - Start a poker game and get dealt various hands
   - Take screenshots showing your hole cards clearly
   - Crop each individual card from YOUR position
   - Save to 'assets/hero_templates/' with same naming convention
   - Repeat for all 52 cards

3. TIPS:
   - Use consistent cropping (same size for all cards in each set)
   - Capture cards under normal playing conditions
   - Board and hero cards can be different sizes
   - Ensure good lighting and no obstruction
   - Test recognition and adjust templates if needed

4. ALTERNATIVE - USE PROVIDED TOOLS:
   - The system can auto-generate templates from screenshots
   - See documentation for calibration tools
   - Manual templates often work better than auto-generated ones
""")


def main():
    """Run all examples."""
    print("POKER CARD RECOGNITION - SEPARATE TEMPLATES EXAMPLE")
    print("=" * 60)
    print("\nThis example demonstrates how to fix card recognition issues")
    print("by using separate templates for board cards and hero cards.\n")
    
    # Run examples
    setup_templates_example()
    create_recognizer_example()
    profile = configure_table_profile_example()
    parse_with_hero_templates_example(profile)
    how_to_create_real_templates()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("""
The key improvements:

1. Separate Templates: Board cards and hero cards use different templates
2. Better Recognition: Each template set is optimized for its card type
3. Easy Configuration: Set hero_templates_dir in TableProfile
4. Automatic Usage: StateParser automatically uses correct templates
5. Backward Compatible: Works without hero templates (falls back to board)

Next steps:
- Create real templates from your poker client screenshots
- Configure your table profile with hero_position and hero_templates_dir
- Test card recognition accuracy
- Adjust templates if needed

For more information, see:
- assets/templates/README.md
- assets/hero_templates/README.md
""")


if __name__ == "__main__":
    main()
