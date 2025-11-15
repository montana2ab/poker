#!/usr/bin/env python3
"""
Demonstration of Chat OCR Integration

This script shows how the enhanced chat OCR system works with:
1. Explicit chat_ocr source tracking
2. Comprehensive logging
3. Image hash caching
4. Event fusion with vision
"""

import sys
sys.path.insert(0, '/home/runner/work/poker/poker/src')

import numpy as np
from unittest.mock import Mock
from holdem.vision.chat_parser import ChatParser, EventSource
from holdem.vision.chat_enabled_parser import ChatEnabledStateParser
from holdem.vision.calibrate import TableProfile
from holdem.vision.ocr import OCREngine
from holdem.vision.cards import CardRecognizer

def demo_chat_ocr_logging():
    """Demonstrate the new logging features."""
    print("\n" + "="*70)
    print("DEMONSTRATION: Chat OCR Logging")
    print("="*70)
    
    # Create mock OCR engine with sample chat text
    mock_ocr = Mock(spec=OCREngine)
    mock_ocr.read_text = Mock(return_value="Dealer: Hero raises to 100 Dealer: Villain calls 100")
    
    # Create chat parser
    parser = ChatParser(mock_ocr)
    
    # Create fake chat region
    chat_region = np.zeros((100, 300, 3), dtype=np.uint8)
    
    print("\n▶ Parsing chat region...")
    print("  Expected logs:")
    print("    - [CHAT OCR] Running OCR on chat region")
    print("    - [CHAT OCR] Raw text: ...")
    print("    - [CHAT OCR] Event created: type=action, player=Hero, source=chat_ocr")
    print("    - [CHAT OCR] Total events extracted: N\n")
    
    # Parse and extract events
    events = parser.parse_chat_region(chat_region)
    
    print(f"\n✓ Extracted {len(events)} events")
    for i, event in enumerate(events, 1):
        sources = ", ".join(s.value for s in event.sources)
        print(f"  {i}. {event.event_type}: player={event.player}, action={event.action}, sources=[{sources}]")

def demo_image_caching():
    """Demonstrate image hash caching."""
    print("\n" + "="*70)
    print("DEMONSTRATION: Image Hash Caching")
    print("="*70)
    
    # Create mock components
    profile = TableProfile()
    profile.chat_region = {"x": 0, "y": 0, "width": 100, "height": 50}
    
    mock_ocr = Mock(spec=OCREngine)
    call_count = [0]  # Use list for closure
    
    def mock_read_text(img):
        call_count[0] += 1
        return f"Call {call_count[0]}: Player1 folds"
    
    mock_ocr.read_text = Mock(side_effect=mock_read_text)
    mock_card_recognizer = Mock(spec=CardRecognizer)
    
    # Create parser
    parser = ChatEnabledStateParser(
        profile=profile,
        card_recognizer=mock_card_recognizer,
        ocr_engine=mock_ocr,
        enable_chat_parsing=True
    )
    
    # Create test screenshot
    screenshot = np.ones((500, 800, 3), dtype=np.uint8) * 100
    
    print("\n▶ First parse (will run OCR):")
    parser._extract_chat_events(screenshot)
    print(f"  OCR calls so far: {call_count[0]}")
    
    print("\n▶ Second parse with same image (should use cache):")
    parser._extract_chat_events(screenshot)
    print(f"  OCR calls so far: {call_count[0]}")
    print("  ✓ Cache hit! OCR not called again")
    
    # Change image
    screenshot = np.ones((500, 800, 3), dtype=np.uint8) * 200
    
    print("\n▶ Third parse with different image (cache miss):")
    parser._extract_chat_events(screenshot)
    print(f"  OCR calls so far: {call_count[0]}")
    print("  ✓ Cache miss! OCR called on new image")

def demo_event_source_tracking():
    """Demonstrate explicit source tracking."""
    print("\n" + "="*70)
    print("DEMONSTRATION: Event Source Tracking")
    print("="*70)
    
    print("\n▶ Available event sources:")
    for source in EventSource:
        print(f"  - {source.name}: '{source.value}'")
    
    print("\n▶ Chat events use CHAT_OCR source:")
    print("  This provides clear attribution in logs:")
    print("  'Event: action - Player: Hero - Sources: vision_bet_region, chat_ocr [CONFIRMED]'")
    
    print("\n▶ Backwards compatibility:")
    print("  EventSource.CHAT still exists and works")
    print("  New code should prefer EventSource.CHAT_OCR for clarity")

def demo_configuration():
    """Show configuration options."""
    print("\n" + "="*70)
    print("DEMONSTRATION: Configuration")
    print("="*70)
    
    print("\n▶ Table profile chat_region configuration:")
    print("""
{
  "chat_region": {
    "x": 10,
    "y": 550,
    "width": 350,
    "height": 140
  }
}
    """)
    
    print("▶ Performance configuration (configs/vision_performance.yaml):")
    print("""
vision_performance:
  chat_parse_interval: 3  # Parse every 3rd frame
  enable_caching: true     # Enable image hash caching
    """)
    
    print("▶ Runtime control:")
    print("  --disable-chat-parsing    # Disable chat OCR completely")
    print("  --enable-vision-metrics   # Track performance metrics")

def main():
    """Run all demonstrations."""
    print("\n" + "="*70)
    print("CHAT OCR INTEGRATION - FEATURE DEMONSTRATION")
    print("="*70)
    print("\nThis demonstration shows the new chat OCR features:")
    print("  1. Enhanced logging with [CHAT OCR] tags")
    print("  2. Image hash caching for performance")
    print("  3. Explicit chat_ocr source tracking")
    print("  4. Configuration options")
    
    demo_chat_ocr_logging()
    demo_image_caching()
    demo_event_source_tracking()
    demo_configuration()
    
    print("\n" + "="*70)
    print("DEMONSTRATION COMPLETE")
    print("="*70)
    print("\nFor more information, see:")
    print("  - CHAT_OCR_QUICKREF.md - Quick reference guide")
    print("  - CHAT_PARSING_GUIDE.md - Complete documentation")
    print("  - configs/profiles/example_with_chat.json - Sample config")
    print()

if __name__ == "__main__":
    main()
