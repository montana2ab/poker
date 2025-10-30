# Texas Hold'em MCCFR System - Implementation Summary

## Overview

This repository contains a complete implementation of a Texas Hold'em poker AI system combining:
- **MCCFR (Monte Carlo Counterfactual Regret Minimization)** for blueprint strategy training
- **Real-time subgame solving** inspired by Pluribus
- **Computer vision** for table state detection
- **Safe execution** with multiple guardrails

## Project Structure

```
poker/
├── README.md                          # Main documentation
├── LICENSE                            # MIT License
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Project configuration
├── .gitignore                         # Git ignore rules
├── setup.py                           # Setup script
├── verify_structure.py                # Structure verification
├── demo_usage.py                      # Usage examples
│
├── assets/                            # Asset files
│   ├── abstraction/
│   │   ├── buckets_config.yaml        # Bucketing configuration
│   │   └── precomputed_buckets.pkl    # Pre-computed buckets (generated)
│   ├── table_profiles/
│   │   └── default_profile.json       # Default table profile
│   ├── templates/                     # Card recognition templates
│   │   └── README.md
│   └── samples/                       # Sample images for testing
│       └── README.md
│
├── src/holdem/                        # Main source code
│   ├── __init__.py                    # Package initialization
│   ├── types.py                       # Core data types
│   ├── config.py                      # Configuration management
│   │
│   ├── utils/                         # Utility modules
│   │   ├── __init__.py
│   │   ├── rng.py                     # Random number generation
│   │   ├── timers.py                  # Timing utilities
│   │   ├── logging.py                 # Logging setup
│   │   └── serialization.py           # Save/load helpers
│   │
│   ├── vision/                        # Computer vision system
│   │   ├── __init__.py
│   │   ├── screen.py                  # Screen capture (mss)
│   │   ├── calibrate.py               # Table calibration
│   │   ├── detect_table.py            # Table detection (ORB/AKAZE)
│   │   ├── cards.py                   # Card recognition
│   │   ├── ocr.py                     # OCR (PaddleOCR/pytesseract)
│   │   ├── parse_state.py             # State parsing
│   │   └── assets_tools.py            # Asset management
│   │
│   ├── abstraction/                   # Game abstraction
│   │   ├── __init__.py
│   │   ├── features.py                # Feature extraction (eval7)
│   │   ├── bucketing.py               # Hand clustering (k-means)
│   │   ├── actions.py                 # Action abstraction (7 buckets)
│   │   └── state_encode.py            # State encoding
│   │
│   ├── mccfr/                         # MCCFR solver
│   │   ├── __init__.py
│   │   ├── game_tree.py               # Game tree structure
│   │   ├── regrets.py                 # Regret tracking
│   │   ├── mccfr_os.py                # Outcome sampling
│   │   ├── solver.py                  # Main solver
│   │   └── policy_store.py            # Policy storage
│   │
│   ├── realtime/                      # Real-time search
│   │   ├── __init__.py
│   │   ├── belief.py                  # Belief state tracking
│   │   ├── subgame.py                 # Subgame construction
│   │   ├── resolver.py                # Subgame resolver (KL reg)
│   │   └── search_controller.py       # Search orchestration
│   │
│   ├── control/                       # Action execution
│   │   ├── __init__.py
│   │   ├── actions.py                 # Action definitions
│   │   ├── executor.py                # Action executor
│   │   └── safety.py                  # Safety checks
│   │
│   ├── rl_eval/                       # Evaluation
│   │   ├── __init__.py
│   │   ├── baselines.py               # Baseline agents
│   │   └── eval_loop.py               # Evaluation loop
│   │
│   └── cli/                           # Command-line interface
│       ├── __init__.py
│       ├── build_buckets.py           # Build abstraction buckets
│       ├── train_blueprint.py         # Train MCCFR blueprint
│       ├── run_dry_run.py             # Dry-run mode
│       ├── run_autoplay.py            # Auto-play mode
│       ├── profile_wizard.py          # Table calibration wizard
│       └── eval_blueprint.py          # Evaluate strategy
│
└── tests/                             # Test suite
    ├── test_bucketing.py              # Bucketing tests
    ├── test_mccfr_sanity.py           # MCCFR sanity checks
    ├── test_realtime_budget.py        # Time budget tests
    └── test_vision_offline.py         # Vision accuracy tests
```

