# Queue Deadlock Fix - Quick Reference

## What Was Fixed
Parallel training with `--num-workers 2` or more was hanging with CPU usage dropping to 0%.

## Why It Happened
**Producer-Consumer Deadlock**: Main process waited for workers to finish before reading their results from the queue. When the queue buffer filled up, workers blocked trying to send results, creating a deadlock.

## The Solution (One Line)
**Collect results from queue WHILE workers are running, not after.**

## Files in This Fix

### Core Fix
- **`src/holdem/mccfr/parallel_solver.py`** - The actual fix (lines 344-383)

### Documentation
- **`QUEUE_DEADLOCK_FIX.md`** - Comprehensive technical explanation
- **`FIX_SUMMARY.md`** - Executive summary
- **`DEADLOCK_DIAGRAM.txt`** - Visual diagram showing old vs new approach
- **`README_QUEUE_FIX.md`** - This file

### Testing & Demo
- **`tests/test_queue_deadlock_fix.py`** - Test suite verifying the fix
- **`demo_queue_deadlock_fix.py`** - Interactive demonstration script

## Before & After

### Before (Deadlock)
```python
# Start workers
for worker_id in range(num_workers):
    p = mp.Process(target=worker_process, ...)
    p.start()

# Wait for workers (BLOCKS HERE if queue full!)
for p in workers:
    p.join()

# Then collect results
results = []
while not queue.empty():
    results.append(queue.get())
```

### After (Fixed)
```python
# Start workers
for worker_id in range(num_workers):
    p = mp.Process(target=worker_process, ...)
    p.start()

# Collect results WHILE workers run
results = []
while len(results) < num_workers:
    try:
        result = queue.get(timeout=1.0)
        results.append(result)
    except queue.Empty:
        pass

# Join workers (already done)
for p in workers:
    p.join(timeout=10)
```

## How to Test

### Run the Demo
```bash
python demo_queue_deadlock_fix.py
```

### Run the Tests
```bash
pytest tests/test_queue_deadlock_fix.py -v
```

### Test Real Training
```bash
python -m holdem.cli.train_blueprint \
  --config configs/blueprint_training_5h_parallel.yaml \
  --time-budget 28800 \
  --snapshot-interval 1200 \
  --buckets assets/abstraction/buckets_mid.pkl \
  --logdir /tmp/test_parallel \
  --tensorboard \
  --num-workers 2 \
  --batch-size 100
```

**Expected Result**: Workers maintain steady CPU usage, no drop to 0%

## Technical Details

### What Changed
1. Moved result collection to happen BEFORE worker join
2. Use `queue.get(timeout=1.0)` in a loop to collect as results arrive
3. Added timeout and error handling
4. Monitor workers for unexpected death during collection

### Why This Works
- Main process continuously drains the queue
- Workers never block on `put()` because space is always available
- By the time all results collected, workers are already done
- Join becomes a formality (timeout 10s instead of 300s)

### Performance Impact
- **None negative** - same amount of work, no added overhead
- **Potentially faster** - workers don't block on queue operations

### Compatibility
- Works with any `--num-workers` value (1, 2, 4, 8, etc.)
- Works with time-budget or iteration-based training
- Cross-platform (Mac, Linux, Windows)
- Backward compatible with existing checkpoints

## Related Resources

### Python Documentation
This is a known issue in Python's multiprocessing:
> "Joining processes that use queues: Bear in mind that a process that has put items in a queue will wait before terminating until all the buffered items are fed by the 'feeder' thread to the underlying pipe."

### Common Pattern
The solution (consume while producing) is the standard pattern for multiprocessing with queues.

## Questions?

### Q: Will this work with 1 worker?
**A**: Yes, it works fine. With 1 worker, the deadlock was less likely but the fix still applies.

### Q: What if I have many workers (8+)?
**A**: Works perfectly. The fix handles any number of workers.

### Q: Does this change checkpoint format?
**A**: No, checkpoint format is unchanged.

### Q: Can I resume old training runs?
**A**: Yes, all existing checkpoints work fine.

### Q: What about memory usage?
**A**: No change. Results are collected one at a time, not all at once.

## Security
CodeQL scan: **0 alerts** ✅

## Code Quality
- ✅ PEP 8 compliant
- ✅ Specific exception handling (`queue.Empty`)
- ✅ All code review feedback addressed
- ✅ Comprehensive test coverage
- ✅ Well documented

## Status
**COMPLETE** - Ready for production use
