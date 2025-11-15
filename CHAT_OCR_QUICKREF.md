# Chat OCR Quick Reference

## Overview

The chat OCR system extracts game events from the poker table's chat/history box and fuses them with vision-based events for higher reliability.

## Configuration

### 1. Add chat_region to your table profile

```json
{
  "chat_region": {
    "x": 10,
    "y": 550,
    "width": 350,
    "height": 140
  }
}
```

**Finding coordinates:**
- `x, y`: Top-left corner of chat box
- `width, height`: Size of chat box
- Include multiple lines of chat text
- Avoid borders and UI elements

### 2. Enable chat parsing in run scripts

```bash
# Chat parsing is enabled by default
python -m holdem.cli.run_dry_run --profile my_profile.json --policy my_policy.pkl

# To disable chat parsing
python -m holdem.cli.run_dry_run --profile my_profile.json --policy my_policy.pkl --disable-chat-parsing
```

### 3. Configure performance settings

Edit `configs/vision_performance.yaml`:

```yaml
vision_performance:
  # Parse chat every N frames (0 = never, 1 = every frame, 3 = every 3rd frame)
  chat_parse_interval: 3
  
  # Enable caching for all vision regions
  enable_caching: true
```

## Expected Log Output

When chat OCR is working, you'll see logs like:

```
[CHAT OCR] Running OCR on chat region
[CHAT OCR] Raw text: 'Dealer: Player1 folds Dealer: Player2 calls 100'
[CHAT OCR] Extracted 2 chat lines
[CHAT OCR] Event created: type=action, player=Player1, action=FOLD, source=chat_ocr
[CHAT OCR] Event created: type=action, player=Player2, action=CALL, amount=100.0, source=chat_ocr
[CHAT OCR] Total events extracted: 2
```

Fused events show sources:

```
Event: action - Player: Hero - Action: RAISE - Amount: 50.0 - 
Confidence: 0.95 - Sources: vision_bet_region, chat_ocr [CONFIRMED]
```

## Performance Optimization

The system uses image hash caching to avoid redundant OCR:

```
[CHAT OCR] Chat region changed (new hash), running OCR on 350x140 region
[CHAT OCR] Chat region unchanged (hash match), reusing cached events
```

This ensures minimal performance impact.

## Troubleshooting

### No chat events in logs?

1. **Check configuration:**
   ```bash
   # Look for this log line
   [CHAT OCR] No chat_region configured in profile
   ```
   → Add `chat_region` to your table profile

2. **Check region bounds:**
   ```bash
   [CHAT OCR] Chat region (10,550,350,140) out of bounds
   ```
   → Verify coordinates are within screenshot dimensions

3. **Verify chat is enabled:**
   ```python
   parser = ChatEnabledStateParser(
       profile=profile,
       enable_chat_parsing=True  # ← Make sure this is True
   )
   ```

4. **Check OCR output:**
   ```bash
   [CHAT OCR] No text extracted from chat region
   ```
   → OCR may not be detecting text. Check chat visibility and quality.

### Chat OCR is slow?

1. **Increase chat_parse_interval:**
   ```yaml
   chat_parse_interval: 5  # Parse every 5th frame instead of every 3rd
   ```

2. **Reduce chat region size:**
   - Capture only the most recent chat lines
   - Typical height: 100-150 pixels (3-5 lines)

3. **Verify caching is working:**
   - Look for "hash match" messages in logs
   - If not seen, chat content may be changing every frame

### Events not fusing correctly?

1. **Check player names match:**
   - Vision and chat must use same player names
   - Enable debug logging to compare

2. **Check timing:**
   - Events must occur within time window (default: 5 seconds)
   - Adjust `time_window_seconds` in EventFuser if needed

3. **Look for [CONFIRMED] or [MULTI-SOURCE] tags:**
   - These indicate successful fusion
   - Single-source events have lower confidence

## Event Sources

| Source | Description |
|--------|-------------|
| `chat_ocr` | Event extracted from chat via OCR |
| `vision_bet_region` | Event detected from bet amount OCR |
| `vision_stack` | Event inferred from stack changes |
| `vision_pot` | Event detected from pot changes |
| `vision` | Generic vision-based event |

## Debug Logging

Enable detailed logging:

```python
import logging
logging.getLogger("vision.chat_parser").setLevel(logging.DEBUG)
logging.getLogger("vision.chat_enabled_parser").setLevel(logging.DEBUG)
```

This shows:
- OCR execution timing
- Raw text extraction
- Event creation details
- Cache hits/misses
- Image hash changes

## Performance Metrics

Typical chat OCR performance:
- **With caching:** <1ms per frame (cache hit)
- **Without caching:** 50-150ms per frame (OCR execution)
- **Cache hit rate:** 80-90% (depends on chat activity)

## See Also

- [CHAT_PARSING_GUIDE.md](CHAT_PARSING_GUIDE.md) - Complete guide
- [configs/vision_performance.yaml](configs/vision_performance.yaml) - Performance settings
- [configs/profiles/example_with_chat.json](configs/profiles/example_with_chat.json) - Sample configuration
