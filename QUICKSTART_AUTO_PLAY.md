# Quick Start: AUTO-PLAY Mode

## 🎯 What This Does

The bot now **automatically clicks** poker table buttons without asking for confirmation!

## 🚀 Quick Start (3 Steps)

### 1. Ensure Your Profile Has Button Regions

Your table profile needs these regions defined:

```json
{
  "button_regions": {
    "fold": {"x": 149, "y": 327, "width": 100, "height": 40},
    "check": {"x": 238, "y": 327, "width": 100, "height": 40},
    "call": {"x": 238, "y": 327, "width": 100, "height": 40},
    "bet": {"x": 328, "y": 327, "width": 100, "height": 40},
    "raise": {"x": 328, "y": 327, "width": 100, "height": 40},
    "allin": {"x": 417, "y": 327, "width": 100, "height": 40}
  }
}
```

See `assets/table_profiles/pokerstars_autoplay_example.json` for a complete example.

### 2. Run Auto-Play Mode

```bash
python -m holdem.cli.run_autoplay \
    --profile assets/table_profiles/pokerstars.json \
    --policy assets/policies/blueprint.pkl \
    --i-understand-the-tos
```

### 3. Watch It Play!

The bot will:
- ✅ Detect game state
- ✅ Decide optimal action
- ✅ **Automatically click the button** (no confirmation needed!)

## 📊 What You'll See

```
[REAL-TIME SEARCH] Action decided: CHECK_CALL (in 111.2ms)
Backmapped check_call to check
[AUTO-PLAY] Auto-confirming action: check
[AUTO-PLAY] Clicking check at screen position (238, 347)
[AUTO-PLAY] Executed action: CHECK_CALL
```

## ⚙️ Optional: Precise Bet Sizing

For exact bet amounts, add this to your profile:

```json
{
  "button_regions": {
    "bet_input_box": {
      "x": 350,
      "y": 280,
      "width": 100,
      "height": 30
    }
  }
}
```

The bot will:
1. Click the input box
2. Type the exact amount
3. Click the bet/raise button

## 🛡️ Safety Features

- **Failsafe**: Move mouse to corner to abort immediately
- **Ctrl+C**: Stop at any time
- **TOS Agreement**: Requires `--i-understand-the-tos` flag
- **Initial Confirmation**: Asks "Continue? (yes/no)" before starting

## 🔄 Manual Mode (Optional)

If you want to confirm each action manually:

```bash
python -m holdem.cli.run_autoplay \
    --profile profile.json \
    --policy policy.pkl \
    --confirm-every-action \
    --i-understand-the-tos
```

This will ask "Execute X? (y/n):" before each action.

## 📖 Full Documentation

- **Usage Guide**: `AUTO_PLAY_IMPLEMENTATION_GUIDE.md`
- **Before/After**: `AUTO_PLAY_BEFORE_AFTER.md`
- **Implementation Details**: `IMPLEMENTATION_COMPLETE_AUTO_PLAY.md`

## ❓ Troubleshooting

### No clicks happening?

1. Check `--i-understand-the-tos` flag is set
2. Verify button regions in your profile
3. Make sure screen region matches your poker window

### Wrong click positions?

Use the calibration tool to update button regions:
```bash
python -m holdem.vision.calibrate --profile your_profile.json
```

### Bet amounts not precise?

Add `bet_input_box` region to your profile (see step 3 in Optional section above).

---

**That's it! The bot now plays poker automatically.** 🎉
