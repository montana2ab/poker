# CLI Wrapper Scripts

This directory contains executable wrapper scripts for all CLI commands in the Texas Hold'em MCCFR system.

## Purpose

These wrapper scripts allow you to run CLI commands without having to:
- Install the package with pip
- Set PYTHONPATH environment variable
- Use the `python -m` syntax

## Available Commands

- `holdem-build-buckets` - Build hand abstraction buckets
- `holdem-train-blueprint` - Train MCCFR blueprint strategy
- `holdem-eval-blueprint` - Evaluate blueprint against baselines
- `holdem-profile-wizard` - Calibrate poker table
- `holdem-dry-run` - Run in observation mode (no clicking)
- `holdem-autoplay` - Run in auto-play mode (requires --i-understand-the-tos)

## Usage

### Direct execution:
```bash
./bin/holdem-build-buckets --help
./bin/holdem-train-blueprint --help
```

### Add to PATH for easier access:
```bash
export PATH=$(pwd)/bin:$PATH
holdem-build-buckets --help
holdem-train-blueprint --help
```

## How They Work

Each wrapper script:
1. Automatically adds the `src/` directory to Python's module search path
2. Imports the corresponding CLI module from `holdem.cli`
3. Calls the main() function of that module

This means you can use these scripts even if the package is not formally installed.

## Example

```bash
# Build buckets using wrapper script
./bin/holdem-build-buckets \
  --hands 500000 \
  --k-preflop 12 --k-flop 60 --k-turn 40 --k-river 24 \
  --out assets/abstraction/precomputed_buckets.pkl

# Same command using Python module syntax (requires PYTHONPATH or installation)
python -m holdem.cli.build_buckets \
  --hands 500000 \
  --k-preflop 12 --k-flop 60 --k-turn 40 --k-river 24 \
  --out assets/abstraction/precomputed_buckets.pkl
```

Both commands are equivalent - use whichever is more convenient for you.
