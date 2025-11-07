"""Test that the queue deadlock fix works correctly.

This test verifies that workers can complete successfully even when
putting large results in the queue, which previously caused deadlock.
"""

import multiprocessing as mp
import time
import pytest
from pathlib import Path
from holdem.types import MCCFRConfig, BucketConfig
from holdem.abstraction.bucketing import HandBucketing


def test_queue_no_deadlock_with_large_results():
    """Test that large results don't cause queue deadlock.
    
    This simulates the scenario where workers put large result dictionaries
    in the queue. The old implementation would deadlock because it waited
    for workers to join before reading the queue.
    """
    mp_context = mp.get_context('spawn')
    
    def worker_with_large_result(worker_id, queue):
        """Worker that puts a large result in queue."""
        # Create a large result similar to what MCCFR workers produce
        large_result = {
            'worker_id': worker_id,
            'utilities': list(range(1000)),  # Large list
            'regret_updates': {f'infoset_{i}': {'action_0': float(i)} for i in range(1000)},
            'strategy_updates': {f'infoset_{i}': {'action_0': float(i)} for i in range(1000)},
            'success': True,
            'error': None
        }
        queue.put(large_result)
    
    # Create queue and start multiple workers
    result_queue = mp_context.Queue()
    workers = []
    num_workers = 2
    
    for i in range(num_workers):
        p = mp_context.Process(target=worker_with_large_result, args=(i, result_queue))
        p.start()
        workers.append(p)
    
    # Collect results while workers are running (NEW APPROACH)
    results = []
    timeout = 10
    start_time = time.time()
    
    while len(results) < num_workers:
        if time.time() - start_time > timeout:
            pytest.fail(f"Timeout waiting for results after {timeout}s")
        
        try:
            result = result_queue.get(timeout=1.0)
            results.append(result)
        except Exception:
            pass
    
    # Join workers (should be quick since they already finished)
    for p in workers:
        p.join(timeout=5)
        assert not p.is_alive(), f"Worker {p.pid} still alive"
    
    # Verify results
    assert len(results) == num_workers
    for i, result in enumerate(results):
        assert result['success'] is True
        assert result['worker_id'] in [0, 1]
        assert len(result['utilities']) == 1000


def test_parallel_solver_no_deadlock():
    """Test that ParallelMCCFRSolver doesn't deadlock with multiple workers.
    
    This is a more comprehensive test that verifies the actual parallel solver
    can run a few iterations without deadlocking.
    """
    from holdem.mccfr.parallel_solver import ParallelMCCFRSolver
    
    # Create minimal config for quick test
    config = MCCFRConfig(
        num_iterations=20,  # Just 20 iterations for quick test
        checkpoint_interval=1000,  # No checkpoint during test
        discount_interval=1000,
        num_workers=2,
        batch_size=10,  # Small batch to make test fast
        tensorboard_log_interval=1000  # No tensorboard logging during test
    )
    
    # Create minimal bucketing (small buckets for fast test)
    bucket_config = BucketConfig(
        k_preflop=8,
        k_flop=20,
        k_turn=20,
        k_river=20,
        num_samples=10,
        seed=42
    )
    bucketing = HandBucketing(bucket_config)
    
    # Initialize solver
    solver = ParallelMCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    # Run training - this should complete without deadlock
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # This should complete in reasonable time without deadlocking
        start_time = time.time()
        try:
            solver.train(logdir=logdir, use_tensorboard=False)
            elapsed = time.time() - start_time
            
            # Should complete in under 60 seconds for just 20 iterations
            assert elapsed < 60, f"Training took too long: {elapsed}s (possible deadlock)"
            
            # Verify training actually ran
            assert solver.iteration == 20
            
        except Exception as e:
            pytest.fail(f"Training failed with error: {e}")


@pytest.mark.timeout(30)
def test_worker_result_collection_order():
    """Test that results can be collected in any order from multiple workers."""
    mp_context = mp.get_context('spawn')
    
    def delayed_worker(worker_id, delay, queue):
        """Worker that sleeps before putting result."""
        time.sleep(delay)
        queue.put({'worker_id': worker_id, 'success': True})
    
    result_queue = mp_context.Queue()
    workers = []
    
    # Start workers with different delays (reverse order completion)
    delays = [0.3, 0.2, 0.1]
    for i, delay in enumerate(delays):
        p = mp_context.Process(target=delayed_worker, args=(i, delay, result_queue))
        p.start()
        workers.append(p)
    
    # Collect results as they arrive
    results = []
    start_time = time.time()
    
    while len(results) < len(workers):
        if time.time() - start_time > 5:
            pytest.fail("Timeout collecting results")
        
        try:
            result = result_queue.get(timeout=1.0)
            results.append(result)
        except Exception:
            pass
    
    # Join workers
    for p in workers:
        p.join(timeout=2)
        assert not p.is_alive()
    
    # Verify we got all results (order may vary)
    assert len(results) == 3
    worker_ids = [r['worker_id'] for r in results]
    assert set(worker_ids) == {0, 1, 2}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
