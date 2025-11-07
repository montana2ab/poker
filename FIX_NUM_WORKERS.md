# Fix Summary: --num-workers Flag Issue on Mac M2

## Problem Description
When launching blueprint training with YAML configuration (specifically `blueprint_training_5h.yaml`) and specifying the number of workers via the `--num-workers` command-line flag, the training did not start properly - the activity monitor remained flat (no CPU usage). However, when running without specifying `--num-workers`, the training worked correctly and used 2 threads by default.

**Important**: The problem occurred specifically when using `--num-workers` with `configs/blueprint_training_5h.yaml`, which does not have `num_workers` defined in the YAML file itself.

## Root Cause
The issue was caused by the improper use of `mp.set_start_method('spawn', force=True)` in two files:
- `src/holdem/mccfr/parallel_solver.py` (line 172)
- `src/holdem/realtime/parallel_resolver.py` (line 157)

The problem occurred because:
1. The multiprocessing context was already initialized in the `__init__` method (when calling `mp.cpu_count()`)
2. Later, in the `train()` method, the code tried to reset the start method with `force=True`
3. This caused conflicts that prevented worker processes from starting properly

## Solution
Replaced the global `mp.set_start_method('spawn', force=True)` approach with a context-based approach using `mp.get_context('spawn')`:

1. **Created a persistent context**: Initialize `self.mp_context = mp.get_context('spawn')` once in `__init__`
2. **Updated all multiprocessing calls**: Changed `mp.Queue()` to `self.mp_context.Queue()` and `mp.Process()` to `self.mp_context.Process()`
3. **Removed the problematic set_start_method call**: No longer needed since we use an explicit context

## Benefits
- ✅ Avoids conflicts with already-initialized multiprocessing context
- ✅ More explicit and predictable behavior
- ✅ Cross-platform compatible (Mac/Linux)
- ✅ Works with any value of `--num-workers` (1, 2, 4, 0 for auto-detect, etc.)
- ✅ No breaking changes - existing code continues to work

## Usage Examples

### Original problematic command (NOW FIXED):
```bash
# This was NOT working before the fix
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training_5h.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/5h_test \
    --num-workers 4 \
    --batch-size 100
```

### Training with specific number of workers:
```bash
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/parallel_4cores \
    --num-workers 4 \
    --batch-size 100
```

### Training with auto-detect (use all CPU cores):
```bash
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/parallel_all_cores \
    --num-workers 0 \
    --batch-size 100
```

### Training in YAML config:
```yaml
# configs/blueprint_training_5h_parallel.yaml (NEW FILE)
time_budget_seconds: 18000  # 5 hours
snapshot_interval_seconds: 900
num_workers: 4  # or 0 for auto-detect
batch_size: 100
# ... other config ...
```

Then run:
```bash
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training_5h_parallel.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/5h_parallel
```

**Note**: A new optimized config file `configs/blueprint_training_5h_parallel.yaml` has been created with `num_workers` pre-configured.

## Testing
- ✅ Verified multiprocessing context creation works correctly
- ✅ Tested with various `num_workers` values (1, 2, 4, 0)
- ✅ Confirmed Queue and Process creation via context
- ✅ Code review completed - no issues found
- ✅ Security scan (CodeQL) - no vulnerabilities found

## Files Modified
1. `src/holdem/mccfr/parallel_solver.py`
   - Added `self.mp_context = mp.get_context('spawn')` in `__init__`
   - Updated `mp.cpu_count()` to `self.mp_context.cpu_count()`
   - Updated `mp.Queue()` to `self.mp_context.Queue()`
   - Updated `mp.Process()` to `self.mp_context.Process()`
   - Removed `mp.set_start_method('spawn', force=True)` from `train()`

2. `src/holdem/realtime/parallel_resolver.py`
   - Same changes as above for consistency

## Verification
You can verify the fix works by running:
```bash
# Monitor CPU usage in Activity Monitor (Mac) or top/htop (Linux)
python -m holdem.cli.train_blueprint \
    --config configs/blueprint_training.yaml \
    --buckets assets/abstraction/precomputed_buckets.pkl \
    --logdir runs/test \
    --num-workers 4 \
    --iters 1000

# You should see 4 Python worker processes consuming CPU
```

## Security Summary
No security vulnerabilities were introduced by this change. CodeQL analysis completed successfully with 0 alerts.
