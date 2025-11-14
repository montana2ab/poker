# Button Detection Feature - Implementation Summary

## Overview
This implementation adds automatic button (dealer) position detection using existing chat and vision data, without adding any new OCR operations or screenshot captures.

## Implementation Details

### 1. Chat Parser Enhancement (`src/holdem/vision/chat_parser.py`)
Added regex patterns to detect PokerStars blind and ante posts:
```python
'post_sb': re.compile(r'^(.+?):\s+posts?\s+small\s+blind\s+\$?([\d,\.]+)', re.IGNORECASE),
'post_bb': re.compile(r'^(.+?):\s+posts?\s+(?:big\s+)?blind\s+\$?([\d,\.]+)', re.IGNORECASE),
'post_ante': re.compile(r'^(.+?):\s+posts?\s+(?:the\s+)?ante\s+\$?([\d,\.]+)', re.IGNORECASE),
```

Created new event types:
- `post_small_blind` - Small blind posting event
- `post_big_blind` - Big blind posting event  
- `post_ante` - Ante posting event

All events have confidence=0.95 and source=EventSource.CHAT.

### 2. ButtonDetector Module (`src/holdem/vision/button_detector.py`)
New lightweight module with O(n) complexity:

**Key Components:**
- `ButtonInferenceResult`: Dataclass holding button_seat, sb_seat, bb_seat
- `ButtonDetector`: Main class for button inference
- `assign_positions_for_6max()`: Utility for position label assignment

**Algorithm:**
1. Find SB and BB seats from blind posting events
2. If SB found and active:
   - For 2 players (heads-up): button = SB
   - For 3+ players: button = seat before SB in circular order
3. Return ButtonInferenceResult

**Performance:**
- No OCR or image processing
- O(n) complexity where n = len(events) + len(active_seats)
- Purely in-memory calculation

### 3. Integration (`src/holdem/vision/chat_enabled_parser.py`)
Added button detection to ChatEnabledStateParser:

**Initialization:**
```python
self.button_detector = ButtonDetector(num_seats=6)
self._last_button_detection_street = None
self._current_hand_button = None
```

**Detection Logic:**
- Called in `parse_with_events()` after event fusion
- Only runs at start of new hand (PREFLOP with empty board)
- Caches result per hand to avoid redundant calls
- Builds `name_to_seat` mapping from current player state
- Updates `state.button_position` when detected

**Performance Optimizations:**
- Detection cached per hand
- Only called once when blind events present
- Reuses existing player state for name_to_seat mapping

### 4. Testing (`tests/`)

**Unit Tests** (`test_button_detector.py`):
- 13 tests covering all scenarios:
  - Heads-up (BTN=SB)
  - 3-6 player detection
  - Circular wrap-around
  - Edge cases (no events, inactive players, missing names)
  - Position assignment utility

**Integration Tests** (`test_button_integration.py`):
- 2 tests demonstrating full flow:
  - Chat parsing → event creation → button detection (6-max)
  - Heads-up button detection

**Results:** ✅ All 15 tests passing

## Usage Example

```python
# Chat parser creates events from PokerStars chat
chat_events = [
    GameEvent(event_type='post_small_blind', player='Alice', amount=50),
    GameEvent(event_type='post_big_blind', player='Bob', amount=100),
]

# Button detector infers button position
detector = ButtonDetector(num_seats=6)
result = detector.infer_button(
    events=chat_events,
    name_to_seat={'Alice': 1, 'Bob': 2, 'Charlie': 3},
    active_seats=[1, 2, 3]
)

# Result: button_seat=0, sb_seat=1, bb_seat=2
print(f"Button at seat {result.button_seat}")
```

## Performance Validation

### No New OCR Operations ✅
- Uses only existing chat events from `ChatParser`
- No new screenshot captures
- No new OCR calls

### O(n) Complexity ✅
- Event iteration: O(len(events))
- Active seats check: O(len(active_seats))
- No nested loops or expensive operations

### Called Once Per Hand ✅
- Detection only runs at PREFLOP with empty board
- Result cached for entire hand
- Prevents redundant calculations

### Memory Efficiency ✅
- Small dataclasses for results
- No large buffers or caches
- Minimal state tracking (3 instance variables)

## Poker Rules Implementation

### Heads-Up (2 Players)
```
BTN = SB (acts first preflop, last postflop)
BB (acts last preflop, first postflop)
```

### Multi-Way (3-6 Players)
```
Circular order (clockwise):
BTN → SB → BB → UTG → MP → CO
```

Button is always the seat immediately before SB in seating order.

## Position Assignment Utility

Optional function `assign_positions_for_6max()` provides position labels:

```python
positions = assign_positions_for_6max(
    button_seat=0,
    active_seats=[0, 1, 2, 3, 4, 5]
)
# Returns: {0: "BTN", 1: "SB", 2: "BB", 3: "UTG", 4: "MP", 5: "CO"}
```

Can be used by decision engine for position-aware strategy.

## Future Enhancements (Optional)

1. **Store hero_position label** in TableState (e.g., "BTN", "SB", "BB")
2. **Validate button consistency** across multiple hands
3. **Fallback to vision** if chat events unavailable
4. **Support for ante-only games** (no blinds)
5. **Multi-table support** with per-table button tracking

## Conclusion

This implementation achieves all requirements:
- ✅ Automatic button detection from chat
- ✅ No new OCR or performance impact
- ✅ O(n) complexity with per-hand caching
- ✅ Handles 2-6 player scenarios correctly
- ✅ Comprehensive test coverage (15 tests)
- ✅ Clean, maintainable code with logging
