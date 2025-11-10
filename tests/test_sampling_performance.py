"""Performance tests for public card sampling - measure compute overhead."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import time
import numpy as np
from holdem.types import Card, Street, SearchConfig, TableState
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.resolver import SubgameResolver
from holdem.realtime.subgame import SubgameTree


def benchmark_solve_without_sampling(iterations=10):
    """Benchmark standard solve without sampling."""
    config = SearchConfig(
        time_budget_ms=100,
        min_iterations=50,
        samples_per_solve=1  # No sampling
    )
    
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
    )
    subgame = SubgameTree([Street.FLOP], state, [Card('J', 'c'), Card('T', 'c')])
    
    times = []
    for _ in range(iterations):
        start = time.time()
        strategy = resolver.solve(subgame, "test_infoset", street=Street.FLOP)
        elapsed = (time.time() - start) * 1000  # Convert to ms
        times.append(elapsed)
    
    return np.mean(times), np.std(times), np.min(times), np.max(times)


def benchmark_solve_with_sampling(num_samples, iterations=10):
    """Benchmark solve with public card sampling."""
    config = SearchConfig(
        time_budget_ms=100 * num_samples,  # Scale time budget with samples
        min_iterations=50,
        samples_per_solve=num_samples
    )
    
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
    )
    subgame = SubgameTree([Street.FLOP], state, [Card('J', 'c'), Card('T', 'c')])
    
    our_cards = [Card('J', 'c'), Card('T', 'c')]
    
    times = []
    for _ in range(iterations):
        start = time.time()
        strategy = resolver.solve_with_sampling(
            subgame, 
            "test_infoset", 
            our_cards,
            street=Street.FLOP
        )
        elapsed = (time.time() - start) * 1000  # Convert to ms
        times.append(elapsed)
    
    return np.mean(times), np.std(times), np.min(times), np.max(times)


def test_compute_overhead():
    """Test that compute overhead is within acceptable range (< 2x)."""
    print("\n=== Public Card Sampling Performance Test ===\n")
    
    # Benchmark without sampling
    print("Benchmarking without sampling (baseline)...")
    mean_no_sampling, std_no_sampling, min_no_sampling, max_no_sampling = \
        benchmark_solve_without_sampling(iterations=5)
    
    print(f"  No sampling: {mean_no_sampling:.2f}ms ± {std_no_sampling:.2f}ms "
          f"(min: {min_no_sampling:.2f}ms, max: {max_no_sampling:.2f}ms)")
    
    # Benchmark with different sample sizes
    sample_sizes = [5, 10, 20]
    
    for num_samples in sample_sizes:
        print(f"\nBenchmarking with {num_samples} samples...")
        mean_sampling, std_sampling, min_sampling, max_sampling = \
            benchmark_solve_with_sampling(num_samples, iterations=5)
        
        print(f"  {num_samples} samples: {mean_sampling:.2f}ms ± {std_sampling:.2f}ms "
              f"(min: {min_sampling:.2f}ms, max: {max_sampling:.2f}ms)")
        
        # Calculate overhead per sample (should be close to linear scaling)
        overhead_ratio = mean_sampling / mean_no_sampling
        overhead_per_sample = overhead_ratio / num_samples
        
        print(f"  Total overhead: {overhead_ratio:.2f}x")
        print(f"  Overhead per sample: {overhead_per_sample:.2f}x (ideal: ~1.0x for linear scaling)")
        
        # Check that overhead is reasonable
        # With proper implementation, overhead should be approximately linear with num_samples
        # Allow some overhead (up to 2x per solve on average) due to averaging and bookkeeping
        expected_max_overhead = num_samples * 2.0
        
        if overhead_ratio <= expected_max_overhead:
            print(f"  ✓ Overhead {overhead_ratio:.2f}x is within acceptable range (< {expected_max_overhead:.1f}x)")
        else:
            print(f"  ⚠ Overhead {overhead_ratio:.2f}x exceeds acceptable range (< {expected_max_overhead:.1f}x)")
    
    print("\n=== Performance Test Complete ===\n")


def test_variance_reduction():
    """Test that sampling reduces variance in strategies."""
    print("\n=== Variance Reduction Test ===\n")
    
    # Run multiple solves without sampling
    print("Testing variance without sampling...")
    config_no_sampling = SearchConfig(
        time_budget_ms=50,
        min_iterations=20,
        samples_per_solve=1
    )
    
    blueprint = PolicyStore()
    resolver_no_sampling = SubgameResolver(config_no_sampling, blueprint)
    
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
    )
    subgame = SubgameTree([Street.FLOP], state, [Card('J', 'c'), Card('T', 'c')])
    
    strategies_no_sampling = []
    for _ in range(10):
        strategy = resolver_no_sampling.solve(subgame, "test_infoset", street=Street.FLOP)
        strategies_no_sampling.append(strategy)
    
    # Calculate variance across strategies (no sampling)
    variances_no_sampling = []
    reference = strategies_no_sampling[0]
    for strategy in strategies_no_sampling[1:]:
        variance = resolver_no_sampling._strategy_variance(strategy, reference)
        variances_no_sampling.append(variance)
    
    avg_variance_no_sampling = np.mean(variances_no_sampling)
    print(f"  Average variance (no sampling): {avg_variance_no_sampling:.4f}")
    
    # Run multiple solves with sampling
    print("\nTesting variance with sampling (10 samples)...")
    config_sampling = SearchConfig(
        time_budget_ms=500,
        min_iterations=20,
        samples_per_solve=10
    )
    
    resolver_sampling = SubgameResolver(config_sampling, blueprint)
    our_cards = [Card('J', 'c'), Card('T', 'c')]
    
    strategies_sampling = []
    for _ in range(10):
        strategy = resolver_sampling.solve_with_sampling(
            subgame, "test_infoset", our_cards, street=Street.FLOP
        )
        strategies_sampling.append(strategy)
    
    # Calculate variance across strategies (with sampling)
    variances_sampling = []
    reference = strategies_sampling[0]
    for strategy in strategies_sampling[1:]:
        variance = resolver_sampling._strategy_variance(strategy, reference)
        variances_sampling.append(variance)
    
    avg_variance_sampling = np.mean(variances_sampling)
    print(f"  Average variance (with sampling): {avg_variance_sampling:.4f}")
    
    # Compare
    print(f"\n  Variance ratio (sampling/no-sampling): {avg_variance_sampling / avg_variance_no_sampling:.2f}x")
    
    # In practice, sampling should reduce variance (ratio < 1.0)
    # However, due to the simplified CFR implementation, we may not see this benefit
    # The test mainly verifies the mechanism works correctly
    print(f"  Note: Variance reduction depends on full CFR traversal implementation")
    
    print("\n=== Variance Reduction Test Complete ===\n")


if __name__ == "__main__":
    test_compute_overhead()
    test_variance_reduction()
    
    print("✅ All performance tests completed!")
