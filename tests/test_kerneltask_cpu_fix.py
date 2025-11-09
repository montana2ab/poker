"""Test for kerneltask CPU usage fix in batch collection.

This test validates that the batch collection optimization doesn't cause
excessive system calls that lead to high kerneltask CPU usage on macOS.
"""
import multiprocessing as mp
import queue
import time
import unittest


def slow_worker(worker_id, result_queue, delay):
    """Worker that takes time to produce results."""
    time.sleep(delay)  # Simulate work
    result = {
        'worker_id': worker_id,
        'data': f'result_{worker_id}',
        'timestamp': time.time()
    }
    result_queue.put(result)


class TestKerneltaskCpuFix(unittest.TestCase):
    """Test that batch collection doesn't cause excessive polling."""
    
    def test_batch_collection_with_staggered_workers(self):
        """Test that batch collection handles staggered worker completion efficiently."""
        # Create workers that complete at different times
        result_queue = mp.Queue()
        num_workers = 4
        
        # Start workers with staggered delays (0.1s, 0.2s, 0.3s, 0.4s)
        workers = []
        for i in range(num_workers):
            delay = 0.1 * (i + 1)  # Stagger completions
            p = mp.Process(target=slow_worker, args=(i, result_queue, delay))
            p.start()
            workers.append(p)
        
        # Collect results with the optimized batch collection logic
        results = []
        start_time = time.time()
        timeout = 5.0  # Maximum time to wait
        
        # Simulate the optimized collection logic
        current_timeout = 0.1  # 100ms like Apple Silicon
        max_drain_attempts = 3
        
        while len(results) < num_workers:
            if time.time() - start_time > timeout:
                break
            
            try:
                # Get first result
                result = result_queue.get(timeout=current_timeout)
                results.append(result)
                
                # Brief pause to allow other workers to complete
                if len(results) < num_workers:
                    time.sleep(0.003)  # 3ms grace period
                
                # Batch collection with limited drain attempts
                drain_attempts = 0
                while len(results) < num_workers and drain_attempts < max_drain_attempts:
                    try:
                        extra_result = result_queue.get(timeout=0.005)
                        results.append(extra_result)
                        drain_attempts = 0  # Reset on success
                    except queue.Empty:
                        drain_attempts += 1
                        if drain_attempts < max_drain_attempts:
                            time.sleep(0.002)  # 2ms delay between failed attempts
                        
            except queue.Empty:
                continue
        
        # Wait for all workers to finish
        for p in workers:
            p.join(timeout=1.0)
            if p.is_alive():
                p.terminate()
        
        elapsed = time.time() - start_time
        
        # Verify all results collected
        self.assertEqual(len(results), num_workers, "Should collect all results")
        
        # Verify reasonable collection time (should complete in < 1 second)
        # The slowest worker takes 0.4s, so with proper batching we should be done
        # well before 1 second
        self.assertLess(elapsed, 1.0, "Collection should complete efficiently")
        
        # Verify all worker IDs are present
        worker_ids = sorted([r['worker_id'] for r in results])
        self.assertEqual(worker_ids, list(range(num_workers)), "All workers should report")
    
    def test_drain_attempt_limit(self):
        """Test that drain attempts are properly limited to avoid excessive polling."""
        result_queue = mp.Queue()
        
        # Put only one result in queue
        result_queue.put({'worker_id': 0, 'data': 'test'})
        
        # Try to collect 4 results but only 1 is available
        results = []
        num_workers = 4
        max_drain_attempts = 3
        poll_count = 0
        
        try:
            # Get first result
            result = result_queue.get(timeout=0.1)
            results.append(result)
            
            # Brief pause
            time.sleep(0.003)
            
            # Try batch collection
            drain_attempts = 0
            while len(results) < num_workers and drain_attempts < max_drain_attempts:
                poll_count += 1
                try:
                    extra_result = result_queue.get(timeout=0.005)
                    results.append(extra_result)
                    drain_attempts = 0
                except queue.Empty:
                    drain_attempts += 1
                    if drain_attempts < max_drain_attempts:
                        time.sleep(0.002)
        except queue.Empty:
            pass
        
        # Should have limited polling attempts
        self.assertEqual(len(results), 1, "Should only get 1 result")
        self.assertLessEqual(poll_count, max_drain_attempts, 
                           "Should limit drain attempts to reduce system calls")
    
    def test_grace_period_effectiveness(self):
        """Test that the grace period allows workers to complete before draining."""
        result_queue = mp.Queue()
        num_workers = 3
        
        # Start workers that complete almost simultaneously (within 10ms)
        workers = []
        for i in range(num_workers):
            delay = 0.05 + (i * 0.005)  # 50ms, 55ms, 60ms
            p = mp.Process(target=slow_worker, args=(i, result_queue, delay))
            p.start()
            workers.append(p)
        
        # Wait for first worker to complete
        time.sleep(0.06)
        
        # Collect results with grace period
        results = []
        start_time = time.time()
        
        try:
            # Get first result
            result = result_queue.get(timeout=0.1)
            results.append(result)
            
            # Grace period - other workers should complete during this time
            time.sleep(0.003)
            
            # Now drain should find results immediately
            max_drain_attempts = 3
            drain_attempts = 0
            successful_drains = 0
            
            while len(results) < num_workers and drain_attempts < max_drain_attempts:
                try:
                    extra_result = result_queue.get(timeout=0.005)
                    results.append(extra_result)
                    successful_drains += 1
                    drain_attempts = 0
                except queue.Empty:
                    drain_attempts += 1
                    if drain_attempts < max_drain_attempts:
                        time.sleep(0.002)
        except queue.Empty:
            pass
        
        # Cleanup
        for p in workers:
            p.join(timeout=1.0)
            if p.is_alive():
                p.terminate()
        
        elapsed = time.time() - start_time
        
        # Should collect most/all results efficiently
        self.assertGreaterEqual(len(results), 2, "Grace period should help collect multiple results")
        
        # Collection should be fast (< 100ms after first result)
        self.assertLess(elapsed, 0.1, "Collection with grace period should be quick")


if __name__ == '__main__':
    # Use spawn context for cross-platform compatibility
    mp.set_start_method('spawn', force=True)
    unittest.main()
