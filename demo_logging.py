#!/usr/bin/env python
"""
Demonstration of enhanced logging for card recognition and OCR.

This script shows how the improved logging helps debug issues with:
- Card recognition (templates, detection)
- OCR functionality (tesseract availability)
- State parsing (board cards, pot, players)
"""

import sys
from pathlib import Path

# Add src to path
try:
    src_path = Path(__file__).parent / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))
except Exception as e:
    print(f"Warning: Could not add src to path: {e}")
    print("Some imports may fail if the package is not installed")
    print()

print("=" * 70)
print("DEMONSTRATION: Enhanced Logging for Vision System")
print("=" * 70)
print()

print("1. Testing Card Recognition Initialization")
print("-" * 70)
try:
    from holdem.vision.cards import CardRecognizer
    
    # Test with missing templates
    print("a) Initializing with non-existent templates directory:")
    recognizer = CardRecognizer(templates_dir=Path("/tmp/nonexistent"), method="template")
    print()
    
    # Test with existing templates
    print("b) Initializing with existing templates directory:")
    templates_dir = Path("assets/templates")
    if templates_dir.exists():
        recognizer = CardRecognizer(templates_dir=templates_dir, method="template")
    else:
        print(f"   Templates directory not found at {templates_dir}")
        print("   Run: python setup_assets.py to create templates")
    print()
except Exception as e:
    print(f"Error: {e}")
    print()

print("2. Testing OCR Engine Initialization")
print("-" * 70)
try:
    from holdem.vision.ocr import OCREngine
    
    print("a) Attempting PaddleOCR initialization:")
    ocr1 = OCREngine(backend="paddleocr")
    print()
    
    print("b) Attempting Pytesseract initialization:")
    ocr2 = OCREngine(backend="pytesseract")
    print()
except Exception as e:
    print(f"Error: {e}")
    print()

print("3. Example of Enhanced Dry-Run Output")
print("-" * 70)
print("The dry-run mode now displays:")
print()
print("  " + "=" * 60)
print("  Street: FLOP")
print("  Pot: $125.50")
print("  Board: Ah Kd Qs (3 cards)")
print("  Players: 6 detected")
print("    - Player1: $1000.00 (pos 0)")
print("    - Player2: $1500.00 (pos 1)")
print("    - Player3: $750.00 (pos 2)")
print("    - ...")
print("  " + "=" * 60)
print("  [DRY RUN] Would analyze and suggest action here")
print()

print("4. Debug Logging Examples")
print("-" * 70)
print("With debug logging enabled, you'll see:")
print()
print("  [DEBUG] Board cards detected: Ah Kd Qs ?? ??")
print("  [DEBUG] Pot detected: 125.5")
print("  [DEBUG] Player 0 stack detected: 1000.0")
print("  [DEBUG] Player 0 name detected: Hero")
print("  [DEBUG] Player 0 cards: Ac Ad")
print("  [DEBUG] Card 0: Recognized Ah with confidence 0.923")
print("  [DEBUG] Card 3: No match found")
print()

print("5. Error Messages and Troubleshooting")
print("-" * 70)
print("When things fail, you'll see helpful messages:")
print()
print("  [WARNING] Failed to parse state - check calibration and OCR")
print("  [WARNING] Troubleshooting tips:")
print("  [WARNING]   1. Verify table is visible and not obscured")
print("  [WARNING]   2. Check that tesseract is installed for OCR")
print("  [WARNING]   3. Ensure card templates exist in assets/templates")
print("  [WARNING]   4. Review calibration regions in profile JSON")
print()

print("=" * 70)
print("SUMMARY OF IMPROVEMENTS")
print("=" * 70)
print()
print("✓ Detailed card detection feedback (board and player cards)")
print("✓ OCR result logging (pot, stacks, names)")
print("✓ Clear error messages with installation instructions")
print("✓ Helpful troubleshooting tips when parsing fails")
print("✓ Visual display of detected game state")
print()
print("These improvements help identify issues like:")
print("  - Missing tesseract installation")
print("  - Missing card templates")
print("  - Incorrect calibration regions")
print("  - OCR recognition failures")
print()
print("=" * 70)
