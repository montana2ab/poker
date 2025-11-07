#!/usr/bin/env python3
"""
Demonstration script showing the queue deadlock issue and fix.

This script demonstrates the deadlock that occurs when:
1. Workers put large results in a queue
2. Main process waits for workers to join BEFORE reading the queue
3. Queue buffer fills up, workers block on put(), deadlock occurs

The fix is to read from the queue WHILE workers are running.
"""

import multiprocessing as mp
import time
import sys


def worker_with_large_result(worker_id, queue):
    """Simulates an MCCFR worker that produces a large result."""
    print(f"Worker {worker_id}: Starting work...")
    time.sleep(0.5)  # Simulate some computation
    
    # Create a large result (similar to MCCFR regret/strategy updates)
    large_result = {
        'worker_id': worker_id,
        'data': list(range(10000)),  # Large data that may fill queue buffer
        'regrets': {f'infoset_{i}': {'action': float(i)} for i in range(5000)},
    }
    
    print(f"Worker {worker_id}: Putting result in queue...")
    queue.put(large_result)  # This may block if queue is full!
    print(f"Worker {worker_id}: Result queued, exiting")


def demonstrate_deadlock_problem():
    """Shows the OLD approach that causes deadlock."""
    print("\n" + "="*70)
    print("DEMONSTRATION: OLD APPROACH (Deadlock Risk)")
    print("="*70)
    
    mp_context = mp.get_context('spawn')
    result_queue = mp_context.Queue()
    workers = []
    
    # Start 2 workers
    for i in range(2):
        p = mp_context.Process(target=worker_with_large_result, args=(i, result_queue))
        p.start()
        workers.append(p)
        print(f"Main: Started worker {i} (PID: {p.pid})")
    
    print("\nMain: Waiting for workers to join (OLD APPROACH - POTENTIAL DEADLOCK)...")
    print("      If queue buffer fills, workers block on put() and can't exit!")
    print("      But we're waiting for them to exit before reading queue...")
    
    # OLD APPROACH: Wait for workers to complete BEFORE reading queue
    # This can deadlock if workers block on queue.put()
    start_time = time.time()
    timeout = 5
    
    for p in workers:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            print(f"\n⚠️  TIMEOUT! Worker {p.pid} did not complete in {timeout}s")
            print("    This indicates a DEADLOCK - worker waiting for queue space,")
            print("    main process waiting for worker to exit.")
            p.terminate()
            p.join()
            return False
        
        p.join(timeout=remaining)
        if p.is_alive():
            print(f"\n⚠️  DEADLOCK DETECTED! Worker {p.pid} still alive after {timeout}s")
            p.terminate()
            p.join()
            return False
    
    # Now read results (but workers already had to complete)
    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    
    elapsed = time.time() - start_time
    print(f"\n✓ Workers completed in {elapsed:.2f}s (no deadlock this time)")
    print(f"  Got {len(results)} results")
    return True


def demonstrate_fixed_approach():
    """Shows the NEW approach that avoids deadlock."""
    print("\n" + "="*70)
    print("DEMONSTRATION: NEW APPROACH (Deadlock-Free)")
    print("="*70)
    
    mp_context = mp.get_context('spawn')
    result_queue = mp_context.Queue()
    workers = []
    
    # Start 2 workers
    for i in range(2):
        p = mp_context.Process(target=worker_with_large_result, args=(i, result_queue))
        p.start()
        workers.append(p)
        print(f"Main: Started worker {i} (PID: {p.pid})")
    
    print("\nMain: Collecting results WHILE workers run (NEW APPROACH)...")
    print("      Workers can put results without blocking!")
    
    # NEW APPROACH: Read from queue WHILE workers are running
    results = []
    timeout = 10
    start_time = time.time()
    num_workers = len(workers)
    
    while len(results) < num_workers:
        if time.time() - start_time > timeout:
            print(f"\n⚠️  TIMEOUT after {timeout}s")
            break
        
        try:
            result = result_queue.get(timeout=1.0)
            results.append(result)
            print(f"Main: Collected result from worker {result['worker_id']} ({len(results)}/{num_workers})")
        except Exception:
            # Queue empty, keep waiting
            pass
    
    print("\nMain: All results collected, now joining workers...")
    
    # Join workers (should be quick since they already finished)
    for p in workers:
        p.join(timeout=2)
        if p.is_alive():
            print(f"⚠️  Worker {p.pid} still alive!")
            p.terminate()
            p.join()
        else:
            print(f"✓ Worker {p.pid} joined successfully")
    
    elapsed = time.time() - start_time
    print(f"\n✓ Workers completed in {elapsed:.2f}s")
    print(f"  Got {len(results)} results")
    return True


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PARALLEL TRAINING QUEUE DEADLOCK - DEMONSTRATION")
    print("="*70)
    print("\nThis demonstrates the deadlock issue that occurs with num_workers > 1")
    print("and the fix that resolves it.")
    
    # Note: The old approach may or may not deadlock depending on queue buffer size
    # and result size. With large enough results, it will deadlock.
    
    print("\n\nPress Enter to see the OLD approach (potential deadlock)...")
    input()
    old_success = demonstrate_deadlock_problem()
    
    print("\n\nPress Enter to see the NEW approach (deadlock-free)...")
    input()
    new_success = demonstrate_fixed_approach()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Old approach: {'✓ Completed' if old_success else '✗ Deadlocked'}")
    print(f"New approach: {'✓ Completed' if new_success else '✗ Failed'}")
    print("\nThe FIX: Collect results from queue WHILE workers are running,")
    print("not after waiting for them to join. This prevents queue buffer")
    print("from filling up and causing workers to block on put().")
    print("="*70)
