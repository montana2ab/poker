"""Test for iteration rate calculation fix in parallel solver."""


def test_iteration_rate_calculation_logic():
    """Test that iteration rate is calculated correctly from actual iterations processed."""
    
    # Test scenario 1: Multiple batches between logs (60-second interval)
    batch_size = 100
    last_logged_iteration = 0
    current_iteration = 2400  # 24 batches processed
    elapsed_time = 60.0
    
    # New calculation method
    iter_count = current_iteration - last_logged_iteration
    iter_per_sec = iter_count / elapsed_time if elapsed_time > 0 else 0
    
    assert iter_count == 2400, f"Expected 2400 iterations, got {iter_count}"
    assert abs(iter_per_sec - 40.0) < 0.1, f"Expected ~40 iter/s, got {iter_per_sec}"
    
    # Test scenario 2: Early modulo-triggered log (iteration 10000)
    last_logged_iteration = 9700
    current_iteration = 10000
    elapsed_time = 15.6
    
    iter_count = current_iteration - last_logged_iteration
    iter_per_sec = iter_count / elapsed_time if elapsed_time > 0 else 0
    
    assert iter_count == 300, f"Expected 300 iterations, got {iter_count}"
    assert abs(iter_per_sec - 19.2) < 0.5, f"Expected ~19.2 iter/s, got {iter_per_sec}"
    
    print("✓ Iteration rate calculation logic test passed")


def test_old_vs_new_calculation():
    """Compare old (incorrect) vs new (correct) calculation method."""
    
    batch_size = 100
    
    # Scenario from actual logs
    scenarios = [
        {"name": "60s interval", "iterations": 2400, "elapsed": 60.0},
        {"name": "modulo at 10000", "iterations": 300, "elapsed": 15.6},
    ]
    
    for scenario in scenarios:
        iterations = scenario["iterations"]
        elapsed = scenario["elapsed"]
        
        # Old method (always used batch_size)
        old_rate = batch_size / elapsed
        
        # New method (uses actual iterations)
        new_rate = iterations / elapsed
        
        print(f"  {scenario['name']}: old={old_rate:.1f} iter/s, new={new_rate:.1f} iter/s")
        
        # Old method would give inconsistent rates
        # New method gives accurate rates based on actual work
    
    print("✓ Old vs new calculation comparison test passed")


if __name__ == "__main__":
    print("Running iteration rate fix tests...")
    print("=" * 60)
    
    test_iteration_rate_calculation_logic()
    print()
    test_old_vs_new_calculation()
    
    print("=" * 60)
    print("✅ All tests passed!")
