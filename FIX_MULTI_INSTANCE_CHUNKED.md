# Fix Summary: Multi-Instance Chunked Training

## Problem
When using `--num-instances 5 --chunked --chunk-minutes 10`, only 1 instance was launched instead of 5.

## Root Cause
In `src/holdem/cli/train_blueprint.py`, the conditional checks were in the wrong order:

```python
# OLD ORDER (BUG):
# 1. Check chunked mode first (line 187)
if config.enable_chunked_training:
    # This matched when both --chunked and --num-instances were specified
    coordinator = ChunkedTrainingCoordinator(...)  # Single instance only!
    coordinator.run()
    return 0

# 2. Check multi-instance second (line 211)
if args.num_instances is not None:
    # This code was NEVER reached when --chunked was also specified
    coordinator = MultiInstanceCoordinator(num_instances=5, ...)
    coordinator.train()
    return 0
```

## Solution
Reordered the conditionals to check multi-instance mode **before** chunked mode:

```python
# NEW ORDER (FIXED):
# 1. Check multi-instance first (line 186)
if args.num_instances is not None:
    # Now this matches first when both flags are present
    coordinator = MultiInstanceCoordinator(num_instances=5, ...)
    # The coordinator internally handles chunked mode for each instance
    coordinator.train()
    return result

# 2. Check chunked mode second (line 214)
if config.enable_chunked_training:
    # Only matches for single-instance chunked mode
    coordinator = ChunkedTrainingCoordinator(...)
    coordinator.run()
    return 0
```

## Why This Works
The `MultiInstanceCoordinator` already has built-in logic to handle chunked mode for each instance (see `multi_instance_coordinator.py` lines 170-200):

```python
# Inside MultiInstanceCoordinator._run_solver_instance()
if instance_config.enable_chunked_training:
    from holdem.mccfr.chunked_coordinator import ChunkedTrainingCoordinator
    coordinator = ChunkedTrainingCoordinator(...)
    coordinator.run()
```

So when you use `--num-instances 5 --chunked --chunk-minutes 10`:
1. Routes to `MultiInstanceCoordinator` with 5 instances
2. Each instance checks `config.enable_chunked_training` and runs in chunked mode
3. All 5 instances launch and train in parallel
4. Each instance restarts after its chunk to free RAM

## Changes Made

### File: `src/holdem/cli/train_blueprint.py`
- Lines 186-237: Reordered conditional checks
- Added explanatory comments
- Added informative logging when both modes are combined

### Diff:
```diff
 # Load buckets
 logger.info(f"Loading buckets from {args.buckets}")
 bucketing = HandBucketing.load(args.buckets)
 
+# Multi-instance mode: Launch multiple independent solver instances
+# Note: This check must come before chunked mode check, because multi-instance
+# coordinator can handle chunked mode for each instance internally
+if args.num_instances is not None:
+    logger.info("=" * 60)
+    logger.info(f"MULTI-INSTANCE MODE: Launching {args.num_instances} independent solver instances")
+    if config.enable_chunked_training:
+        logger.info("CHUNKED TRAINING: Each instance will run in chunked mode")
+    ...
+    return result
+
 # Chunked training mode: Run training in chunks with process restart
+# Note: Single-instance chunked mode (when --num-instances is not specified)
 if config.enable_chunked_training:
     ...
     return 0
 
-# Multi-instance mode: Launch multiple independent solver instances
-if args.num_instances is not None:
-    ...
-    return result
```

## Testing

### Tests Passed:
✅ `tests/test_chunked_multi_instance.py` (4/4 tests pass)
✅ `tests/test_multi_instance_cli_validation.py` (5/5 tests pass)
✅ CodeQL security scan (0 alerts)

### Scenarios Verified:

| Scenario | Args | Expected Behavior | Result |
|----------|------|-------------------|--------|
| Problem case | `--num-instances 5 --chunked --chunk-minutes 10` | 5 instances in chunked mode | ✅ FIXED |
| Single chunked | `--chunked --chunk-minutes 10` | 1 instance in chunked mode | ✅ Works |
| Multi no chunked | `--num-instances 3` | 3 instances normal mode | ✅ Works |
| Standard | (no flags) | 1 instance normal mode | ✅ Works |

## Impact

### Before Fix:
```bash
python -m holdem.cli.train_blueprint \
  --num-instances 5 --chunked --chunk-minutes 10 \
  --buckets data/buckets.pkl --logdir runs/test

# Output: Only 1 instance launched ❌
```

### After Fix:
```bash
python -m holdem.cli.train_blueprint \
  --num-instances 5 --chunked --chunk-minutes 10 \
  --buckets data/buckets.pkl --logdir runs/test

# Output: All 5 instances launched ✅
# Each instance runs in chunked mode ✅
# Each instance restarts after 10 minutes to free RAM ✅
```

## No Breaking Changes

All existing functionality continues to work:
- ✅ Single-instance chunked mode (`--chunked` alone)
- ✅ Multi-instance without chunked (`--num-instances` alone)
- ✅ Standard single-instance mode (no flags)
- ✅ All CLI argument combinations

## Summary

This was a simple but critical fix. By reordering the conditional checks, we ensure that multi-instance mode is handled correctly even when combined with chunked training. The fix:

1. **Minimal change**: Only reordered existing code blocks
2. **No new logic**: Uses existing coordinator capabilities
3. **Well-tested**: All existing tests pass
4. **No security issues**: CodeQL scan found 0 alerts
5. **Backward compatible**: No breaking changes to existing functionality

The user's command will now work as expected, launching 5 parallel instances that each run in chunked mode.
