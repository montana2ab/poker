# Texas Hold'em MCCFR + Real-time Search (Pluribus-style)

A complete poker AI system combining Monte Carlo Counterfactual Regret Minimization (MCCFR) with real-time search capabilities, inspired by Pluribus. Features include computer vision for table state detection, action abstraction, blueprint strategy training, and real-time subgame solving.

> **🚀 New to the project?** Start with [GETTING_STARTED.md](GETTING_STARTED.md) for a quick setup guide!

> **⚠️ BREAKING CHANGE (v0.2.0)**: Action abstraction has been updated with improved bet sizing and renamed actions (`BET_ONE_HALF_POT` → `BET_OVERBET_150`). **Old checkpoints and trained policies are incompatible** with the new action space. You must retrain from scratch. See [ACTION_ABSTRACTION_FIX_SUMMARY.md](ACTION_ABSTRACTION_FIX_SUMMARY.md) for details.

## Features

- **Vision System**: Cross-platform screen capture (mss) with native window management (pywinauto on Windows, Quartz/pygetwindow on macOS, pygetwindow on Linux), table detection with ORB/AKAZE feature matching, card recognition via template matching + optional CNN, OCR for stacks/pot/bets (PaddleOCR with pytesseract fallback)
- **Abstraction**: Street and position-aware action menus with proper bet sizing. Preflop: `{25%, 50%, 100%, 200%}`, Flop IP: `{33%, 75%, 100%, 150%}`, Flop OOP: `{33%, 75%, 100%}`, Turn: `{66%, 100%, 150%}`, River: `{75%, 100%, 150%, ALL-IN}` + k-means clustering per street based on equity, position, SPR, draws (see [FEATURE_EXTRACTION.md](FEATURE_EXTRACTION.md) for details on 10-dimensional preflop and 34-dimensional postflop feature vectors)
- **Blueprint Training**: MCCFR/CFR+ with outcome sampling, exports average policy to JSON/PyTorch format
- **Real-time Search**: Belief updates for opponent ranges, limited subgame construction (current street + 1), re-solving with KL regularization toward blueprint, time-budgeted (e.g., 80ms), fallback to blueprint on timeout
- **Control**: Dry-run mode by default; optional auto-click with confirmations, minimum delays, hotkeys (pause/stop), requires `--i-understand-the-tos` flag

## Platform Support

This project supports **Windows**, **macOS**, and **Linux**:
- **Windows**: Uses `pywinauto` for native window management via Win32 API
- **macOS**: Uses `pyobjc-framework-Quartz` for native Quartz window management, with `pygetwindow` as fallback
- **Linux**: Uses `pygetwindow` for X11 window management

## Requirements

- Python 3.11+
- Dependencies: See `requirements.txt`

## Installation

### Quick Install (Recommended)

```bash
# Clone the repository (if not already done)
git clone https://github.com/montana2ab/poker.git
cd poker

# Run the installation script
./install.sh
```

### Manual Installation

```bash
# Option 1: Install as a package (requires pip access to PyPI)
pip install -e .

# Option 2: Use PYTHONPATH (if pip install fails)
export PYTHONPATH=$(pwd)/src:$PYTHONPATH

# Option 3: Source the activation script
source activate.sh
```

### Using the CLI Commands

After installation, you can use the CLI commands in three ways:

```bash
# Method 1: Using wrapper scripts (easiest)
./bin/holdem-build-buckets --help
./bin/holdem-train-blueprint --help

# Method 2: Using Python module syntax (requires proper installation or PYTHONPATH)
python -m holdem.cli.build_buckets --help
python -m holdem.cli.train_blueprint --help

# Method 3: Add bin/ to your PATH
export PATH=$(pwd)/bin:$PATH
holdem-build-buckets --help
```

## Quick Start

### 1. Calibration (Create Table Profile)

Detect and calibrate your poker table window:

```bash
python -m holdem.cli.profile_wizard --window-title "MyPokerTable" \
  --seats 9 \
  --out assets/table_profiles/default_profile.json
```

**For PokerStars on macOS (9-player tables):**
```bash
python -m holdem.cli.profile_wizard --window-title "Hold'em" \
  --owner-name "PokerStars" \
  --seats 9 \
  --out assets/table_profiles/pokerstars_nlhe_9max.json
```

**For 6-max tables:**
```bash
python -m holdem.cli.profile_wizard --window-title "MyPokerTable" \
  --seats 6 \
  --out assets/table_profiles/6max_profile.json
```

