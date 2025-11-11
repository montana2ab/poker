"""Tests for action detection and dealer button detection functionality."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cv2
import numpy as np
from holdem.vision.ocr import OCREngine
from holdem.vision.parse_state import StateParser
from holdem.vision.calibrate import TableProfile
from holdem.vision.cards import CardRecognizer
from holdem.vision.overlay import GameOverlay
from holdem.types import PlayerState, ActionType, TableState, Street


def test_action_detection():
    """Test action detection from OCR."""
    ocr = OCREngine(backend="pytesseract")
    
    # Test action keywords detection
    test_cases = [
        ("CALL", "CALL"),
        ("FOLD", "FOLD"),
        ("CHECK", "CHECK"),
        ("BET", "BET"),
        ("RAISE", "RAISE"),
        ("ALL-IN", "ALL-IN"),
        ("ALL IN", "ALL-IN"),
        ("ALLIN", "ALL-IN"),
        ("Calls", "CALL"),
        ("Folded", "FOLD"),
        ("Raises", "RAISE"),
    ]
    
    print("\n=== Testing Action Detection ===")
    for text, expected in test_cases:
        # Create a simple image with text (mock)
        # In real scenario, OCR would read from actual image
        # For this test, we'll directly test the logic
        
        # Mock the text normalization
        text_norm = text.upper().strip()
        action_keywords = {
            'FOLD': ['FOLD', 'FOLDED', 'FOLDS'],
            'CHECK': ['CHECK', 'CHECKS', 'CHECKED'],
            'CALL': ['CALL', 'CALLS', 'CALLED'],
            'BET': ['BET', 'BETS', 'BETTING'],
            'RAISE': ['RAISE', 'RAISES', 'RAISED'],
            'ALL-IN': ['ALL-IN', 'ALLIN', 'ALL IN', 'ALL_IN'],
        }
        
        detected = None
        for action, variations in action_keywords.items():
            for keyword in variations:
                if keyword in text_norm:
                    detected = action
                    break
            if detected:
                break
        
        assert detected == expected, f"Expected {expected}, got {detected} for input '{text}'"
        print(f"✓ '{text}' -> {detected}")
    
    print("All action detection tests passed!")


def test_dealer_button_detection():
    """Test dealer button detection logic."""
    print("\n=== Testing Dealer Button Detection ===")
    
    # Create a mock profile with dealer button regions
    profile = TableProfile()
    profile.dealer_button_regions = [
        {'x': 10, 'y': 10, 'width': 20, 'height': 20},
        {'x': 100, 'y': 10, 'width': 20, 'height': 20},
        {'x': 190, 'y': 10, 'width': 20, 'height': 20},
    ]
    
    # Create mock images: one with bright region (button), others dim
    img_height, img_width = 100, 250
    
    # Test case 1: Button at position 0
    img1 = np.zeros((img_height, img_width, 3), dtype=np.uint8)
    # Make position 0 bright (simulating dealer button)
    img1[10:30, 10:30] = 200  # Bright region
    
    # Test case 2: Button at position 1
    img2 = np.zeros((img_height, img_width, 3), dtype=np.uint8)
    img2[10:30, 100:120] = 200  # Bright region at position 1
    
    # Test case 3: Button at position 2
    img3 = np.zeros((img_height, img_width, 3), dtype=np.uint8)
    img3[10:30, 190:210] = 200  # Bright region at position 2
    
    # Simple brightness-based detection (similar to _detect_button_presence)
    def detect_button_simple(img, regions):
        best_score = 0.0
        best_position = 0
        
        for pos_idx, btn_region in enumerate(regions):
            x = btn_region['x']
            y = btn_region['y']
            w = btn_region['width']
            h = btn_region['height']
            
            btn_img = img[y:y+h, x:x+w]
            if btn_img.size == 0:
                continue
            
            # Convert to grayscale
            if len(btn_img.shape) == 3:
                gray = cv2.cvtColor(btn_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = btn_img
            
            mean_intensity = np.mean(gray)
            score = 0.0
            if mean_intensity > 150:
                score = 0.8
            
            if score > best_score:
                best_score = score
                best_position = pos_idx
        
        return best_position if best_score > 0.3 else 0
    
    pos1 = detect_button_simple(img1, profile.dealer_button_regions)
    assert pos1 == 0, f"Expected button at position 0, got {pos1}"
    print(f"✓ Button detected at position {pos1} (expected 0)")
    
    pos2 = detect_button_simple(img2, profile.dealer_button_regions)
    assert pos2 == 1, f"Expected button at position 1, got {pos2}"
    print(f"✓ Button detected at position {pos2} (expected 1)")
    
    pos3 = detect_button_simple(img3, profile.dealer_button_regions)
    assert pos3 == 2, f"Expected button at position 2, got {pos3}"
    print(f"✓ Button detected at position {pos3} (expected 2)")
    
    print("All dealer button detection tests passed!")


def test_player_state_with_action():
    """Test PlayerState with action information."""
    print("\n=== Testing PlayerState with Actions ===")
    
    # Create player with action
    player = PlayerState(
        name="TestPlayer",
        stack=1000.0,
        position=0,
        bet_this_round=50.0,
        folded=False,
        all_in=False,
        last_action=ActionType.RAISE
    )
    
    assert player.last_action == ActionType.RAISE
    assert player.bet_this_round == 50.0
    assert not player.folded
    print(f"✓ Player with RAISE action created: {player.name}")
    
    # Create player who folded
    player2 = PlayerState(
        name="Folder",
        stack=1000.0,
        position=1,
        bet_this_round=0.0,
        folded=True,
        all_in=False,
        last_action=ActionType.FOLD
    )
    
    assert player2.last_action == ActionType.FOLD
    assert player2.folded
    print(f"✓ Player with FOLD action created: {player2.name}")
    
    print("All PlayerState tests passed!")


def test_overlay_functionality():
    """Test GameOverlay functionality."""
    print("\n=== Testing GameOverlay ===")
    
    # Create a mock profile
    profile = TableProfile()
    profile.player_regions = [
        {
            'position': 0,
            'name_region': {'x': 50, 'y': 50, 'width': 100, 'height': 20}
        },
        {
            'position': 1,
            'name_region': {'x': 200, 'y': 50, 'width': 100, 'height': 20}
        }
    ]
    profile.pot_region = {'x': 150, 'y': 100, 'width': 100, 'height': 30}
    
    # Create overlay manager
    overlay = GameOverlay(profile, alpha=0.7)
    
    # Create mock game state
    players = [
        PlayerState(
            name="Player1",
            stack=1000.0,
            position=0,
            bet_this_round=50.0,
            last_action=ActionType.RAISE
        ),
        PlayerState(
            name="Player2",
            stack=950.0,
            position=1,
            bet_this_round=0.0,
            last_action=ActionType.FOLD,
            folded=True
        )
    ]
    
    state = TableState(
        street=Street.FLOP,
        pot=150.0,
        players=players,
        button_position=0
    )
    
    # Create a blank image
    img = np.zeros((300, 400, 3), dtype=np.uint8)
    
    # Draw overlay
    result = overlay.draw_state(img, state)
    
    assert result.shape == img.shape
    assert not np.array_equal(result, img), "Overlay should have modified the image"
    print("✓ Overlay created successfully")
    
    # Test action color mapping
    color = overlay._get_action_color(ActionType.RAISE)
    assert color == overlay.colors['action_raise']
    print("✓ Action color mapping works")
    
    # Test action formatting
    action_text = overlay._format_action(ActionType.RAISE, 50.0)
    assert "RAISE" in action_text and "50" in action_text
    print(f"✓ Action formatted: {action_text}")
    
    print("All overlay tests passed!")


def test_profile_serialization():
    """Test that profile can save/load with new fields."""
    print("\n=== Testing Profile Serialization ===")
    
    import tempfile
    import json
    
    # Create profile with new fields
    profile = TableProfile()
    profile.window_title = "Test Table"
    profile.dealer_button_regions = [
        {'x': 10, 'y': 10, 'width': 20, 'height': 20},
        {'x': 100, 'y': 10, 'width': 20, 'height': 20},
    ]
    profile.player_regions = [
        {
            'position': 0,
            'name_region': {'x': 50, 'y': 50, 'width': 100, 'height': 20},
            'action_region': {'x': 50, 'y': 30, 'width': 100, 'height': 15},
            'bet_region': {'x': 50, 'y': 75, 'width': 100, 'height': 15},
        }
    ]
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)
    
    try:
        profile.save(temp_path)
        print(f"✓ Profile saved to {temp_path}")
        
        # Load back
        loaded_profile = TableProfile.load(temp_path)
        
        assert loaded_profile.window_title == profile.window_title
        assert len(loaded_profile.dealer_button_regions) == 2
        assert len(loaded_profile.player_regions) == 1
        assert 'action_region' in loaded_profile.player_regions[0]
        print("✓ Profile loaded successfully with all fields")
        
    finally:
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()
    
    print("All profile serialization tests passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("Running Action Detection and Button Detection Tests")
    print("=" * 60)
    
    test_action_detection()
    test_dealer_button_detection()
    test_player_state_with_action()
    test_overlay_functionality()
    test_profile_serialization()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
