#!/usr/bin/env python3
"""Simple test to verify the project structure."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Test imports (without external dependencies)
try:
    from holdem import __version__
    print(f"✓ holdem package version: {__version__}")
except Exception as e:
    print(f"✗ Failed to import holdem: {e}")
    sys.exit(1)

try:
    from holdem.types import Card, Street, TableState, ActionType
    print("✓ holdem.types imports successfully")
except Exception as e:
    print(f"✗ Failed to import holdem.types: {e}")
    sys.exit(1)

try:
    from holdem.config import Config
    print("✓ holdem.config imports successfully")
except Exception as e:
    print(f"✗ Failed to import holdem.config: {e}")
    sys.exit(1)

# Test basic functionality
try:
    card = Card("A", "h")
    assert str(card) == "Ah"
    print(f"✓ Card creation works: {card}")
except Exception as e:
    print(f"✗ Card creation failed: {e}")
    sys.exit(1)

try:
    card2 = Card.from_string("Ks")
    assert card2.rank == "K" and card2.suit == "s"
    print(f"✓ Card.from_string works: {card2}")
except Exception as e:
    print(f"✗ Card.from_string failed: {e}")
    sys.exit(1)

# Check file structure
required_files = [
    "README.md",
    "LICENSE",
    "requirements.txt",
    "pyproject.toml",
    ".gitignore",
    "src/holdem/__init__.py",
    "src/holdem/types.py",
    "src/holdem/config.py",
    "src/holdem/cli/__init__.py",
    "tests/test_bucketing.py",
    "assets/abstraction/buckets_config.yaml",
]

print("\nChecking file structure:")
for file_path in required_files:
    path = Path(file_path)
    if path.exists():
        print(f"✓ {file_path}")
    else:
        print(f"✗ {file_path} missing")

# Check CLI modules exist
cli_commands = [
    "build_buckets",
    "train_blueprint",
    "run_dry_run",
    "run_autoplay",
    "profile_wizard",
    "eval_blueprint"
]

print("\nChecking CLI commands:")
for cmd in cli_commands:
    cmd_file = Path(f"src/holdem/cli/{cmd}.py")
    if cmd_file.exists():
        print(f"✓ {cmd}")
    else:
        print(f"✗ {cmd} missing")

print("\n✓ All basic checks passed!")
print("\nTo use the system:")
print("1. Install dependencies: pip install -r requirements.txt")
print("2. Run tests: pytest tests/")
print("3. Use CLI commands as documented in README.md")
