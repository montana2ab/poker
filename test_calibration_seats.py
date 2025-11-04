#!/usr/bin/env python3
"""Test script to verify calibration supports variable seat counts."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from holdem.vision.calibrate import calibrate_interactive


def test_6max_calibration():
    """Test that 6-max calibration creates 6 player regions."""
    # Create a dummy screenshot
    screenshot = np.zeros((800, 1200, 3), dtype=np.uint8)
    
    # Run calibration with 6 seats
    profile = calibrate_interactive(screenshot, "Test Table", seats=6)
    
    assert len(profile.player_regions) == 6, \
        f"Expected 6 player regions for 6-max, got {len(profile.player_regions)}"
    
    # Verify positions are 0-5
    positions = [p["position"] for p in profile.player_regions]
    assert positions == list(range(6)), \
        f"Expected positions 0-5, got {positions}"
    
    print("✓ 6-max calibration test passed")


def test_9max_calibration():
    """Test that 9-max calibration creates 9 player regions."""
    # Create a dummy screenshot
    screenshot = np.zeros((800, 1200, 3), dtype=np.uint8)
    
    # Run calibration with 9 seats (default)
    profile = calibrate_interactive(screenshot, "Test Table", seats=9)
    
    assert len(profile.player_regions) == 9, \
        f"Expected 9 player regions for 9-max, got {len(profile.player_regions)}"
    
    # Verify positions are 0-8
    positions = [p["position"] for p in profile.player_regions]
    assert positions == list(range(9)), \
        f"Expected positions 0-8, got {positions}"
    
    print("✓ 9-max calibration test passed")


def test_default_seats():
    """Test that default is 9 seats."""
    # Create a dummy screenshot
    screenshot = np.zeros((800, 1200, 3), dtype=np.uint8)
    
    # Run calibration without specifying seats (should default to 9)
    profile = calibrate_interactive(screenshot, "Test Table")
    
    assert len(profile.player_regions) == 9, \
        f"Expected 9 player regions by default, got {len(profile.player_regions)}"
    
    print("✓ Default seats test passed")


def test_player_regions_have_required_fields():
    """Test that player regions have all required fields."""
    screenshot = np.zeros((800, 1200, 3), dtype=np.uint8)
    profile = calibrate_interactive(screenshot, "Test Table", seats=9)
    
    required_fields = ["position", "name_region", "stack_region", "card_region"]
    
    for i, player_region in enumerate(profile.player_regions):
        for field in required_fields:
            assert field in player_region, \
                f"Player region {i} missing required field: {field}"
        
        # Verify nested regions have x, y, width, height
        for region_type in ["name_region", "stack_region", "card_region"]:
            region = player_region[region_type]
            for coord in ["x", "y", "width", "height"]:
                assert coord in region, \
                    f"Player {i} {region_type} missing {coord}"
    
    print("✓ Player region fields test passed")


if __name__ == "__main__":
    print("Testing calibration with variable seat counts...")
    print()
    
    test_6max_calibration()
    test_9max_calibration()
    test_default_seats()
    test_player_regions_have_required_fields()
    
    print()
    print("All tests passed! ✓")
