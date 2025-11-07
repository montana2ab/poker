"""Test parallel training functionality."""

import multiprocessing as mp
from pathlib import Path
from holdem.types import MCCFRConfig, BucketConfig
from holdem.abstraction.bucketing import HandBucketing


def test_parallel_config():
    """Test that parallel configuration parameters work."""
    # Test default values
    config = MCCFRConfig()
    assert config.num_workers == 1
    assert config.batch_size == 100
    
    # Test custom values
    config = MCCFRConfig(num_workers=4, batch_size=50)
    assert config.num_workers == 4
    assert config.batch_size == 50
    
    # Test auto-detect (0 means use all cores)
    config = MCCFRConfig(num_workers=0)
    assert config.num_workers == 0


def test_parallel_solver_init():
    """Test that parallel solver initializes correctly."""
    from holdem.mccfr.parallel_solver import ParallelMCCFRSolver
    
    # Create mock bucketing
    bucket_config = BucketConfig(k_preflop=24, k_flop=80, k_turn=80, k_river=64)
    bucketing = HandBucketing(bucket_config)
    bucketing.fitted = True  # Mark as fitted to avoid actual training
    
    # Test with explicit worker count
    config = MCCFRConfig(num_iterations=100, num_workers=2, batch_size=10)
    solver = ParallelMCCFRSolver(config, bucketing, num_players=2)
    assert solver.num_workers == 2
    
    # Test with auto-detect
    config = MCCFRConfig(num_iterations=100, num_workers=0, batch_size=10)
    solver = ParallelMCCFRSolver(config, bucketing, num_players=2)
    assert solver.num_workers == mp.cpu_count()
    
    # Test with single worker (should work like sequential)
    config = MCCFRConfig(num_iterations=100, num_workers=1, batch_size=10)
    solver = ParallelMCCFRSolver(config, bucketing, num_players=2)
    assert solver.num_workers == 1


def test_search_config_parallel():
    """Test parallel search configuration."""
    from holdem.types import SearchConfig
    
    # Test default
    config = SearchConfig()
    assert config.num_workers == 1
    
    # Test custom
    config = SearchConfig(num_workers=2)
    assert config.num_workers == 2


def test_cpu_count():
    """Test that we can detect CPU count."""
    num_cores = mp.cpu_count()
    assert num_cores >= 1
    print(f"Detected {num_cores} CPU cores")


if __name__ == "__main__":
    print("Testing parallel training configuration...")
    test_parallel_config()
    print("✓ Parallel config test passed")
    
    print("\nTesting parallel solver initialization...")
    test_parallel_solver_init()
    print("✓ Parallel solver init test passed")
    
    print("\nTesting search config...")
    test_search_config_parallel()
    print("✓ Search config test passed")
    
    print("\nTesting CPU detection...")
    test_cpu_count()
    print("✓ CPU detection test passed")
    
    print("\n✅ All tests passed!")
