# Fix Summary: Spectator Mode Board Card Detection

## Problem
The user reported that spectator mode (dry-run) was not detecting the flop/board cards. The state was always showing `PREFLOP` even when community cards were visible on the poker table.

## Root Cause
The card recognition system was failing silently - when cards couldn't be recognized from the screenshot, it would return `None` values which were then filtered out, resulting in an empty board and the state being interpreted as `PREFLOP`.

The issue could be caused by several factors:
- Incorrect card region coordinates in the table profile
- Card templates not matching the actual cards on screen
- Poor image quality or visibility in the captured region

## Solution

### 1. Enhanced Debug Logging
Added detailed logging throughout the card recognition pipeline to help diagnose issues:

**In `parse_state.py`:**
- Logs the extraction region coordinates
- Logs the number of cards recognized with their names
- Logs warnings when no cards are detected

**In `cards.py`:**
- Logs which card position is being recognized
- Shows the best match score even when below threshold
- Indicates which template set (board vs hero) is being used

### 2. Debug Image Saving
Added a new `--debug-images` command-line flag that saves extracted card regions to disk for inspection.

**Usage:**
```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/pokerstars_messalina_9max.json \
  --policy runs/blueprint/avg_policy.json \
  --debug-images /tmp/debug_cards
```

This creates numbered image files (`board_region_0001.png`, `board_region_0002.png`, etc.) showing exactly what the system is trying to recognize.

**Benefits:**
- Users can verify that card regions are correctly positioned
- Visual inspection of extracted images helps identify quality issues
- Easy to compare extracted regions with templates

### 3. Error Handling
Added proper error handling for file I/O operations:
- cv2.imwrite now checks for success/failure
- Errors are logged as warnings instead of crashing silently

### 4. Documentation
Updated both English and French documentation:

**README.md:**
- Added troubleshooting section for board card detection
- Documented the `--debug-images` flag with usage examples

**GUIDE_AUTO_CAPTURE.md:**
- Added specific troubleshooting section for spectator mode
- Provided step-by-step debugging workflow
- Explained how to verify templates and coordinates

## How Users Can Fix Their Issue

### Step 1: Enable Debug Mode
Run dry-run with debug images enabled:

```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/pokerstars_messalina_9max.json \
  --policy runs/blueprint/avg_policy.json \
  --debug-images /tmp/debug_cards
```

### Step 2: Check the Logs
Look for these log messages:
- `Recognized X board card(s): ...` - Shows successfully recognized cards
- `No board cards recognized` - Indicates recognition failure
- `No board card match above threshold` - Shows best match score

### Step 3: Inspect Debug Images
Open the saved images in `/tmp/debug_cards/` and verify:
- Are the cards visible in the extracted region?
- Are they clear and not blurry?
- Do they match the templates in `assets/templates/`?

### Step 4: Fix Common Issues

**If the region is wrong:**
- Use the profile wizard to recalibrate: `python -m holdem.cli.profile_wizard`
- Manually adjust `card_regions` coordinates in the profile JSON

**If templates don't match:**
- Re-capture templates using: `python capture_templates.py`
- Organize and identify them: `python organize_captured_templates.py`

**If cards are blurry or not visible:**
- Ensure the poker client is not minimized
- Check for overlapping windows
- Verify screen resolution matches profile settings
- Wait for animations to complete before capturing

## Changes Made

### Modified Files
1. **src/holdem/vision/parse_state.py**
   - Added `debug_dir` parameter to `StateParser.__init__`
   - Added debug image saving in `_parse_board`
   - Enhanced logging for card recognition results
   - Added error handling for file I/O

2. **src/holdem/vision/cards.py**
   - Added detailed logging in `recognize_cards`
   - Improved logging in `_recognize_template`
   - Shows best match even when below threshold

3. **src/holdem/cli/run_dry_run.py**
   - Added `--debug-images` command-line argument
   - Passes debug directory to `StateParser`
   - Creates debug directory if specified

4. **README.md**
   - Added troubleshooting section for dry-run mode
   - Documented `--debug-images` flag with examples

5. **GUIDE_AUTO_CAPTURE.md**
   - Added specific troubleshooting for spectator mode flop detection
   - Added step-by-step debugging workflow

### New Files
1. **tests/test_debug_images.py**
   - Tests that debug images are saved when enabled
   - Tests that no images are saved when disabled
   - Tests sequential numbering of debug images

## Security Summary
No security vulnerabilities were introduced or found by CodeQL analysis.

## Testing
- All existing tests pass
- New tests verify debug image saving functionality
- Manual syntax validation completed

## User Impact
- **Positive:** Users can now diagnose card recognition issues themselves
- **Minimal:** No breaking changes to existing functionality
- **Improved:** Better observability and troubleshooting capabilities
