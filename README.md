# Texas Hold'em MCCFR + Real-time Search (Pluribus-style)

A complete poker AI system combining Monte Carlo Counterfactual Regret Minimization (MCCFR) with real-time search capabilities, inspired by Pluribus. Features include computer vision for table state detection, action abstraction, blueprint strategy training, and real-time subgame solving.

> **🚀 New to the project?** Start with [GETTING_STARTED.md](GETTING_STARTED.md) for a quick setup guide!

> **⚠️ BREAKING CHANGE (v0.2.0)**: Action abstraction has been updated with improved bet sizing and renamed actions (`BET_ONE_HALF_POT` → `BET_OVERBET_150`). **Old checkpoints and trained policies are incompatible** with the new action space. You must retrain from scratch. See [ACTION_ABSTRACTION_FIX_SUMMARY.md](ACTION_ABSTRACTION_FIX_SUMMARY.md) for details.

> **🎉 NEW: Multi-Player (6-max) Support**: The system now supports 2-6 player games with full 6-max position support (BTN/SB/BB/UTG/MP/CO). See [GUIDE_6MAX_TRAINING.md](GUIDE_6MAX_TRAINING.md) for details.

## Features

- **Multi-Player Support**: Full support for 2-6 players with position-aware features. Train blueprints for heads-up, 3-max, or 6-max poker with dedicated position handling (BTN, SB, BB, UTG, MP, CO)
- **Vision System**: Cross-platform screen capture (mss) with native window management (pywinauto on Windows, Quartz/pygetwindow on macOS, pygetwindow on Linux), table detection with ORB/AKAZE feature matching, card recognition via template matching + optional CNN, OCR for stacks/pot/bets (PaddleOCR with pytesseract fallback), **VisionMetrics** for comprehensive performance tracking (OCR accuracy %, MAE for amounts, card recognition accuracy, configurable thresholds/alerts, JSON/text reporting)
- **Abstraction**: Street and position-aware action menus with proper bet sizing. Preflop: `{25%, 50%, 100%, 200%}`, Flop IP: `{33%, 75%, 100%, 150%}`, Flop OOP: `{33%, 75%, 100%}`, Turn: `{66%, 100%, 150%}`, River: `{75%, 100%, 150%, ALL-IN}` + k-means clustering per street based on equity, position, SPR, draws (see [FEATURE_EXTRACTION.md](FEATURE_EXTRACTION.md) for details on 10-dimensional preflop and 34-dimensional postflop feature vectors)
- **Blueprint Training**: Linear MCCFR with DCFR/CFR+ adaptive discounting, dynamic regret pruning, and warm-start from checkpoints. Multiple training modes: iteration-based, time-budget, chunked (automatic restart), and multi-instance (distributed). Adaptive and scheduled epsilon decay. Outcome sampling with validation metrics (L2 regret slope, policy entropy per street). Exports average policy to JSON/PyTorch format. See [DCFR_IMPLEMENTATION.md](DCFR_IMPLEMENTATION.md), [CHUNKED_TRAINING.md](CHUNKED_TRAINING.md), [ADAPTIVE_EPSILON_GUIDE.md](ADAPTIVE_EPSILON_GUIDE.md), and [GUIDE_MULTI_INSTANCE.md](GUIDE_MULTI_INSTANCE.md).
- **Real-time Search**: Belief updates for opponent ranges, limited subgame construction (current street + 1), re-solving with street and position-aware KL regularization toward blueprint, public card sampling (Pluribus technique), optional CFV Net neural network leaf evaluator, time-budgeted (e.g., 80ms) with parallel solving support, fallback to blueprint on timeout
- **Evaluation Tools**: AIVAT variance reduction (78-94% reduction), head-to-head policy evaluation with duplicate deals and position swapping, bb/100 winrate with 95% confidence intervals, automatic snapshot monitoring, JSON/CSV output. See [AIVAT_IMPLEMENTATION_SUMMARY.md](AIVAT_IMPLEMENTATION_SUMMARY.md), [EVAL_PROTOCOL.md](EVAL_PROTOCOL.md), and [tools/README.md](tools/README.md).
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
# Heads-up (2 players) - default
python -m holdem.cli.build_buckets --hands 500000 \
  --k-preflop 24 --k-flop 80 --k-turn 80 --k-river 64 \
  --config assets/abstraction/buckets_config.yaml \
  --out assets/abstraction/precomputed_buckets.pkl