📖 **See [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) for detailed calibration instructions, troubleshooting, and platform-specific tips.**

### 2. Build Abstraction Buckets

Generate hand clusters for abstraction:

```bash
python -m holdem.cli.build_buckets --hands 500000 \
  --k-preflop 24 --k-flop 80 --k-turn 80 --k-river 64 \
  --config assets/abstraction/buckets_config.yaml \
  --out assets/abstraction/precomputed_buckets.pkl
```

### 3. Train Blueprint Strategy

Run MCCFR training to build the base strategy:

```bash
# Single-process training
python -m holdem.cli.train_blueprint --iters 2500000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint

# Multi-core parallel training (recommended for faster training)
python -m holdem.cli.train_blueprint --iters 2500000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint \
  --num-workers 0 --batch-size 100
```

💡 **Tip**: Use `--num-workers 0` to automatically use all available CPU cores for faster training. See [PARALLEL_TRAINING.md](PARALLEL_TRAINING.md) for details.

### 4. Evaluate Blueprint

Test the blueprint strategy against baselines:

```bash
python -m holdem.cli.eval_blueprint \
  --policy runs/blueprint/avg_policy.json \
  --episodes 200000
```

### 5. Run in Dry-Run Mode

Test the system without clicking:

```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 --min-iters 100
```

**Troubleshooting card recognition:** If board cards (flop, turn, river) are not being detected, use the `--debug-images` flag to save extracted card regions for inspection:

```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --debug-images /tmp/debug_cards
```

This will save the card regions to `/tmp/debug_cards/board_region_XXXX.png` files, allowing you to verify:
- The card region coordinates in your table profile are correct
- The cards are visible and clear in the extracted region
- The extracted cards match the templates in `assets/templates/` or `assets/hero_templates/`


### 6. Run Auto-Play (Use with Caution!)

**WARNING**: Auto-play mode will click on your screen. Use only on approved platforms and with proper authorization.

```bash
python -m holdem.cli.run_autoplay \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 \
  --confirm-every-action true \
  --i-understand-the-tos
```

## Project Structure

```
holdem-mccfr-search/
  README.md                    # This file
  requirements.txt             # Python dependencies
  LICENSE                      # MIT License
  assets/
    table_profiles/
      default_profile.json     # Table calibration data
    templates/                 # Card recognition templates
    samples/                   # Sample images for testing
    abstraction/
      buckets_config.yaml      # Bucketing configuration
      precomputed_buckets.pkl  # Pre-computed hand clusters
  src/holdem/
    __init__.py
    types.py                   # Core data types
    config.py                  # Configuration management
    utils/                     # Utility modules
      __init__.py
      rng.py                   # Random number generation
      timers.py                # Timing utilities
      logging.py               # Logging setup
      serialization.py         # Save/load helpers
    vision/                    # Computer vision system
      __init__.py
      screen.py                # Screen capture
      calibrate.py             # Table calibration
      detect_table.py          # Table detection
      cards.py                 # Card recognition
      ocr.py                   # OCR for text
      parse_state.py           # Parse game state
      assets_tools.py          # Asset management
    abstraction/               # Game abstraction
      __init__.py
      features.py              # Feature extraction
      bucketing.py             # Hand clustering
      actions.py               # Action abstraction
      state_encode.py          # State encoding
    mccfr/                     # MCCFR solver
      __init__.py
      game_tree.py             # Game tree structure
      regrets.py               # Regret management
      mccfr_os.py              # Outcome sampling
      solver.py                # Main solver
      policy_store.py          # Policy storage
    realtime/                  # Real-time search
      __init__.py
      belief.py                # Belief state tracking
      subgame.py               # Subgame construction
      resolver.py              # Subgame resolver
      search_controller.py     # Search orchestration
    control/                   # Action execution
      __init__.py
      actions.py               # Action definitions
      executor.py              # Action executor
      safety.py                # Safety checks
    rl_eval/                   # Evaluation
      __init__.py
      baselines.py             # Baseline agents
      eval_loop.py             # Evaluation loop
    cli/                       # Command-line interface
      __init__.py
      build_buckets.py         # Build abstraction
      train_blueprint.py       # Train blueprint
      run_dry_run.py           # Dry-run mode
      run_autoplay.py          # Auto-play mode
      profile_wizard.py        # Table calibration
      eval_blueprint.py        # Evaluate strategy
  tests/
    test_bucketing.py          # Bucketing tests
    test_mccfr_sanity.py       # MCCFR sanity checks
    test_realtime_budget.py    # Time budget tests
    test_vision_offline.py     # Vision accuracy tests
```

