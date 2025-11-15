# Vision Performance Optimization Guide

This guide explains the optimizations implemented to reduce vision parse latency from ~2-4s to <1s.

## Overview

The vision system performs several expensive operations on every frame:
- Homography transformation (perspective correction)
- Board card recognition (5 cards with template matching)
- Hero card recognition (2 cards with template matching)
- OCR for pot, stacks, bets, names

These optimizations reduce redundant work while maintaining accuracy.

## Optimization 1: Disable Homography

**What it does**: Skip expensive perspective correction when table position is fixed.

**When to use**: 
- When using a fixed poker client window that doesn't move
- When table layout is consistent
- When regions are calibrated to raw screenshot coordinates

**How to enable**:
```yaml
# configs/vision_performance.yaml
vision_performance:
  detect_table:
    enable_homography: false
    health_check_window: 20  # Warn after N invalid parses
```

**Performance impact**: Saves ~200-500ms per frame

**Safety**: Health check warns if no valid data detected for N consecutive frames

## Optimization 2: Skip Board Parsing in PREFLOP

**What it does**: Skips board card recognition when street is PREFLOP (board is always empty).

**When it works**: Automatically detects PREFLOP based on board cache or empty board.

**How it works**:
- Checks cached street from previous frame
- If PREFLOP, skips expensive 5-card template matching
- Board is set to empty array []

**Performance impact**: Saves ~500-800ms per PREFLOP frame

**Safety**: Board parsing resumes automatically on FLOP/TURN/RIVER

## Optimization 3: Freeze Hero Cards When Stable

**What it does**: Once hero cards are recognized and stable, reuses them without re-recognition.

**How it works**:
- HeroCache tracks card stability across frames
- After N consistent frames (default: 2), marks cards as stable
- Stable cards are reused directly without template matching
- Cache resets on new hand detection (PREFLOP + small pot)

**Performance impact**: Saves ~200-400ms per frame after cards stabilize

**Safety**: 
- Requires multiple frames to stabilize (prevents false positives)
- Resets automatically on new hands
- Falls back to recognition if cache is invalid

## Optimization 4: Fixed Hero Position

**What it does**: Skip hero position detection when position is known and fixed.

**When to use**:
- When always sitting in the same seat
- For single-table play
- When seat doesn't change between sessions

**How to enable**:
```bash
# CLI argument
python run_dry_run.py --hero-position 2 ...
python run_autoplay.py --hero-position 2 ...
```

**Performance impact**: Saves ~50-100ms per frame

**Safety**: Falls back to auto-detection if not specified

## Configuration

All optimizations are controlled via `configs/vision_performance.yaml`:

```yaml
vision_performance:
  # Enable/disable optimizations
  enable_caching: true
  enable_light_parse: true
  
  # Homography settings
  detect_table:
    enable_homography: true  # Set to false to skip perspective correction
    health_check_window: 20  # Number of frames to check before warning
  
  # Board cache
  board_cache:
    enabled: true
    stability_threshold: 2  # Frames needed to stabilize
  
  # Hero cache
  hero_cache:
    enabled: true
    stability_threshold: 2  # Frames needed to stabilize
```

## Expected Performance Improvements

### Before Optimizations
- Mean Parse Latency: ~2176ms
- P95 Parse Latency: ~3844ms
- P99 Parse Latency: ~4024ms

### After Optimizations (Expected)
- Mean Parse Latency: ~600-800ms (60-65% reduction)
- P95 Parse Latency: ~1200-1500ms (60-65% reduction)
- P99 Parse Latency: ~1500-2000ms (50-60% reduction)

**Note**: Actual improvements depend on:
- Table layout complexity
- OCR backend speed
- Hardware performance
- Game phase (PREFLOP benefits most)

## Monitoring

Use VisionMetrics to track parse latency:

```bash
# Enable metrics
python run_dry_run.py --enable-vision-metrics --metrics-report-interval 60 ...

# Check metrics output
# Metrics are logged every 60 seconds and at shutdown
```

## Troubleshooting

### High latency with homography disabled

**Symptom**: Parse latency doesn't improve after disabling homography

**Solutions**:
1. Check that regions are calibrated to raw screenshot coordinates
2. Verify table window doesn't move
3. Check health warnings in logs

### Invalid game state

**Symptom**: Bot makes incorrect decisions, state looks wrong

**Solutions**:
1. Re-enable homography if table moves
2. Recalibrate regions
3. Check vision metrics for card recognition confidence

### Hero cards not recognized

**Symptom**: Hero cards are None or incorrect

**Solutions**:
1. Check hero card templates
2. Verify card region calibration
3. Check cache stability threshold (may need to increase)
4. Look for "New hand detected" messages in logs

### Board cards wrong on FLOP

**Symptom**: Board has incorrect cards after transition from PREFLOP

**Solutions**:
1. Check board cache stability
2. Verify card templates
3. Check board region calibration
4. Board recognition should resume automatically on FLOP

## Backward Compatibility

All optimizations are **opt-in** and backward compatible:

- Default config enables all safety features
- Homography is enabled by default
- Hero position auto-detection works as before
- Existing configs continue to work

## Testing

Run tests to verify optimizations:

```bash
# Run optimization tests
pytest tests/test_vision_parse_optimization.py -v

# Run cache tests
pytest tests/test_vision_performance_cache.py -v

# Run all vision tests
pytest tests/test_vision*.py -v
```

## Best Practices

1. **Start conservative**: Use default settings first
2. **Monitor metrics**: Track parse latency and card recognition accuracy
3. **Disable homography last**: Only after confirming table doesn't move
4. **Use fixed hero position**: When possible for best performance
5. **Calibrate carefully**: Ensure regions are accurate before optimizing
6. **Test thoroughly**: Verify bot behavior in dry-run mode first