# 6-max (6 players)
python -m holdem.cli.build_buckets --hands 500000 \
  --num-players 6 \
  --k-preflop 24 --k-flop 80 --k-turn 80 --k-river 64 \
  --config assets/abstraction/6max_buckets_config.yaml \
  --out assets/abstraction/6max_buckets.pkl
```

📖 **For 6-max training, see [GUIDE_6MAX_TRAINING.md](GUIDE_6MAX_TRAINING.md) for complete instructions.**

### 3. Train Blueprint Strategy

Run MCCFR training to build the base strategy:

#### Basic Training

```bash
# Single-process training with DCFR adaptive discounting (default)
python -m holdem.cli.train_blueprint --iters 2500000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint

# Multi-core parallel training (recommended for faster training)
python -m holdem.cli.train_blueprint --iters 2500000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint \
  --num-workers 0 --batch-size 100

# 6-max training with configuration file
python -m holdem.cli.train_blueprint \
  --config configs/6max_training.yaml \
  --buckets assets/abstraction/6max_buckets.pkl \
  --logdir runs/6max_blueprint

# Resume training from checkpoint with warm-start
python -m holdem.cli.train_blueprint --iters 5000000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint \
  --resume-from runs/blueprint/checkpoints/checkpoint_iter2500000.pkl
```

#### Advanced Training Modes

**Time-Budget Training** - Train for a fixed duration instead of iterations:
```bash
# Train for 8 days (691200 seconds) with hourly snapshots
python -m holdem.cli.train_blueprint \
  --time-budget 691200 \
  --snapshot-interval 3600 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint_8d
```
See [BLUEPRINT_TIME_BUDGET.md](BLUEPRINT_TIME_BUDGET.md) for details on time-based training.

**Chunked Training** - For memory-constrained environments or long runs:
```bash
# Train in 100k iteration chunks with automatic restart
python -m holdem.cli.train_blueprint \
  --config configs/chunked_training.yaml \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/chunked \
  --chunked --chunk-iterations 100000
```
Process automatically restarts after each chunk to free 100% of RAM. See [CHUNKED_TRAINING.md](CHUNKED_TRAINING.md) for details.

**Multi-Instance Training** - For large-scale or distributed setups:
```bash
# Launch 4 independent instances, each processing 625k iterations
python -m holdem.cli.train_blueprint --iters 2500000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/multi_instance \
  --num-instances 4

# Time-budget mode: each instance runs for full duration independently
python -m holdem.cli.train_blueprint --time-budget 691200 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/multi_instance \
  --num-instances 4
```
See [GUIDE_MULTI_INSTANCE.md](GUIDE_MULTI_INSTANCE.md) for detailed documentation (in French).

#### Training Features

💡 **Parallel Training**: Use `--num-workers 0` to automatically use all available CPU cores. See [PARALLEL_TRAINING.md](PARALLEL_TRAINING.md) for details.

💡 **DCFR/CFR+ Discounting**: Training uses Linear MCCFR with adaptive discounting by default for faster convergence. Configurable via `discount_mode: "dcfr"` in YAML. See [DCFR_IMPLEMENTATION.md](DCFR_IMPLEMENTATION.md).

💡 **Epsilon Schedules**: Automatically decay exploration epsilon during training for better convergence:
```yaml
epsilon_schedule:
  - [0, 0.6]           # High exploration initially
  - [1000000, 0.3]     # Moderate at 1M iterations
  - [2000000, 0.1]     # Low exploration at 2M
