# Checkpoint Resume Fix - Implementation Summary

## Problem Statement

When resuming from a checkpoint in multi-instance training mode, the system was selecting the wrong checkpoint files, causing training to restart from iteration 0 instead of continuing from the saved iteration.

### Original Error Logs
```
WARNING - Metadata file not found: /Volumes/122/runs/.../checkpoint_iter22158_t3600s_regrets_metadata.json
WARNING - Cannot restore training state without metadata
INFO - Successfully loaded checkpoint at iteration 0  # ❌ Should be 22158!
```

## Root Cause Analysis

When the `save_checkpoint` method saves training state, it creates **three files**:

1. `checkpoint_iter22158_t3600s.pkl` - Main policy checkpoint file
2. `checkpoint_iter22158_t3600s_metadata.json` - Metadata (iteration, RNG state, epsilon, etc.)
3. `checkpoint_iter22158_t3600s_regrets.pkl` - Full regrets state (for warm-start)

The bug was in `_find_resume_checkpoints` method in `multi_instance_coordinator.py`:

```python
# OLD CODE (buggy)
checkpoint_files = list(checkpoint_dir.glob("checkpoint_*.pkl"))
```

This glob pattern matched **both** files #1 and #3. Since file #3 (`_regrets.pkl`) is created last, it has the latest modification time. When `max(..., key=lambda p: p.stat().st_mtime)` selected it, the code then looked for:

`checkpoint_iter22158_t3600s_regrets_metadata.json` ❌ **DOES NOT EXIST**

But the actual metadata file is:

`checkpoint_iter22158_t3600s_metadata.json` ✅ **EXISTS**

## Solution

Modified the checkpoint discovery to exclude `_regrets.pkl` files:

```python
# NEW CODE (fixed)
checkpoint_files = [
    f for f in checkpoint_dir.glob("checkpoint_*.pkl")
    if not f.stem.endswith("_regrets")  # 🔥 Filter out auxiliary regrets files
]
```

This ensures only main checkpoint files are selected, which have corresponding metadata files.

## Files Changed

### Production Code (1 file, 4 lines changed)
- `src/holdem/mccfr/multi_instance_coordinator.py` - Fixed checkpoint discovery logic

### Test Code (3 files added/updated)
- `tests/test_checkpoint_resume_fix.py` - New comprehensive unit tests
- `test_multi_instance_resume.py` - Updated mock setup
- `manual_test_checkpoint_fix.py` - Integration test simulating exact problem scenario

## Testing Results

### Unit Tests ✅
```
Testing checkpoint selection excludes _regrets.pkl files...
  ✓ Found checkpoints for all instances
  ✓ Instance 0 checkpoint: checkpoint_iter22158_t3600s.pkl (correctly excludes _regrets.pkl)
  ✓ Instance 0 metadata file exists: checkpoint_iter22158_t3600s_metadata.json
  ✓ Instance 1 checkpoint: checkpoint_iter22158_t3600s.pkl (correctly excludes _regrets.pkl)
  ✓ Instance 1 metadata file exists: checkpoint_iter22158_t3600s_metadata.json

Testing selection of latest main checkpoint...
  ✓ Selected latest checkpoint: checkpoint_iter300_t1800s.pkl

Results: 2 passed, 0 failed
```

### Integration Test ✅
```
Simulating 6 instances with exact checkpoint structure from problem...

✅ Instance 0: checkpoint_iter22158_t3600s.pkl
   ✓ Metadata file exists: checkpoint_iter22158_t3600s_metadata.json
✅ Instance 1: checkpoint_iter22001_t3608s.pkl
   ✓ Metadata file exists: checkpoint_iter22001_t3608s_metadata.json
✅ Instance 2: checkpoint_iter22001_t3607s.pkl
   ✓ Metadata file exists: checkpoint_iter22001_t3607s_metadata.json
✅ Instance 3: checkpoint_iter22375_t3600s.pkl
   ✓ Metadata file exists: checkpoint_iter22375_t3600s_metadata.json
✅ Instance 4: checkpoint_iter22217_t3600s.pkl
   ✓ Metadata file exists: checkpoint_iter22217_t3600s_metadata.json
✅ Instance 5: checkpoint_iter22361_t3600s.pkl
   ✓ Metadata file exists: checkpoint_iter22361_t3600s_metadata.json

✅ SUCCESS: All checkpoints correctly selected (no _regrets.pkl)
✅ All metadata files can be found
```

### Existing Tests ✅
```
test_multi_instance_resume.py - Results: 4 passed, 0 failed
```

### Security Scan ✅
```
CodeQL Analysis: 0 alerts found
```

## Impact & Benefits

✅ **Resume now works correctly** - Training continues from saved iteration
✅ **Backward compatible** - No changes to checkpoint saving logic
✅ **Minimal change** - Only 4 lines modified, surgical fix
✅ **Well tested** - Comprehensive test coverage added
✅ **No security issues** - CodeQL analysis passed with 0 alerts

## Usage

The fix is automatic and requires no changes to user code. Simply use the same command that was failing before:

```bash
python -m holdem.cli.train_blueprint \
  --config configs/smoke_test_30m.yaml \
  --buckets assets/abstraction/buckets_mid_street.pkl \
  --logdir "$RUN" \
  --tensorboard \
  --num-instances 6 \
  --resume-from /Volumes/122/runs/blueprint_mid_m2_v2
```

Now it will correctly resume from the saved checkpoint iteration instead of restarting from 0.

## Expected New Logs

After the fix, you should see:

```
INFO - Found checkpoint for instance 0: checkpoint_iter22158_t3600s.pkl
INFO - Resuming instance 0 from checkpoint: .../checkpoint_iter22158_t3600s.pkl
INFO - Successfully loaded checkpoint at iteration 22158  # ✅ Correct!
INFO - Resuming from iteration 22158 to 28800
```

No more metadata warnings, and training continues from the correct iteration! 🎉
