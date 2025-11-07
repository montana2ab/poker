"""Test that the diagnostic test worker function can be pickled.

This test verifies the fix for the multiprocessing pickle error that occurs
when using the 'spawn' start method on macOS M2 systems.
"""

import multiprocessing as mp


def test_diagnostic_worker_is_picklable():
    """Test that _diagnostic_test_worker is at module level and can be pickled."""
    # Import the function
    from holdem.mccfr.parallel_solver import _diagnostic_test_worker
    
    # Verify it's a function
    assert callable(_diagnostic_test_worker), "_diagnostic_test_worker should be callable"
    
    # Verify it can be pickled (this is what happens with spawn)
    import pickle
    pickled = pickle.dumps(_diagnostic_test_worker)
    unpickled = pickle.loads(pickled)
    assert callable(unpickled), "Unpickled function should be callable"


def test_diagnostic_worker_with_spawn_context():
    """Test that _diagnostic_test_worker works with spawn multiprocessing context."""
    from holdem.mccfr.parallel_solver import _diagnostic_test_worker
    
    # Use 'spawn' context (required on macOS)
    mp_context = mp.get_context('spawn')
    test_queue = mp_context.Queue()
    
    # Start process - this will fail if function can't be pickled
    test_proc = mp_context.Process(target=_diagnostic_test_worker, args=(test_queue,))
    test_proc.start()
    test_proc.join(timeout=5)
    
    # Verify process completed
    assert not test_proc.is_alive(), "Worker process should have completed"
    
    # Verify result
    assert not test_queue.empty(), "Worker should have put result in queue"
    result = test_queue.get(timeout=1)
    assert result == "test_success", f"Expected 'test_success', got {result}"