```
See [EPSILON_SCHEDULE_FEATURES.md](EPSILON_SCHEDULE_FEATURES.md) and [configs/epsilon_schedule_example.yaml](configs/epsilon_schedule_example.yaml).

💡 **Adaptive Epsilon**: Performance-based epsilon transitions that adapt to your hardware:
```yaml
adaptive_epsilon_enabled: true
adaptive_target_ips: 35.0              # Expected iterations/second
adaptive_min_infoset_growth: 10.0      # Minimum new infosets per 1000 iters
```
See [ADAPTIVE_EPSILON_GUIDE.md](ADAPTIVE_EPSILON_GUIDE.md) for details.

💡 **Dynamic Pruning**: Pluribus-style regret pruning for faster convergence (enabled by default):
```yaml
enable_pruning: true
pruning_threshold: -300000000.0
pruning_probability: 0.95
```

💡 **Infoset Versioning**: Standardized v2 format with abbreviated action sequences (e.g., `v2:FLOP:12:C-B75-C`). See [INFOSET_VERSIONING.md](INFOSET_VERSIONING.md).

### 4. Evaluate Blueprint

Test the blueprint strategy against baselines:

```bash
# Standard evaluation
python -m holdem.cli.eval_blueprint \
  --policy runs/blueprint/avg_policy.json \
  --episodes 200000
```

#### Advanced Evaluation Methods

**AIVAT Variance Reduction** - 78-94% variance reduction for faster, more reliable results:
```bash
python -m holdem.cli.eval_blueprint \
  --policy runs/blueprint/avg_policy.json \
  --episodes 50000 \
  --use-aivat \
  --warmup-episodes 5000
```
AIVAT (Actor-Independent Variance-reduced Advantage Technique) reduces sample requirements by 2-5x. See [AIVAT_IMPLEMENTATION_SUMMARY.md](AIVAT_IMPLEMENTATION_SUMMARY.md) and [EVAL_PROTOCOL.md](EVAL_PROTOCOL.md).

**Head-to-Head Evaluation** - Compare two policies with statistically rigorous duplicate deals:
```bash
python tools/eval_h2h.py \
  runs/blueprint_v1/avg_policy.json \
  runs/blueprint_v2/avg_policy.json \
  --hands 1000 --output results/
```
Produces bb/100 winrate with 95% confidence intervals. See [tools/README.md](tools/README.md) for details.

**Automatic Snapshot Monitoring** - Watch for new training snapshots and auto-evaluate:
```bash
python -m holdem.cli.watch_snapshots \
  --snapshot-dir runs/blueprint/snapshots \
  --episodes 10000 \
  --check-interval 60
```
See [EPSILON_SCHEDULE_FEATURES.md](EPSILON_SCHEDULE_FEATURES.md) for details on the snapshot watcher.

### 5. Run in Dry-Run Mode

Test the system without clicking:

```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 --min-iters 100

# With parallel real-time solving (use all CPU cores)
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 --min-iters 100 \
  --num-workers 0
```

#### Real-time Search Configuration

The system supports several advanced real-time search features:

**Public Card Sampling** - Pluribus technique to reduce variance:
- Solves K sampled future boards and averages strategies
- Configurable via `samples_per_solve` (default: 1, typical: 10-50)
- See [PUBLIC_CARD_SAMPLING_GUIDE.md](PUBLIC_CARD_SAMPLING_GUIDE.md)

**Enhanced KL Regularization** - Street and position-aware blueprint adherence:
- Street-based weights: Flop 0.30, Turn 0.50, River 0.70
- Position adjustment: +0.10 bonus when Out Of Position
- See [KL_REGULARIZATION_ENHANCEMENT.md](KL_REGULARIZATION_ENHANCEMENT.md)

**CFV Net Neural Network Leaf Evaluator** - Fast, accurate value estimation:
- ≤1ms inference (vs 10-50ms for rollouts)
- MAE < 0.30 bb with uncertainty estimation
- Gating logic with automatic fallback to rollouts
- See [CFV_NET_README.md](CFV_NET_README.md)

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

## Configuration

The system supports extensive configuration through YAML files and command-line arguments. Several example configurations are provided in the `configs/` directory.

### Training Configuration Options

#### Training Modes

**Iteration-Based** (default):
```bash
--iters 2500000  # Train for 2.5M iterations
```

**Time-Budget**:
```bash
--time-budget 691200  # Train for 8 days (in seconds)
--snapshot-interval 3600  # Save snapshots every hour
```
See [BLUEPRINT_TIME_BUDGET.md](BLUEPRINT_TIME_BUDGET.md).

**Chunked Mode** (memory-constrained):
```bash
--chunked --chunk-iterations 100000  # 100k iterations per chunk
# OR
--chunked --chunk-minutes 60.0  # 60 minutes per chunk
```
See [CHUNKED_TRAINING.md](CHUNKED_TRAINING.md).

**Multi-Instance** (distributed):
```bash
--num-instances 4  # Launch 4 independent solver instances
```
See [GUIDE_MULTI_INSTANCE.md](GUIDE_MULTI_INSTANCE.md).

#### Exploration Configuration

**Static Epsilon**:
```bash
--epsilon 0.6  # Fixed exploration rate
```

**Epsilon Schedule** (in YAML):
```yaml
epsilon_schedule:
  - [0, 0.6]           # High exploration initially
  - [1000000, 0.3]     # Moderate at 1M iterations
  - [2000000, 0.1]     # Low at 2M iterations
