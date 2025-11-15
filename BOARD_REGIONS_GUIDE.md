# Board Regions Configuration Guide

## Overview

The `board_regions` feature optimizes board card detection by dividing the board into 3 separate zones (flop, turn, river). This approach:

1. **Reduces parse time** - Only scans the necessary zone at each street
2. **Increases reliability** - Smaller zones are less prone to false detections
3. **Improves stability** - Once a zone is detected, it's locked and not re-scanned

## How It Works

### State Machine

The board detection uses a state machine with the following progression:

```
PREFLOP → FLOP → TURN → RIVER
  (skip)   (scan   (scan  (scan
           flop)   turn)  river)
```

- **PREFLOP**: Board scanning is completely skipped (no board cards exist)
- **FLOP**: Only the flop zone is scanned until 3 stable cards are detected
- **TURN**: Once flop is locked, only the turn zone is scanned
- **RIVER**: Once turn is locked, only the river zone is scanned

### Stability Frames

Each zone requires stability before being locked:
- Default: 2 consecutive frames with same cards
- Prevents false positives from temporary detection errors
- Once locked, the zone is never re-scanned for the current hand

### New Hand Detection

The board state automatically resets when a new hand is detected:
- Pot reset (drops from high value to blind level)
- Board reset (river cards disappear)
- PREFLOP state with empty board

## Configuration

### Basic Structure

Add `board_regions` to your table profile JSON:

```json
{
  "board_regions": {
    "flop": {
      "x": 350,
      "y": 270,
      "width": 150,
      "height": 60
    },
    "turn": {
      "x": 500,
      "y": 270,
      "width": 50,
      "height": 60
    },
    "river": {
      "x": 550,
      "y": 270,
      "width": 50,
      "height": 60
    }
  }
}
```

### Calibration Steps

1. **Take a screenshot** with all 5 board cards visible (river street)

2. **Open in image editor** (GIMP, Photoshop, Preview, etc.)

3. **Measure flop zone**:
   - Draw tight box around first 3 cards
   - Note x, y coordinates of top-left corner
   - Note width and height
   - Keep margins minimal (2-5 pixels)

4. **Measure turn zone**:
   - Draw tight box around 4th card only
   - Should NOT overlap with flop zone
   - Keep as small as possible

5. **Measure river zone**:
   - Draw tight box around 5th card only
   - Should NOT overlap with turn zone
   - Keep as small as possible

6. **Update config file** with measured coordinates

### Example Measurements

For a typical PokerStars table at 1920x1080:

```json
"board_regions": {
  "flop": {
    "x": 710,
    "y": 400,
    "width": 180,
    "height": 70
  },
  "turn": {
    "x": 895,
    "y": 400,
    "width": 65,
    "height": 70
  },
  "river": {
    "x": 965,
    "y": 400,
    "width": 65,
    "height": 70
  }
}
```

### Best Practices

✅ **DO**:
- Make zones as small as possible while fully containing cards
- Leave 2-5 pixel margins to account for variations
- Test with multiple screenshots to verify coverage
- Keep zones non-overlapping
- Measure with all cards visible (river)

❌ **DON'T**:
- Make zones too large (defeats the optimization)
- Overlap zones (causes duplicate detections)
- Include pot chips or other table elements
- Measure from screenshots without all cards

## Backward Compatibility

The `board_regions` feature is **completely optional**:

- If NOT configured: Falls back to legacy single-region detection using `card_regions[0]`
- All existing configs continue to work without modification
- You can add `board_regions` gradually to existing profiles

## Performance Impact

### Expected Improvements

With `board_regions` configured:

- **Parse time**: -20% to -40% reduction
- **Board scans per hand**: Reduced from ~100-200 to ~10-20
- **CPU usage**: Lower due to smaller scan areas
- **Reliability**: Improved due to zone isolation

### Metrics

Monitor these metrics to verify improvements:

```python
# In vision_metrics
- parse_latency_ms (P50, P95, P99)
- board_scan_count_per_hand
- zone_lock_times (flop, turn, river)
```

## Troubleshooting

### Cards not detected

**Problem**: Flop/turn/river cards not recognized

**Solutions**:
1. Verify zone coordinates cover the entire card
2. Add 2-5 pixels margin around cards
3. Check with debug images: `debug_board_flop_*.png`, etc.
4. Ensure templates match your poker client

### False detections

**Problem**: Cards detected when zone is empty

**Solutions**:
1. Make zones smaller
2. Ensure zones don't include pot chips or decorations
3. Increase stability_threshold in code if needed

### Zones locked too early

**Problem**: Wrong cards locked in zone

**Solutions**:
1. Increase stability threshold (default: 2 frames)
2. Check zone positioning
3. Verify templates are accurate

### Zones not locking

**Problem**: Cards detected but never locked

**Solutions**:
1. Check logs for stability frame counts
2. Verify all 3 flop cards detected (not 2 or 1)
3. Ensure turn/river detected as single card

## Implementation Details

### Code Structure

- `src/holdem/vision/vision_cache.py`: BoardCache state machine
- `src/holdem/vision/calibrate.py`: TableProfile with board_regions
- `src/holdem/vision/parse_state.py`: Zone-based detection logic

### State Machine Methods

```python
# Check state
board_cache.has_flop()      # True if flop locked
board_cache.has_turn()      # True if turn locked
board_cache.has_river()     # True if river locked

# Control scanning
board_cache.should_scan_flop()   # True if should scan flop
board_cache.should_scan_turn()   # True if should scan turn
board_cache.should_scan_river()  # True if should scan river

# Mark detection
board_cache.mark_flop([card1, card2, card3])
board_cache.mark_turn(card4)
board_cache.mark_river(card5)

# Reset for new hand
board_cache.reset_for_new_hand()
```

## See Also

- Example config: `configs/profiles/example_with_board_regions.json`
- Tests: `tests/test_board_state.py`
- Vision cache documentation: See `vision_cache.py` docstrings
