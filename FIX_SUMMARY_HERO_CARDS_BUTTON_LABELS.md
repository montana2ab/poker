# Fix Summary: Hero Cards Tracking and Button Label Filtering

## Overview

This fix addresses two critical issues in the poker vision system:

1. **Hero cards tracker degrading from 2 confirmed cards to 1 card**
2. **Button labels ("Raise", "Call", etc.) being interpreted as player names**

## Problem Details

### Issue 1: Hero Cards Degradation

**Bug Symptom (from logs):**
```
[10:17:29] Hero cards (tracked): Qc, 3s
[10:17:34] Card recognition summary: 1/2 hero cards recognized
          hero best=Qc score=0.991
          hero best=3s score=0.609 thr=0.65
          [HERO CARDS] Confirming stable cards: Qc
          Hero cards (tracked): Qc
```

**Root Cause:**
The `HeroCardsTracker` in `parse_state.py` would accept any stable candidate, even if it meant downgrading from 2 confirmed cards to 1 card. When one card's confidence temporarily dropped below the threshold, the tracker would treat a single card as a valid new candidate and confirm it after 2 stable frames.

**Impact:**
- Incorrect hero cards during hand analysis
- State machine confusion about hero's actual holding
- Potential incorrect AI decisions based on partial hand information

### Issue 2: Button Labels as Player Names

**Bug Symptom (from logs):**
```
Event: action - Player: Raise - ActionType.BET - Amount: 5752.0 - Sources: vision_bet_region
```

**Root Cause:**
OCR was reading button text ("Raise", "Call", "Bet", etc.) from the poker client UI and interpreting these as player names. The vision system would then create action events with these button labels as the player name.

**Impact:**
- False action events attributed to non-existent players
- Event fusion confusion when trying to correlate with real player names
- Log noise and difficulty debugging actual game events

## Solution Implementation

### Fix 1: Hero Cards Downgrade Prevention

**File:** `src/holdem/vision/parse_state.py`

**Changes to `HeroCardsTracker.update()`:**

```python
# CRITICAL: Once we have 2 confirmed cards, never downgrade to fewer cards
if self.confirmed_cards and len(self.confirmed_cards) == 2:
    # If new detection has fewer than 2 cards, ignore it and keep confirmed cards
    if len(cards) < 2:
        logger.debug(
            f"[HERO CARDS] Ignoring downgrade from 2 confirmed cards to {len(cards)} card(s). "
            f"Keeping confirmed: {self._cards_str(self.confirmed_cards)}"
        )
        return self.confirmed_cards
```

**Key Logic:**
1. Once `confirmed_cards` contains 2 cards, this becomes "sticky"
2. Any new detection with fewer than 2 cards is ignored
3. The tracker returns the previously confirmed 2 cards
4. Only when a new 2-card hand is stable for 2+ frames will it replace the confirmed cards
5. The tracker is reset at the start of each new hand

**Logging Improvements:**
- Clear message when 2 cards are first confirmed: `"Confirmed hero cards for current hand: Qc, 3s"`
- Debug message when downgrade is prevented: `"Ignoring downgrade from 2 confirmed cards to 1 card(s)"`

### Fix 2: Button Label Filtering

**Files:** 
- `src/holdem/vision/parse_state.py`
- `src/holdem/vision/event_fusion.py`

**New Utility Function:**

```python
def is_button_label(name: str) -> bool:
    """
    Return True if 'name' looks like a button label (Raise, Call, Bet, Fold, Check, All-in)
    rather than a player name.
    """
    if not name:
        return False
    
    cleaned = name.strip().lower()
    button_words = {
        "raise", "call", "bet", "fold", "check",
        "all-in", "all in", "allin",
    }
    
    is_button = cleaned in button_words
    if is_button:
        logger.debug(f"[VISION] Detected button label: '{name}'")
    
    return is_button
```

**Applied Filtering:**

1. **In `_parse_players()` (parse_state.py):**
   - Checks OCR player names before assignment
   - If button label detected, keeps default `Player{N}` name instead

2. **In `create_vision_events_from_state()` (event_fusion.py):**
   - Checks player names before creating action events
   - Filters out events where player name is a button label
   - Applied in 3 locations:
     - Stack delta action inference
     - Fold event creation
     - Bet/raise/call event creation

## Testing

### Unit Tests

**tests/test_hero_cards_tracker_downgrade_fix.py:**
- `test_prevents_downgrade_from_2_to_1_card`: Core downgrade prevention test
- `test_prevents_downgrade_from_2_to_0_cards`: Handles None/empty detections
- `test_allows_upgrade_from_1_to_2_cards`: Ensures upgrades still work
- `test_allows_change_from_2_to_different_2_cards`: Handles new hands
- `test_reset_clears_confirmed_cards`: Verifies reset functionality
- `test_ignores_single_card_when_2_confirmed`: Tests exact bug scenario
- `test_logs_confirmed_hero_cards_message`: Verifies logging
- `test_logs_downgrade_prevention`: Verifies debug logging

**tests/test_button_label_filtering.py:**
- `test_detects_raise/call/bet/fold/check/all_in_variants`: Tests all button labels
- `test_rejects_real_player_names`: Ensures real names not filtered
- `test_rejects_empty_or_none`: Edge case handling
- `test_rejects_partial_matches`: Prevents false positives
- `test_button_label_not_used_as_player_name`: Integration test
- `test_real_player_names_still_work`: Ensures no regression

