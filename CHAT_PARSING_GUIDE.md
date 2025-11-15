# Chat Parsing and Event Fusion Guide

## Overview

This guide explains how to use the chat parsing and event fusion system to create more reliable game state tracking by combining information from multiple sources (vision OCR and table chat).

## Motivation

When observing a poker table through computer vision alone, several issues can arise:

- **OCR errors**: Stack amounts, pot sizes, and bet amounts may be misread
- **Timing issues**: Vision may miss rapid actions
- **Ambiguity**: Hard to distinguish between bet, raise, and call actions from vision alone
- **Missing info**: Can't see opponent hole cards or showdown results from vision

The **chat/history box** on most poker clients provides a text log of all game events with precise information. By combining chat parsing with vision, we can:

✓ **Cross-validate** events from multiple sources  
✓ **Improve accuracy** using precise chat data  
✓ **Detect missed events** that vision didn't capture  
✓ **Track source reliability** for debugging  

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    Screenshot                            │
└───────────┬─────────────────────────┬───────────────────┘
            │                         │
     ┌──────▼──────┐          ┌──────▼──────┐
     │   Vision    │          │    Chat     │
     │   Parser    │          │   Parser    │
     └──────┬──────┘          └──────┬──────┘
            │                         │
            │ Vision Events           │ Chat Events
            │                         │
     ┌──────▼─────────────────────────▼──────┐
     │         Event Fuser                    │
     │  - Match events by type/player/time   │
     │  - Calculate confidence scores         │
     │  - Merge data (prefer chat)           │
     └──────────────┬────────────────────────┘
                    │
             ┌──────▼──────┐
             │   Fused     │
             │   Events    │
             │ (reliable)  │
             └─────────────┘
```

### Event Sources

1. **Vision Events**: Extracted by comparing consecutive `TableState` snapshots
   - Player fold status changes
   - Bet amount increases
   - Board card appearances
   - Pot changes

2. **Chat Events**: Parsed from chat/history text using regex patterns
   - Action messages: "Player1 folds", "Hero raises to $50"
   - Street changes: "*** FLOP *** [Ah Kd Qs]"
   - Card deals: "Dealt to Hero [As Kh]"
   - Showdowns: "Player1 shows [Ac Ad]"
   - Pot updates: "Pot is $125.50"
   - Wins: "Hero wins $200.00"

3. **Fused Events**: Combined events with confidence scores
   - Multi-source: Confirmed by both vision and chat (confidence ≥ 0.90)
   - Single-source: Only from one source (confidence ≥ 0.70)

## Usage

### 1. Configure Table Profile

Add a `chat_region` to your table profile JSON to specify where the chat/history box is located:

```json
{
  "window_title": "PokerStars",
  "chat_region": {
    "x": 10,
    "y": 400,
    "width": 300,
    "height": 200
  },
  "card_regions": [...],
  "player_regions": [...],
  ...
}
```

**Tips for finding the chat region:**
- Most poker clients have a chat/hand history box in the bottom-left or right
- The region should include the scrolling text area
- Make sure to capture multiple lines (height ~150-250px)
- Avoid including borders or player avatars

### 2. Use ChatEnabledStateParser

```python
from holdem.vision.chat_parser import ChatParser
from holdem.vision.event_fusion import EventFuser
from holdem.vision.parse_state import StateParser
from holdem.vision.calibrate import TableProfile
from holdem.vision.ocr import OCREngine
from holdem.vision.cards import CardRecognizer

# Load table profile
profile = TableProfile.load("assets/table_profiles/my_profile.json")

# Initialize components
ocr_engine = OCREngine()
card_recognizer = CardRecognizer(template_dir="assets/templates")

# Create chat-enabled parser
from examples.demo_chat_event_fusion import ChatEnabledStateParser

parser = ChatEnabledStateParser(
    profile=profile,
    card_recognizer=card_recognizer,
    ocr_engine=ocr_engine,
    enable_chat_parsing=True,  # Enable chat parsing
    debug_dir=Path("debug/")   # Optional: save debug images
)

# Process screenshots
screenshot = capture_screen()  # Your capture method
state, events = parser.parse_with_events(screenshot)

