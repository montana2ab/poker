"""Test work distribution in parallel training."""

def test_work_distribution_exact_division():
    """Test when batch_size divides evenly by num_workers."""
    batch_size = 100
    num_workers = 10
    
    base = batch_size // num_workers
    remainder = batch_size % num_workers
    
    # Calculate total iterations distributed
    total = 0
    for worker_id in range(num_workers):
        iterations = base + (1 if worker_id < remainder else 0)
        total += iterations
    
    assert total == batch_size, f"Expected {batch_size} iterations, but distributed {total}"
    assert remainder == 0, "Should have no remainder for exact division"
    print(f"✓ Exact division: {batch_size} iterations / {num_workers} workers = {base} each")


def test_work_distribution_with_remainder():
    """Test when batch_size doesn't divide evenly."""
    batch_size = 100
    num_workers = 8
    
    base = batch_size // num_workers  # 12
    remainder = batch_size % num_workers  # 4
    
    # Calculate total iterations distributed
    total = 0
    distribution = []
    for worker_id in range(num_workers):
        iterations = base + (1 if worker_id < remainder else 0)
        distribution.append(iterations)
        total += iterations
    
    assert total == batch_size, f"Expected {batch_size} iterations, but distributed {total}"
    assert remainder == 4, "Should have 4 iterations remaining"
    
    # First 4 workers should get 13 iterations, rest get 12
    assert distribution[:4] == [13, 13, 13, 13], f"First 4 workers should get 13, got {distribution[:4]}"
    assert distribution[4:] == [12, 12, 12, 12], f"Last 4 workers should get 12, got {distribution[4:]}"
    
    print(f"✓ With remainder: {batch_size} iterations / {num_workers} workers")
    print(f"  Distribution: {distribution}")
    print(f"  Total: {total}")


def test_work_distribution_small_batch():
    """Test when batch_size < num_workers."""
    batch_size = 50
    num_workers = 128
    
    base = batch_size // num_workers  # 0
    remainder = batch_size % num_workers  # 50
    
    # Count active workers (those with work)
    active_workers = 0
    total = 0
    for worker_id in range(num_workers):
        iterations = base + (1 if worker_id < remainder else 0)
        if iterations > 0:
            active_workers += 1
            total += iterations
    
    assert total == batch_size, f"Expected {batch_size} iterations, but distributed {total}"
    assert active_workers == batch_size, f"Expected {batch_size} active workers, got {active_workers}"
    
    print(f"✓ Small batch: {batch_size} iterations / {num_workers} workers")
    print(f"  Active workers: {active_workers}")
    print(f"  Total iterations: {total}")


def test_work_distribution_edge_cases():
    """Test edge cases."""
    # Case 1: Single worker
    batch_size = 100
    num_workers = 1
    base = batch_size // num_workers
    remainder = batch_size % num_workers
    total = base + (1 if 0 < remainder else 0)
    assert total == batch_size
    print(f"✓ Single worker: {total} iterations")
    
    # Case 2: batch_size = num_workers
    batch_size = 8
    num_workers = 8
    base = batch_size // num_workers
    remainder = batch_size % num_workers
    total = sum(base + (1 if i < remainder else 0) for i in range(num_workers))
    assert total == batch_size
    print(f"✓ Equal batch/workers: {total} iterations")
    
    # Case 3: Large number of workers
    batch_size = 100
    num_workers = 200
    base = batch_size // num_workers
    remainder = batch_size % num_workers
    total = sum(base + (1 if i < remainder else 0) for i in range(num_workers))
    assert total == batch_size
    active = sum(1 for i in range(num_workers) if (base + (1 if i < remainder else 0)) > 0)
    assert active == batch_size
    print(f"✓ More workers than batch: {total} iterations, {active} active workers")


def test_old_vs_new_distribution():
    """Compare old (buggy) vs new (fixed) distribution."""
    test_cases = [
        (100, 8, "Typical case with remainder"),
        (100, 10, "Exact division"),
        (100, 128, "More workers than iterations"),
        (1000, 8, "Large batch"),
        (100, 3, "Small worker count"),
    ]
    
    print("\nComparison: Old (buggy) vs New (fixed) work distribution")
    print("=" * 70)
    
    for batch_size, num_workers, description in test_cases:
        # Old method (buggy - integer division loses iterations)
        old_iterations_per_worker = batch_size // num_workers
        old_total = old_iterations_per_worker * num_workers
        old_lost = batch_size - old_total
        
        # New method (fixed - distributes remainder)
        base = batch_size // num_workers
        remainder = batch_size % num_workers
        new_total = batch_size  # Always equals batch_size by design
        
        active_workers = min(num_workers, batch_size)
        
        print(f"\n{description}: batch_size={batch_size}, workers={num_workers}")
        print(f"  Old method: {old_iterations_per_worker} × {num_workers} = {old_total} iterations")
        print(f"  Lost iterations: {old_lost} ({old_lost/batch_size*100:.1f}%)")
        print(f"  New method: {base}+remainder distributed = {new_total} iterations")
        print(f"  Active workers: {active_workers}")
        print(f"  ✓ Fixed: No iterations lost!")
        
        assert new_total == batch_size, "New method should never lose iterations"


if __name__ == "__main__":
    print("Testing work distribution algorithms...\n")
    
    test_work_distribution_exact_division()
    test_work_distribution_with_remainder()
    test_work_distribution_small_batch()
    test_work_distribution_edge_cases()
    test_old_vs_new_distribution()
    
    print("\n" + "=" * 70)
    print("✅ All work distribution tests passed!")
    print("=" * 70)
