# Chat Parsing and Event Fusion Integration

## Overview

The vision features for chat parsing and event fusion have been integrated into both **dry run** and **auto play** modes. This enhancement allows the system to combine information from multiple sources (vision OCR and table chat) for more reliable game state tracking.

## What's New

### Features Integrated

1. **Chat Parsing** - Extracts game events from the poker client's chat/history box using OCR
2. **Event Fusion** - Combines events from vision and chat sources for higher accuracy
3. **Action Detection** - Already available, now works seamlessly with chat parsing
4. **Multi-Source Confirmation** - Events confirmed by both vision and chat have higher confidence

### Benefits

- ✅ **Higher Reliability** - Events confirmed by multiple sources are more trustworthy
- ✅ **Better Accuracy** - Precise chat data preferred over vision OCR for amounts
- ✅ **Source Traceability** - Know where each piece of information came from
- ✅ **Confidence Scoring** - Filter out unreliable single-source events

## How to Use

### Enable Chat Parsing (Recommended)

Chat parsing is **enabled by default** when a `chat_region` is configured in your table profile.

#### 1. Configure Table Profile

Add a `chat_region` to your table profile JSON:

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
  "player_regions": [...]
}
```

**Tips for finding the chat region:**
- Most poker clients have a chat/hand history box in the bottom-left or right
- The region should include the scrolling text area
- Capture multiple lines of text (height ~150-250px)
- Avoid including borders or player avatars

#### 2. Run Dry Run or Auto Play Normally

```bash
# Dry run mode with chat parsing
./bin/holdem-dry-run \
  --profile assets/table_profiles/pokerstars.json \
  --policy data/blueprint.pkl \
  --buckets data/buckets.pkl

# Auto play mode with chat parsing
./bin/holdem-autoplay \
  --profile assets/table_profiles/pokerstars.json \
  --policy data/blueprint.pkl \
  --buckets data/buckets.pkl \
  --i-understand-the-tos
```

### Disable Chat Parsing (Optional)

If you want to use only vision-based detection:

```bash
./bin/holdem-dry-run \
  --profile assets/table_profiles/pokerstars.json \
  --policy data/blueprint.pkl \
  --disable-chat-parsing
```

## Event Logging

When chat parsing is enabled, you'll see event logs like:

```
[INFO] Extracted 3 events from chat
[INFO] Fused 5 events, 4 reliable
[INFO] [EVENT] action: RAISE (sources: chat, vision, confidence: 0.95) [MULTI-SOURCE]
[INFO] [EVENT] street_change: FLOP (sources: chat, confidence: 0.70)
[INFO] [EVENT] pot_update: None (sources: vision, confidence: 0.70)
```

### Event Types

- **action** - Player action (fold, check, call, bet, raise, all-in)
- **street_change** - Street transition (flop, turn, river)
- **card_deal** - Hole cards dealt to player
- **showdown** - Player shows cards at showdown
- **pot_update** - Pot amount changed
- **pot_win** - Player wins pot

### Confidence Scores

- **0.90-0.95** - Multi-source confirmation (chat + vision)
- **0.70** - Single source (chat or vision only)
- **< 0.70** - Filtered out as unreliable

## Technical Details

### Architecture

```
Screenshot
    ├── Vision Parser → Vision Events
    └── Chat Parser → Chat Events
              ↓
        Event Fuser
              ↓
      Fused Events (with confidence)
```

### Components

- **ChatParser** (`holdem.vision.chat_parser`) - Parses game events from chat text
- **EventFuser** (`holdem.vision.event_fusion`) - Combines events from multiple sources
- **ChatEnabledStateParser** (`holdem.vision.chat_enabled_parser`) - Wrapper that integrates chat parsing with standard vision parsing

### Backward Compatibility

- If no `chat_region` is configured, the system works exactly as before (vision only)
- Use `--disable-chat-parsing` flag to explicitly disable chat parsing
- The standard `parse()` method is still available for compatibility

## Troubleshooting

### Chat parsing not working?

1. **Verify chat region** - Make sure `chat_region` is properly configured in your profile
2. **Check OCR quality** - Enable debug images to verify chat text is being read correctly
3. **Adjust confidence threshold** - Lower threshold if events are being filtered out

### Events not fusing correctly?

1. **Check time window** - Events must occur within 5 seconds to be matched
2. **Verify event types** - Only matching event types are fused together
3. **Review logs** - Look for source information and confidence scores

### Performance issues?

1. **Disable chat parsing** - Use `--disable-chat-parsing` if OCR is slow
2. **Optimize chat region** - Make chat region smaller to reduce OCR workload
3. **Use faster OCR backend** - Switch between paddleocr and pytesseract

## Testing

Run the integration test to verify everything is working:

```bash
python tests/test_vision_features_integration.py
```

Expected output:
```
✅ All integration tests passed!
  ✓ ChatEnabledStateParser properly defined
  ✓ Vision module exports ChatEnabledStateParser
  ✓ Chat parser and event fusion modules available
  ✓ Action detection available in parse_state
  ✓ run_dry_run.py integrated with chat parsing
  ✓ run_autoplay.py integrated with chat parsing
```

## Examples

See the example demo:
```bash
python examples/demo_chat_event_fusion.py
```

## Related Documentation

- `CHAT_PARSING_GUIDE.md` - Detailed guide on chat parsing and event fusion
- `IMPLEMENTATION_SUMMARY_CHAT_PARSING.md` - Implementation details
- `tests/test_chat_parsing.py` - Unit tests for chat parser
- `tests/test_action_detection.py` - Tests for action detection

## Next Steps

1. Configure `chat_region` in your table profiles
2. Test chat parsing with your poker client
3. Verify OCR quality on chat text
4. Monitor event fusion in logs
5. Adjust confidence threshold as needed
