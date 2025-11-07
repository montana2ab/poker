# Summary: Multiprocessing Queue Deadlock Fix

## Issue Report
User reported that when running `train_blueprint` with `--num-workers 2`, the training would start but CPU usage would drop to 0% after an initial spike, indicating the worker processes were hanging.

## Root Cause
**Classic Producer-Consumer Deadlock**

The original code in `parallel_solver.py` had this problematic sequence:
1. Start worker processes that compute MCCFR iterations
2. Wait for ALL workers to complete using `p.join()`
3. Only then collect results from the queue

This caused a deadlock because:
- Workers finish their work and try to `queue.put()` large result dictionaries
- Queue buffer has limited size and fills up
- Workers block on `put()` waiting for space in the queue
- Main process is stuck in `join()` waiting for workers to exit
- **DEADLOCK**: Main waits for workers, workers wait for queue space

## Solution
**Collect Results While Workers Are Running**

Changed the sequence to:
1. Start worker processes
2. **Immediately start collecting results from queue** using `queue.get(timeout=1.0)`
3. As results arrive, queue space is freed for workers to continue
4. Join workers after all results collected (workers already done by then)

## Key Code Changes

### Before (Deadlock):
```python
# Wait for workers to complete
for p in workers:
    p.join(timeout=timeout_seconds)

# Then collect results
results = []
while not result_queue.empty():
    results.append(result_queue.get())
```

### After (Fixed):
```python
# Collect results WHILE workers are running
results = []
while len(results) < num_workers:
    try:
        result = result_queue.get(timeout=1.0)
        results.append(result)
    except queue.Empty:
        pass

# Join workers (already done)
for p in workers:
    p.join(timeout=10)
```

## Files Modified
- `src/holdem/mccfr/parallel_solver.py` - Fixed the deadlock in `train()` method
- `tests/test_queue_deadlock_fix.py` - Comprehensive tests
- `demo_queue_deadlock_fix.py` - Interactive demonstration
- `QUEUE_DEADLOCK_FIX.md` - Detailed documentation

## Testing
- Created tests that simulate large results that would trigger deadlock
- Test with multiple workers to verify the fix
- All tests pass
- Code review: All feedback addressed
- Security scan: 0 alerts (passed)

## Verification
Users can now run with multiple workers without deadlock:
```bash
python -m holdem.cli.train_blueprint \
  --num-workers 2 \
  --batch-size 100 \
  --config configs/blueprint_training_5h_parallel.yaml \
  ...
```

Workers will maintain steady CPU usage without dropping to 0%.

## Impact
- **Fixes**: Critical deadlock preventing multi-worker training
- **Performance**: No negative impact, potentially faster since workers don't block
- **Compatibility**: Works with all worker counts (1, 2, 4, 8, etc.)
- **Safety**: Specific exception handling, proper timeout, worker monitoring

## Related Documentation
- Python multiprocessing docs warn about this exact issue
- Common pitfall when using Process + Queue together
- Solution is standard pattern: consume from queue while producers run
