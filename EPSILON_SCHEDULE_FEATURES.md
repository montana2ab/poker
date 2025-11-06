# New Features: Epsilon Schedule, TensorBoard Metrics, Snapshot Watcher, and Bucket Validation

This document describes the new features added to the MCCFR training system.

## 1. Epsilon Schedule

### Overview
The epsilon schedule allows you to configure step-based epsilon decay during training. Instead of using a static exploration epsilon value, you can define thresholds where epsilon changes to different values.

### Configuration

Add an `epsilon_schedule` to your YAML config:

```yaml
epsilon_schedule:
  - [0, 0.6]           # Start at 0.6 (iteration 0)
  - [1000000, 0.3]     # Drop to 0.3 at iteration 1M
  - [2000000, 0.1]     # Drop to 0.1 at iteration 2M
```

Format: Each entry is `[iteration_threshold, epsilon_value]`

### How It Works
- The solver automatically updates epsilon during training
- At each iteration, the highest applicable epsilon value is used
- Example: At iteration 500,000, epsilon = 0.6; at iteration 1,500,000, epsilon = 0.3
- Logged to TensorBoard under `Training/Epsilon`

### Command Line
Static epsilon via CLI:
```bash
holdem-train-blueprint --config blueprint_training.yaml --buckets buckets.pkl --logdir ./logs --epsilon 0.5
```

Schedule via YAML (recommended):
```bash
holdem-train-blueprint --config epsilon_schedule_example.yaml --buckets buckets.pkl --logdir ./logs
```

## 2. New TensorBoard Metrics

### Policy Entropy Metrics

Tracks the diversity of the learned policy:

- **`policy_entropy/preflop`**: Average policy entropy for preflop decisions
- **`policy_entropy/flop`**: Average policy entropy for flop decisions
- **`policy_entropy/turn`**: Average policy entropy for turn decisions
- **`policy_entropy/river`**: Average policy entropy for river decisions
- **`policy_entropy/IP`**: Average policy entropy for In Position plays
- **`policy_entropy/OOP`**: Average policy entropy for Out Of Position plays

Higher entropy = more exploratory/mixed strategies
Lower entropy = more deterministic strategies

### Regret Normalization Metrics

Tracks the magnitude of regrets per street:

- **`avg_regret_norm/preflop`**: Average L2 norm of regrets for preflop infosets
- **`avg_regret_norm/flop`**: Average L2 norm of regrets for flop infosets
- **`avg_regret_norm/turn`**: Average L2 norm of regrets for turn infosets
- **`avg_regret_norm/river`**: Average L2 norm of regrets for river infosets

These metrics help monitor convergence - decreasing regret norms indicate the strategy is stabilizing.

### Viewing Metrics

Launch TensorBoard:
```bash
tensorboard --logdir ./logs/tensorboard
```

Then navigate to http://localhost:6006

## 3. Snapshot Watcher

### Overview
The snapshot watcher automatically monitors a snapshot directory and triggers evaluation when new snapshots appear.

### Usage

```bash
holdem-watch-snapshots \
  --snapshot-dir ./logs/snapshots \
  --episodes 10000 \
  --check-interval 60
```

### Parameters
- `--snapshot-dir`: Directory containing training snapshots (required)
- `--episodes`: Number of episodes for evaluation (default: 10000)
- `--check-interval`: Check interval in seconds (default: 60)
- `--eval-script`: Custom evaluation script path (default: holdem-eval-blueprint)

### How It Works
1. Scans the snapshot directory at regular intervals
2. Detects new `snapshot_*` directories
3. Finds the policy file (`avg_policy.pkl` or `avg_policy.json`)
4. Triggers evaluation using `holdem-eval-blueprint`
5. Saves results to `{snapshot_dir}/evaluation/results.json`

### Example Workflow

Terminal 1 - Training:
```bash
holdem-train-blueprint \
  --config blueprint_training.yaml \
  --buckets buckets.pkl \
  --logdir ./logs \
  --time-budget 86400 \
  --snapshot-interval 3600
```

Terminal 2 - Watching:
```bash
holdem-watch-snapshots \
  --snapshot-dir ./logs/snapshots \
  --episodes 20000 \
  --check-interval 300
```

## 4. Bucket Validation Fail-Safe

### Overview
When resuming training from a checkpoint, the system validates that the bucket configuration matches to prevent training with incompatible abstractions.

### Resume Training

```bash
holdem-train-blueprint \
  --config blueprint_training.yaml \
  --buckets buckets.pkl \
  --logdir ./logs \
  --resume-from ./logs/checkpoints/checkpoint_iter1000000.pkl
```

### Validation Process
1. Loads checkpoint metadata
2. Calculates SHA256 hash of current bucket configuration
3. Compares with checkpoint's bucket_sha
4. If mismatch: **Refuses to start** and logs detailed error
5. If match: Continues training from checkpoint

### Error Example
```
ERROR: BUCKET VALIDATION FAILED: Bucket configuration mismatch!
Current SHA: abc123...
Checkpoint SHA: def456...
Cannot resume training with incompatible bucket configuration.
```

### Metadata Included
Both checkpoints and snapshots now include:
- `bucket_file_sha`: SHA256 hash of bucket config
- `k_preflop`, `k_flop`, `k_turn`, `k_river`: Bucket sizes
- `num_samples`, `seed`: Bucket generation parameters

## Complete Example

### Training Configuration (epsilon_schedule_example.yaml)
```yaml
num_iterations: 2500000
checkpoint_interval: 100000

epsilon_schedule:
  - [0, 0.6]
  - [1000000, 0.3]
  - [2000000, 0.1]

use_linear_weighting: true
discount_interval: 1000
tensorboard_log_interval: 1000
```

### Training Command
```bash
holdem-train-blueprint \
  --config configs/epsilon_schedule_example.yaml \
  --buckets assets/abstraction/buckets.pkl \
  --logdir ./training_logs \
  --tensorboard
```

### Monitor Training
```bash
# Terminal 1: TensorBoard
tensorboard --logdir ./training_logs/tensorboard

# Terminal 2: Snapshot Watcher
holdem-watch-snapshots \
  --snapshot-dir ./training_logs/snapshots \
  --episodes 10000
```

### Resume After Interruption
```bash
holdem-train-blueprint \
  --config configs/epsilon_schedule_example.yaml \
  --buckets assets/abstraction/buckets.pkl \
  --logdir ./training_logs \
  --resume-from ./training_logs/checkpoints/checkpoint_iter1000000.pkl
```

## Testing

All features are fully tested:
- `tests/test_epsilon_schedule.py`: Epsilon schedule functionality
- `tests/test_tensorboard_metrics.py`: Policy entropy and regret norm metrics
- `tests/test_bucket_validation.py`: Bucket hash and validation
- `tests/test_snapshot_watcher.py`: Snapshot detection and monitoring

Run tests:
```bash
pytest tests/test_epsilon_schedule.py -v
pytest tests/test_tensorboard_metrics.py -v
pytest tests/test_bucket_validation.py -v
pytest tests/test_snapshot_watcher.py -v
```