### Verification

**verify_fixes.py:**
Comprehensive demonstration script that:
1. Simulates the exact bug scenario from the logs
2. Shows downgrade prevention in action
3. Demonstrates button label filtering
4. Provides clear before/after comparison

**Results:**
```
✓ Fix 1: Hero cards tracker prevents downgrade from 2 to 1 card
✓ Fix 2: Button labels filtered out, not used as player names
```

## Expected Behavior After Fix

### Hero Cards Tracking

**Before Fix:**
```
[10:17:29] Hero cards (tracked): Qc, 3s    ← 2 cards confirmed
[10:17:34] Hero cards (tracked): Qc        ← Degraded to 1 card ✗
```

**After Fix:**
```
[10:17:29] Confirmed hero cards for current hand: Qc, 3s  ← 2 cards confirmed
[10:17:34] Hero cards (tracked): Qc, 3s                   ← Still 2 cards ✓
[10:17:34] [DEBUG] Ignoring downgrade from 2 confirmed cards to 1 card(s)
```

### Button Label Filtering

**Before Fix:**
```
Event: action - Player: Raise - ActionType.BET - Amount: 5752.0  ✗
Event: action - Player: Call - ActionType.CALL - Amount: 100.0   ✗
```

**After Fix:**
```
[VISION] Ignoring button label as player name at position 0: Raise
[VISION] Ignoring action event for button label: player=Call
Event: action - Player: guyeast - ActionType.BET - Amount: 5752.0  ✓
Event: action - Player: hilanderJojo - ActionType.CALL - Amount: 100.0  ✓
```

## Backwards Compatibility

- ✅ No changes to public API
- ✅ No changes to existing function signatures
- ✅ Real player names work exactly as before
- ✅ Hero cards cache mechanism unchanged
- ✅ Event fusion logic enhanced, not replaced
- ✅ All existing functionality preserved

## Files Changed

1. `src/holdem/vision/parse_state.py` (modified)
   - Added `is_button_label()` function
   - Enhanced `HeroCardsTracker.update()` logic
   - Updated `_parse_players()` to filter button labels

2. `src/holdem/vision/event_fusion.py` (modified)
   - Imported `is_button_label()` function
   - Added filtering in event creation logic

3. `tests/test_hero_cards_tracker_downgrade_fix.py` (new)
   - Comprehensive unit tests for downgrade prevention

4. `tests/test_button_label_filtering.py` (new)
   - Unit and integration tests for button label filtering

5. `verify_fixes.py` (new)
   - Demonstration and verification script

## Security Considerations

- No new dependencies added
- No external API calls introduced
- Filtering logic is defensive (whitelist approach)
- No security vulnerabilities introduced
- Input validation on all string comparisons
- Safe handling of None/empty values

## Performance Impact

- **Negligible:** Two additional checks per frame:
  1. Length check on confirmed cards (O(1))
  2. String comparison for button labels (O(1) dictionary lookup)
- No additional memory allocation required
- No additional I/O operations
- Logging is debug-level, minimal impact

## Maintenance Notes

### To Add New Button Labels

If new button labels appear in the UI, add them to the `button_words` set in `is_button_label()`:

```python
button_words = {
    "raise", "call", "bet", "fold", "check",
    "all-in", "all in", "allin",
    # Add new labels here:
    # "new_label",
}
```

### To Adjust Hero Cards Stability Threshold

Modify the `stability_threshold` parameter when creating `HeroCardsTracker`:

```python
self.hero_cards_tracker = HeroCardsTracker(stability_threshold=3)  # Default is 2
```

Higher values = more frames required for confirmation = more stable but slower to update
Lower values = fewer frames required = faster updates but less stable

## Integration Points

This fix integrates with:
- ✅ Vision state parsing (`StateParser`)
- ✅ Chat-enabled parsing (`ChatEnabledStateParser`)
- ✅ Event fusion system (`EventFuser`)
- ✅ OCR engine (no changes required)
- ✅ Card recognition (no changes required)
- ✅ Action detection (enhanced filtering)

## Validation Checklist

- [x] Hero cards never downgrade from 2 to 1 during same hand
- [x] Hero cards correctly reset between hands
- [x] Button labels filtered from player names
- [x] Real player names work normally
- [x] Event logging shows correct player names
- [x] No "Player: Raise" in action events
- [x] All unit tests pass
- [x] Verification script passes
- [x] No syntax errors
- [x] No new security vulnerabilities
- [x] Backwards compatible
- [x] Documentation complete

## Conclusion

These fixes address critical vision system bugs that were causing:
1. Incorrect hero card tracking (degradation from 2 to 1 card)
2. False action events with button labels as player names

The implementation is:
- ✅ Minimal and surgical
- ✅ Well-tested with comprehensive unit tests
- ✅ Backwards compatible
- ✅ Performance-neutral
- ✅ Security-conscious
- ✅ Well-documented

The expected improvements:
- ✅ More stable hero card recognition throughout hands
- ✅ Cleaner event logs with only real player names
- ✅ Better event fusion accuracy
- ✅ Improved AI decision-making based on correct hero cards
