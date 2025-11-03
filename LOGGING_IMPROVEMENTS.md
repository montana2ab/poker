# Vision System Logging Improvements

## Problem Addressed

Users reported that while calibration worked via position and pot recognition worked after installing tesseract, there was no visibility into what cards (hands/board) were being detected. The system lacked feedback about:
- Whether card templates were loaded
- Which cards were detected on the board
- What player cards were recognized
- OCR success/failure for pot and stacks

## Solution

Enhanced logging throughout the vision pipeline to provide clear feedback about detection and recognition results.

## Changes Made

### 1. Enhanced Dry-Run Mode Output (`src/holdem/cli/run_dry_run.py`)

**Before:**
```
State: FLOP, Pot=125.50, Players=6
[DRY RUN] Would analyze and suggest action here
```

**After:**
```
============================================================
Street: FLOP
Pot: $125.50
Board: Ah Kd Qs (3 cards)
Players: 6 detected
  - Player1: $1000.00 (pos 0)
  - Player2: $1500.00 (pos 1)
  - Player3: $750.00 (pos 2)
  ...
============================================================
[DRY RUN] Would analyze and suggest action here
```

**Plus helpful error messages when parsing fails:**
```
Failed to parse state - check calibration and OCR
Troubleshooting tips:
  1. Verify table is visible and not obscured
  2. Check that tesseract is installed for OCR
  3. Ensure card templates exist in assets/templates
  4. Review calibration regions in profile JSON
```

### 2. State Parser Debugging (`src/holdem/vision/parse_state.py`)

Added debug logging for:
- **Board cards**: Shows detected cards or `??` for unrecognized
- **Pot OCR**: Logs successful detection or failure
- **Player information**: Logs stack, name, and card detection
- **Region bounds checking**: Warns if regions are out of bounds

Example debug output:
```
[DEBUG] Board cards detected: Ah Kd Qs ?? ??
[DEBUG] Pot detected: 125.5
[DEBUG] Player 0 stack detected: 1000.0
[DEBUG] Player 0 name detected: Hero
[DEBUG] Player 0 cards: Ac Ad
```

### 3. Card Recognition Feedback (`src/holdem/vision/cards.py`)

**Missing templates warning:**
```
[WARNING] Templates directory not found: assets/templates
[WARNING] Card recognition will not work without templates!
[WARNING] Run: python setup_assets.py to create card templates
```

**No templates found:**
```
[ERROR] No card templates found! Card recognition will fail.
[ERROR] Run: python setup_assets.py to create card templates
```

**Recognition process logging:**
```
[DEBUG] Attempting to recognize 5 cards from image of size (100, 350, 3)
[DEBUG] Card 0: Recognized Ah with confidence 0.923
[DEBUG] Card 1: Recognized Kd with confidence 0.887
[DEBUG] Card 3: No match found
```

### 4. OCR Engine Improvements (`src/holdem/vision/ocr.py`)

**Better initialization messages:**
```
[INFO] PaddleOCR initialized successfully
```

**Pytesseract availability check:**
```
[ERROR] Tesseract is not installed or not in PATH
[ERROR] Install tesseract: https://github.com/tesseract-ocr/tesseract
[ERROR]   - macOS: brew install tesseract
[ERROR]   - Ubuntu: sudo apt install tesseract-ocr
[ERROR]   - Windows: Download from GitHub releases
```

**Fallback handling:**
```
[WARNING] PaddleOCR not available, falling back to pytesseract
[WARNING] Install PaddleOCR with: pip install paddleocr
```

## Benefits

### For Debugging
1. **Immediate feedback** on what's working and what's not
2. **Clear error messages** with actionable solutions
3. **Step-by-step visibility** into the detection pipeline

### For Users
1. **Installation guidance** when dependencies are missing
2. **Troubleshooting tips** when detection fails
3. **Visual confirmation** of detected cards and game state

### For Development
1. **Easier debugging** of calibration issues
2. **Quick identification** of template or OCR problems
3. **Better understanding** of detection accuracy

## Usage

### Enable Debug Logging

To see detailed debug output, set the logging level when running:

```bash
# Enable debug logging (shows all card/OCR detection details)
export HOLDEM_LOG_LEVEL=DEBUG

# Run dry-run mode
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/my_profile.json \
  --policy runs/blueprint/avg_policy.json
```

### Example Output Flow

1. **Initialization:**
   - Card templates loaded (or warning if missing)
   - OCR backend initialized (or error if unavailable)

2. **Each observation cycle:**
   - Screenshot captured
   - Table detected (or warning if failed)
   - State parsed with detailed logging:
     - Board cards: Shows each card or `??`
     - Pot: Shows detected amount or failure
     - Players: Shows name, stack, and cards

3. **Final display:**
   - Formatted state summary
   - Action suggestion (in real mode)

## Troubleshooting Examples

### Missing Card Templates
```
[WARNING] Templates directory not found: assets/templates
[ERROR] No card templates found! Card recognition will fail.
```
**Solution:** Run `python setup_assets.py`

### Missing Tesseract
```
[ERROR] Tesseract is not installed or not in PATH
[ERROR]   - macOS: brew install tesseract
```
**Solution:** Install tesseract for your platform

### Cards Not Detected
```
[DEBUG] Board cards detected: ?? ?? ?? ?? ??
[DEBUG] Card 0: No match found
```
**Possible causes:**
- Template images don't match table card design
- Calibration regions incorrect
- Low image quality/lighting

### OCR Not Working
```
[DEBUG] Pot OCR failed - no number detected
```
**Possible causes:**
- OCR backend not installed
- Pot region incorrectly calibrated
- Text too small or obscured

## Related Files

- `src/holdem/cli/run_dry_run.py` - Enhanced state display
- `src/holdem/vision/parse_state.py` - Debug logging for parsing
- `src/holdem/vision/cards.py` - Card recognition feedback
- `src/holdem/vision/ocr.py` - OCR initialization messages
- `demo_logging.py` - Demonstration script

## Testing

Run the demonstration script to see examples of the logging:
```bash
python demo_logging.py
```

Or test with actual dry-run mode (requires profile and policy):
```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/pokerstars_nlhe_9max.json \
  --policy runs/blueprint/avg_policy.json \
  --interval 2.0
```
