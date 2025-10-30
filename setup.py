#!/usr/bin/env python3
"""Setup script to initialize the poker AI system."""

import sys
from pathlib import Path

print("=" * 70)
print("Texas Hold'em MCCFR System - Setup")
print("=" * 70)
print()

# Create directories
print("Creating directory structure...")
dirs = [
    "assets/templates",
    "assets/samples",
    "assets/abstraction",
    "assets/table_profiles",
    "runs",
]

for dir_path in dirs:
    Path(dir_path).mkdir(parents=True, exist_ok=True)
    print(f"  ✓ {dir_path}/")

print()

# Try to setup vision assets if dependencies are available
print("Setting up vision assets...")
try:
    sys.path.insert(0, str(Path(__file__).parent / 'src'))
    from holdem.vision.assets_tools import setup_vision_assets
    
    assets_dir = Path("assets")
    setup_vision_assets(assets_dir)
    print("✓ Vision assets created (52 card templates)")
except ImportError as e:
    print(f"⚠ Skipping vision assets (missing dependencies: {e})")
    print("  Run 'pip install -r requirements.txt' then:")
    print("  python -c 'from holdem.vision.cards import create_mock_templates; from pathlib import Path; create_mock_templates(Path(\"assets/templates\"))'")

print()

print("=" * 70)
print("Setup complete!")
print("=" * 70)
print()
print("Directory structure:")
print(f"  • assets/templates/ - Card recognition templates")
print(f"  • assets/samples/ - Sample images for testing")
print(f"  • assets/abstraction/ - Bucket configuration")
print(f"  • assets/table_profiles/ - Table calibration profiles")
print()
print("Next steps:")
print("  1. Install dependencies: pip install -r requirements.txt")
print("  2. Run verification: python verify_structure.py")
print("  3. See demo usage: python demo_usage.py")
print("  4. Review README.md for full documentation")
print()
