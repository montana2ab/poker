#!/usr/bin/env python3
"""
Quick test script to demonstrate the package works.
This shows the basic structure without requiring full dependencies.
"""

import sys
from pathlib import Path

# Add src to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root / 'src'))

print("=" * 70)
print("Texas Hold'em MCCFR System - Quick Test")
print("=" * 70)
print()

# Test basic imports
print("Testing basic imports...")
print("-" * 70)

try:
    import holdem
    print(f"✓ holdem v{holdem.__version__}")
    
    from holdem.types import Card, Street, ActionType
    print("✓ holdem.types (Card, Street, ActionType)")
    
    from holdem.config import Config
    print("✓ holdem.config (Config)")
    
    # Create a test card
    card = Card(rank='A', suit='h')
    print(f"✓ Created card: {card}")
    
    # Test card from string
    card2 = Card.from_string("Ks")
    print(f"✓ Card from string: {card2}")
    
    print()
    print("✓ All basic imports working!")
    print()
    
except ImportError as e:
    print(f"✗ Import failed: {e}")
    print()
    print("Make sure to run this from the repository root:")
    print("  cd /path/to/poker && python quick_test.py")
    sys.exit(1)

print("-" * 70)
print("Available CLI commands (via wrapper scripts):")
print("-" * 70)
print("  ./bin/holdem-profile-wizard    - Calibrate poker table")
print("  ./bin/holdem-build-buckets     - Build abstraction buckets")
print("  ./bin/holdem-train-blueprint   - Train MCCFR strategy")
print("  ./bin/holdem-eval-blueprint    - Evaluate strategy")
print("  ./bin/holdem-dry-run           - Test in observation mode")
print("  ./bin/holdem-autoplay          - Run auto-play mode")
print()

print("For help with any command:")
print("  ./bin/holdem-build-buckets --help")
print()

print("-" * 70)
print("Next steps:")
print("-" * 70)
print("1. Install dependencies:")
print("   pip install -r requirements.txt")
print()
print("2. Read the guides:")
print("   - DEVELOPMENT.md  - Complete development guide")
print("   - QUICKSTART.md   - Quick command reference")
print("   - README.md       - Full documentation")
print()
print("3. Run setup:")
print("   python setup.py")
print()
print("4. Verify everything:")
print("   python test_structure.py")
print()
print("=" * 70)
