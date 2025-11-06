# Blueprint Training Time-Budget Mode

This document explains the new time-budget based training mode for blueprint strategy training.

## Overview

The blueprint training system now supports two modes:

1. **Iteration-based mode** (original): Train for a fixed number of iterations
2. **Time-budget mode** (new): Train for a specified amount of time (e.g., 8 days CPU time)

## Features

### Time-Budget Training
- Specify training duration in seconds (e.g., 691200s for 8 days)
- Automatic time management and progress tracking
- Training stops when time budget is reached

### Automatic Snapshots
- Save policy snapshots at regular intervals (e.g., every 10 minutes)
- Snapshots include:
  - Overall average policy
  - Per-street policies (preflop, flop, turn, river)
  - Metadata with metrics

### Enhanced Metrics
Each checkpoint and snapshot includes:
- Average regret per street (preflop, flop, turn, river)
- Percentage of pruned iterations
- Iterations per second (throughput)
- Total iterations completed
- Number of information sets

### Regular Discounting
- Apply Linear MCCFR discounting at configurable intervals
- Separate discount factors for regrets (α) and strategy (β)
- Configured via `discount_interval` parameter

## Usage

### Using YAML Configuration

Create a configuration file (e.g., `my_config.yaml`):

```yaml
# Time-budget mode (8 days CPU time)
time_budget_seconds: 691200

# Snapshot configuration
snapshot_interval_seconds: 600  # Every 10 minutes

# Discount configuration
discount_interval: 1000
regret_discount_alpha: 1.0
strategy_discount_beta: 1.0

# Exploration
exploration_epsilon: 0.6

# Pruning
enable_pruning: true
pruning_threshold: -300000000.0
pruning_probability: 0.95
```

Then run:

```bash
./bin/holdem-train-blueprint \
  --config my_config.yaml \
  --buckets path/to/buckets.pkl \
  --logdir path/to/logs
```

### Using Command-Line Arguments

#### Time-Budget Mode

```bash
./bin/holdem-train-blueprint \
  --time-budget 691200 \
  --snapshot-interval 600 \
  --buckets path/to/buckets.pkl \
  --logdir path/to/logs
```

#### Iteration Mode (Original)

```bash
./bin/holdem-train-blueprint \
  --iters 2500000 \
  --checkpoint-interval 100000 \
  --buckets path/to/buckets.pkl \
  --logdir path/to/logs
```

### Combining YAML and CLI Arguments

CLI arguments override YAML configuration:

```bash
./bin/holdem-train-blueprint \
  --config base_config.yaml \
  --time-budget 86400 \
  --buckets path/to/buckets.pkl \
  --logdir path/to/logs
```

## Time Conversions

Common time budgets:

- 1 hour: `3600` seconds
- 12 hours: `43200` seconds
- 1 day: `86400` seconds
- 8 days: `691200` seconds
- 30 days: `2592000` seconds

## Output Structure

### Time-Budget Mode

```
logdir/
├── snapshots/
│   ├── snapshot_iter10000_t600s/
│   │   ├── avg_policy.pkl
│   │   ├── avg_policy.json
│   │   ├── avg_policy_preflop.json
│   │   ├── avg_policy_flop.json
│   │   ├── avg_policy_turn.json
│   │   ├── avg_policy_river.json
│   │   └── metadata.json
│   ├── snapshot_iter20000_t1200s/
│   │   └── ...
│   └── ...
├── checkpoints/
│   ├── checkpoint_iter100000_t3600s.pkl
│   ├── checkpoint_iter100000_t3600s_metadata.json
│   └── ...
├── tensorboard/
│   └── ...
├── avg_policy.pkl
└── avg_policy.json
```

### Metadata Format

Each snapshot/checkpoint includes a `metadata.json` file:

```json
{
  "iteration": 10000,
  "elapsed_seconds": 600.5,
  "elapsed_hours": 0.17,
  "elapsed_days": 0.007,
  "metrics": {
    "avg_regret_preflop": 123.45,
    "avg_regret_flop": 234.56,
    "avg_regret_turn": 345.67,
    "avg_regret_river": 456.78,
    "pruned_iterations_pct": 15.2,
    "iterations_per_second": 16.65,
    "total_iterations": 10000,
    "num_infosets": 5432
  }
}
```

## Monitoring Training

### Console Output

In time-budget mode, you'll see progress updates:

```
INFO - Iteration 50000 (16.5 iter/s) - Utility: 0.001234 - Elapsed: 3000.1s, Remaining: 688199.9s
```

### TensorBoard

Monitor training progress with TensorBoard:

```bash
tensorboard --logdir path/to/logs/tensorboard
```

Available metrics:
- Training/Utility
- Training/UtilityMovingAvg
- Training/PruningRate
- Performance/IterationsPerSecond

## Best Practices

1. **For long runs (days)**: Use time-budget mode with hourly snapshots
   ```yaml
   time_budget_seconds: 691200  # 8 days
   snapshot_interval_seconds: 3600  # 1 hour
   ```

2. **For development/testing**: Use iteration mode with fewer iterations
   ```yaml
   num_iterations: 100000
   checkpoint_interval: 10000
   ```

3. **Adjust discount interval** based on training length:
   - Short runs (hours): 100-500 iterations
   - Medium runs (days): 1000-5000 iterations
   - Long runs (weeks): 5000-10000 iterations

4. **Monitor pruning rate**: Should be 5-20% for optimal training
   - Too high (>30%): Consider lowering `pruning_threshold`
   - Too low (<5%): Pruning is not effective

## Configuration Reference

### MCCFRConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `time_budget_seconds` | float? | None | Time budget in seconds (None = use iterations) |
| `num_iterations` | int | 2500000 | Number of iterations (used if time_budget is None) |
| `snapshot_interval_seconds` | float | 600 | Snapshot interval in seconds (10 min) |
| `checkpoint_interval` | int | 100000 | Checkpoint interval in iterations |
| `discount_interval` | int | 1000 | Apply discount every N iterations |
| `regret_discount_alpha` | float | 1.0 | Regret discount factor (1.0 = no discount) |
| `strategy_discount_beta` | float | 1.0 | Strategy discount factor (1.0 = no discount) |
| `exploration_epsilon` | float | 0.6 | Exploration probability |
| `enable_pruning` | bool | True | Enable dynamic pruning |
| `pruning_threshold` | float | -3e8 | Regret threshold for pruning |
| `pruning_probability` | float | 0.95 | Skip probability when pruning |

## Examples

### 8-Day Training Run

```bash
./bin/holdem-train-blueprint \
  --time-budget 691200 \
  --snapshot-interval 3600 \
  --discount-interval 5000 \
  --buckets data/buckets.pkl \
  --logdir runs/blueprint_8days \
  --tensorboard
```

### Quick Test (1 hour)

```bash
./bin/holdem-train-blueprint \
  --time-budget 3600 \
  --snapshot-interval 300 \
  --discount-interval 500 \
  --buckets data/buckets.pkl \
  --logdir runs/test_1hour
```

### Resume from Checkpoint

Currently, resuming from checkpoints needs to be implemented. For now, start a new run with adjusted time budget to account for previous progress.
