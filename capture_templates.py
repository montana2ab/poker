#!/usr/bin/env python
"""
Quick launcher for automatic card template capture.

This script provides an easy way to start capturing card templates
during gameplay.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from holdem.cli.capture_templates import main

if __name__ == "__main__":
    sys.exit(main())