## Testing

Run the test suite:

```bash
pytest tests/
```

Individual test modules:
- `test_bucketing.py`: Verify stable bucket assignments with seed
- `test_mccfr_sanity.py`: Check regret convergence and non-uniform policies
- `test_realtime_budget.py`: Validate time budget adherence and fallback
- `test_vision_offline.py`: Verify card/OCR accuracy ≥97-98% on samples

## Troubleshooting

### Installation Issues

**Problem: `ModuleNotFoundError: holdem`**
- Solution: The package needs to be properly installed. Run:
  ```bash
  pip install -e .
  ```
  Or set PYTHONPATH:
  ```bash
  export PYTHONPATH=$(pwd)/src:$PYTHONPATH
  ```

**Problem: `Multiple .egg-info directories found`**
- Solution: This has been fixed by renaming `setup.py` to `setup_assets.py`. If you still encounter this, run:
  ```bash
  make clean
  find . -name "*.egg-info" -type d -exec rm -rf {} +
  pip install -e .
  ```

**Problem: CLI commands not found (e.g., `holdem-build-buckets: command not found`)**
- Solution: Install the package with pip to get entry points:
  ```bash
  pip install -e .
  ```
  Or use the wrapper scripts directly:
  ```bash
  ./bin/holdem-build-buckets --help
  ```

### Dependency Issues

**Problem: `ModuleNotFoundError: cv2` (opencv-python)**
- Solution: Install opencv-python:
  ```bash
  pip install opencv-python
  ```

**Problem: Version conflicts or instability**
- Solution: All dependencies now have pinned version ranges. Use:
  ```bash
  pip install -r requirements.txt
  ```

### macOS Specific Issues

**Problem: Window detection not working on macOS**
- Cause: macOS requires the `pyobjc-framework-Quartz` package for native window management
- Solution: The package is automatically installed on macOS via platform-specific dependencies. If you encounter issues:
  ```bash
  pip install pyobjc-framework-Quartz
  ```
  If Quartz is not available, the system will automatically fall back to `pygetwindow`.

**Problem: PokerStars table not detected on macOS**
- Solution: Use the `--owner-name` flag for better detection:
  ```bash
  holdem-profile-wizard --window-title "Hold'em" \
    --owner-name "PokerStars" \
    --out assets/table_profiles/pokerstars.json
  ```
  Or use the pre-configured template: `assets/table_profiles/pokerstars_nlhe_9max_template.json`
- See [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) for complete PokerStars setup instructions

**Problem: AppleScript/Accessibility Error -10003**
- Cause: macOS requires explicit permissions for screen recording and accessibility
- Solution:
  1. Open System Preferences → Security & Privacy → Privacy
  2. Add your terminal/IDE to "Screen Recording" permissions
  3. Add your terminal/IDE to "Accessibility" permissions
  4. Restart the terminal/IDE after granting permissions

**Problem: Auto-play not clicking**
- Cause: macOS Automation permissions required
- Solution:
  1. Open System Preferences → Security & Privacy → Privacy → Automation
  2. Enable permissions for Python/Terminal to control System Events
  3. Restart and try again

### Missing Assets

**Problem: `FileNotFoundError: avg_policy.json`**
- Cause: Blueprint policy needs to be trained first
- Solution: Train the blueprint before using it:
  ```bash
  holdem-build-buckets --out assets/abstraction/precomputed_buckets.pkl
  holdem-train-blueprint --buckets assets/abstraction/precomputed_buckets.pkl --logdir runs/blueprint
  ```
  The training will create `runs/blueprint/avg_policy.json`

**Problem: Missing card templates**
- Cause: Vision assets not created
- Solution: Run the asset setup:
  ```bash
  python setup_assets.py
  ```

**Problem: `FileNotFoundError: table profile`**
- Cause: Table profile needs to be created
- Solution: Run the profile wizard:
  ```bash
  holdem-profile-wizard --window-title "YourPokerTable" --out assets/table_profiles/my_profile.json
  ```

### Runtime Issues

**Problem: Bot stuck at PREFLOP, doesn't detect cards**
- Cause: The `hero_position` field is not set in your table profile
- Solution: Edit your table profile JSON and add the `hero_position` field:
  ```json
  {
    "hero_position": 0,
    "player_regions": [
      {
        "position": 0,
        "card_region": {"x": 130, "y": 700, "width": 100, "height": 80}
      },
      ...
    ]
  }
  ```
  Set `hero_position` to the index (0-8 for 9-max) of your seat position in the `player_regions` array.
