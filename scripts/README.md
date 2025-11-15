# Experimentation Scripts

This directory contains scripts for running experiments and comparisons.

## Available Scripts

### `compare_buckets_training.py`
Train multiple bucket configurations for comparison.

**Usage:**
```bash
python scripts/compare_buckets_training.py --configs A B --iters 100000 --output experiments/
```

See `ABSTRACTION_EXPERIMENTS.md` for detailed usage.

### `compare_buckets_eval.py`
Evaluate and compare trained bucket configurations head-to-head.

**Usage:**
```bash
python scripts/compare_buckets_eval.py --experiment experiments/ --hands 10000
```

See `ABSTRACTION_EXPERIMENTS.md` for detailed usage.

## Documentation

For complete documentation on running abstraction experiments, see:
- [ABSTRACTION_EXPERIMENTS.md](../ABSTRACTION_EXPERIMENTS.md)

For testing, see:
- [tests/test_abstraction_experiments.py](../tests/test_abstraction_experiments.py)
