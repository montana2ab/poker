# Chunked Training Mode

This document explains the chunked training mode for memory-constrained environments and long training runs.

## Overview

Chunked training mode splits long training runs into segments (chunks). At the end of each chunk, the solver:

1. **Saves a complete checkpoint** with all metadata (iteration, RNG state, epsilon, regrets, etc.)
2. **Flushes TensorBoard logs** to ensure no data loss
3. **Terminates the process** to release 100% of RAM
4. **Automatically resumes** from the last checkpoint when restarted

**Key benefit**: No loss of continuity. All state is preserved:
- Global iteration counter (t_global)
- RNG state (reproducibility)
- Exploration epsilon (ε)
- Discount parameters (DCFR α/β)
- Bucket hash (validation)
- Cumulative elapsed time
- Full regret state

## Use Cases

Chunked training is ideal for:

1. **Memory-Constrained Environments**
   - Process restart releases 100% of RAM
   - Prevents memory leaks from accumulating
   - Useful on systems with limited memory

2. **Long Training Runs**
   - Safe interruption points every chunk
   - Training can survive system restarts
   - Easy to pause and resume

3. **Job Schedulers**
   - Compatible with SLURM, PBS, or other batch systems
   - Can split long runs into shorter job slots
   - Automatic continuation across job submissions

4. **Development and Testing**
   - Test long-running training without committing full time
   - Easy to inspect intermediate results
   - Quick iteration on training parameters

## Features

### Chunk Boundaries

Chunks can be defined by:
- **Iterations**: Fixed number of iterations per chunk (e.g., 100k iterations)
- **Time**: Fixed time duration per chunk (e.g., 60 minutes)
- **Hybrid**: Both limits (chunk ends when either is reached first)

### State Preservation

All critical state is preserved across chunks:
- **Iteration counter**: Continues from last checkpoint
- **RNG state**: Ensures reproducibility across chunks
- **Epsilon schedule**: Tracks position in epsilon decay schedule
- **DCFR state**: Preserves discount factors and iteration-dependent parameters
- **Regrets**: Full regret tracker state (warm-start)
- **Strategy sum**: Accumulated strategy for average policy
- **Bucket hash**: Validates bucket compatibility on resume
- **Cumulative time**: Tracks total elapsed time across all chunks

### Automatic Checkpointing

- Checkpoints saved at end of each chunk
- Also saves checkpoints at regular intervals within chunks (if configured)
- Complete checkpoint includes:
  - Policy file (`.pkl`)
  - Metadata file (`_metadata.json`)
  - Regrets file (`_regrets.pkl`)

### TensorBoard Integration

- TensorBoard logs are continuous across chunks
- Logs flushed before process exit
- Resume automatically continues logging to same directory

## Configuration

### In Python

```python
from holdem.types import MCCFRConfig

# Iteration-based chunks
config = MCCFRConfig(
    # Total training
    num_iterations=1_000_000,
    
    # Chunked mode
    enable_chunked_training=True,
    chunk_size_iterations=100_000,  # 100k iterations per chunk
    
    # Regular checkpoints within chunks
    checkpoint_interval=25_000,
    
    # DCFR settings
    discount_mode="dcfr",
    discount_interval=1000,
    
    # Exploration
    exploration_epsilon=0.6,
    enable_pruning=True
)
```

```python
# Time-based chunks
config = MCCFRConfig(
    # Total training
    time_budget_seconds=8 * 24 * 3600,  # 8 days
    
    # Chunked mode
    enable_chunked_training=True,
    chunk_size_minutes=60.0,  # 1 hour per chunk
    
    # Regular snapshots within chunks
    snapshot_interval_seconds=900,  # 15 minutes
    
    # DCFR settings
    discount_mode="dcfr",
    discount_interval=5000,
    
    # Exploration
    exploration_epsilon=0.6,
    enable_pruning=True
)
```

```python
# Hybrid chunks (whichever comes first)
config = MCCFRConfig(
    # Total training
    num_iterations=2_000_000,
    time_budget_seconds=48 * 3600,  # 48 hours
    
    # Chunked mode
    enable_chunked_training=True,
    chunk_size_iterations=50_000,   # 50k iterations OR
    chunk_size_minutes=30.0,        # 30 minutes (whichever first)
    
    # Regular checkpoints
    checkpoint_interval=10_000,
    
    # DCFR settings
    discount_mode="dcfr",
    discount_interval=1000,
    
    # Exploration
    exploration_epsilon=0.6,
    enable_pruning=True
)
```