# Use fused events
for event in events:
    if event.is_multi_source():
        print(f"✓ CONFIRMED: {event.event_type}")
        print(f"  Player: {event.player}")
        print(f"  Action: {event.action}")
        print(f"  Amount: ${event.amount:.2f}")
        print(f"  Confidence: {event.confidence:.2%}")
        print(f"  Sources: {[s.value for s in event.sources]}")
    else:
        print(f"? Single source: {event.event_type} (confidence: {event.confidence:.2%})")
```

### 3. Event Types

| Event Type | Description | Available Sources |
|------------|-------------|-------------------|
| `action` | Player action (fold, check, call, bet, raise, all-in) | Vision + Chat |
| `street_change` | Street transition (flop, turn, river) | Vision + Chat |
| `card_deal` | Hole cards dealt to player | Chat only |
| `showdown` | Player shows cards at showdown | Chat only |
| `pot_update` | Pot amount changed | Vision + Chat |
| `pot_win` | Player wins pot | Chat only |

### 4. Confidence Scoring

Events are assigned confidence scores based on:

- **Multi-source confirmation**: Events confirmed by both vision and chat get ≥ 0.90
- **Single source**: Events from only one source get ≥ 0.70
- **Data consistency**: Inconsistent amounts reduce confidence by 10%

**Reliability filtering:**
- Default threshold: 0.70 (configurable)
- Events below threshold are discarded
- Use `event_fuser.get_reliable_events()` to filter

```python
# Configure event fuser
event_fuser = EventFuser(
    time_window_seconds=5.0,     # Match events within 5 seconds
    confidence_threshold=0.7      # Minimum confidence to keep event
)

# Fuse events
fused_events = event_fuser.fuse_events(chat_events, vision_events)

# Get only reliable events
reliable_events = event_fuser.get_reliable_events(fused_events)
```

## Advanced Features

### Source Traceability

Every event tracks which sources contributed to it:

```python
event = GameEvent(
    event_type="action",
    player="Hero",
    action=ActionType.RAISE,
    amount=50.0,
    sources=[EventSource.CHAT, EventSource.VISION],
    raw_data={
        'chat': 'Hero raises to $50',
        'vision': {'prev_bet': 0.0, 'curr_bet': 50.0}
    }
)

# Check sources
if EventSource.CHAT in event.sources:
    print("Event confirmed by chat")

if event.is_confirmed():  # Multiple sources
    print("Event has multi-source confirmation")
```

### Data Preference Rules

When merging data from multiple sources:

1. **Amounts**: Prefer chat (more precise than OCR'd vision)
2. **Cards**: Prefer chat (exact text vs template matching)
3. **Player names**: Use chat (vision may have OCR errors)
4. **Timing**: Use earliest timestamp

```python
# Merge amounts - prefers chat
chat_event = GameEvent(amount=25.0, sources=[EventSource.CHAT])
vision_event = GameEvent(amount=24.5, sources=[EventSource.VISION])
merged_amount = event_fuser._merge_amounts([chat_event, vision_event])
# Result: 25.0 (from chat)

# Merge cards - prefers chat
chat_cards = [Card('A', 'h'), Card('K', 'd')]
vision_cards = [Card('A', 'h'), Card('Q', 'd')]  # OCR error
merged_cards = event_fuser._merge_cards([chat_event, vision_event])
# Result: chat_cards (more reliable)
```

### Time Window Matching

Events from different sources are matched if they:
- Have the same event type
- Refer to the same player (for player events)
- Occur within the time window (default: 5 seconds)
- Have consistent data (amounts within 5%, same action type)

```python
# These events would match
chat_event = GameEvent(
    event_type="action",
    player="Hero",
    action=ActionType.RAISE,
    timestamp=datetime(2024, 1, 1, 12, 0, 0)
)

vision_event = GameEvent(
    event_type="action",
    player="Hero",
    action=ActionType.RAISE,
    timestamp=datetime(2024, 1, 1, 12, 0, 2)  # 2 seconds later
)

