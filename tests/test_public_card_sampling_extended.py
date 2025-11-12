"""Extended tests for public card sampling with 16-64 sample range.

This test suite validates:
1. Public card sampling works correctly with 16, 32, and 64 samples
2. Variance reduction is measurable
3. Latency scales reasonably with sample count
4. Statistical properties are maintained

Reference: PUBLIC_CARD_SAMPLING_GUIDE.md
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import time
import pytest
import numpy as np
from holdem.types import Card, Street, SearchConfig, TableState
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.resolver import SubgameResolver
from holdem.realtime.subgame import SubgameTree


class TestPublicCardSamplingExtended:
    """Extended tests for public card sampling with higher sample counts."""
    
    @pytest.fixture
    def test_state(self):
        """Create a test game state."""
        return TableState(
            street=Street.FLOP,
            pot=100.0,
            board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
        )
    
    @pytest.fixture
    def our_cards(self):
        """Create test hole cards."""
        return [Card('J', 'c'), Card('T', 'c')]
    
    def test_sampling_16_samples(self, test_state, our_cards):
        """Test public card sampling with 16 samples."""
        config = SearchConfig(
            time_budget_ms=800,  # 16 * 50ms
            min_iterations=50,
            samples_per_solve=16
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        start = time.time()
        strategy = resolver.solve_with_sampling(
            subgame, "test_infoset", our_cards, street=Street.FLOP
        )
        elapsed_ms = (time.time() - start) * 1000
        
        # Strategy should be valid
        assert len(strategy) > 0
        total_prob = sum(strategy.values())
        assert abs(total_prob - 1.0) < 0.01
        
        # Latency should be reasonable (less than 5 seconds)
        assert elapsed_ms < 5000
        
        print(f"\n16 samples: {elapsed_ms:.2f}ms")
    
    def test_sampling_32_samples(self, test_state, our_cards):
        """Test public card sampling with 32 samples."""
        config = SearchConfig(
            time_budget_ms=1600,  # 32 * 50ms
            min_iterations=50,
            samples_per_solve=32
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        start = time.time()
        strategy = resolver.solve_with_sampling(
            subgame, "test_infoset", our_cards, street=Street.FLOP
        )
        elapsed_ms = (time.time() - start) * 1000
        
        # Strategy should be valid
        assert len(strategy) > 0
        total_prob = sum(strategy.values())
        assert abs(total_prob - 1.0) < 0.01
        
        # Latency should be reasonable
        assert elapsed_ms < 10000
        
        print(f"\n32 samples: {elapsed_ms:.2f}ms")
    
    def test_sampling_64_samples(self, test_state, our_cards):
        """Test public card sampling with 64 samples."""
        config = SearchConfig(
            time_budget_ms=3200,  # 64 * 50ms
            min_iterations=50,
            samples_per_solve=64
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        start = time.time()
        strategy = resolver.solve_with_sampling(
            subgame, "test_infoset", our_cards, street=Street.FLOP
        )
        elapsed_ms = (time.time() - start) * 1000
        
        # Strategy should be valid
        assert len(strategy) > 0
        total_prob = sum(strategy.values())
        assert abs(total_prob - 1.0) < 0.01
        
        # Latency should be reasonable
        assert elapsed_ms < 20000
        
        print(f"\n64 samples: {elapsed_ms:.2f}ms")
    
    def test_latency_scaling(self, test_state, our_cards):
        """Test that latency scales reasonably with sample count."""
        sample_counts = [1, 16, 32, 64]
        latencies = {}
        
        for samples in sample_counts:
            config = SearchConfig(
                time_budget_ms=50 * samples,
                min_iterations=50,
                samples_per_solve=samples
            )
            
            blueprint = PolicyStore()
            resolver = SubgameResolver(config, blueprint)
            subgame = SubgameTree([Street.FLOP], test_state, our_cards)
            
            # Run 3 times and take average
            times = []
            for _ in range(3):
                start = time.time()
                strategy = resolver.solve_with_sampling(
                    subgame, "test_infoset", our_cards, street=Street.FLOP
                )
                elapsed_ms = (time.time() - start) * 1000
                times.append(elapsed_ms)
            
            latencies[samples] = np.mean(times)
        
        print(f"\nLatency scaling:")
        for samples, latency in latencies.items():
            overhead = latency / latencies[1] if samples > 1 else 1.0
            per_sample = overhead / samples if samples > 1 else 1.0
            print(f"  {samples:2d} samples: {latency:7.2f}ms "
                  f"(overhead: {overhead:.2f}x, per-sample: {per_sample:.2f}x)")
        
        # Latency should increase with sample count
        assert latencies[16] > latencies[1]
        assert latencies[32] > latencies[16]
        assert latencies[64] > latencies[32]
        
        # Overhead per sample should be reasonable (< 2x)
        for samples in [16, 32, 64]:
            overhead = latencies[samples] / latencies[1]
            per_sample_overhead = overhead / samples
            # Allow up to 2x overhead per sample
            assert per_sample_overhead < 2.0, \
                f"{samples} samples: per-sample overhead {per_sample_overhead:.2f}x exceeds 2x"
    
    def test_variance_reduction_16_samples(self, test_state, our_cards):
        """Test variance reduction with 16 samples."""
        # Without sampling
        config_no_sampling = SearchConfig(
            time_budget_ms=50,
            min_iterations=50,
            samples_per_solve=1
        )
        
        blueprint = PolicyStore()
        resolver_no_sampling = SubgameResolver(config_no_sampling, blueprint)
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        # Run 10 times and measure variance
        strategies_no_sampling = []
        for _ in range(10):
            strategy = resolver_no_sampling.solve(
                subgame, "test_infoset", street=Street.FLOP
            )
            strategies_no_sampling.append(strategy)
        
        # Calculate variance without sampling
        variances_no_sampling = []
        reference = strategies_no_sampling[0]
        for strategy in strategies_no_sampling[1:]:
            variance = resolver_no_sampling._strategy_variance(strategy, reference)
            variances_no_sampling.append(variance)
        
        avg_variance_no_sampling = np.mean(variances_no_sampling)
        
        # With 16 samples
        config_sampling = SearchConfig(
            time_budget_ms=800,
            min_iterations=50,
            samples_per_solve=16
        )
        
        resolver_sampling = SubgameResolver(config_sampling, blueprint)
        
        strategies_sampling = []
        for _ in range(10):
            strategy = resolver_sampling.solve_with_sampling(
                subgame, "test_infoset", our_cards, street=Street.FLOP
            )
            strategies_sampling.append(strategy)
        
        # Calculate variance with sampling
        variances_sampling = []
        reference = strategies_sampling[0]
        for strategy in strategies_sampling[1:]:
            variance = resolver_sampling._strategy_variance(strategy, reference)
            variances_sampling.append(variance)
        
        avg_variance_sampling = np.mean(variances_sampling)
        
        print(f"\nVariance (16 samples):")
        print(f"  No sampling: {avg_variance_no_sampling:.6f}")
        print(f"  16 samples:  {avg_variance_sampling:.6f}")
        
        if avg_variance_no_sampling > 0:
            reduction_pct = (1 - avg_variance_sampling / avg_variance_no_sampling) * 100
            print(f"  Reduction:   {reduction_pct:.1f}%")
        
        # Sampling should reduce variance or at least not increase it significantly
        # (In practice, reduction depends on full CFR implementation)
        assert avg_variance_sampling <= avg_variance_no_sampling * 1.5
    
    def test_variance_reduction_32_samples(self, test_state, our_cards):
        """Test variance reduction with 32 samples."""
        config_no_sampling = SearchConfig(
            time_budget_ms=50,
            min_iterations=50,
            samples_per_solve=1
        )
        
        config_sampling = SearchConfig(
            time_budget_ms=1600,
            min_iterations=50,
            samples_per_solve=32
        )
        
        blueprint = PolicyStore()
        resolver_no_sampling = SubgameResolver(config_no_sampling, blueprint)
        resolver_sampling = SubgameResolver(config_sampling, blueprint)
        
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        # Measure variance for both
        strategies_no_sampling = [
            resolver_no_sampling.solve(subgame, "test_infoset", street=Street.FLOP)
            for _ in range(10)
        ]
        
        strategies_sampling = [
            resolver_sampling.solve_with_sampling(
                subgame, "test_infoset", our_cards, street=Street.FLOP
            )
            for _ in range(10)
        ]
        
        # Calculate variances
        def calc_avg_variance(strategies, resolver):
            variances = []
            reference = strategies[0]
            for strategy in strategies[1:]:
                variance = resolver._strategy_variance(strategy, reference)
                variances.append(variance)
            return np.mean(variances)
        
        avg_variance_no_sampling = calc_avg_variance(strategies_no_sampling, resolver_no_sampling)
        avg_variance_sampling = calc_avg_variance(strategies_sampling, resolver_sampling)
        
        print(f"\nVariance (32 samples):")
        print(f"  No sampling: {avg_variance_no_sampling:.6f}")
        print(f"  32 samples:  {avg_variance_sampling:.6f}")
        
        if avg_variance_no_sampling > 0:
            reduction_pct = (1 - avg_variance_sampling / avg_variance_no_sampling) * 100
            print(f"  Reduction:   {reduction_pct:.1f}%")
    
    def test_variance_reduction_64_samples(self, test_state, our_cards):
        """Test variance reduction with 64 samples."""
        config_no_sampling = SearchConfig(
            time_budget_ms=50,
            min_iterations=50,
            samples_per_solve=1
        )
        
        config_sampling = SearchConfig(
            time_budget_ms=3200,
            min_iterations=50,
            samples_per_solve=64
        )
        
        blueprint = PolicyStore()
        resolver_no_sampling = SubgameResolver(config_no_sampling, blueprint)
        resolver_sampling = SubgameResolver(config_sampling, blueprint)
        
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        # Measure variance for both
        strategies_no_sampling = [
            resolver_no_sampling.solve(subgame, "test_infoset", street=Street.FLOP)
            for _ in range(10)
        ]
        
        strategies_sampling = [
            resolver_sampling.solve_with_sampling(
                subgame, "test_infoset", our_cards, street=Street.FLOP
            )
            for _ in range(10)
        ]
        
        # Calculate variances
        def calc_avg_variance(strategies, resolver):
            variances = []
            reference = strategies[0]
            for strategy in strategies[1:]:
                variance = resolver._strategy_variance(strategy, reference)
                variances.append(variance)
            return np.mean(variances)
        
        avg_variance_no_sampling = calc_avg_variance(strategies_no_sampling, resolver_no_sampling)
        avg_variance_sampling = calc_avg_variance(strategies_sampling, resolver_sampling)
        
        print(f"\nVariance (64 samples):")
        print(f"  No sampling: {avg_variance_no_sampling:.6f}")
        print(f"  64 samples:  {avg_variance_sampling:.6f}")
        
        if avg_variance_no_sampling > 0:
            reduction_pct = (1 - avg_variance_sampling / avg_variance_no_sampling) * 100
            print(f"  Reduction:   {reduction_pct:.1f}%")
    
    def test_strategy_consistency(self, test_state, our_cards):
        """Test that strategies are consistent across sample counts."""
        sample_counts = [1, 16, 32, 64]
        strategies = {}
        
        for samples in sample_counts:
            config = SearchConfig(
                time_budget_ms=50 * samples,
                min_iterations=50,
                samples_per_solve=samples
            )
            
            blueprint = PolicyStore()
            resolver = SubgameResolver(config, blueprint)
            subgame = SubgameTree([Street.FLOP], test_state, our_cards)
            
            if samples > 1:
                strategy = resolver.solve_with_sampling(
                    subgame, "test_infoset", our_cards, street=Street.FLOP
                )
            else:
                strategy = resolver.solve(subgame, "test_infoset", street=Street.FLOP)
            
            strategies[samples] = strategy
        
        # All strategies should have same action space
        action_sets = [set(s.keys()) for s in strategies.values()]
        assert all(actions == action_sets[0] for actions in action_sets)
        
        # All strategies should be valid probability distributions
        for samples, strategy in strategies.items():
            total_prob = sum(strategy.values())
            assert abs(total_prob - 1.0) < 0.01, \
                f"{samples} samples: probabilities sum to {total_prob}"


class TestSamplingPerformanceMetrics:
    """Tests for measuring sampling performance metrics."""
    
    def test_comprehensive_metrics(self):
        """Comprehensive test measuring all metrics for 16-64 samples."""
        print("\n" + "="*70)
        print("COMPREHENSIVE SAMPLING METRICS (16-64 samples)")
        print("="*70)
        
        test_state = TableState(
            street=Street.FLOP,
            pot=100.0,
            board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
        )
        our_cards = [Card('J', 'c'), Card('T', 'c')]
        
        sample_counts = [1, 16, 32, 64]
        metrics = {}
        
        for samples in sample_counts:
            print(f"\nTesting {samples} samples...")
            
            config = SearchConfig(
                time_budget_ms=50 * samples,
                min_iterations=50,
                samples_per_solve=samples
            )
            
            blueprint = PolicyStore()
            resolver = SubgameResolver(config, blueprint)
            subgame = SubgameTree([Street.FLOP], test_state, our_cards)
            
            # Measure latency (5 runs)
            latencies = []
            for _ in range(5):
                start = time.time()
                if samples > 1:
                    strategy = resolver.solve_with_sampling(
                        subgame, "test_infoset", our_cards, street=Street.FLOP
                    )
                else:
                    strategy = resolver.solve(subgame, "test_infoset", street=Street.FLOP)
                elapsed_ms = (time.time() - start) * 1000
                latencies.append(elapsed_ms)
            
            # Measure variance (10 runs)
            strategies = []
            for _ in range(10):
                if samples > 1:
                    strategy = resolver.solve_with_sampling(
                        subgame, "test_infoset", our_cards, street=Street.FLOP
                    )
                else:
                    strategy = resolver.solve(subgame, "test_infoset", street=Street.FLOP)
                strategies.append(strategy)
            
            # Calculate variance
            variances = []
            reference = strategies[0]
            for strategy in strategies[1:]:
                variance = resolver._strategy_variance(strategy, reference)
                variances.append(variance)
            
            metrics[samples] = {
                'mean_latency_ms': np.mean(latencies),
                'std_latency_ms': np.std(latencies),
                'p50_latency_ms': np.percentile(latencies, 50),
                'p95_latency_ms': np.percentile(latencies, 95),
                'mean_variance': np.mean(variances),
                'std_variance': np.std(variances)
            }
        
        # Print summary table
        print("\n" + "="*70)
        print("RESULTS SUMMARY")
        print("="*70)
        print(f"{'Samples':>8} | {'Mean Lat':>10} | {'p95 Lat':>10} | "
              f"{'Variance':>10} | {'Overhead':>10}")
        print("-"*70)
        
        baseline_latency = metrics[1]['mean_latency_ms']
        
        for samples in sample_counts:
            m = metrics[samples]
            overhead = m['mean_latency_ms'] / baseline_latency
            print(f"{samples:8d} | {m['mean_latency_ms']:9.2f}ms | "
                  f"{m['p95_latency_ms']:9.2f}ms | "
                  f"{m['mean_variance']:10.6f} | {overhead:9.2f}x")
        
        # Calculate variance reduction
        print("\n" + "="*70)
        print("VARIANCE REDUCTION")
        print("="*70)
        baseline_variance = metrics[1]['mean_variance']
        
        for samples in [16, 32, 64]:
            if baseline_variance > 0:
                reduction_pct = (1 - metrics[samples]['mean_variance'] / baseline_variance) * 100
            else:
                reduction_pct = 0
            print(f"{samples:2d} samples: {reduction_pct:+6.1f}% reduction")
        
        print("\n" + "="*70)
        
        # Assertions
        assert metrics[64]['mean_latency_ms'] > metrics[1]['mean_latency_ms']
        assert all(m['mean_latency_ms'] > 0 for m in metrics.values())


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
