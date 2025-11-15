# Chat OCR Focus Mode

This document describes the chat OCR focus mode, a special debug mode for calibrating and testing the chat OCR system.

## Overview

The chat OCR focus mode (`--chat-ocr-focus`) is a lightweight debug mode that processes only the chat region of poker table screenshots. It skips all other vision components (pot, stacks, bets, board cards, hero cards) to provide fast cycle times for chat OCR calibration and testing.

## Purpose

This mode is designed for:
- **Calibrating chat OCR**: Fine-tune OCR settings and preprocessing
- **Testing chat parsing**: Verify event extraction from chat lines
- **Debugging chat issues**: Identify problems with chat region detection or OCR accuracy
- **Measuring performance**: Profile chat OCR latency without full vision overhead

**Note:** This is a debug/calibration mode only - not for production gameplay.

## Usage

### Basic Usage

```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/your_profile.json \
  --policy assets/policies/dummy.bin \
  --chat-ocr-focus
```

### With Detailed Logging

```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/your_profile.json \
  --policy assets/policies/dummy.bin \
  --chat-ocr-focus \
  --enable-detailed-vision-logs
```

This creates a JSONL log file at `logs/chat_ocr_focus/chat_ocr_focus_YYYYMMDD_HHMMSS.jsonl`.

### With Custom OCR Backend

```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/your_profile.json \
  --policy assets/policies/dummy.bin \
  --chat-ocr-focus \
  --ocr-backend easyocr
```

Supported backends: `paddleocr` (default), `easyocr`, `pytesseract`

## Requirements

1. **Profile with chat_region**: Your table profile JSON must define a `chat_region`:
   ```json
   {
     "chat_region": {
       "x": 5,
       "y": 562,
       "width": 399,
       "height": 72
     }
   }
   ```

2. **Dummy policy/buckets**: The mode skips policy loading but still requires the arguments. You can use any existing policy file.

## What It Does

When `--chat-ocr-focus` is enabled:

1. ✅ Loads table profile
2. ✅ Creates minimal vision components (screen capture, table detector, OCR engine)
3. ❌ **SKIPS** policy loading (fast startup)
4. ❌ **SKIPS** bucket loading
5. ❌ **SKIPS** card recognizer setup
6. ❌ **SKIPS** full state parser setup

### Processing Loop

For each cycle:

1. **Screenshot** - Capture table image
2. **Table Detection** - Warp/align table if needed
3. **Chat Crop** - Extract chat region from table image
4. **Preprocessing** - Convert to grayscale + enhance contrast (alpha=1.2, beta=10)
5. **OCR** - Run OCR on preprocessed chat image
6. **Parse** - Extract events from chat lines (actions, board updates, etc.)
7. **Log** - Display detailed timing and results

## Logged Information

### Console Output

Each cycle logs:
- Detailed timing for each step (ms)
- Raw OCR text (all lines detected)
- Extracted events with details:
  - Event type
  - Player name
  - Action type
  - Amount
  - Confidence

Example:
```
[CHAT OCR FOCUS] ===== Cycle 1 =====
[CHAT OCR FOCUS] Screenshot latency: 12.34 ms
[CHAT OCR FOCUS] Chat crop latency: 0.45 ms
[CHAT OCR FOCUS] Preprocess latency: 1.23 ms
[CHAT OCR FOCUS] OCR latency: 45.67 ms
[CHAT OCR FOCUS] Chat parse latency: 2.34 ms
[CHAT OCR FOCUS] Total chat cycle latency: 62.03 ms

[CHAT OCR FOCUS] Raw chat text (2 lines):
[CHAT OCR FOCUS]   Line 1: Dealer: Player1 bets 850
[CHAT OCR FOCUS]   Line 2: Dealer: Player2 calls 850

[CHAT OCR FOCUS] Extracted 2 event(s):
[CHAT OCR FOCUS] Event from chat: type=action, player=Player1, action=ActionType.BET, amount=850.0, confidence=1.00
[CHAT OCR FOCUS] Event from chat: type=action, player=Player2, action=ActionType.CALL, amount=850.0, confidence=1.00
```

### JSONL Log File

When `--enable-detailed-vision-logs` is used, structured JSON records are written to a log file:

```jsonl
{"timestamp": "2025-11-15T19:01:23.456", "cycle": 1, "latencies_ms": {"screenshot": 12.34, "crop": 0.45, "preprocess": 1.23, "ocr": 45.67, "parse": 2.34, "total": 62.03}, "chat_lines": ["Dealer: Player1 bets 850", "Dealer: Player2 calls 850"], "events": [{"type": "action", "player": "Player1", "action": "BET", "amount": 850.0, "confidence": 1.0}, {"type": "action", "player": "Player2", "action": "CALL", "amount": 850.0, "confidence": 1.0}]}
```

## Performance

Typical latencies in chat OCR focus mode:
- **Screenshot**: 10-20 ms
- **Chat crop**: <1 ms
- **Preprocessing**: 1-3 ms
- **OCR**: 30-100 ms (depends on backend and chat region size)
- **Parse**: 1-5 ms
- **Total cycle**: 50-150 ms

Compare to full vision mode: ~2000 ms (20x slower)

## Troubleshooting

### "No chat_region defined in profile"

Add a `chat_region` to your table profile JSON. Use the profile wizard or manually define the region coordinates.

### "Chat region out of bounds"

The chat_region coordinates are invalid for the captured image. Check:
- Screen region is correct
- Chat region coordinates are within screen region bounds
- Table detection/warping is working correctly

### OCR returns no text

Possible causes:
- Chat region is blank or outside visible area
- OCR backend not properly installed
- Chat text color/contrast too low
- Chat region too small

Try:
- Verify chat_region visually in a screenshot
- Test different OCR backends (`--ocr-backend`)
- Adjust preprocessing (modify alpha/beta in code if needed)

### Events not extracted

Possible causes:
- Chat format doesn't match expected patterns
- OCR text has errors that prevent parsing
- Chat parser patterns need adjustment

Check:
- Raw OCR text output
- Chat parser regex patterns in `holdem/vision/chat_parser.py`

## Implementation Details

### Image Preprocessing

Chat images are preprocessed to improve OCR accuracy:
1. Convert to grayscale (if not already)
2. Apply contrast enhancement: `cv2.convertScaleAbs(img, alpha=1.2, beta=10)`
   - `alpha=1.2`: Increase contrast by 20%
   - `beta=10`: Increase brightness by 10

### OCR Backends

Three backends are supported:
- **PaddleOCR** (default): Best accuracy, slower
- **EasyOCR**: Good balance of speed and accuracy
- **Pytesseract**: Fastest, lower accuracy

### Event Parsing

Chat lines are parsed into game events:
- **Actions**: fold, check, call, bet, raise, all-in
- **Board updates**: flop, turn, river card deals
- **Pot updates**: pot size changes
- **Showdown**: player card reveals

See `holdem/vision/chat_parser.py` for pattern definitions.

## See Also

- `holdem/vision/chat_parser.py` - Chat line parsing logic
- `holdem/vision/chat_enabled_parser.py` - Integration with vision system
- `tests/test_chat_ocr_focus_mode.py` - Test suite

## Future Enhancements

Possible improvements:
- Real-time visualization of chat region
- A/B testing of preprocessing parameters
- OCR backend performance comparison
- Chat pattern training/tuning mode
- Export chat OCR accuracy metrics