# Match result: True (same player, action, within time window)
```

## Chat Pattern Support

The chat parser recognizes common poker client message formats:

### Actions
```
Player1 folds
Hero checks
Player2 calls $10.50
Hero bets $25.00
Player1 raises to $50
Player2 is all-in
```

### Street Changes
```
*** FLOP *** [Ah Kd Qs]
*** TURN *** [Ah Kd Qs Jc]
*** RIVER *** [Ah Kd Qs Jc Ts]
```

### Card Deals
```
Dealt to Hero [As Kh]
Dealt to Player1 [2c 2d]
```

### Showdowns
```
Hero shows [As Ah]
Player1 shows [Kc Kd]
```

### Pot Information
```
Pot is $125.50
Hero wins $200.00
Player1 wins $150.00 from main pot
```

### Customizing Patterns

If your poker client uses different formats, you can extend the patterns:

```python
from holdem.vision.chat_parser import ChatParser

# Add custom pattern
ChatParser.PATTERNS['custom_action'] = re.compile(
    r'^(.+?)\s+makes\s+a\s+bet\s+of\s+\$?([\d,\.]+)',
    re.IGNORECASE
)

# Or subclass and override
class CustomChatParser(ChatParser):
    PATTERNS = {
        **ChatParser.PATTERNS,
        'fold': re.compile(r'^(.+?)\s+has\s+folded', re.IGNORECASE),
        # ... more patterns
    }
```

## Debugging

### Enable Debug Logging

```python
from holdem.utils.logging import get_logger, set_log_level
import logging

# Enable debug logging
set_log_level(logging.DEBUG)

# Logs will show:
# - Chat lines extracted
# - Events parsed from chat
# - Vision events created
# - Event matching results
# - Fusion decisions
```

### Save Debug Images

```python
parser = ChatEnabledStateParser(
    profile=profile,
    card_recognizer=card_recognizer,
    ocr_engine=ocr_engine,
    debug_dir=Path("debug/chat_regions/")
)

# Chat region images will be saved to debug/chat_regions/
# Review them to ensure chat region is correctly positioned
```

### Inspect Raw Event Data

```python
for event in reliable_events:
    print(f"Event: {event.event_type}")
    print(f"  Raw data: {event.raw_data}")
    print(f"  Source events: {len(event.source_events)}")
    for src_event in event.source_events:
        print(f"    - {src_event.sources[0].value}: {src_event.raw_data}")
```

## Best Practices

1. **Profile Configuration**
   - Carefully position the chat_region to capture all chat text
   - Test OCR quality on chat text (should be high contrast)
   - Avoid overlapping regions (chat vs player info)

2. **Event Handling**
   - Always check `is_multi_source()` for critical decisions
   - Use confidence threshold to filter unreliable events
   - Log all events for debugging and analysis

3. **Performance**
   - Chat OCR is relatively fast but not free
   - Consider parsing chat only when needed (e.g., after actions)
   - Reuse OCR engine instance (don't create new ones per frame)

4. **Testing**
   - Test with various poker clients (different chat formats)
   - Verify time window is appropriate for your capture rate
   - Check confidence thresholds on real data

5. **Error Handling**
   - Handle OCR failures gracefully (return empty events)
   - Don't crash on unparseable chat lines
   - Fall back to vision-only if chat parsing fails

## Limitations

- **OCR Quality**: Chat parsing depends on OCR accuracy. Poor contrast or small fonts may cause issues.
- **Format Variations**: Different poker clients use different chat formats. May need pattern customization.
- **Language Support**: Current patterns are English-only. Extend for other languages.
- **Timing**: Events must occur within the time window to be matched. Very fast actions may be missed.
- **Private Info**: Chat only shows public information. Opponent hole cards are only visible at showdown.

## Future Enhancements

Potential improvements to the system:

- [ ] Multi-language chat pattern support
- [ ] Machine learning-based chat parsing (vs regex)
- [ ] Adaptive time window based on action frequency
- [ ] Historical event replay for missed actions
- [ ] Integration with hand history file parsing
- [ ] Conflict resolution when chat and vision strongly disagree
- [ ] Pattern learning from user corrections

## Testing

The chat parsing system includes comprehensive tests:

```bash
# Run chat parsing tests
python -m pytest tests/test_chat_parsing.py -v