- The system needs to know which player is you to detect your hole cards during PREFLOP
- See [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) for detailed instructions on setting hero_position

**Problem: dtype mismatch or KMeans.predict crashes**
- Status: FIXED - This issue has been resolved by:
  - Ensuring all features return float64 arrays
  - Adding `utils/arrays.py` with dtype/contiguity utilities
  - Using `prepare_for_sklearn()` in bucketing code

**Problem: IndentationError in bucketing code**
- Status: VERIFIED - No indentation errors found in current codebase

**Problem: Tests fail with `ModuleNotFoundError`**
- Solution: Ensure package is installed or PYTHONPATH is set:
  ```bash
  pip install -e .
  # OR
  PYTHONPATH=$(pwd)/src pytest tests/
  ```

## Safety & Legal

⚠️ **IMPORTANT**: 
- This software is for educational and research purposes only
- Auto-play features are disabled by default and require explicit confirmation
- Always verify compliance with platform Terms of Service before using auto-play
- The developers assume no liability for misuse

## Documentation

- **[Getting Started](GETTING_STARTED.md)** - Quick setup guide for new users
- **[Parallel Training](PARALLEL_TRAINING.md)** - Guide to multi-core training and real-time solving
- **[Feature Extraction](FEATURE_EXTRACTION.md)** - Detailed guide to the 10-dimensional preflop and 34-dimensional postflop feature extraction system
- **[Real-time Re-Solving](REALTIME_RESOLVING.md)** - Complete guide to real-time search integration
- **[Calibration Guide](CALIBRATION_GUIDE.md)** - Complete table calibration manual (English & Français)
- **[Development Guide](DEVELOPMENT.md)** - Complete setup and workflow guide
- **[Quick Reference](QUICKSTART.md)** - Quick command reference
- **[Implementation Details](IMPLEMENTATION.md)** - Technical architecture
- **[Bin Directory](bin/README.md)** - CLI wrapper scripts guide

## License

MIT License - see LICENSE file for details

## Architecture

### Vision Pipeline
1. Screen capture via `mss`
2. Table detection using ORB/AKAZE feature matching with perspective warp
3. Card recognition: Template matching + optional lightweight CNN
4. OCR: PaddleOCR (primary) with pytesseract fallback
5. Parse complete `TableState` object

### Abstraction
- **Actions**: 7-bucket system (Fold, Check/Call, 0.25p, 0.5p, 1.0p, 2.0p, All-in)
- **Buckets**: k-means clustering per street (24/80/80/64 buckets for preflop/flop/turn/river) using comprehensive feature extraction
  - Preflop: 10-dimensional features (hand strength, suitedness, connectivity, equity)
  - Postflop: 34-dimensional features (hand categories, draw types, board texture, equity, SPR, position)
  - See [FEATURE_EXTRACTION.md](FEATURE_EXTRACTION.md) for complete details

### Blueprint Training
- Algorithm: MCCFR with CFR+ (outcome sampling)
- Output: Average policy in JSON/PyTorch format
- Configurable iterations and abstraction granularity

### Real-time Search
1. **Belief Update**: Maintain opponent hand range distributions
2. **Subgame Construction**: Limited to current street + next street
3. **Re-solving**: MCCFR with KL divergence regularization toward blueprint
4. **Time Budget**: Default 80ms, fallback to blueprint if timeout
5. **Minimum Iterations**: Configurable lower bound for search quality

### Control System
- **Dry-run**: Observe only, no mouse clicks
- **Auto-play**: Requires `--i-understand-the-tos` flag
- **Confirmations**: Optional per-action confirmation
- **Safety**: Minimum delays, hotkeys for pause/stop

## Contributing

Contributions are welcome! Please ensure:
1. Code passes all tests
2. New features include tests
3. Documentation is updated
4. Follows existing code style

## References

- [Pluribus: Superhuman AI for multiplayer poker](https://science.sciencemag.org/content/365/6456/885)
- [Monte Carlo Sampling for Regret Minimization](https://papers.nips.cc/paper/2009/file/00411460f7c92d2124a67ea0f4cb5f85-Paper.pdf)
- [DeepStack: Expert-level artificial intelligence in heads-up no-limit poker](https://science.sciencemag.org/content/356/6337/508)