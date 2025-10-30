# Texas Hold'em MCCFR + Real-time Search (Pluribus-style)

A complete poker AI system combining Monte Carlo Counterfactual Regret Minimization (MCCFR) with real-time search capabilities, inspired by Pluribus. Features include computer vision for table state detection, action abstraction, blueprint strategy training, and real-time subgame solving.

## Features

- **Vision System**: Screen capture (mss), table detection with ORB/AKAZE feature matching, card recognition via template matching + optional CNN, OCR for stacks/pot/bets (PaddleOCR with pytesseract fallback)
- **Abstraction**: 7-action bucket {Fold, Check/Call, 0.25×pot, 0.5×pot, 1.0×pot, 2.0×pot, All-in} + k-means clustering per street based on equity, position, SPR, draws
- **Blueprint Training**: MCCFR/CFR+ with outcome sampling, exports average policy to JSON/PyTorch format
- **Real-time Search**: Belief updates for opponent ranges, limited subgame construction (current street + 1), re-solving with KL regularization toward blueprint, time-budgeted (e.g., 80ms), fallback to blueprint on timeout
- **Control**: Dry-run mode by default; optional auto-click with confirmations, minimum delays, hotkeys (pause/stop), requires `--i-understand-the-tos` flag

## Requirements

- Python 3.11+
- Dependencies: See `requirements.txt`

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Calibration (Create Table Profile)

Detect and calibrate your poker table window:

```bash
python -m holdem.cli.profile_wizard --window-title "MyPokerTable" \
  --out assets/table_profiles/default_profile.json
```

### 2. Build Abstraction Buckets

Generate hand clusters for abstraction:

```bash
python -m holdem.cli.build_buckets --hands 500000 \
  --k-preflop 12 --k-flop 60 --k-turn 40 --k-river 24 \
  --config assets/abstraction/buckets_config.yaml \
  --out assets/abstraction/precomputed_buckets.pkl
```

### 3. Train Blueprint Strategy

Run MCCFR training to build the base strategy:

```bash
python -m holdem.cli.train_blueprint --iters 2500000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint
```

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

## Safety & Legal

⚠️ **IMPORTANT**: 
- This software is for educational and research purposes only
- Auto-play features are disabled by default and require explicit confirmation
- Always verify compliance with platform Terms of Service before using auto-play
- The developers assume no liability for misuse

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
- **Buckets**: k-means clustering per street using equity (eval7), position, SPR, draw features

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