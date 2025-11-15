# CLI Wrapper Scripts

This directory contains executable wrapper scripts for all CLI commands in the Texas Hold'em MCCFR system.

## Purpose

These wrapper scripts allow you to run CLI commands without having to:
- Install the package with pip
- Set PYTHONPATH environment variable
- Use the `python -m` syntax

## Available Commands

### Core Training & Evaluation

- `holdem-build-buckets` - Build hand abstraction buckets
- `holdem-train-blueprint` - Train MCCFR blueprint strategy
- `holdem-eval-blueprint` - Evaluate blueprint against baselines
- `holdem-profile-wizard` - Calibrate poker table
- `holdem-dry-run` - Run in observation mode (no clicking)
- `holdem-autoplay` - Run in auto-play mode (requires --i-understand-the-tos)

### Benchmark Scripts (Pluribus-style Evaluation)

- `run_eval_blueprint_vs_baselines.py` - Evaluate blueprint against baseline agents
- `run_eval_resolve_vs_blueprint.py` - Evaluate RT search with resolve against baselines

These benchmark scripts implement the standard evaluation protocol documented in `EVAL_PROTOCOL.md`.

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

### Benchmark Scripts

#### Quick Test (1,000 hands)
```bash
# Test blueprint against baselines
./bin/run_eval_blueprint_vs_baselines.py \
  --policy runs/blueprint/avg_policy.json \
  --quick-test

# Test RT search with resolve
./bin/run_eval_resolve_vs_blueprint.py \
  --policy runs/blueprint/avg_policy.json \
  --quick-test \
  --samples-per-solve 16
```

#### Standard Evaluation (50,000 hands)
```bash
# Blueprint evaluation
./bin/run_eval_blueprint_vs_baselines.py \
  --policy runs/blueprint/avg_policy.json \
  --num-hands 50000 \
  --seed 42 \
  --out eval_runs/blueprint_eval.json

# RT search evaluation with 16 samples per solve
./bin/run_eval_resolve_vs_blueprint.py \
  --policy runs/blueprint/avg_policy.json \
  --num-hands 50000 \
  --samples-per-solve 16 \
  --time-budget 80 \
  --seed 42 \
  --out eval_runs/resolve_eval.json
```

#### With AIVAT Variance Reduction
```bash
./bin/run_eval_blueprint_vs_baselines.py \
  --policy runs/blueprint/avg_policy.json \
  --num-hands 100000 \
  --use-aivat \
  --out eval_runs/blueprint_aivat.json
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

## Evaluation Results

All evaluation results are saved to the `eval_runs/` directory with timestamped JSON files:
- `EVAL_RESULTS_blueprint_vs_baselines_YYYY-MM-DD_HH-MM-SS.json`
- `EVAL_RESULTS_resolve_vs_baselines_YYYY-MM-DD_HH-MM-SS.json`

Each JSON file contains:
- Metadata (timestamp, policy path, configuration)
- bb/100 results with 95% confidence intervals for each baseline
- Latency statistics (for RT search evaluations)
- Full statistical summary

See `EVAL_PROTOCOL.md` for complete evaluation protocol documentation.

