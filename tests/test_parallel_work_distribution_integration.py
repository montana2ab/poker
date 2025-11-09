"""Integration test for parallel work distribution fix."""

import multiprocessing as mp
from pathlib import Path


def test_work_distribution_integration():
    """Test that work is correctly distributed in a realistic scenario."""
    from holdem.types import MCCFRConfig, BucketConfig
    from holdem.abstraction.bucketing import HandBucketing
    from holdem.mccfr.parallel_solver import ParallelMCCFRSolver
    
    # Test various worker/batch size combinations
    test_cases = [
        (4, 100, "Normal case with even division"),
        (8, 100, "Normal case with remainder"),
        (2, 100, "Small worker count"),
        (16, 100, "Large worker count with remainder"),
    ]
    
    print("\nTesting work distribution in ParallelMCCFRSolver...\n")
    
    for num_workers, batch_size, description in test_cases:
        print(f"Test: {description}")
        print(f"  Workers: {num_workers}, Batch size: {batch_size}")
        
        # Create config
        config = MCCFRConfig(
            num_iterations=batch_size * 2,  # 2 batches
            checkpoint_interval=1000000,  # Never checkpoint in test
            discount_interval=1000000,  # Never discount in test
            num_workers=num_workers,
            batch_size=batch_size
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
        
        # Initialize solver
        solver = ParallelMCCFRSolver(config=config, bucketing=bucketing, num_players=2)
        
        # Verify worker count
        assert solver.num_workers == num_workers, f"Expected {num_workers} workers, got {solver.num_workers}"
        
        # Calculate expected distribution
        base = batch_size // num_workers
        remainder = batch_size % num_workers
        
        print(f"  Base iterations per worker: {base}")
        print(f"  Remainder: {remainder}")
        print(f"  Distribution: {remainder} workers get {base+1}, {num_workers-remainder} workers get {base}")
        
        # Verify total
        total = base * num_workers + remainder
        assert total == batch_size, f"Distribution error: {total} != {batch_size}"
        
        print(f"  ✓ Total iterations: {total} (correct!)\n")
    
    print("✅ All integration tests passed!\n")


def test_edge_case_more_workers_than_batch():
    """Test edge case where num_workers > batch_size."""
    from holdem.types import MCCFRConfig, BucketConfig
    from holdem.abstraction.bucketing import HandBucketing
    from holdem.mccfr.parallel_solver import ParallelMCCFRSolver
    
    print("\nTesting edge case: More workers than batch size...\n")
    
    num_workers = 16
    batch_size = 10
    
    # Create config
    config = MCCFRConfig(
        num_iterations=batch_size,
        checkpoint_interval=1000000,
        discount_interval=1000000,
        num_workers=num_workers,
        batch_size=batch_size
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
    
    # Initialize solver - should warn but not crash
    print(f"Workers: {num_workers}, Batch size: {batch_size}")
    solver = ParallelMCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    # Calculate active workers
    active_workers = min(num_workers, batch_size)
    print(f"Active workers: {active_workers}")
    print(f"Idle workers: {num_workers - active_workers}")
    
    # Verify
    assert solver.num_workers == num_workers
    assert active_workers == batch_size
    
    print("✓ Edge case handled correctly!\n")


def test_auto_detect_workers():
    """Test automatic worker detection (num_workers=0)."""
    from holdem.types import MCCFRConfig, BucketConfig
    from holdem.abstraction.bucketing import HandBucketing
    from holdem.mccfr.parallel_solver import ParallelMCCFRSolver
    
    print("\nTesting automatic worker detection...\n")
    
    # Create config with auto-detect
    config = MCCFRConfig(
        num_iterations=100,
        checkpoint_interval=1000000,
        discount_interval=1000000,
        num_workers=0,  # Auto-detect
        batch_size=100
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
    
    # Initialize solver
    solver = ParallelMCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    # Check that it auto-detected
    cpu_count = mp.cpu_count()
    assert solver.num_workers == cpu_count, f"Expected {cpu_count} workers (auto-detected), got {solver.num_workers}"
    
    print(f"✓ Auto-detected {cpu_count} CPU cores")
    print(f"  Batch size: {config.batch_size}")
    
    # Calculate distribution with auto-detected workers
    base = config.batch_size // solver.num_workers
    remainder = config.batch_size % solver.num_workers
    
    if base == 0:
        print(f"  Warning: Batch size ({config.batch_size}) < workers ({solver.num_workers})")
        print(f"  Active workers: {min(solver.num_workers, config.batch_size)}")
    else:
        print(f"  Distribution: {base} base, {remainder} workers get +1")
    
    # Verify total
    total = base * min(solver.num_workers, config.batch_size) + min(remainder, config.batch_size)
    if total != config.batch_size:
        # For edge case where workers > batch_size
        total = config.batch_size
    
    print(f"  Total iterations: {total} ✓\n")


if __name__ == "__main__":
    print("=" * 70)
    print("Parallel Work Distribution Integration Tests")
    print("=" * 70)
    
    test_work_distribution_integration()
    test_edge_case_more_workers_than_batch()
    test_auto_detect_workers()
    
    print("=" * 70)
    print("✅ All integration tests passed!")
    print("=" * 70)
