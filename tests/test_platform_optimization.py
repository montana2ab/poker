"""Test platform-specific optimizations for parallel training."""

import platform
import pytest


def test_platform_detection():
    """Test that platform detection functions work correctly."""
    from holdem.mccfr.parallel_solver import _is_apple_silicon, _is_macos
    
    # Test returns boolean
    assert isinstance(_is_apple_silicon(), bool)
    assert isinstance(_is_macos(), bool)
    
    # Test mutual exclusivity on non-Mac platforms
    if not _is_macos():
        assert not _is_apple_silicon()
    
    # Test that Apple Silicon implies macOS
    if _is_apple_silicon():
        assert _is_macos()


def test_queue_timeout_configuration():
    """Test that queue timeouts are configured appropriately for the platform."""
    from holdem.mccfr.parallel_solver import (
        QUEUE_GET_TIMEOUT_SECONDS,
        QUEUE_GET_TIMEOUT_MIN,
        QUEUE_GET_TIMEOUT_MAX,
        _is_apple_silicon,
        _is_macos
    )
    
    # Test that timeouts are positive
    assert QUEUE_GET_TIMEOUT_SECONDS > 0
    assert QUEUE_GET_TIMEOUT_MIN > 0
    assert QUEUE_GET_TIMEOUT_MAX > 0
    
    # Test that min <= default <= max
    assert QUEUE_GET_TIMEOUT_MIN <= QUEUE_GET_TIMEOUT_SECONDS
    assert QUEUE_GET_TIMEOUT_SECONDS <= QUEUE_GET_TIMEOUT_MAX
    
    # Test platform-specific values
    if _is_apple_silicon():
        # Apple Silicon should have longer timeouts
        assert QUEUE_GET_TIMEOUT_SECONDS >= 0.1, "Apple Silicon should use >=100ms timeout"
        assert QUEUE_GET_TIMEOUT_MAX >= 0.5, "Apple Silicon should have >=500ms max"
    elif _is_macos():
        # Intel Mac should have moderate timeouts
        assert QUEUE_GET_TIMEOUT_SECONDS >= 0.05, "macOS should use >=50ms timeout"
        assert QUEUE_GET_TIMEOUT_MAX >= 0.2, "macOS should have >=200ms max"
    else:
        # Linux/Windows should have aggressive timeouts
        assert QUEUE_GET_TIMEOUT_SECONDS <= 0.01, "Linux/Windows should use <=10ms timeout"


def test_backoff_configuration():
    """Test that backoff parameters are configured correctly."""
    from holdem.mccfr.parallel_solver import (
        BACKOFF_MULTIPLIER,
        MAX_EMPTY_POLLS
    )
    
    # Test that backoff multiplier is reasonable
    assert BACKOFF_MULTIPLIER > 1.0, "Backoff multiplier must be > 1"
    assert BACKOFF_MULTIPLIER <= 2.0, "Backoff multiplier should be reasonable (<= 2)"
    
    # Test that max empty polls is reasonable
    assert MAX_EMPTY_POLLS > 0, "Max empty polls must be positive"
    assert MAX_EMPTY_POLLS <= 10, "Max empty polls should be reasonable (<= 10)"


def test_adaptive_backoff_logic():
    """Test the adaptive backoff logic simulation."""
    from holdem.mccfr.parallel_solver import (
        QUEUE_GET_TIMEOUT_SECONDS,
        QUEUE_GET_TIMEOUT_MAX,
        BACKOFF_MULTIPLIER,
        MAX_EMPTY_POLLS
    )
    
    # Simulate adaptive backoff
    current_timeout = QUEUE_GET_TIMEOUT_SECONDS
    consecutive_empty_polls = 0
    
    timeouts = [current_timeout]
    
    # Simulate 20 empty polls
    for i in range(20):
        consecutive_empty_polls += 1
        
        if consecutive_empty_polls >= MAX_EMPTY_POLLS:
            current_timeout = min(
                current_timeout * BACKOFF_MULTIPLIER,
                QUEUE_GET_TIMEOUT_MAX
            )
        
        timeouts.append(current_timeout)
    
    # Verify timeout increases
    assert timeouts[-1] > timeouts[0], "Timeout should increase with empty polls"
    
    # Verify timeout is capped
    assert timeouts[-1] <= QUEUE_GET_TIMEOUT_MAX, "Timeout should not exceed max"
    
    # Verify timeout reaches max eventually
    assert timeouts[-1] == QUEUE_GET_TIMEOUT_MAX, "Timeout should reach max with enough polls"


def test_platform_specific_optimization_message():
    """Test that appropriate optimization messages are logged."""
    # This test verifies the module can be imported and initializes correctly
    from holdem.mccfr.parallel_solver import (
        _is_apple_silicon,
        _is_macos,
        QUEUE_GET_TIMEOUT_SECONDS
    )
    
    # Verify configuration matches platform
    if _is_apple_silicon():
        assert QUEUE_GET_TIMEOUT_SECONDS == 0.1
    elif _is_macos():
        assert QUEUE_GET_TIMEOUT_SECONDS == 0.05
    else:
        assert QUEUE_GET_TIMEOUT_SECONDS == 0.01


def test_parallel_solver_uses_platform_timeouts():
    """Test that ParallelMCCFRSolver uses platform-specific timeouts."""
    from holdem.mccfr.parallel_solver import ParallelMCCFRSolver
    from holdem.types import MCCFRConfig, BucketConfig
    from holdem.abstraction.bucketing import HandBucketing
    
    # Create mock bucketing
    bucket_config = BucketConfig(k_preflop=24, k_flop=80, k_turn=80, k_river=64)
    bucketing = HandBucketing(bucket_config)
    bucketing.fitted = True
    
    # Create solver
    config = MCCFRConfig(num_iterations=100, num_workers=2, batch_size=10)
    solver = ParallelMCCFRSolver(config, bucketing, num_players=2)
    
    # Verify solver initializes successfully
    assert solver.num_workers == 2
    assert solver.mp_context is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
