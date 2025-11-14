"""Integration test demonstrating button detection from chat events."""

from holdem.vision.button_detector import ButtonDetector
from holdem.vision.chat_parser import ChatParser


class MockOCREngine:
    """Mock OCR engine for testing."""
    def read_text(self, image):
        # Return mock chat text with blind posts
        return """Vasily65: posts small blind 50
Victor F.700: posts big blind 100"""


def test_button_detection_integration():
    """Integration test: chat parsing → button detection."""
    
    # Create chat parser
    ocr_engine = MockOCREngine()
    chat_parser = ChatParser(ocr_engine)
    
    # Parse chat events (simulating chat region extraction)
    import numpy as np
    mock_image = np.zeros((100, 100, 3), dtype=np.uint8)
    chat_events = chat_parser.parse_chat_region(mock_image)
    
    # Verify we got blind events
    sb_events = [e for e in chat_events if e.event_type == 'post_small_blind']
    bb_events = [e for e in chat_events if e.event_type == 'post_big_blind']
    
    assert len(sb_events) == 1, "Should have 1 SB event"
    assert len(bb_events) == 1, "Should have 1 BB event"
    assert sb_events[0].player == 'Vasily65'
    assert bb_events[0].player == 'Victor F.700'
    
    # Create button detector
    detector = ButtonDetector(num_seats=6)
    
    # Simulate name_to_seat mapping (from vision cache)
    name_to_seat = {
        'Alice': 0,
        'Vasily65': 1,  # SB
        'Victor F.700': 2,  # BB
        'Bob': 3,
        'Charlie': 4,
        'Dave': 5,
    }
    
    # Active seats (all players in hand)
    active_seats = [0, 1, 2, 3, 4, 5]
    
    # Infer button
    result = detector.infer_button(chat_events, name_to_seat, active_seats)
    
    # Verify button detection
    assert result.sb_seat == 1, "SB should be at seat 1"
    assert result.bb_seat == 2, "BB should be at seat 2"
    assert result.button_seat == 0, "Button should be at seat 0 (before SB)"
    
    print("✅ Integration test passed!")
    print(f"   Button: seat {result.button_seat}")
    print(f"   SB: seat {result.sb_seat} (player: {sb_events[0].player})")
    print(f"   BB: seat {result.bb_seat} (player: {bb_events[0].player})")
    

def test_heads_up_integration():
    """Integration test for heads-up button detection."""
    
    # Create chat parser
    ocr_engine = MockOCREngine()
    chat_parser = ChatParser(ocr_engine)
    
    # Parse chat events
    import numpy as np
    mock_image = np.zeros((100, 100, 3), dtype=np.uint8)
    chat_events = chat_parser.parse_chat_region(mock_image)
    
    # Create button detector
    detector = ButtonDetector(num_seats=6)
    
    # Heads-up: only 2 players
    name_to_seat = {
        'Vasily65': 0,  # BTN/SB in heads-up
        'Victor F.700': 1,  # BB
    }
    
    active_seats = [0, 1]
    
    # Infer button
    result = detector.infer_button(chat_events, name_to_seat, active_seats)
    
    # In heads-up, button IS small blind
    assert result.button_seat == 0, "Button should equal SB in heads-up"
    assert result.sb_seat == 0
    assert result.bb_seat == 1
    
    print("✅ Heads-up integration test passed!")
    print(f"   Heads-up: BTN = SB = seat {result.button_seat}")
    print(f"   BB: seat {result.bb_seat}")


if __name__ == "__main__":
    test_button_detection_integration()
    test_heads_up_integration()
    print("\n🎉 All integration tests passed!")