# Tests cover:
# - All chat pattern types
# - Event fusion logic
# - Confidence scoring
# - Time window matching
# - Data merging preferences
```

## Example: Full Integration

```python
from pathlib import Path
from holdem.vision.calibrate import TableProfile
from holdem.vision.ocr import OCREngine
from holdem.vision.cards import CardRecognizer
from examples.demo_chat_event_fusion import ChatEnabledStateParser

# Setup
profile = TableProfile.load("assets/table_profiles/pokerstars.json")
ocr_engine = OCREngine()
card_recognizer = CardRecognizer(template_dir="assets/templates")

parser = ChatEnabledStateParser(
    profile=profile,
    card_recognizer=card_recognizer,
    ocr_engine=ocr_engine,
    enable_chat_parsing=True
)

# Main loop
while playing:
    screenshot = capture_screen()
    state, events = parser.parse_with_events(screenshot)
    
    if state:
        # Use table state for decision making
        print(f"Pot: ${state.pot:.2f}, Street: {state.street.name}")
    
    # Process events
    for event in events:
        if event.event_type == "action":
            handle_action(event)
        elif event.event_type == "street_change":
            handle_street_change(event)
        elif event.event_type == "showdown":
            handle_showdown(event)
        
        # Log high-confidence events
        if event.confidence >= 0.9:
            log_reliable_event(event)
```

## Logging and Debugging

### Chat OCR Logging

The system now includes comprehensive logging for chat OCR operations:

```
[CHAT OCR] Running OCR on chat region
[CHAT OCR] Raw text: 'Dealer: Player1 folds Dealer: Player2 calls 100'
[CHAT OCR] Line: Dealer: Player1 folds Dealer: Player2 calls 100
[CHAT OCR] Event created: type=action, player=Player1, action=FOLD, amount=None, source=chat_ocr
[CHAT OCR] Event created: type=action, player=Player2, action=CALL, amount=100.0, source=chat_ocr
[CHAT OCR] Total events extracted: 2
[CHAT OCR] Extracted 2 events from chat
```

### Event Source Tracking

All events now clearly indicate their source with the `chat_ocr` label:

```python
# Event sources in logs
Event: action - Player: Hero - Action: RAISE - Amount: 50.0 - Confidence: 0.95 - Sources: vision_bet_region, chat_ocr [CONFIRMED]
```

### Performance Monitoring

Chat OCR includes image hash caching to avoid redundant processing:

```
[CHAT OCR] Chat region changed (new hash), running OCR on 300x200 region
[CHAT OCR] Chat region unchanged (hash match), reusing cached events
```

This ensures minimal performance impact from chat parsing.

### Enabling Debug Logging

To see detailed chat OCR logs:

```python
import logging
logging.getLogger("vision.chat_parser").setLevel(logging.DEBUG)
logging.getLogger("vision.chat_enabled_parser").setLevel(logging.DEBUG)
```

### Troubleshooting

**No chat events appearing in logs?**
1. Verify `chat_region` is configured in your table profile
2. Check that `enable_chat_parsing=True` when creating ChatEnabledStateParser
3. Look for `[CHAT OCR] No chat_region configured` in logs
4. Ensure the chat region coordinates are correct and within screenshot bounds

**Chat OCR is slow?**
1. Chat region image hashing is enabled by default (no OCR if unchanged)
2. Adjust `chat_parse_interval` in `vision_performance.yaml` to skip frames
3. Set smaller chat_region dimensions if possible

**Events not being fused correctly?**
1. Check event timestamps are within the time window (default: 5 seconds)
2. Verify player names match between vision and chat
3. Look for `[CONFIRMED]` or `[MULTI-SOURCE]` tags in event logs

## References

- [Chat Parser Implementation](../src/holdem/vision/chat_parser.py)
- [Event Fusion Implementation](../src/holdem/vision/event_fusion.py)
- [Demo Example](../examples/demo_chat_event_fusion.py)
- [Tests](../tests/test_chat_parsing.py)

## Support

If you encounter issues:

1. Check debug logs for OCR and parsing errors
2. Verify chat_region positioning with debug images
3. Test chat patterns with your specific poker client
4. Review test cases for expected behavior
5. Open an issue with example screenshots and logs
