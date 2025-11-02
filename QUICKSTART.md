# Quick Reference Guide

## Installation

```bash
# Clone repository
git clone https://github.com/montana2ab/poker.git
cd poker

# Quick install (recommended)
./install.sh

# Or manual setup
pip install -r requirements.txt  # Install dependencies
python setup_assets.py                   # Create directory structure

# Verify installation
python verify_structure.py
```

## Environment Setup

If the installation fails or you prefer not to install the package globally:

```bash
# Method 1: Source the activation script
source activate.sh

# Method 2: Set PYTHONPATH manually
export PYTHONPATH=$(pwd)/src:$PYTHONPATH

# Method 3: Add bin/ to PATH for easier access
export PATH=$(pwd)/bin:$PATH
```

## Quick Start Commands

You can use the commands in multiple ways:

```bash
# Using wrapper scripts (easiest, no setup needed)
./bin/holdem-profile-wizard \
  --window-title "MyPokerTable" \
  --out assets/table_profiles/my_table.json

./bin/holdem-build-buckets \
  --hands 500000 \
  --k-preflop 12 --k-flop 60 --k-turn 40 --k-river 24 \
  --out assets/abstraction/precomputed_buckets.pkl

./bin/holdem-train-blueprint \
  --iters 2500000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint

./bin/holdem-eval-blueprint \
  --policy runs/blueprint/avg_policy.json \
  --episodes 200000

./bin/holdem-dry-run \
  --profile assets/table_profiles/my_table.json \
  --policy runs/blueprint/avg_policy.json

# OR using Python module syntax (requires PYTHONPATH or installation)
python -m holdem.cli.profile_wizard --help
python -m holdem.cli.build_buckets --help
# etc...
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_bucketing.py -v

# Run with coverage
pytest tests/ --cov=holdem --cov-report=html
```

## Common Issues

### Missing dependencies
```bash
pip install -r requirements.txt
```

### Import errors
```bash
export PYTHONPATH=/path/to/poker/src:$PYTHONPATH
```

### Card templates missing
```bash
python -c "from holdem.vision.cards import create_mock_templates; \
           from pathlib import Path; \
           create_mock_templates(Path('assets/templates'))"
```

## Project Structure

- `src/holdem/` - Main source code
  - `vision/` - Computer vision system
  - `abstraction/` - Game abstraction
  - `mccfr/` - MCCFR solver
  - `realtime/` - Real-time search
  - `control/` - Action execution
  - `cli/` - Command-line interface
- `tests/` - Test suite
- `assets/` - Configuration and data files

## Safety Notes

⚠️ **Auto-play requires --i-understand-the-tos flag**
⚠️ **Always test in dry-run mode first**
⚠️ **Verify platform Terms of Service compliance**
⚠️ **Developers assume NO liability for misuse**

## Help

```bash
# Get help for any command
python -m holdem.cli.build_buckets --help
python -m holdem.cli.train_blueprint --help
python -m holdem.cli.run_dry_run --help
```

## More Info

- Full documentation: `README.md`
- Implementation details: `IMPLEMENTATION.md`
- Usage examples: `python demo_usage.py`
