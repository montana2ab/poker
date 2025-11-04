# Card Recognition Fix - Summary of Changes

## Problem Identified

The issue reported was that hero cards (player's hole cards) were not being recognized correctly, or were being confused with board cards. The root cause was that **board cards and hero cards have different visual characteristics** in the poker client:

- Different sizes
- Different lighting/backgrounds
- Different rendering styles
- Different viewing angles

Using the same templates for both led to poor recognition accuracy, especially during preflop when only hero cards are visible.

## Solution Implemented

Created **separate template support** for board cards and hero cards, allowing the system to use optimized templates for each card type.

## Files Changed

### Core Vision System

1. **`src/holdem/vision/cards.py`**
   - Added `hero_templates_dir` parameter to `CardRecognizer.__init__()`
   - Added `hero_templates` dictionary to store hero card templates
   - Added `_load_hero_templates()` method
   - Added `use_hero_templates` parameter to `recognize_card()` and `recognize_cards()`
   - Updated `_recognize_template()` to select correct template set
   - Updated `create_mock_templates()` to support `for_hero` parameter
   - Added automatic fallback to board templates when hero templates unavailable

2. **`src/holdem/vision/parse_state.py`**
   - Updated `_parse_player_cards()` to use `use_hero_templates=True`
   - Hero cards now automatically use hero templates when available

3. **`src/holdem/vision/calibrate.py`**
   - Added `hero_templates_dir` field to `TableProfile`
   - Updated `save()` to persist `hero_templates_dir`
   - Updated `load()` to restore `hero_templates_dir`

### CLI Tools

4. **`src/holdem/cli/run_dry_run.py`**
   - Updated to load hero templates from profile if configured
   - Automatically passes hero templates to `CardRecognizer`

5. **`src/holdem/cli/run_autoplay.py`**
   - Updated to load hero templates from profile if configured
   - Automatically passes hero templates to `CardRecognizer`

### Tests

6. **`tests/test_hero_card_detection.py`**
   - Added `test_card_recognizer_with_hero_templates()`
   - Added `test_card_recognizer_fallback_to_board_templates()`
   - Added `test_state_parser_with_separate_hero_templates()`
   - Updated `test_table_profile_hero_position_save_load()` to test hero_templates_dir

### Documentation & Examples

7. **`assets/templates/README.md`** - Updated with:
   - Explanation of separate templates
   - Why separate templates improve accuracy
   - Instructions for creating both template sets

8. **`assets/hero_templates/README.md`** - New file with:
   - Explanation of hero card templates
   - Visual differences between hero and board cards
   - Step-by-step guide for creating hero templates

9. **`GUIDE_CORRECTION_CARTES.md`** - New French guide with:
   - Problem explanation
   - Solution overview
   - Step-by-step usage instructions
   - Configuration examples
   - Technical details

10. **`example_hero_templates.py`** - New example script with:
    - 5 comprehensive examples
    - Template creation demo
    - Configuration demo
    - Usage patterns
    - Production deployment guide

## Key Features

### 1. Backward Compatible
- Works with or without hero templates
- Falls back to board templates if hero templates not available
- Existing code continues to work unchanged

### 2. Automatic Template Selection
```python
# StateParser automatically uses correct templates
state_parser.parse(screenshot)
# → Board cards use board templates
# → Hero cards use hero templates (if available)
```

### 3. Flexible Configuration
```json
{
  "hero_position": 0,
  "hero_templates_dir": "assets/hero_templates"
}
```

### 4. Easy Template Creation
```python
# Create board templates
create_mock_templates(Path("assets/templates"), for_hero=False)

# Create hero templates  
create_mock_templates(Path("assets/hero_templates"), for_hero=True)
```

## Usage

### Basic Usage (Backward Compatible)
```python
# Works as before - uses only board templates
recognizer = CardRecognizer(Path("assets/templates"))
```

### Enhanced Usage (With Hero Templates)
```python
# Uses both template sets
recognizer = CardRecognizer(
    templates_dir=Path("assets/templates"),
    hero_templates_dir=Path("assets/hero_templates")
)

# Recognize board card
board_card = recognizer.recognize_card(img, use_hero_templates=False)

# Recognize hero card
hero_card = recognizer.recognize_card(img, use_hero_templates=True)
```

### In Table Profile
```json
{
  "window_title": "PokerStars",
  "hero_position": 0,
  "hero_templates_dir": "assets/hero_templates",
  "player_regions": [...],
  "card_regions": [...]
}
```

## Benefits

1. **Better Accuracy**: Each template set optimized for its card type
2. **Preflop Detection**: Improved hero card detection during preflop
3. **Flexible**: Works with or without hero templates
4. **Automatic**: StateParser uses correct templates automatically
5. **Easy Setup**: Clear documentation and examples

## Migration Guide

### For Existing Users

1. **No changes required** - code continues to work as before
2. **Optional enhancement**:
   - Create hero card templates from screenshots
   - Add to `assets/hero_templates/`
   - Set `hero_templates_dir` in table profile
   - Enjoy improved accuracy!

### For New Users

1. Follow `GUIDE_CORRECTION_CARTES.md` (French)
2. Or run `python example_hero_templates.py` (English)
3. Create templates from real poker screenshots
4. Configure table profile
5. Start playing with better card recognition

## Testing

All changes are covered by comprehensive tests:
- Template loading and fallback
- Card recognition with both template sets
- Profile save/load with hero_templates_dir
- StateParser integration

Run tests:
```bash
pytest tests/test_hero_card_detection.py -v
```

## Next Steps

1. **Create Real Templates**: Replace mock templates with real card images
2. **Configure Profile**: Set `hero_position` and `hero_templates_dir`
3. **Test Recognition**: Verify improved accuracy
4. **Adjust as Needed**: Fine-tune templates based on results

## Statistics

- **10 files changed**
- **684 insertions**
- **30 deletions**
- **Net: +654 lines**
- **100% backward compatible**
- **Comprehensive test coverage**

## Support

- See `GUIDE_CORRECTION_CARTES.md` for French documentation
- Run `python example_hero_templates.py` for examples
- Check `assets/templates/README.md` and `assets/hero_templates/README.md`
- Review test cases in `tests/test_hero_card_detection.py`