```
See [configs/epsilon_schedule_example.yaml](configs/epsilon_schedule_example.yaml).

**Adaptive Epsilon** (in YAML):
```yaml
adaptive_epsilon_enabled: true
adaptive_target_ips: 35.0              # Expected iterations/second
adaptive_min_infoset_growth: 10.0      # Minimum new infosets per 1000 iters
adaptive_window_merges: 10             # Average over last 10 logging intervals
```
See [ADAPTIVE_EPSILON_GUIDE.md](ADAPTIVE_EPSILON_GUIDE.md).

#### Discounting Configuration

**DCFR/CFR+ Mode** (recommended, in YAML):
```yaml
discount_mode: "dcfr"                  # Adaptive discounting
discount_interval: 1000                # Apply every 1000 iterations
dcfr_reset_negative_regrets: true      # CFR+ behavior
```

**Static Discounting** (in YAML):
```yaml
discount_mode: "static"
discount_interval: 1000
regret_discount_alpha: 1.0
strategy_discount_beta: 1.0
```

See [DCFR_IMPLEMENTATION.md](DCFR_IMPLEMENTATION.md).

#### Pruning Configuration

**Dynamic Regret Pruning** (Pluribus-style, in YAML):
```yaml
enable_pruning: true
pruning_threshold: -300000000.0        # Pluribus value
pruning_probability: 0.95              # Skip 95% of pruned actions
```

#### Parallel Training

**Worker-based** (single instance, multiple workers):
```bash
--num-workers 0  # Use all CPU cores
--batch-size 100  # Iterations per worker batch
```

**Multi-instance** (multiple independent solvers):
```bash
--num-instances 4  # Cannot be combined with --num-workers
```

See [PARALLEL_TRAINING.md](PARALLEL_TRAINING.md).

### Real-time Search Configuration

Configure in YAML under `search:` or `rt:` sections:

**Time Budget and Iterations**:
```yaml
search:
  time_budget_ms: 80                   # 80ms decision time
  min_iterations: 100                  # Minimum CFR iterations
  max_iterations: 1200                 # Maximum CFR iterations
  depth_limit: 1                       # Streets to look ahead
```

**KL Regularization** (street and position-aware):
```yaml
search:
  kl_weight: 1.0                       # Base weight
  kl_weight_flop: 0.30                 # Flop-specific (more exploration)
  kl_weight_turn: 0.50                 # Turn-specific
  kl_weight_river: 0.70                # River-specific (stay closer to blueprint)
  kl_weight_oop_bonus: 0.10            # Bonus when out of position
  blueprint_clip_min: 1e-6             # Numerical stability
```
See [KL_REGULARIZATION_ENHANCEMENT.md](KL_REGULARIZATION_ENHANCEMENT.md).

**Public Card Sampling** (Pluribus technique):
```yaml
search:
  samples_per_solve: 10                # Sample 10 future boards (1 = disabled)
