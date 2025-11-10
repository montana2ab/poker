# Multi-Instance Resume Functionality

## Overview

This document describes the new resume functionality added to the multi-instance training mode. Previously, multi-instance mode did not support resuming from checkpoints. Now, you can resume interrupted multi-instance training runs.

## What's New

### ✅ Resume Support Added

- **Before**: `--resume-from` was incompatible with `--num-instances`
- **After**: `--resume-from` works with `--num-instances` to resume interrupted training

### Key Features

1. **Per-Instance Resume**: Each instance resumes from its own latest checkpoint
2. **Graceful Fallback**: If a checkpoint is missing, that instance starts fresh
3. **Checkpoint Validation**: Bucket compatibility is verified before resuming
4. **Progress Continuation**: Training continues from where it was interrupted

## Usage

### Basic Resume Command

```bash
# Original training run
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/training_original \
  --iters 1000000 \
  --num-instances 4 \
  --checkpoint-interval 10000

# [Training interrupted after some iterations]

# Resume from previous run
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/training_resumed \
  --iters 1000000 \
  --num-instances 4 \
  --checkpoint-interval 10000 \
  --resume-from runs/training_original
```

### How It Works

1. **Checkpoint Discovery**: The system scans `runs/training_original/instance_N/checkpoints/` for each instance
2. **Latest Checkpoint**: For each instance, it finds the most recent checkpoint file
3. **Resume Training**: Each instance loads its checkpoint and continues from that iteration
4. **Missing Checkpoints**: If an instance has no checkpoint, it starts from iteration 0

### Directory Structure

```
runs/training_original/
├── progress/
│   ├── instance_0_progress.json
│   ├── instance_1_progress.json
│   └── ...
├── instance_0/
│   └── checkpoints/
│       ├── checkpoint_iter10000.pkl        ← Latest checkpoint found
│       ├── checkpoint_iter10000_metadata.json
│       ├── checkpoint_iter20000.pkl
│       └── checkpoint_iter20000_metadata.json
├── instance_1/
│   └── checkpoints/
│       └── ...
└── ...
```

## Important Considerations

### ⚠️ Configuration Consistency

When resuming, you should use the **same configuration** as the original run:

- Same `--buckets` file (validated automatically)
- Same `--num-instances` count
- Same `--iters` total (or `--time-budget`)
- Same `--checkpoint-interval`

### Iteration Ranges

In iteration-based mode:
- Each instance is assigned a specific iteration range
- On resume, the instance loads its checkpoint and continues from where it stopped
- The iteration counter picks up from the checkpoint

### Time-Budget Mode

In time-budget mode:
- Each instance resumes from its last checkpoint
- The time budget applies from the resume point
- Useful for long-running training that needs to be split across multiple sessions

## Examples

### Example 1: Simple Resume

```bash
# Start training
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/day1 \
  --iters 5000000 \
  --num-instances 8

# [Ctrl+C after a few hours]

# Resume next day
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/day2 \
  --iters 5000000 \
  --num-instances 8 \
  --resume-from runs/day1
```

### Example 2: Resume with Time Budget

```bash
# Initial 24-hour training
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/week1_day1 \
  --time-budget 86400 \
  --num-instances 4 \
  --snapshot-interval 3600

# Resume for another 24 hours
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/week1_day2 \
  --time-budget 86400 \
  --num-instances 4 \
  --snapshot-interval 3600 \
  --resume-from runs/week1_day1
```

### Example 3: Partial Resume (Some Instances Failed)

If some instances failed in the previous run:

```bash
# Previous run where instance 2 failed
# runs/training/instance_0/checkpoints/ ✓ has checkpoints
# runs/training/instance_1/checkpoints/ ✓ has checkpoints
# runs/training/instance_2/checkpoints/ ✗ no checkpoints (failed early)
# runs/training/instance_3/checkpoints/ ✓ has checkpoints

# Resume - instance 2 will start fresh, others will resume
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/training_retry \
  --iters 1000000 \
  --num-instances 4 \
  --resume-from runs/training
```

## Implementation Details

### Modified Files

1. **`src/holdem/mccfr/multi_instance_coordinator.py`**
   - Added `resume_checkpoint` parameter to `_run_solver_instance()`
   - Added `_find_resume_checkpoints()` method
   - Modified `train()` method to accept `resume_from` parameter
   - Updated both time-budget and iteration-based modes

2. **`src/holdem/cli/train_blueprint.py`**
   - Removed validation that prevented `--resume-from` with `--num-instances`
   - Updated help text to mention resume support
   - Modified multi-instance coordinator call to pass `resume_from`

3. **`GUIDE_MULTI_INSTANCE.md`**
   - Updated documentation to reflect resume support
   - Added examples and best practices
   - Updated FAQ section

### Testing

Tests are available in:
- `test_multi_instance_resume.py` - New resume functionality tests
- `test_multi_instance.py` - Updated to reflect time-budget support

Run tests:
```bash
python test_multi_instance_resume.py
python test_multi_instance.py
```

## Troubleshooting

### Checkpoint Not Found

If you see warnings like "No checkpoint directory found for instance N":
- Check that the `--resume-from` directory path is correct
- Verify that the directory contains `instance_N/checkpoints/` subdirectories
- Some instances may start fresh if their checkpoints are missing (this is normal)

### Bucket Validation Failed

If you see "Cannot safely resume training with different bucket configuration":
- Ensure you're using the **exact same buckets file** as the original training
- The bucketing configuration must match for resume to work

### Wrong Number of Instances

If resuming with a different `--num-instances` than the original:
- The system will look for checkpoints based on the new count
- Missing instances will start fresh
- Extra instances from the original run will be ignored
- **Best practice**: Use the same number of instances

## Benefits

1. **Fault Tolerance**: Training can be interrupted and resumed without losing progress
2. **Flexibility**: Split long training runs across multiple sessions
3. **Resource Management**: Stop and resume based on resource availability
4. **Experimentation**: Try different configurations while keeping previous work

## Limitations

1. **Configuration Consistency**: Best results when using the same configuration
2. **Checkpoint Storage**: Requires disk space for all instance checkpoints
3. **Directory Management**: New logdir for each resume (recommended for clarity)

## Future Enhancements

Potential improvements for future versions:
- Automatic checkpoint cleanup (keeping only N latest checkpoints)
- Resume progress summary showing which instances resumed vs. started fresh
- Cross-machine resume support for distributed training
- Checkpoint merging across resumed runs

## References

- Original multi-instance implementation: `IMPLEMENTATION_SUMMARY_MULTI_INSTANCE.md`
- Multi-instance guide: `GUIDE_MULTI_INSTANCE.md`
- MCCFR solver documentation: `DCFR_IMPLEMENTATION.md`
