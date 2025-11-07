#!/usr/bin/env python3
"""
Test to verify that queue blocking is properly handled with timeouts.

This test simulates workers sending large results to verify that:
1. Workers don't block indefinitely when queue is slow to consume
2. Main process actively consumes results even with large data
3. System handles concurrent result submissions gracefully
"""

import multiprocessing as mp
import queue
import time
from typing import Dict


def worker_with_large_result(worker_id: int, task_queue: mp.Queue, result_queue: mp.Queue, 
                              result_size: int = 10000):
    """Worker that produces large results to stress-test queue handling."""
    print(f"Worker {worker_id}: Started")
    
    while True:
        try:
            task = task_queue.get(timeout=0.01)
        except queue.Empty:
            continue
        
        if task is None:
            print(f"Worker {worker_id}: Shutdown signal received")
            break
        
        print(f"Worker {worker_id}: Processing task...")
        
        # Simulate computation
        work_start = time.time()
        computation_result = 0
        for _ in range(1000):
            computation_result += sum(range(1000))
        
        # Create large result (simulating regret/strategy updates)
        large_result = {
            'worker_id': worker_id,
            'computation_result': computation_result,
            'large_data': {f'infoset_{i}': {'action_0': i * 1.5, 'action_1': i * 2.5} 
                           for i in range(result_size)},
            'work_duration': time.time() - work_start
        }
        
        print(f"Worker {worker_id}: Completed computation in {time.time() - work_start:.3f}s, sending result...")
        
        # Try to put result with timeout (like the fix)
        put_start = time.time()
        try:
            result_queue.put(large_result, timeout=10.0)
            put_duration = time.time() - put_start
            print(f"Worker {worker_id}: Successfully sent result (put took {put_duration:.3f}s)")
        except queue.Full:
            print(f"Worker {worker_id}: ERROR - Queue full after 10s timeout!")
            result_queue.put({'worker_id': worker_id, 'error': 'Queue full'}, block=False)
    
    print(f"Worker {worker_id}: Exiting")


def main():
    """Test queue handling with multiple workers sending large results."""
    print("="*70)
    print("Queue Blocking Test with Large Results")
    print("="*70)
    print("\nThis test verifies that:")
    print("  1. Workers can send large results without blocking indefinitely")
    print("  2. Main process can collect results even when they're large")
    print("  3. Multiple workers don't cause queue deadlock")
    print()
    
    # Test parameters
    num_workers = 4
    result_size = 5000  # Number of infosets to simulate
    
    ctx = mp.get_context('spawn')
    task_queue = ctx.Queue()
    result_queue = ctx.Queue()
    
    print(f"Starting {num_workers} workers with result_size={result_size}...")
    
    # Start workers
    workers = []
    for i in range(num_workers):
        p = ctx.Process(target=worker_with_large_result, 
                       args=(i, task_queue, result_queue, result_size))
        p.start()
        workers.append(p)
        print(f"  Started worker {i} (PID {p.pid})")
    
    time.sleep(0.5)  # Let workers initialize
    
    # Send tasks to all workers
    print(f"\nDispatching tasks to {num_workers} workers...")
    for i in range(num_workers):
        task_queue.put({'task_id': i})
        time.sleep(0.001)  # Small stagger
    
    # Collect results with short timeout (like the fix)
    print("\nCollecting results...")
    results = []
    start_time = time.time()
    timeout = 30
    
    while len(results) < num_workers:
        if time.time() - start_time > timeout:
            print(f"ERROR: Timeout after {timeout}s, only got {len(results)}/{num_workers} results")
            break
        
        try:
            result = result_queue.get(timeout=0.01)
            results.append(result)
            if 'error' in result:
                print(f"  Received ERROR from worker {result['worker_id']}: {result.get('error')}")
            else:
                data_size = len(result.get('large_data', {}))
                print(f"  Received result from worker {result['worker_id']} (data size: {data_size} items)")
        except queue.Empty:
            pass
    
    collection_time = time.time() - start_time
    print(f"\nCollected {len(results)}/{num_workers} results in {collection_time:.3f}s")
    
    # Shutdown workers
    print("\nShutting down workers...")
    for _ in range(num_workers):
        task_queue.put(None)
    
    for i, p in enumerate(workers):
        p.join(timeout=5)
        if p.is_alive():
            print(f"  Worker {i} did not exit cleanly, terminating...")
            p.terminate()
            p.join()
    
    # Check results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    if len(results) == num_workers:
        errors = [r for r in results if 'error' in r]
        if errors:
            print(f"✗ FAILED: {len(errors)} workers reported errors")
            for r in errors:
                print(f"    Worker {r['worker_id']}: {r['error']}")
        else:
            print(f"✓ SUCCESS: All {num_workers} workers completed successfully")
            print(f"  Collection time: {collection_time:.3f}s")
            return True
    else:
        print(f"✗ FAILED: Only collected {len(results)}/{num_workers} results")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
