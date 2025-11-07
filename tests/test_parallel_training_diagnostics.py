"""Test parallel training diagnostics and error handling."""

import pytest
import multiprocessing as mp
from pathlib import Path
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing, BucketConfig

# Test timeout constant used across all tests
TEST_TIMEOUT_SECONDS = 5


def test_multiprocessing_context_creation():
    """Test that multiprocessing context can be created."""
    mp_context = mp.get_context('spawn')
    assert mp_context is not None
    assert mp_context.cpu_count() > 0


def test_simple_worker_spawn():
    """Test that a simple worker can be spawned and complete."""
    mp_context = mp.get_context('spawn')
    
    def simple_worker(queue):
        queue.put("success")
    
    test_queue = mp_context.Queue()
    proc = mp_context.Process(target=simple_worker, args=(test_queue,))
    proc.start()
    proc.join(timeout=TEST_TIMEOUT_SECONDS)
    
    assert not proc.is_alive(), "Worker process should have completed"
    assert not test_queue.empty(), "Worker should have put result in queue"
    
    result = test_queue.get()
    assert result == "success"


def test_worker_error_handling():
    """Test that worker errors are properly captured."""
    mp_context = mp.get_context('spawn')
    
    def failing_worker(queue):
        try:
            raise ValueError("Test error")
        except Exception as e:
            queue.put({'error': str(e), 'success': False})
    
    test_queue = mp_context.Queue()
    proc = mp_context.Process(target=failing_worker, args=(test_queue,))
    proc.start()
    proc.join(timeout=TEST_TIMEOUT_SECONDS)
    
    assert not proc.is_alive(), "Worker process should have completed"
    assert not test_queue.empty(), "Worker should have put error result in queue"
    
    result = test_queue.get()
    assert result['success'] is False
    assert 'Test error' in result['error']


def test_parallel_solver_initialization():
    """Test that ParallelMCCFRSolver can be initialized."""
    from holdem.mccfr.parallel_solver import ParallelMCCFRSolver
    
    # Create minimal config
    config = MCCFRConfig(
        num_iterations=100,
        checkpoint_interval=50,
        discount_interval=100,
        num_workers=2,
        batch_size=10
    )
    
    # Create minimal bucketing
    bucket_config = BucketConfig(
        k_preflop=8,
        k_flop=50,
        k_turn=50,
        k_river=50,
        num_samples=10,
        seed=42
    )
    bucketing = HandBucketing(bucket_config)
    
    # Initialize solver - this should not raise
    solver = ParallelMCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    assert solver is not None
    assert solver.num_workers == 2
    assert solver.mp_context is not None


def test_config_with_num_workers():
    """Test MCCFRConfig with various num_workers values."""
    # Test with specific worker count
    config1 = MCCFRConfig(
        num_iterations=100,
        num_workers=4,
        batch_size=20
    )
    assert config1.num_workers == 4
    
    # Test with auto-detect (0)
    config2 = MCCFRConfig(
        num_iterations=100,
        num_workers=0,
        batch_size=20
    )
    assert config2.num_workers == 0
    
    # Test with single process (1)
    config3 = MCCFRConfig(
        num_iterations=100,
        num_workers=1,
        batch_size=20
    )
    assert config3.num_workers == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