### In YAML Config

```yaml
# Total training
num_iterations: 1000000

# Chunked training mode
enable_chunked_training: true
chunk_size_iterations: 100000

# Regular checkpoints
checkpoint_interval: 25000

# DCFR discounting
discount_mode: "dcfr"
discount_interval: 1000

# Exploration
exploration_epsilon: 0.6
enable_pruning: true
```

### Via CLI

```bash
# Iteration-based chunks
./bin/holdem-train-blueprint \
  --buckets data/buckets.pkl \
  --logdir runs/chunked_training \
  --iters 1000000 \
  --chunked \
  --chunk-iterations 100000

# Time-based chunks
./bin/holdem-train-blueprint \
  --buckets data/buckets.pkl \
  --logdir runs/chunked_training \
  --time-budget 691200 \
  --chunked \
  --chunk-minutes 60

# Hybrid chunks
./bin/holdem-train-blueprint \
  --buckets data/buckets.pkl \
  --logdir runs/chunked_training \
  --iters 2000000 \
  --time-budget 172800 \
  --chunked \
  --chunk-iterations 50000 \
  --chunk-minutes 30
```

## Usage Workflow

### Initial Run

```bash
# Start training (runs one chunk and exits)
./bin/holdem-train-blueprint \
  --buckets data/buckets.pkl \
  --logdir runs/my_training \
  --iters 1000000 \
  --chunked \
  --chunk-iterations 100000
```

Output:
```
Chunked Training Mode Initialized
Chunk size: 100,000 iterations
Starting fresh training (no checkpoint found)
...
Chunk iteration limit reached: 100000 >= 100000
Saving checkpoint at iteration 100000...
Checkpoint saved successfully
Flushing TensorBoard logs...
Chunk Complete - Process will now exit to free memory
Progress: iteration 100000
Restart this command to continue training from checkpoint
```

### Continue Training

Simply run the same command again:

```bash
# Automatically resumes from checkpoint
./bin/holdem-train-blueprint \
  --buckets data/buckets.pkl \
  --logdir runs/my_training \
  --iters 1000000 \
  --chunked \
  --chunk-iterations 100000
```

Output:
```
Chunked Training Mode Initialized
Chunk size: 100,000 iterations
Resuming from checkpoint: runs/my_training/checkpoints/checkpoint_iter100000.pkl
Successfully resumed from iteration 100000
...
Chunk iteration limit reached: 200000 >= 200000
Saving checkpoint at iteration 200000...
```

### Automate with Loop

For unattended training, use a loop:

```bash
#!/bin/bash
# run_chunked_training.sh

while true; do
    ./bin/holdem-train-blueprint \
        --buckets data/buckets.pkl \
        --logdir runs/my_training \
        --iters 1000000 \
        --chunked \
        --chunk-iterations 100000
    
    # Check exit code
    if [ $? -ne 0 ]; then
        echo "Training failed or interrupted"
        break
    fi
    
    # Optional: Add a small delay between chunks
    sleep 5
done

echo "Training complete or stopped"
```

### Use with Job Scheduler (SLURM)

```bash
#!/bin/bash
#SBATCH --job-name=poker_chunk
#SBATCH --time=01:00:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=4

# Run one chunk (1 hour time limit)
./bin/holdem-train-blueprint \
    --buckets data/buckets.pkl \
    --logdir runs/my_training \
    --time-budget 691200 \
    --chunked \
    --chunk-minutes 55

# Auto-resubmit if training not complete
# Check if training finished
ITER=$(jq '.iteration' runs/my_training/checkpoints/checkpoint_iter*_metadata.json 2>/dev/null | tail -1)
if [ "$ITER" -lt "1000000" ]; then
    sbatch $0  # Resubmit this script
fi
```

## Monitoring

### Check Progress

```bash
# List checkpoints
ls -lth runs/my_training/checkpoints/ | head -5

# View latest checkpoint metadata
cat runs/my_training/checkpoints/checkpoint_iter*_metadata.json | jq
```