```
See [PUBLIC_CARD_SAMPLING_GUIDE.md](PUBLIC_CARD_SAMPLING_GUIDE.md).

**CFV Net Neural Network Leaf Evaluator**:
```yaml
rt:
  leaf:
    mode: "cfv_net"                    # Use neural network (vs "rollout" or "blueprint")
    cfv_net:
      checkpoint: "assets/cfv_net/6max_best.onnx"
      stats: "assets/cfv_net/stats.json"
      gating:
        tau_flop: 0.20                 # PI width threshold (bb)
        tau_turn: 0.16
        tau_river: 0.12
        ood_sigma: 4.0                 # Out-of-distribution threshold
      fallback: "rollout"              # Fallback when gating rejects
```
See [CFV_NET_README.md](CFV_NET_README.md).

**Parallel Real-time Solving**:
```yaml
search:
  num_workers: 1                       # Workers for parallel solving
```
Or via CLI:
```bash
--num-workers 0  # Use all CPU cores for real-time solving
```

### Complete Configuration Examples

See `configs/` directory for complete examples:
- **[configs/default.yaml](configs/default.yaml)** - Minimal configuration
- **[configs/blueprint_training.yaml](configs/blueprint_training.yaml)** - Standard 2-player training
- **[configs/6max_training.yaml](configs/6max_training.yaml)** - 6-player training with all features
- **[configs/epsilon_schedule_example.yaml](configs/epsilon_schedule_example.yaml)** - Epsilon schedule demo
- **[configs/chunked_training.yaml](configs/chunked_training.yaml)** - Chunked training demo
- **[configs/cfv_net_m2.yaml](configs/cfv_net_m2.yaml)** - CFV Net for M2 chips
- **[configs/cfv_net_server.yaml](configs/cfv_net_server.yaml)** - CFV Net for servers

### TensorBoard Metrics

Training automatically logs comprehensive metrics to TensorBoard:

**Core Metrics**:
- `Training/Utility` - Average game utility
- `Training/Epsilon` - Current exploration epsilon
- `Performance/IterationsPerSecond` - Training throughput

**Policy Metrics**:
- `policy_entropy/preflop`, `flop`, `turn`, `river` - Strategy diversity per street
- `policy_entropy/IP`, `OOP` - Strategy diversity by position

**Regret Metrics**:
- `avg_regret_norm/preflop`, `flop`, `turn`, `river` - Regret convergence per street

**Pruning Metrics**:
- `Training/PruningRate` - Percentage of pruned iterations

Launch TensorBoard:
```bash
tensorboard --logdir runs/blueprint/tensorboard
```

See [EPSILON_SCHEDULE_FEATURES.md](EPSILON_SCHEDULE_FEATURES.md) for details.

## Documentation

### Getting Started
- **[Getting Started](GETTING_STARTED.md)** - Quick setup guide for new users
- **[Quick Reference](QUICKSTART.md)** - Quick command reference
- **[Development Guide](DEVELOPMENT.md)** - Complete setup and workflow guide

### Training Guides
- **[Parallel Training](PARALLEL_TRAINING.md)** - Multi-core training and real-time solving
- **[DCFR Implementation](DCFR_IMPLEMENTATION.md)** - Adaptive discounting and CFR+ details
- **[Chunked Training](CHUNKED_TRAINING.md)** - Memory-constrained training with automatic restart
- **[Multi-Instance Training](GUIDE_MULTI_INSTANCE.md)** - Distributed training guide (Français)
- **[Time-Budget Training](BLUEPRINT_TIME_BUDGET.md)** - Time-based training with snapshots
- **[Adaptive Epsilon](ADAPTIVE_EPSILON_GUIDE.md)** - Performance-based exploration scheduling
- **[Epsilon Schedules](EPSILON_SCHEDULE_FEATURES.md)** - Step-based epsilon decay and TensorBoard metrics
- **[6-max Training](GUIDE_6MAX_TRAINING.md)** - Complete guide for 6-player poker
- **[Infoset Versioning](INFOSET_VERSIONING.md)** - Standardized action sequence encoding

### Abstraction & Features
- **[Feature Extraction](FEATURE_EXTRACTION.md)** - 10D preflop and 34D postflop feature systems
- **[Bucket Creation Guide](GUIDE_CREATION_BUCKETS.md)** - Complete bucketing guide (Français)

### Real-time Search
- **[Real-time Re-Solving](REALTIME_RESOLVING.md)** - Complete real-time search integration guide
- **[Public Card Sampling](PUBLIC_CARD_SAMPLING_GUIDE.md)** - Pluribus board sampling technique
- **[KL Regularization](KL_REGULARIZATION_ENHANCEMENT.md)** - Street and position-aware blueprint adherence
- **[CFV Net](CFV_NET_README.md)** - Neural network leaf evaluator guide

### Evaluation
- **[AIVAT Implementation](AIVAT_IMPLEMENTATION_SUMMARY.md)** - Variance reduction for evaluation
- **[Evaluation Protocol](EVAL_PROTOCOL.md)** - Complete evaluation methodology

### Vision & Calibration
- **[Calibration Guide](CALIBRATION_GUIDE.md)** - Complete table calibration manual (English & Français)
- **[PokerStars Setup](POKERSTARS_SETUP.md)** - PokerStars-specific configuration
- **[VisionMetrics Guide](VISION_METRICS_GUIDE.md)** - Comprehensive performance tracking (OCR accuracy, MAE, alerts, reporting)

### Architecture & Implementation
- **[Implementation Details](IMPLEMENTATION.md)** - Technical architecture overview
- **[Pluribus Executive Summary](PLURIBUS_EXECUTIVE_SUMMARY.md)** - Feature parity analysis with Pluribus AI
- **[Bin Directory](bin/README.md)** - CLI wrapper scripts guide
- **[Tools Directory](tools/README.md)** - Evaluation and utility tools

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
- **Algorithm**: Linear MCCFR with outcome sampling
- **Discounting**: DCFR/CFR+ adaptive discounting for faster convergence
- **Pruning**: Dynamic regret pruning (Pluribus-style) with configurable thresholds
- **Exploration**: Static, scheduled, or adaptive epsilon decay
- **Training Modes**: 
  - Iteration-based (fixed number of iterations)
  - Time-budget (fixed training duration with automatic snapshots)
  - Chunked (automatic process restart for memory management)
  - Multi-instance (distributed training across multiple solvers)
- **Checkpointing**: Full state preservation (RNG, regrets, epsilon, discount factors)
- **Resume**: Warm-start from checkpoints with bucket compatibility validation
- **Metrics**: Comprehensive TensorBoard logging (policy entropy, regret norms per street/position, pruning rate, throughput)
- **Output**: Average policy in JSON/PyTorch format with infoset versioning (v2 format)
- **Infosets**: Versioned format with abbreviated action sequences (e.g., `v2:FLOP:12:C-B75-C`)

### Real-time Search
1. **Belief Update**: Maintain opponent hand range distributions
2. **Subgame Construction**: Limited to current street + next street
3. **Public Card Sampling**: Sample K future boards (Pluribus technique) to reduce variance
4. **Re-solving**: MCCFR with street and position-aware KL divergence regularization toward blueprint
5. **Leaf Evaluation**: 
   - Monte Carlo rollouts (default)
   - Blueprint CFV values
   - CFV Net neural network (fast, accurate with gating logic)
6. **Time Budget**: Default 80ms, fallback to blueprint if timeout
7. **Minimum Iterations**: Configurable lower bound for search quality
8. **Parallel Solving**: Multi-worker support for faster real-time computation

### Evaluation
- **Standard Evaluation**: Play against baselines with configurable episodes
- **AIVAT**: Actor-Independent Variance-reduced Advantage Technique (78-94% variance reduction, 2-5x sample efficiency)
- **Head-to-Head**: Duplicate deals with position swapping for fair comparison
- **Metrics**: bb/100 winrate with 95% confidence intervals
- **Snapshot Watcher**: Automatic evaluation when new training snapshots appear
- **Output**: JSON/CSV results with detailed statistics

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