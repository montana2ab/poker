"""
Demo of chat parsing and event fusion with vision system.

This example shows how to:
1. Extract events from table chat using OCR
2. Extract events from vision by comparing table states
3. Fuse events from both sources for higher reliability
4. Track event sources and confidence scores
"""

import numpy as np
from pathlib import Path
from typing import Optional

from holdem.vision.chat_parser import ChatParser, EventSource
from holdem.vision.event_fusion import EventFuser
from holdem.vision.ocr import OCREngine
from holdem.vision.calibrate import TableProfile
from holdem.vision.parse_state import StateParser
from holdem.vision.cards import CardRecognizer
from holdem.types import TableState
from holdem.utils.logging import get_logger

logger = get_logger("demo.chat_event_fusion")


class ChatEnabledStateParser:
    """Extended StateParser with chat parsing and event fusion."""
    
    def __init__(
        self,
        profile: TableProfile,
        card_recognizer: CardRecognizer,
        ocr_engine: OCREngine,
        enable_chat_parsing: bool = True,
        debug_dir: Optional[Path] = None
    ):
        """Initialize chat-enabled state parser.
        
        Args:
            profile: Table calibration profile
            card_recognizer: Card recognition engine
            ocr_engine: OCR engine for text extraction
            enable_chat_parsing: Whether to parse chat for events
            debug_dir: Optional directory for debug images
        """
        self.profile = profile
        self.state_parser = StateParser(
            profile=profile,
            card_recognizer=card_recognizer,
            ocr_engine=ocr_engine,
            debug_dir=debug_dir
        )
        
        self.enable_chat_parsing = enable_chat_parsing
        self.chat_parser = ChatParser(ocr_engine) if enable_chat_parsing else None
        self.event_fuser = EventFuser(
            time_window_seconds=5.0,
            confidence_threshold=0.7
        )
        
        self.prev_state: Optional[TableState] = None
    
    def parse_with_events(self, screenshot: np.ndarray):
        """Parse table state and extract fused events.
        
        Args:
            screenshot: Screenshot of poker table
            
        Returns:
            Tuple of (TableState, List[FusedEvent])
        """
        # Parse vision state
        current_state = self.state_parser.parse(screenshot)
        
        if current_state is None:
            logger.warning("Failed to parse table state from vision")
            return None, []
        
        # Extract vision events by comparing states
        vision_events = []
        if self.prev_state is not None:
            vision_events = self.event_fuser.create_vision_events_from_state(
                self.prev_state, current_state
            )
            logger.info(f"Extracted {len(vision_events)} events from vision")
        
        # Extract chat events if enabled
        chat_events = []
        if self.enable_chat_parsing and self.profile.chat_region:
            chat_events = self._extract_chat_events(screenshot)
            logger.info(f"Extracted {len(chat_events)} events from chat")
        
        # Fuse events from both sources
        fused_events = self.event_fuser.fuse_events(chat_events, vision_events)
        
        # Filter for reliable events only
        reliable_events = self.event_fuser.get_reliable_events(fused_events)
        
        logger.info(f"Fused {len(fused_events)} events, {len(reliable_events)} reliable")
        
        # Log event details
        for event in reliable_events:
            sources_str = ", ".join(s.value for s in event.sources)
            multi_source = " [CONFIRMED]" if event.is_multi_source() else ""
            logger.info(
                f"Event: {event.event_type} - "
                f"Player: {event.player} - "
                f"Action: {event.action} - "
                f"Amount: {event.amount} - "
                f"Confidence: {event.confidence:.2f} - "
                f"Sources: {sources_str}{multi_source}"
            )
        
        # Update previous state
        self.prev_state = current_state
        
        return current_state, reliable_events
    
    def _extract_chat_events(self, screenshot: np.ndarray):
        """Extract events from chat region."""
        if not self.chat_parser or not self.profile.chat_region:
            return []
        
        # Extract chat region
        region = self.profile.chat_region
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        
        if y + h > screenshot.shape[0] or x + w > screenshot.shape[1]:
            logger.warning(f"Chat region ({x},{y},{w},{h}) out of bounds")
            return []
        
        chat_region = screenshot[y:y+h, x:x+w]
        
        # Parse chat for events
        events = self.chat_parser.parse_chat_region(chat_region)
        
        return events


