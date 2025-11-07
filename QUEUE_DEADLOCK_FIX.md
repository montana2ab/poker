# Fix: Queue Deadlock in Parallel Training (num_workers > 1)

## Problem Description

When running blueprint training with `--num-workers 2` or higher, the training would start but CPU usage would drop to 0% after an initial spike. The activity monitor would show multiple Python processes that started but were not actively running.

### User Report (Translated from French)
- **With `--num-workers 1`**: No problem, CPU usage goes to 100%, training runs normally
- **With `--num-workers 2`**: Multiple Python processes start, CPU usage spikes initially, then collapses to 0%

This is a classic **multiprocessing queue deadlock** issue.

## Root Cause Analysis

### The Deadlock Scenario

The original code in `parallel_solver.py` had this sequence:

```python
# 1. Start all worker processes
for worker_id in range(num_workers):
    p = mp.Process(target=worker_process, args=(..., result_queue))
    p.start()
    workers.append(p)

# 2. Wait for ALL workers to complete (OLD APPROACH - DEADLOCK!)
for p in workers:
    p.join(timeout=timeout_seconds)

# 3. Then collect results from queue
results = []
while not result_queue.empty():
    results.append(result_queue.get())
```

**Why this causes a deadlock:**

1. Workers complete their MCCFR iterations and create large result dictionaries containing:
   - Utilities (list of floats)
   - Regret updates (dict with thousands of infosets)
   - Strategy updates (dict with thousands of infosets)

2. Workers try to `queue.put(result)` to send results back to main process

3. **Queue buffer has limited size** - when results are large, the queue buffer fills up

4. When buffer is full, `queue.put()` **blocks** waiting for space

5. Worker process **cannot exit** until `put()` completes

6. Main process is stuck in `p.join()` **waiting for worker to exit**

7. **DEADLOCK**: Main waits for worker to exit, worker waits for queue space

### Why It Works with `--num-workers 1`

With a single worker, there's less contention for queue space and the single result may fit in the buffer before it fills up. The deadlock is much less likely to occur.

### Why It Fails with `--num-workers 2` or More

With multiple workers trying to put large results simultaneously:
- Queue buffer fills up quickly
- Workers block on `put()` waiting for main to read
- Main is waiting for workers in `join()` instead of reading
- Instant deadlock

## The Solution

The fix is simple but critical: **Read from the queue WHILE workers are running**, not after waiting for them to complete.

### New Approach

```python
# 1. Start all worker processes (same as before)
for worker_id in range(num_workers):
    p = mp.Process(target=worker_process, args=(..., result_queue))
    p.start()
    workers.append(p)

# 2. Collect results WHILE workers are running (NEW APPROACH)
results = []
while len(results) < num_workers:
    try:
        result = result_queue.get(timeout=1.0)
        results.append(result)
    except queue.Empty:
        pass  # Queue empty, keep waiting

# 3. Join workers (should be quick since they already finished)
for p in workers:
    p.join(timeout=10)
```

**Why this works:**

1. Main process immediately starts reading from queue
2. As soon as a worker puts a result, main reads it → queue space freed
3. Worker's `put()` completes → worker can exit
4. No blocking, no deadlock
5. By the time all results are collected, workers are already done or nearly done

## Changes Made

### File: `src/holdem/mccfr/parallel_solver.py`

Modified the `train()` method around line 342-383:

**Before:**
```python
# Wait for all workers to complete with timeout
for p in workers:
    p.join(timeout=timeout_seconds)

# Collect results from all workers
results = []
while not result_queue.empty():
    results.append(result_queue.get())
```

**After:**
```python
# Collect results while workers are running to avoid queue deadlock
results = []
timeout_seconds = max(WORKER_TIMEOUT_MIN_SECONDS, iterations_per_worker * WORKER_TIMEOUT_MULTIPLIER)
start_wait_time = time.time()

while len(results) < self.num_workers:
    # Check if timeout exceeded
    if time.time() - start_wait_time > timeout_seconds:
        logger.error(f"Timeout waiting for worker results after {timeout_seconds}s")
        break
    
    # Try to get result from queue with short timeout
    try:
        result = result_queue.get(timeout=1.0)
        results.append(result)
        logger.debug(f"Collected result from worker {result['worker_id']} ({len(results)}/{self.num_workers})")
    except queue.Empty:
        pass
    
    # Check if any worker has died unexpectedly
    for p in workers:
        if not p.is_alive() and p.exitcode is not None and p.exitcode != 0:
            logger.error(f"Worker process {p.pid} died with exit code {p.exitcode}")

# Now join all workers (they should be done or nearly done)
for p in workers:
    p.join(timeout=10)
```

