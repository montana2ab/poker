# Automatic Chunk Restart Feature

## Overview

The chunked training mode now supports **automatic restart** after each chunk completes. This eliminates the need to manually restart the training process when using time-based chunks.

## How It Works

### Before (Manual Restart Required)
Previously, when using `--chunked --chunk-minutes 10`, the training would:
1. Run for 10 minutes
2. Save checkpoint
3. Exit with message: "Restart this command to continue training from checkpoint"
4. **Require manual restart** by the user

### After (Automatic Restart)
Now, the training automatically:
1. Runs for 10 minutes (one chunk)
2. Saves checkpoint
3. **Automatically restarts** from the checkpoint
4. Continues until training completion criteria is met (time budget or iteration limit)

## Usage Example

```bash
python -m holdem.cli.train_blueprint \
  --config configs/smoke_test_30m.yaml \
  --buckets assets/abstraction/buckets_mid_street.pkl \
  --logdir "$RUN" \
  --tensorboard \
  --num-instances 5 \
  --chunked \
  --chunk-minutes 25 \
  --chunk-restart-delay 5.0 \  # Optional: delay between restarts (default: 5s)
  --time-budget 28800  # 8 hours
```

With this configuration:
- Each instance runs chunks of 25 minutes
- After each 25-minute chunk:
  - Checkpoint is saved
  - Memory is freed by recreating the solver
  - Training **automatically continues** from the checkpoint
- This loops until the 8-hour time budget is reached
- No manual intervention needed!

## Benefits

1. **Memory Management**: Each chunk restart releases memory, preventing memory leaks
2. **Robustness**: Regular checkpoints protect against crashes
3. **Convenience**: No need to manually restart training
4. **Continuous Training**: Seamless progression across chunks
5. **Progress Tracking**: Real-time updates every 100 iterations or 10 seconds

## Progress Tracking

The progress tracking now correctly shows:
- **Time-based mode**: 
  - Current iteration
  - Elapsed time
  - Time budget
  - Percentage complete based on time
  
- **Iteration-based mode**:
  - Current iteration
  - Target iteration
  - Percentage complete based on iterations

Example output:
```
[11/10/25 23:21:52] INFO     ============================================================
                    INFO     Overall Progress: 16.7%
                    INFO     ------------------------------------------------------------
                    INFO     Instance 0: ▶️ 16.7% (elapsed 600s/3600s, iter 612)
                    INFO     Instance 1: ▶️ 16.5% (elapsed 595s/3600s, iter 585)
                    INFO     Instance 2: ▶️ 16.4% (elapsed 592s/3600s, iter 592)
                    INFO     Instance 3: ▶️ 16.8% (elapsed 603s/3600s, iter 603)
                    INFO     Instance 4: ▶️ 16.3% (elapsed 586s/3600s, iter 586)
                    INFO     ============================================================
```

## Technical Details

### Implementation
- `ChunkedTrainingCoordinator.run()` now contains a `while True` loop
- Loop continues until `_is_training_complete()` returns `True`
- Each iteration:
  1. Loads latest checkpoint (if any)
  2. Runs one chunk of training
  3. Saves checkpoint
  4. Checks completion criteria
  5. Either breaks (if complete) or continues to next chunk

### Completion Criteria
Training stops when:
- **Time-budget mode**: `cumulative_elapsed_seconds >= time_budget_seconds`
- **Iteration mode**: `current_iteration >= num_iterations`
- **User interrupt**: Ctrl+C (saves checkpoint before exiting)

### Memory Management
Each chunk restart:
1. Releases the old solver object
2. Creates a new solver instance
3. Loads checkpoint with full state
4. Continues training seamlessly

This prevents memory accumulation over long training runs.

## Interruption Handling

You can safely interrupt training at any time with Ctrl+C:
- Current chunk checkpoint is saved
- Progress is recorded
- Training can be resumed by restarting the command
- All state is preserved in the checkpoint

## Compatibility

This feature is compatible with:
- ✅ Multi-instance mode (`--num-instances`)
- ✅ Time-budget mode (`--time-budget`)
- ✅ Iteration-based mode (`--iters`)
- ✅ Time-based chunks (`--chunk-minutes`)
- ✅ Iteration-based chunks (`--chunk-iterations`)
- ✅ TensorBoard logging (`--tensorboard`)

## Notes

- The automatic restart happens in the same process (no subprocess spawning)
- Each restart has a configurable delay (default: 5 seconds) to allow RAM to be fully freed by the OS
  - Use `--chunk-restart-delay <seconds>` to customize this delay
  - Increase the delay if RAM is not being freed quickly enough on your system
- Progress tracking updates every 100 iterations or 10 seconds
- All RNG state, epsilon schedules, and discount factors are preserved across chunks
- Cumulative elapsed time is properly tracked across chunk restarts for accurate time-budget enforcement
