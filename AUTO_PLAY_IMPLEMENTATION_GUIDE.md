# AUTO-PLAY Implementation Guide

## Overview

The auto-play mode has been fully implemented to enable automatic mouse control without user confirmation prompts. The bot will now automatically click buttons on the poker table based on the AI's decisions.

## Changes Implemented

### 1. Executor Changes (`src/holdem/control/executor.py`)

- **No confirmation prompts**: When `confirm_every_action=False` (default in auto-play), the executor skips `input()` prompts and proceeds directly to clicking
- **Auto-play logging**: All actions now log with `[AUTO-PLAY]` prefix for easy debugging
- **Enhanced bet/raise**: Supports precise bet amount input via `bet_input_box` region
- **Screen position logging**: All mouse clicks log the exact (x, y) coordinates

### 2. CLI Changes (`src/holdem/cli/run_autoplay.py`)

- **Default behavior**: `--confirm-every-action` now defaults to `False` (auto-play mode)
- **Manual override**: Pass `--confirm-every-action` flag to enable manual confirmation mode

## Usage

### Basic Auto-Play (No Confirmation)

```bash
python -m holdem.cli.run_autoplay \
    --profile assets/table_profiles/pokerstars.json \
    --policy assets/policies/blueprint.pkl \
    --i-understand-the-tos
```

This will:
1. Ask for initial confirmation ("Continue? (yes/no): ")
2. Start auto-play mode
3. Automatically click buttons without asking "(y/n)" for each action

### Manual Confirmation Mode

If you want to confirm each action manually:

```bash
python -m holdem.cli.run_autoplay \
    --profile assets/table_profiles/pokerstars.json \
    --policy assets/policies/blueprint.pkl \
    --confirm-every-action \
    --i-understand-the-tos
```

This will ask "Execute X? (y/n):" before each action.

## Log Output Examples

### Auto-Play Mode (Default)

```
[REAL-TIME SEARCH] Action decided: CHECK_CALL (in 111.2ms)
Backmapped check_call to check
[AUTO-PLAY] Auto-confirming action: check
[AUTO-PLAY] Clicking check at screen position (238, 347)
[AUTO-PLAY] Executed action: CHECK_CALL
```

### Manual Confirmation Mode

```
[REAL-TIME SEARCH] Action decided: BET_POT (in 4.9ms)
Backmapped bet_1.0p to bet(567.00)
Execute bet(567.00)? (y/n): y
[AUTO-PLAY] Clicking bet at screen position (368, 347)
[AUTO-PLAY] Executed action: BET_POT
```

## Bet Amount Input

For precise bet sizing, add a `bet_input_box` region to your table profile:

```json
{
  "button_regions": {
    "bet": {
      "x": 328,
      "y": 327,
      "width": 100,
      "height": 40
    },
    "bet_input_box": {
      "x": 350,
      "y": 280,
      "width": 100,
      "height": 30
    }
  }
}
```

When `bet_input_box` is configured, the bot will:
1. Click in the input box
2. Select all text (Ctrl+A)
3. Type the exact bet amount
4. Click the bet/raise button

If `bet_input_box` is not configured, the bot will just click the bet/raise button with the default amount and log a warning.

## Button Regions Reference

Your table profile must have these button regions defined:

- **Required**:
  - `fold`: Fold button
  - `check`: Check button (used for CHECK actions)
  - `call`: Call button (used for CALL actions)
  - `bet`: Bet button (used for BET actions)
  - `raise`: Raise button (used for RAISE actions)
  - `allin`: All-in button

- **Optional**:
  - `bet_input_box`: Input field for typing bet amounts (for precise sizing)

See `assets/table_profiles/pokerstars_autoplay_example.json` for a complete example.

## Safety Features

All existing safety features remain in place:

1. **pyautogui.FAILSAFE**: Move mouse to screen corner to immediately abort
2. **TOS agreement**: Requires `--i-understand-the-tos` flag
3. **Initial confirmation**: Always asks "Continue? (yes/no):" before starting
4. **Ctrl+C**: Stop at any time with keyboard interrupt
5. **Safety checks**: All existing safety checks in SafetyChecker remain active

## Troubleshooting

### No clicks happening

Check these:
1. `--i-understand-the-tos` flag is set
2. `confirm_every_action=False` in config (default for auto-play)
3. Button regions are defined in your profile
4. Screen region matches your poker client window

### Wrong click positions

The button regions in your profile may not match your poker client. Use the calibration tool to update them:

```bash
python -m holdem.vision.calibrate --profile your_profile.json
```

### Bet amounts not precise

Add a `bet_input_box` region to your profile. Without it, the bot will use the client's default bet amount.

### Failsafe triggered

If you accidentally move the mouse to a screen corner, pyautogui will raise a failsafe exception. This is a safety feature. Move your mouse away from corners during auto-play.

## Development Notes

### Architecture

The confirmation logic is in two places:
1. `_execute_concrete_action()` - For actions with state context
2. `execute_action()` - For simple abstract actions

Both check `self.config.confirm_every_action`:
- `True`: Ask for confirmation with `input()`
- `False`: Auto-confirm and log with `[AUTO-PLAY]` prefix

### Testing

Due to GUI dependencies (pyautogui, X11), tests cannot run in headless environments. Manual testing on a system with a display is required.

Test checklist:
- [ ] Auto-play mode clicks buttons without confirmation
- [ ] Manual mode still asks for confirmation
- [ ] Bet/raise with bet_input_box types amounts correctly
- [ ] Bet/raise without bet_input_box uses default amounts
- [ ] All actions log screen positions
- [ ] Failsafe abort works (move mouse to corner)
- [ ] Ctrl+C stops execution cleanly
