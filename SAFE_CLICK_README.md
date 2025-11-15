# Safe Click Feature - Documentation

## Overview

The Safe Click feature prevents the auto-play bot from accidentally clicking on checkboxes ("Call 100"/"Call Any") when action buttons are not yet visible on screen.

## Problem

In auto-play mode, the bot sometimes attempts to click action buttons (Fold, Call, Pot, etc.) before they are fully rendered. At that moment, checkbox UI elements ("Call 100" / "Call Any") may still be visible at the same screen location, causing the bot to accidentally check these options instead of executing the intended action.

## Solution

A lightweight visual verification system that:
1. Captures a small screen region around each button before clicking (~40x20 pixels)
2. Analyzes key pixels to detect whether a checkbox or action button is present
3. Only performs the click if a valid action button is detected
4. Skips the click if checkboxes or dark background (unrendered UI) is detected

## Implementation

### Core Module: `src/holdem/control/safe_click.py`

**Main Function:**
```python
def safe_click_action_button(
    x: int, 
    y: int, 
    width: int, 
    height: int, 
    label: Optional[str] = None,
    click_delay: float = 0.1
) -> bool
```

**Returns:**
- `True` if the click was performed successfully
- `False` if the UI is not ready or checkbox was detected

### Detection Algorithm

The algorithm analyzes pixel luminance values to distinguish between UI states:

1. **Checkbox Detection**:
   - Checks pixel at left side (where checkbox square appears)
   - Dark pixel (luminance < 0.3) indicates checkbox presence

2. **Button Detection**:
   - Checks average luminance in center region
   - Light background (luminance > 0.5) indicates valid button

3. **Decision Logic**:
   - ✅ Light center → Valid button → Click
   - ❌ Dark checkbox + Non-light center → Checkbox UI → Skip
   - ❌ Non-light center → Button not rendered → Skip

### Integration

The safe click is integrated into `ActionExecutor` for all action button clicks:

- **Simple Actions**: Fold, Call, Check, All-in
- **Complex Actions**: Bet, Raise (with amount input)
- **Quick Bet Actions**: Bet Half Pot, Bet Pot

### Configuration

Enable or disable via `ControlConfig`:

```python
config = ControlConfig(
    dry_run=False,
    confirm_every_action=False,
    i_understand_the_tos=True,
    safe_click_enabled=True  # Default: True
)
```

## Performance

- **Overhead**: < 10ms per click verification
- **Memory**: Minimal (~5KB for small screen capture)
- **CPU**: Simple pixel analysis, no heavy computation
- **Impact**: Negligible on overall auto-play performance

## Usage

### In Auto-Play Mode

Safe click is automatically enabled by default. No code changes needed:

```python
from holdem.control.executor import ActionExecutor

# Safe click is enabled by default
executor = ActionExecutor(config, profile)

# All action button clicks are now protected
executor.execute(action, state)
```

### Disabling Safe Click

If needed, you can disable it (not recommended):

```python
config = ControlConfig(
    dry_run=False,
    confirm_every_action=False,
    i_understand_the_tos=True,
    safe_click_enabled=False  # Disable safe click
)
```

## Logging

The feature logs at two levels:

### DEBUG Level (Detailed)
```
[SAFE_CLICK] Pixel analysis: checkbox_lum=0.12, center_lum=0.45, avg_center_lum=0.48
[SAFE_CLICK] Checkbox UI detected at action button location
[SAFE_CLICK] Skip click: Call - UI not ready or checkbox detected
```

### INFO Level (Summary)
```
[AUTOPLAY] Skip action click, UI not ready or checkbox detected (action=Call)
```

## Testing

### Unit Tests

Located in `tests/test_safe_click.py`:
- 20 tests covering pixel analysis, safe click function, and integration scenarios
- All edge cases tested (valid button, checkbox, dark background, failures)

### Integration Tests

Located in `tests/test_executor_safe_click_integration.py`:
- 13 tests covering executor integration
- Tests for enabled/disabled modes
- Tests for all action types

### Running Tests

```bash
# Run safe click tests only
pytest tests/test_safe_click.py tests/test_executor_safe_click_integration.py -v

# Run all executor tests (including legacy)
pytest tests/test_executor_autoplay.py -v
```

## Troubleshooting

### Issue: Click always skipped

**Symptoms**: All action clicks are being skipped

**Possible Causes**:
1. Screen capture failing (check display/permissions)
2. Button luminance threshold too strict
3. Screen region coordinates incorrect

**Solutions**:
1. Check logs for capture errors
2. Adjust thresholds in `safe_click.py` if needed
3. Verify button region configuration in profile

### Issue: Checkbox still clicked

**Symptoms**: Bot still clicks checkboxes occasionally

**Possible Causes**:
1. Safe click disabled in configuration
2. Detection thresholds need tuning
3. UI rendering timing issue

**Solutions**:
1. Verify `safe_click_enabled=True`
2. Check DEBUG logs for pixel values
3. Adjust detection thresholds if needed

### Issue: Performance degradation

**Symptoms**: Auto-play is slower

**Possible Causes**:
1. Screen capture taking too long
2. Running on very slow hardware

**Solutions**:
1. Check system resources
2. Disable safe click if absolutely necessary
3. Optimize screen capture settings

## Best Practices

1. **Always Use Safe Click**: Keep it enabled by default
2. **Monitor Logs**: Check for skip messages in DEBUG mode
3. **Tune Thresholds**: Adjust if false positives/negatives occur
4. **Test Thoroughly**: Verify behavior in your environment
5. **Report Issues**: Document any edge cases encountered

## Future Improvements

Possible enhancements:
- Adaptive thresholds based on screen brightness
- Machine learning-based button detection
- Configurable detection parameters per profile
- Visual feedback in debug mode

## License

This feature is part of the holdem-mccfr project and follows the same MIT license.