## Components

### 1. Vision System
- **Screen capture**: mss library for fast screen grabbing
- **Table detection**: ORB/AKAZE feature matching with perspective warp
- **Card recognition**: Template matching + optional CNN
- **OCR**: PaddleOCR (primary) with pytesseract fallback
- **State parsing**: Complete TableState object construction

### 2. Abstraction Layer
- **Actions**: 7-bucket system (Fold, Check/Call, 0.25p, 0.5p, 1.0p, 2.0p, All-in)
- **Hand bucketing**: K-means clustering per street
  - Preflop: 12 buckets
  - Flop: 60 buckets
  - Turn: 40 buckets
  - River: 24 buckets
- **Features**: Equity (eval7), position, SPR, draws

### 3. MCCFR Blueprint Training
- Algorithm: MCCFR with CFR+ (outcome sampling)
- Configurable iterations (default: 2.5M)
- Checkpoints every 100k iterations
- Export to JSON/PyTorch format

### 4. Real-time Search
- **Belief tracking**: Opponent hand range distributions
- **Subgame construction**: Limited to current + next street
- **Resolver**: MCCFR with KL divergence regularization
- **Time budget**: Default 80ms, configurable
- **Fallback**: Blueprint strategy on timeout

### 5. Control System
- **Dry-run mode**: Observe only, no clicks (default)
- **Auto-play mode**: Requires --i-understand-the-tos flag
- **Safety features**:
  - Confirmation for every action (optional)
  - Minimum delays between actions
  - PyAutoGUI failsafe
  - Session time limits
  - Action count limits

### 6. CLI Commands

All commands are invoked via `python -m holdem.cli.<command>`:

1. **profile_wizard**: Calibrate poker table
2. **build_buckets**: Build hand abstraction
3. **train_blueprint**: Train MCCFR strategy
4. **eval_blueprint**: Evaluate against baselines
5. **run_dry_run**: Safe observation mode
6. **run_autoplay**: Automated play (with safety)

### 7. Test Suite

Four test modules ensuring:
- Stable bucket assignments with seed
- MCCFR regret convergence
- Time budget adherence
- Vision accuracy ≥97-98%

## Key Features

✓ **Complete implementation** - All components functional
✓ **Safety-first design** - Dry-run by default, multiple guardrails
✓ **Modular architecture** - Easy to extend and customize
✓ **Well-documented** - Comprehensive README and inline comments
✓ **Tested** - Test suite for critical components
✓ **MIT License** - Free to use and modify

## Dependencies

Core:
- numpy, scikit-learn (abstraction)
- torch (optional, for policy export)
- eval7 (equity calculation)
- opencv-python (vision)
- mss, pyautogui, pywinauto (screen/control)
- paddleocr, pytesseract (OCR)
- rich, tensorboard (logging)
- pyyaml (configuration)
- pytest (testing)

## Usage Workflow

1. **Calibrate**: `python -m holdem.cli.profile_wizard ...`
2. **Build buckets**: `python -m holdem.cli.build_buckets ...`
3. **Train blueprint**: `python -m holdem.cli.train_blueprint ...`
4. **Evaluate**: `python -m holdem.cli.eval_blueprint ...`
5. **Test (dry-run)**: `python -m holdem.cli.run_dry_run ...`
6. **Deploy (auto-play)**: `python -m holdem.cli.run_autoplay ...` ⚠️

## Implementation Notes

This implementation provides:
- A complete, working poker AI system
- All required CLI commands as specified
- Proper safety features and guardrails
- Comprehensive documentation
- Test coverage for critical paths

The code is production-ready for research and educational purposes. For live play, additional considerations are needed:
- Higher-quality card templates
- Fine-tuned table profiles
- Longer MCCFR training
- Platform-specific compliance checks

## Files Summary

Total files created: 59
- Source code: 46 Python files
- Tests: 4 test files
- Documentation: 5 markdown/config files
- Scripts: 3 utility scripts
- Assets: 1 config file

Lines of code: ~4,400 (excluding blanks/comments)

## License

MIT License - See LICENSE file for details
