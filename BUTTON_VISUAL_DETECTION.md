# Visual Button Detection

## Overview

This implementation adds visual detection of the dealer button on PokerStars tables using color-based analysis. It complements the existing logical detection (based on SB/BB blind events) with a visual fallback for cases where blind events are not available or ambiguous.

## Features

- **Ultra-fast detection**: ~1ms on 6-max tables (P99: 1.05ms, worst case: 0.6ms)
- **Hybrid approach**: Logical (SB/BB) detection first, visual as fallback
- **Backward compatible**: Works without `button_region` fields in table profiles
- **Configurable**: Multiple detection modes via `vision_performance.yaml`
- **Robust**: Frame stabilization prevents false positives

## How It Works

### Detection Algorithm

The `detect_button_by_color()` function analyzes small (16x16) color patches at each seat to detect the dealer button, which appears as a light gray circle (RGB: 180-220) with a dark "D" letter.

**Algorithm steps:**
1. Extract 16x16 patch at each seat's `button_region`
2. Convert to grayscale
3. Check maximum brightness (must be in 180-220 range)
4. Check variance (must be >100 to detect darker "D")
5. Sample bright pixels and verify color neutrality (R≈G≈B)
6. Return seat if exactly one candidate found

**Performance optimizations:**
- No template matching or OCR
- Minimal memory allocation
- Vectorized numpy operations
- Samples only 10 bright pixels (not all)
- Skips copy operations

### Hybrid Detection Strategy

In `chat_enabled_parser.py`, button detection follows this sequence:

```python
1. Try logical detection (SB/BB blind events)
   ↓ if fails
2. Try visual detection (color-based)
   ↓ if succeeds
3. Stabilize over 2+ frames
   ↓
4. Update button position
```

**Detection modes** (configured in `vision_performance.yaml`):
- `hybrid` (default): Logical first, visual fallback
- `logical_only`: Only use SB/BB logic
- `visual_only`: Only use visual detection
- `off`: Disable button detection

## Configuration

### Table Profile

Add `button_region` to each seat in your table profile JSON:

```json
{
  "player_regions": [
    {
      "position": 0,
      "name_region": {"x": 778, "y": 131, "width": 116, "height": 25},
      "button_region": {"x": 760, "y": 131, "width": 16, "height": 16}
    },
    ...
  ]
}
```

**Calibration tips:**
- Place region where dealer button appears when that seat has button
- Use 16x16 or 18x18 size (small regions are faster)
- Position should cover the gray circle with "D"

### Performance Config

In `configs/vision_performance.yaml`:

```yaml
vision_performance:
  vision_button_detection:
    mode: "hybrid"           # Detection strategy
    min_stable_frames: 2     # Frames needed to confirm detection
```

## Performance Characteristics

**Benchmark results** (6-max table, 1000 iterations):

| Metric | Normal Case | Worst Case (Ambiguous) |
|--------|-------------|------------------------|
| Mean   | 0.99 ms     | 0.54 ms               |
| Median | 0.99 ms     | 0.54 ms               |
| P95    | 1.01 ms     | 0.59 ms               |
| P99    | 1.06 ms     | 0.61 ms               |
| Max    | 1.77 ms     | 0.79 ms               |

**Impact on full parse:**
- Only runs on full parses (not light parses)
- Adds ~1ms to parse time when needed
- Negligible impact since it's only a fallback

## Testing

**Unit tests** (`tests/test_visual_button_detection.py`):
- 13 tests covering edge cases, boundaries, integration
- Tests for color matching, contrast detection, ambiguous cases
- All tests pass

**Run tests:**
```bash
pytest tests/test_visual_button_detection.py -v
```

**Performance benchmark:**
```bash
python /tmp/benchmark_visual_button.py
```

## Usage Example

```python
from holdem.vision.button_detector import detect_button_by_color
from holdem.vision.calibrate import TableProfile

# Load table profile with button_regions
profile = TableProfile.load("pokerstars_6max.json")

# Detect button in screenshot
button_seat = detect_button_by_color(screenshot, profile)

if button_seat is not None:
    print(f"Button detected at seat {button_seat}")
else:
    print("Button not detected (ambiguous or not visible)")
```

## Limitations

1. **Requires calibration**: `button_region` coordinates must be set per table
2. **Color-specific**: Tuned for PokerStars gray button (RGB: 180-220)
3. **Not frame-perfect**: Requires 2 frames for stability (prevents false positives)
4. **Single-candidate only**: Returns None if multiple seats match (ambiguous)

## Future Improvements

1. **Auto-calibration**: Detect button regions automatically
2. **Multi-site support**: Add color profiles for other poker sites
3. **ML-based detection**: Use small CNN for more robust detection
4. **Adaptive thresholds**: Learn ideal color ranges from samples

## Troubleshooting

**Button not detected:**
- Check `button_region` coordinates in table profile
- Verify button is actually visible on screen
- Check logs for debug messages (`[BUTTON VISUAL]`)
- Try `mode: "visual_only"` to isolate visual detection

**False positives:**
- Increase `min_stable_frames` (e.g., to 3)
- Verify color thresholds match your table theme
- Check for other UI elements in `button_region`

**Performance issues:**
- Visual detection only runs on full parses by design
- Reduce `button_region` size to 12x12 or 14x14
- Use `mode: "logical_only"` if visual not needed