### Key Improvements

1. **Non-blocking collection**: Uses `queue.get(timeout=1.0)` in a loop
2. **Active monitoring**: Checks for worker crashes while collecting results
3. **Timeout handling**: Prevents infinite wait if something goes wrong
4. **Debug logging**: Logs each result as it's collected
5. **Quick join**: Workers already finished, so join is fast

## Testing

### New Test File: `tests/test_queue_deadlock_fix.py`

Created comprehensive tests:

1. **`test_queue_no_deadlock_with_large_results()`**
   - Tests that large results don't cause deadlock
   - Simulates the exact scenario that was failing

2. **`test_parallel_solver_no_deadlock()`**
   - Full integration test with ParallelMCCFRSolver
   - Runs actual training with 2 workers
   - Verifies completion without deadlock

3. **`test_worker_result_collection_order()`**
   - Tests that results can be collected in any order
   - Verifies workers with different completion times work correctly

### Demo Script: `demo_queue_deadlock_fix.py`

Interactive demonstration showing:
- The old approach and why it can deadlock
- The new approach and how it prevents deadlock
- Side-by-side comparison

Run with: `python demo_queue_deadlock_fix.py`

## Verification

To verify the fix works:

```bash
# This should now work without deadlock
python -m holdem.cli.train_blueprint \
  --config configs/blueprint_training_5h_parallel.yaml \
  --time-budget 28800 \
  --snapshot-interval 1200 \
  --buckets assets/abstraction/buckets_mid.pkl \
  --logdir /Volumes/122/Blueprintmid_8h_v3 \
  --tensorboard \
  --num-workers 2 \
  --batch-size 100

# Monitor with activity monitor or top/htop
# You should see:
# - 2 worker Python processes with consistent CPU usage
# - No drop to 0% usage after initial spike
# - Steady progress through iterations
```

## Related Issues

This issue is related to the classic **producer-consumer deadlock** in multiprocessing:
- Workers are producers (putting results in queue)
- Main process is consumer (getting results from queue)
- If consumer waits for producers to finish before consuming, deadlock occurs

This is documented in Python's multiprocessing documentation:
> "Joining processes that use queues: Bear in mind that a process that has put items in a queue will wait before terminating until all the buffered items are fed by the 'feeder' thread to the underlying pipe. However, if you try to join that process you may get a deadlock unless you are sure that all items which have been put on the queue have been consumed."

## Additional Notes

### Performance Impact

The fix has **no negative performance impact**:
- Results are collected as they arrive (same total time)
- No additional overhead from the loop (1 second timeout is reasonable)
- Workers can complete without blocking (potentially faster!)

### Compatibility

The fix is compatible with:
- All values of `--num-workers` (1, 2, 4, 8, etc.)
- Both time-budget and iteration-based training
- All existing checkpoints and configurations
- Mac, Linux, and Windows (cross-platform)

### Future Improvements

Possible future enhancements:
1. Use `multiprocessing.Queue.qsize()` to monitor queue fill level
2. Adaptive timeout based on expected result size
3. Progress bar showing worker completion status
4. Separate queues per worker to avoid contention

## Summary

**Problem**: Queue deadlock with `--num-workers > 1` causing CPU usage to drop to 0%

**Root Cause**: Main process waited for workers to join before reading queue, workers blocked on queue.put() when buffer filled

**Solution**: Collect results from queue WHILE workers are running, not after

**Result**: Parallel training now works reliably with any number of workers

**Files Modified**:
- `src/holdem/mccfr/parallel_solver.py` (train method)
- `tests/test_queue_deadlock_fix.py` (new tests)
- `demo_queue_deadlock_fix.py` (demonstration script)
