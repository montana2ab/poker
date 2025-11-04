#!/usr/bin/env python
"""
Complete workflow example: Auto-capture and use card templates.

This demonstrates the full process from capturing templates to using them
for card recognition.
"""

from pathlib import Path
from holdem.vision.auto_capture import CardTemplateCapture
from holdem.vision.calibrate import TableProfile
from holdem.vision.cards import CardRecognizer
from holdem.utils.logging import setup_logger

logger = setup_logger("example_complete_workflow")


def example_workflow():
    """
    Demonstrate complete workflow from capture to recognition.
    """
    print("=" * 70)
    print("COMPLETE WORKFLOW: AUTO-CAPTURE AND CARD RECOGNITION")
    print("=" * 70)
    print()
    
    # =========================================================================
    # STEP 1: Configure Table Profile
    # =========================================================================
    print("STEP 1: Configure Table Profile")
    print("-" * 70)
    
    profile = TableProfile()
    profile.window_title = "PokerStars - Hold'em No Limit"
    profile.hero_position = 0  # You are at position 0
    
    # Define where cards appear on screen
    profile.card_regions = [
        {"x": 400, "y": 320, "width": 400, "height": 120}  # Board cards
    ]
    
    profile.player_regions = [
        {
            "position": 0,  # Hero (you)
            "name_region": {"x": 150, "y": 650, "width": 120, "height": 25},
            "stack_region": {"x": 150, "y": 675, "width": 120, "height": 25},
            "card_region": {"x": 130, "y": 700, "width": 160, "height": 100}
        },
        # Add other players...
    ]
    
    # Set hero templates directory
    profile.hero_templates_dir = "assets/hero_templates"
    
    # Save profile
    profile_path = Path("assets/table_profiles/my_profile.json")
    profile.save(profile_path)
    
    print(f"✓ Profile saved to: {profile_path}")
    print(f"  - Hero position: {profile.hero_position}")
    print(f"  - Hero templates: {profile.hero_templates_dir}")
    print()
    
    # =========================================================================
    # STEP 2: Auto-Capture Templates (simulated)
    # =========================================================================
    print("STEP 2: Auto-Capture Templates During Gameplay")
    print("-" * 70)
    print()
    print("In real usage, you would run:")
    print("  python capture_templates.py --profile my_profile.json")
    print()
    print("This would:")
    print("  1. Monitor the poker table while you play")
    print("  2. Automatically capture board cards at flop/turn/river")
    print("  3. Automatically capture your hole cards when dealt")
    print("  4. Save images to assets/templates_captured/")
    print()
    print("Example output during capture:")
    print("  Capture #1: Board +3 (total: 3), Hero +2 (total: 2)")
    print("  Capture #2: Board +1 (total: 4), Hero +0 (total: 2)")
    print("  Capture #3: Board +1 (total: 5), Hero +0 (total: 2)")
    print("  Overall progress: 6.7% (7/104 cards)")
    print()
    print("After playing for a while, you'll have captured many cards!")
    print()
    
    # =========================================================================
    # STEP 3: Organize and Label Templates
    # =========================================================================
    print("STEP 3: Organize and Label Captured Templates")
    print("-" * 70)
    print()
    print("After capture, organize the templates:")
    print()
    print("  # Board cards")
    print("  python organize_captured_templates.py \\")
    print("      --input assets/templates_captured/board \\")
    print("      --output assets/templates")
    print()
    print("  # Hero cards")
    print("  python organize_captured_templates.py \\")
    print("      --input assets/templates_captured/hero \\")
    print("      --output assets/hero_templates")
    print()
    print("This tool will:")
    print("  1. Show each captured card image")
    print("  2. Ask you to identify it (e.g., 'Ah', 'Ks', '7d')")
    print("  3. Rename and save to the correct location")
    print("  4. Skip duplicates")
    print()
    
    # =========================================================================
    # STEP 4: Use Templates for Recognition
    # =========================================================================
    print("STEP 4: Use Templates for Card Recognition")
    print("-" * 70)
    print()
    
    # Load profile (in real use, this would be the saved one)
    loaded_profile = TableProfile.load(profile_path)
    
    # Create recognizer with both template sets
    board_templates = Path("assets/templates")
    hero_templates = Path(loaded_profile.hero_templates_dir or "assets/hero_templates")
    
    print(f"Creating CardRecognizer with:")
    print(f"  - Board templates: {board_templates}")
    print(f"  - Hero templates: {hero_templates}")
    print()
    
    # In production, these directories would have real captured templates
    # For this example, we just show the configuration
    
    print("Usage in code:")
    print()
    print("  recognizer = CardRecognizer(")
    print("      templates_dir=board_templates,")
    print("      hero_templates_dir=hero_templates,")
    print("      method='template'")
    print("  )")
    print()
    print("  # Recognize board card")
    print("  board_card = recognizer.recognize_card(")
    print("      board_card_img,")
    print("      use_hero_templates=False")
    print("  )")
    print()
    print("  # Recognize hero card")
    print("  hero_card = recognizer.recognize_card(")
    print("      hero_card_img,")
    print("      use_hero_templates=True")
    print("  )")
    print()
    
    # =========================================================================
    # STEP 5: Play Poker with Better Recognition!
    # =========================================================================
    print("STEP 5: Play Poker with Improved Card Recognition")
    print("-" * 70)
    print()
    print("Now you can use the system normally:")
    print()
    print("  # Dry-run mode (observe only)")
    print("  python -m holdem.cli.run_dry_run \\")
    print("      --profile my_profile.json \\")
    print("      --policy my_policy.pkl")
    print()
    print("The system will automatically:")
    print("  ✓ Use board templates for community cards")
    print("  ✓ Use hero templates for your hole cards")
    print("  ✓ Achieve better recognition accuracy")
    print("  ✓ Improve preflop detection")
    print()
    
    # =========================================================================
    # BENEFITS
    # =========================================================================
    print("=" * 70)
    print("BENEFITS OF THIS WORKFLOW")
    print("=" * 70)
    print()
    print("✅ No Manual Cropping")
    print("   - Cards are captured automatically during gameplay")
    print("   - Just play poker, the system does the rest")
    print()
    print("✅ Optimal Quality")
    print("   - Templates captured in real playing conditions")
    print("   - Correct lighting, resolution, and positioning")
    print()
    print("✅ Separate Templates")
    print("   - Board cards and hero cards use different templates")
    print("   - Each optimized for its specific appearance")
    print()
    print("✅ Complete Coverage")
    print("   - Capture all 52 cards for board")
    print("   - Capture all 52 cards for hero")
    print("   - 104 total templates for maximum accuracy")
    print()
    print("✅ Progress Tracking")
    print("   - See how many cards captured in real-time")
    print("   - Know when you have complete coverage")
    print()
    print("✅ Easy Organization")
    print("   - Interactive tool to label cards")
    print("   - Automatic duplicate detection")
    print()
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    print("=" * 70)
    print("TYPICAL CAPTURE SESSION")
    print("=" * 70)
    print()
    print("Playing Time:    1 hour")
    print("Hands Played:    ~30-50 hands")
    print("Board Cards:     ~25-35 unique cards captured")
    print("Hero Cards:      ~15-25 unique cards captured")
    print("Total Captured:  ~40-60 cards (38-58% complete)")
    print()
    print("After 2-3 sessions: ~80-90% coverage")
    print("After 4-5 sessions: ~95-100% coverage")
    print()
    
    # =========================================================================
    # NEXT STEPS
    # =========================================================================
    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print()
    print("1. Create your table profile with correct regions")
    print("2. Run capture_templates.py while playing")
    print("3. Play poker for 1-2 hours to capture many cards")
    print("4. Organize templates with organize_captured_templates.py")
    print("5. Use the templates with improved recognition!")
    print()
    print("See documentation:")
    print("  - README_AUTO_CAPTURE.md (quick start)")
    print("  - GUIDE_AUTO_CAPTURE.md (complete guide in French)")
    print("  - GUIDE_CORRECTION_CARTES.md (setup guide)")
    print()
    print("=" * 70)


if __name__ == "__main__":
    example_workflow()
