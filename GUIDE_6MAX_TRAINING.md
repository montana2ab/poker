# Multi-Player (6-max) Training Guide

This guide explains how to train and use the poker AI for multi-player games, specifically 6-max (6-player) poker.

## Overview

The system now supports 2-6 player games with full 6-max position support:
- **BTN** (Button) - Best position, acts last postflop
- **SB** (Small Blind) - Acts first postflop (worst position)
- **BB** (Big Blind) - Acts second postflop
- **UTG** (Under The Gun) - First to act preflop
- **MP** (Middle Position) - Middle position
- **CO** (Cutoff) - Second best position, one before button

## Quick Start

### 1. Build 6-max Buckets

```bash
python -m holdem.cli.build_buckets \
  --num-players 6 \
  --hands 500000 \
  --k-preflop 24 \
  --k-flop 80 \
  --k-turn 80 \
  --k-river 64 \
  --out buckets/6max_buckets.pkl
```

### 2. Train 6-max Blueprint

Using configuration file:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/6max_training.yaml \
  --buckets buckets/6max_buckets.pkl \
  --logdir logs/6max_training
```

Or using command-line arguments:

```bash
python -m holdem.cli.train_blueprint \
  --num-players 6 \
  --iters 5000000 \
  --buckets buckets/6max_buckets.pkl \
  --logdir logs/6max_training \
  --checkpoint-interval 250000 \
  --epsilon 0.6 \
  --num-workers 0
```

### 3. Monitor Training

```bash
tensorboard --logdir logs/6max_training/tensorboard
```

## Configuration

### Number of Players

The `num_players` parameter must be consistent across:
1. **Bucket building** (`--num-players` in `build_buckets`)
2. **Training configuration** (`num_players` in config YAML or `--num-players` CLI)
3. **Bucketing config** (`num_players` in `BucketConfig`)

Valid values: 2, 3, 4, 5, or 6

### Example Configurations

#### Heads-Up (2-player)
```yaml
bucket:
  num_players: 2
mccfr:
  num_players: 2
  num_iterations: 2500000
```

#### 3-max
```yaml
bucket:
  num_players: 3
mccfr:
  num_players: 3
  num_iterations: 3000000
```

#### 6-max
```yaml
bucket:
  num_players: 6
mccfr:
  num_players: 6
  num_iterations: 5000000
```

## Training Recommendations

### Iteration Counts

The required number of iterations increases with player count:
- **2 players (HU)**: 2.5M - 5M iterations
- **3 players**: 3M - 6M iterations
- **4-5 players**: 4M - 8M iterations
- **6 players (6-max)**: 5M - 10M iterations

### Memory Requirements

Memory usage increases with player count:
- **2 players**: ~4-8 GB RAM
- **3 players**: ~6-10 GB RAM
- **6 players**: ~12-20 GB RAM

Use chunked training for memory-constrained environments:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/6max_training.yaml \
  --buckets buckets/6max_buckets.pkl \
  --logdir logs/6max_training \
  --chunked \
  --chunk-iterations 500000
```

### Parallel Training

For 6-max, parallel training is highly recommended:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/6max_training.yaml \
  --buckets buckets/6max_buckets.pkl \
  --logdir logs/6max_training \
  --num-workers 0  # Use all CPU cores
  --batch-size 100
```

## Position-Aware Features

The system automatically adjusts for multi-player scenarios:

### Action Abstraction
- **Street-specific bet sizing**: Different sizing for flop/turn/river
- **Position-aware actions**: IP gets more options than OOP
- **Multi-way pot adjustments**: Bet sizing accounts for multiple opponents

### Hand Bucketing
- **Opponent count**: Features adjust based on `num_opponents = num_players - 1`
- **Position context**: Buckets consider relative position
- **Equity calculation**: Multi-way equity computed against N-1 opponents

### Real-time Search
- **Belief tracking**: Maintains ranges for all opponents
- **Subgame construction**: Handles multi-way pots
- **KL regularization**: Position-aware regularization weights

## Backward Compatibility

All changes are **opt-in** and **backward compatible**:
- Default `num_players=2` maintains heads-up behavior
- Existing checkpoints continue to work for 2-player
- No breaking changes to existing APIs

## Advanced: Mixed Training

You can train policies for different player counts, but they are **not compatible**:
- Train separate blueprints for each player count
- Do not mix buckets/checkpoints between different player counts
- Each configuration needs its own bucket file

## Examples

### Complete 6-max Workflow

```bash
# 1. Build buckets for 6-max
python -m holdem.cli.build_buckets \
  --num-players 6 \
  --out buckets/6max.pkl

# 2. Train blueprint (8 days time budget)
python -m holdem.cli.train_blueprint \
  --config configs/6max_training.yaml \
  --buckets buckets/6max.pkl \
  --logdir logs/6max_8d \
  --time-budget 691200  # 8 days in seconds

# 3. Monitor training
tensorboard --logdir logs/6max_8d/tensorboard

# 4. Export policy (after training)
python -m holdem.cli.export_policy \
  --checkpoint logs/6max_8d/checkpoint_final.pkl \
  --out policies/6max_policy.json
```

### Resume Training

```bash
python -m holdem.cli.train_blueprint \
  --config configs/6max_training.yaml \
  --buckets buckets/6max.pkl \
  --logdir logs/6max_training \
  --resume-from logs/6max_training/checkpoint_2500000.pkl
```

## Performance Tips

1. **Use all CPU cores**: Set `num_workers: 0` for automatic core detection
2. **Adjust batch size**: Larger batches (100-200) improve parallel efficiency
3. **Enable pruning**: Pluribus-style pruning reduces computation significantly
4. **Use epsilon schedule**: Adaptive exploration improves convergence
5. **Monitor metrics**: Watch TensorBoard for regret slope and policy entropy

## Troubleshooting

### "Unsupported number of players" Error
- Ensure `num_players` is between 2 and 6
- Check that bucket and training configs match

### "Buckets not built yet" Error
- Build buckets before training: `build_buckets` CLI
- Verify bucket file path is correct

### "Bucket validation failed" Error
- Ensure bucket `num_players` matches training config
- Don't reuse buckets between different player counts

### High Memory Usage
- Use chunked training: `--chunked --chunk-iterations 500000`
- Reduce number of parallel workers
- Consider smaller bucket counts (k values)

## References

- **Pluribus Paper**: "Superhuman AI for multiplayer poker" (Brown & Sandholm, 2019)
- **External Sampling**: More stable for multi-player games
- **Action Abstraction**: [ACTION_ABSTRACTION_FIX_SUMMARY.md](../ACTION_ABSTRACTION_FIX_SUMMARY.md)
- **Bucketing**: [GUIDE_CREATION_BUCKETS.md](../GUIDE_CREATION_BUCKETS.md)

## Support

For issues or questions:
- GitHub Issues: https://github.com/montana2ab/poker/issues
- Discussions: https://github.com/montana2ab/poker/discussions