### Monitor with TensorBoard

```bash
# TensorBoard logs are continuous across chunks
tensorboard --logdir runs/my_training/tensorboard
```

### Track Cumulative Time

```bash
# Get elapsed time from latest checkpoint
jq '.elapsed_seconds' runs/my_training/checkpoints/checkpoint_iter*_metadata.json | tail -1

# Convert to hours
jq '.elapsed_seconds / 3600' runs/my_training/checkpoints/checkpoint_iter*_metadata.json | tail -1
```

### Check Training Completion

```bash
# Check iteration progress
jq '.iteration' runs/my_training/checkpoints/checkpoint_iter*_metadata.json | tail -1

# Check if time budget reached
jq '.elapsed_seconds' runs/my_training/checkpoints/checkpoint_iter*_metadata.json | tail -1
```

## Technical Details

### Checkpoint Format

Each checkpoint consists of three files:

1. **checkpoint_iterN.pkl** - Policy and strategy data
2. **checkpoint_iterN_metadata.json** - Metadata including:
   - Iteration number
   - Cumulative elapsed time
   - Chunk elapsed time
   - RNG state
   - Epsilon value
   - Discount parameters
   - Bucket configuration hash
   - Performance metrics
3. **checkpoint_iterN_regrets.pkl** - Full regret tracker state

### State Restoration

When resuming from a checkpoint, the coordinator:

1. Finds the most recent complete checkpoint
2. Creates a new solver instance
3. Loads checkpoint data:
   - Restores iteration counter
   - Restores RNG state
   - Restores epsilon value
   - Restores cumulative elapsed time
   - Restores full regret state (warm-start)
   - Validates bucket compatibility
4. Continues training from restored state

### Memory Management

Process restart between chunks ensures:
- All heap memory is freed
- No memory leaks accumulate
- Fresh memory allocation for next chunk
- Consistent memory usage pattern

### Reproducibility

Training is reproducible across chunks because:
- RNG state is saved and restored
- Iteration counter is exact
- All DCFR parameters are preserved
- Bucket configuration is validated

## Examples

See `examples/chunked_training_example.py` for more examples:

```bash
python examples/chunked_training_example.py
```

## Limitations

- Chunked mode is not compatible with multi-instance mode (`--num-instances`)
- Each chunk runs in a single process (chunked mode works best with `num_workers=1`)
- Very short chunks may have overhead from process restart

## Comparison with Standard Training

| Feature | Standard Training | Chunked Training |
|---------|------------------|------------------|
| Memory usage | Grows over time | Reset each chunk |
| Process lifetime | Entire training | One chunk |
| Interruption | Lost progress | Safe at chunk end |
| Resume | Manual checkpoint load | Automatic |
| Monitoring | Continuous | Continuous (via TB) |
| Overhead | None | Small (process restart) |

## Best Practices

1. **Choose appropriate chunk size**
   - Too small: Overhead from restarts
   - Too large: Less frequent memory cleanup
   - Recommended: 50k-100k iterations or 30-60 minutes

2. **Use with TensorBoard**
   - Monitor continuous progress across chunks
   - Verify metrics are smooth across boundaries

3. **Regular checkpoints within chunks**
   - Set `checkpoint_interval` for safety
   - Allows recovery if chunk is interrupted

4. **Validate bucket compatibility**
   - Bucket validation is automatic
   - Ensures correct abstraction across chunks

5. **Monitor disk space**
   - Checkpoints accumulate over training
   - Clean up old checkpoints if needed

## Troubleshooting

### Chunk doesn't complete

Check:
- Sufficient disk space for checkpoints
- Logdir is writable
- No errors in logs

### Training doesn't resume

Check:
- Checkpoint files are complete (3 files per checkpoint)
- Bucket file matches checkpoint
- Logdir path is correct

### Memory still growing

Check:
- Chunk size is appropriate
- Process actually exits between chunks
- No external memory leaks

## See Also

- [CHECKPOINT_FORMAT.md](CHECKPOINT_FORMAT.md) - Checkpoint file format
- [BLUEPRINT_TIME_BUDGET.md](BLUEPRINT_TIME_BUDGET.md) - Time-budget training
- [examples/chunked_training_example.py](examples/chunked_training_example.py) - Usage examples