def demo_chat_event_fusion():
    """Demonstrate chat parsing and event fusion."""
    print("=" * 60)
    print("Chat Parsing and Event Fusion Demo")
    print("=" * 60)
    
    # This is a conceptual demo showing the API usage
    # In practice, you would:
    # 1. Load a table profile with chat_region configured
    # 2. Capture screenshots from the poker table
    # 3. Process each screenshot to extract and fuse events
    
    print("\n1. Setup Components:")
    print("   - Create table profile with chat_region")
    print("   - Initialize OCR engine")
    print("   - Initialize card recognizer")
    print("   - Create ChatEnabledStateParser")
    
    print("\n2. Process Each Screenshot:")
    print("   - Parse vision state (cards, pot, stacks, etc.)")
    print("   - Extract chat text using OCR")
    print("   - Parse chat for game events (actions, street changes)")
    print("   - Compare previous and current vision states")
    print("   - Fuse events from chat and vision sources")
    print("   - Calculate confidence scores")
    
    print("\n3. Event Fusion Benefits:")
    print("   ✓ Higher reliability - events confirmed by multiple sources")
    print("   ✓ Better accuracy - prefer precise chat data over OCR'd vision")
    print("   ✓ Source traceability - know where each piece of info came from")
    print("   ✓ Confidence scoring - filter out unreliable single-source events")
    
    print("\n4. Example Event Sources:")
    print("   Chat:")
    print("     'Player1 folds'")
    print("     'Hero raises to $50'")
    print("     '*** FLOP *** [Ah Kd Qs]'")
    print("     'Hero wins $125.50'")
    
    print("\n   Vision:")
    print("     - Player fold status changed")
    print("     - Bet amount increased")
    print("     - Board cards appeared")
    print("     - Pot amount changed")
    
    print("\n5. Fused Event Example:")
    print("   Event Type: action")
    print("   Player: Hero")
    print("   Action: RAISE")
    print("   Amount: $50.00 (from chat - more precise)")
    print("   Confidence: 0.95 (confirmed by both sources)")
    print("   Sources: [CHAT, VISION]")
    print("   Status: ✓ CONFIRMED")
    
    print("\n" + "=" * 60)
    print("Implementation Notes:")
    print("=" * 60)
    
    print("\nTo enable chat parsing in your table profile:")
    print("""
{
  "window_title": "PokerTable",
  "chat_region": {
    "x": 10,
    "y": 400,
    "width": 300,
    "height": 200
  },
  ...
}
    """)
    
    print("\nUsage in code:")
    print("""
# Create parser with chat enabled
parser = ChatEnabledStateParser(
    profile=profile,
    card_recognizer=card_recognizer,
    ocr_engine=ocr_engine,
    enable_chat_parsing=True
)

# Process screenshot
state, events = parser.parse_with_events(screenshot)

# Use fused events
for event in events:
    if event.is_multi_source():
        print(f"Confirmed: {event.event_type} - confidence {event.confidence}")
    """)
    
    print("\n" + "=" * 60)


def demo_event_types():
    """Show all supported event types and their sources."""
    print("\n" + "=" * 60)
    print("Supported Event Types")
    print("=" * 60)
    
    events = [
        ("action", "Player action (fold, check, call, bet, raise, all-in)", "Both"),
        ("street_change", "Street transition (flop, turn, river)", "Both"),
        ("card_deal", "Hole cards dealt to player", "Chat"),
        ("showdown", "Player shows cards at showdown", "Chat"),
        ("pot_update", "Pot amount changed", "Both"),
        ("pot_win", "Player wins pot", "Chat"),
    ]
    
    print("\n{:<20} {:<40} {:<10}".format("Event Type", "Description", "Sources"))
    print("-" * 70)
    
    for event_type, description, sources in events:
        print("{:<20} {:<40} {:<10}".format(event_type, description, sources))
    
    print("\n" + "=" * 60)


def demo_confidence_scoring():
    """Explain confidence scoring system."""
    print("\n" + "=" * 60)
    print("Confidence Scoring System")
    print("=" * 60)
    
    print("\nConfidence Calculation:")
    print("  • Multi-source (chat + vision): 0.90-0.95")
    print("  • Single-source (chat only): 0.70")
    print("  • Single-source (vision only): 0.70")
    print("  • Inconsistent data: -10% penalty")
    
    print("\nReliability Filtering:")
    print("  • Default threshold: 0.70")
    print("  • Events below threshold are discarded")
    print("  • Multi-source events always pass")
    
    print("\nBest Practices:")
    print("  1. Use multi-source confirmation for critical decisions")
    print("  2. Prefer chat data for precise amounts")
    print("  3. Use vision as fallback when chat unavailable")
    print("  4. Log all fused events for debugging")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo_chat_event_fusion()
    demo_event_types()
    demo_confidence_scoring()
    
    print("\n✓ Chat parsing and event fusion demo complete!")
    print("\nNext steps:")
    print("  1. Configure chat_region in your table profile")
    print("  2. Test chat parsing with your poker client")
    print("  3. Verify OCR quality on chat text")
    print("  4. Adjust confidence threshold as needed")
    print("  5. Monitor event fusion in logs")
