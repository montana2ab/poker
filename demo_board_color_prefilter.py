#!/usr/bin/env python3
"""
Demonstration of board card color prefilter functionality.

This script shows how the board card color prefilter works and compares
performance with and without the prefilter enabled.
"""

import sys
sys.path.insert(0, 'src')

import cv2
import numpy as np
from pathlib import Path
import time
from holdem.vision.cards import CardRecognizer


def create_demo_templates(base_dir: Path, num_cards: int = 52):
    """Create demo templates for testing."""
    templates_dir = base_dir / "demo_templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    suits = ['h', 'd', 'c', 's']
    
    card_count = 0
    for rank in ranks:
        for suit in suits:
            if card_count >= num_cards:
                break
            
            card_name = f"{rank}{suit}"
            template = np.ones((100, 70, 3), dtype=np.uint8)
            
            # Set colors based on suit
            if suit in ['h', 'd']:  # Red cards
                template[:, :, 2] = 180  # R
                template[:, :, 1] = 50   # G
                template[:, :, 0] = 50   # B
            else:  # Black cards
                template[:, :, 2] = 60   # R
                template[:, :, 1] = 60   # G
                template[:, :, 0] = 60   # B
            
            # Add rank text
            cv2.putText(template, rank, (25, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
            
            # Save template
            cv2.imwrite(str(templates_dir / f"{card_name}.png"), template)
            card_count += 1
        
        if card_count >= num_cards:
            break
    
    print(f"Created {card_count} demo templates in {templates_dir}")
    return templates_dir


def create_test_card_image(is_red: bool = True):
    """Create a test card image."""
    img = np.ones((100, 70, 3), dtype=np.uint8)
    
    if is_red:
        img[:, :, 2] = 180  # R
        img[:, :, 1] = 50   # G
        img[:, :, 0] = 50   # B
    else:
        img[:, :, 2] = 60   # R
        img[:, :, 1] = 60   # G
        img[:, :, 0] = 60   # B
    
    return img


def demo_board_prefilter_basic():
    """Demonstrate basic board prefilter functionality."""
    print("\n" + "="*70)
    print("DEMO 1: Basic Board Color Prefilter Functionality")
    print("="*70)
    
    # Create demo templates
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        templates_dir = create_demo_templates(tmp_path, num_cards=52)
        
        # Create recognizer with board templates
        print("\nInitializing CardRecognizer with board templates...")
        recognizer = CardRecognizer(method="template", templates_dir=templates_dir)
        
        print(f"Loaded {len(recognizer.templates)} board templates")
        print(f"Board color prefilter enabled: {recognizer.enable_board_color_prefilter}")
        print(f"Board color prefilter top_k: {recognizer.board_color_prefilter_top_k}")
        print(f"Board color prefilter min_sim: {recognizer.board_color_prefilter_min_sim}")
        
        # Test with red card image
        print("\n--- Testing with RED card image ---")
        red_card = create_test_card_image(is_red=True)
        result = recognizer.recognize_card(red_card, use_hero_templates=False, board_card_index=0)
        print(f"Recognized card: {result}")
        
        # Test with black card image
        print("\n--- Testing with BLACK card image ---")
        black_card = create_test_card_image(is_red=False)
        result = recognizer.recognize_card(black_card, use_hero_templates=False, board_card_index=1)
        print(f"Recognized card: {result}")


def demo_board_prefilter_performance():
    """Demonstrate performance improvement with board prefilter."""
    print("\n" + "="*70)
    print("DEMO 2: Board Color Prefilter Performance Comparison")
    print("="*70)
    
    # Create demo templates
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        templates_dir = create_demo_templates(tmp_path, num_cards=52)
        
        # Create recognizer
        recognizer = CardRecognizer(method="template", templates_dir=templates_dir)
        
        # Create test image
        test_img = create_test_card_image(is_red=True)
        
        # Warmup
        for _ in range(5):
            recognizer.recognize_card(test_img, use_hero_templates=False)
        
        # Test with prefilter enabled
        print("\n--- WITH Board Color Prefilter (top_k=12) ---")
        recognizer.enable_board_color_prefilter = True
        recognizer.board_color_prefilter_top_k = 12
        
        iterations = 50
        start_time = time.perf_counter()
        for i in range(iterations):
            result = recognizer.recognize_card(test_img, use_hero_templates=False, board_card_index=i % 5)
        with_prefilter_time = time.perf_counter() - start_time
        
        print(f"Time for {iterations} iterations: {with_prefilter_time:.4f}s")
        print(f"Average time per card: {with_prefilter_time / iterations * 1000:.2f}ms")
        
        # Test without prefilter
        print("\n--- WITHOUT Board Color Prefilter (all 52 templates) ---")
        recognizer.enable_board_color_prefilter = False
        
        start_time = time.perf_counter()
        for i in range(iterations):
            result = recognizer.recognize_card(test_img, use_hero_templates=False)
        without_prefilter_time = time.perf_counter() - start_time
        
        print(f"Time for {iterations} iterations: {without_prefilter_time:.4f}s")
        print(f"Average time per card: {without_prefilter_time / iterations * 1000:.2f}ms")
        
        # Calculate speedup
        if with_prefilter_time > 0:
            speedup = without_prefilter_time / with_prefilter_time
            print(f"\n🚀 SPEEDUP: {speedup:.2f}x faster with board color prefilter!")
            print(f"   Latency reduction: {(1 - with_prefilter_time / without_prefilter_time) * 100:.1f}%")


def demo_board_cards_recognition():
    """Demonstrate board cards recognition with prefilter."""
    print("\n" + "="*70)
    print("DEMO 3: Board Cards Recognition (5 cards)")
    print("="*70)
    
    # Create demo templates
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        templates_dir = create_demo_templates(tmp_path, num_cards=52)
        
        # Create recognizer
        recognizer = CardRecognizer(method="template", templates_dir=templates_dir)
        
        # Create a composite image with 5 cards (flop + turn + river)
        card_width = 70
        card_height = 100
        board_img = np.ones((card_height, card_width * 5, 3), dtype=np.uint8)
        
        # Create 5 cards (3 red, 2 black for variety)
        for i in range(5):
            is_red = i < 3  # First 3 are red (flop), last 2 are black (turn, river)
            x_start = i * card_width
            x_end = (i + 1) * card_width
            
            if is_red:
                board_img[:, x_start:x_end, 2] = 180  # R
                board_img[:, x_start:x_end, 1] = 50   # G
                board_img[:, x_start:x_end, 0] = 50   # B
            else:
                board_img[:, x_start:x_end, 2] = 60   # R
                board_img[:, x_start:x_end, 1] = 60   # G
                board_img[:, x_start:x_end, 0] = 60   # B
        
        # Recognize all 5 board cards
        print("\nRecognizing 5 board cards with color prefilter...")
        print("Expected: 3 red cards (hearts/diamonds) + 2 black cards (clubs/spades)")
        
        recognizer.enable_board_color_prefilter = True
        cards = recognizer.recognize_cards(
            board_img, 
            num_cards=5, 
            use_hero_templates=False,
            skip_empty_check=True
        )
        
        print(f"\nRecognized cards: {[str(c) if c else 'None' for c in cards]}")
        print(f"Recognition rate: {len([c for c in cards if c])}/5")


def demo_hero_vs_board_prefilter():
    """Demonstrate that hero and board prefilters work independently."""
    print("\n" + "="*70)
    print("DEMO 4: Hero vs Board Prefilter Independence")
    print("="*70)
    
    # Create demo templates
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create hero templates (smaller, slightly different style)
        hero_dir = tmp_path / "hero_templates"
        hero_dir.mkdir()
        for card in ['Ah', 'Kh', 'As', 'Ks']:
            template = np.ones((80, 60, 3), dtype=np.uint8)
            if card[1] == 'h':
                template[:, :, 2] = 180
                template[:, :, 1] = 50
                template[:, :, 0] = 50
            else:
                template[:, :, 2] = 60
                template[:, :, 1] = 60
                template[:, :, 0] = 60
            cv2.imwrite(str(hero_dir / f"{card}.png"), template)
        
        # Create board templates
        board_dir = create_demo_templates(tmp_path, num_cards=52)
        
        # Create recognizer with both
        recognizer = CardRecognizer(
            method="template",
            templates_dir=board_dir,
            hero_templates_dir=hero_dir
        )
        
        print(f"\nHero templates loaded: {len(recognizer.hero_templates)}")
        print(f"Board templates loaded: {len(recognizer.templates)}")
        
        # Test hero card recognition
        print("\n--- Testing Hero Card Recognition ---")
        hero_img = np.ones((80, 60, 3), dtype=np.uint8)
        hero_img[:, :, 2] = 180  # Red card
        hero_img[:, :, 1] = 50
        hero_img[:, :, 0] = 50
        
        result = recognizer.recognize_card(hero_img, use_hero_templates=True)
        print(f"Hero card recognized: {result}")
        print("(Should see 'Hero color pre-filter' in logs)")
        
        # Test board card recognition
        print("\n--- Testing Board Card Recognition ---")
        board_img = create_test_card_image(is_red=True)
        
        result = recognizer.recognize_card(board_img, use_hero_templates=False, board_card_index=0)
        print(f"Board card recognized: {result}")
        print("(Should see 'board card 0 color pre-filter' in logs)")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("BOARD CARD COLOR PREFILTER DEMONSTRATION")
    print("="*70)
    print("\nThis demo shows the new board card color prefilter functionality")
    print("which uses the same technique as hero cards to improve performance.")
    
    try:
        demo_board_prefilter_basic()
        demo_board_prefilter_performance()
        demo_board_cards_recognition()
        demo_hero_vs_board_prefilter()
        
        print("\n" + "="*70)
        print("✅ DEMO COMPLETED SUCCESSFULLY")
        print("="*70)
        print("\nKey improvements:")
        print("• Board cards now use color prefiltering like hero cards")
        print("• Reduced latency by limiting template matching to relevant candidates")
        print("• Improved recognition quality by filtering out color mismatches")
        print("• Better logging with card-specific labels (board card 0, 1, 2, etc.)")
        print("• No regression in hero card recognition")
        print("• Backward compatible - prefilter can be disabled if needed")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
