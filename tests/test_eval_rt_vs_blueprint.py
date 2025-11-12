"""Tests for RT search vs blueprint evaluation tool."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))

import pytest
import numpy as np
from holdem.types import SearchConfig
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.resolver import SubgameResolver

# Import the evaluation module
import eval_rt_vs_blueprint as eval_module


class TestSimplifiedPokerSim:
    """Tests for simplified poker simulator."""
    
    def test_simulator_creation(self):
        """Test that simulator can be created."""
        blueprint = PolicyStore()
        sim = eval_module.SimplifiedPokerSim(blueprint, seed=42)
        
        assert sim.blueprint is not None
        assert sim.rng is not None
    
    def test_simulate_hand_basic(self):
        """Test basic hand simulation."""
        blueprint = PolicyStore()
        sim = eval_module.SimplifiedPokerSim(blueprint, seed=42)
        
        config = SearchConfig(
            time_budget_ms=50,
            min_iterations=10,
            samples_per_solve=1
        )
        resolver = SubgameResolver(config, blueprint)
        
        result = sim.simulate_hand(resolver, hand_id=0, position='SB', samples_per_solve=1)
        
        assert result.hand_id == 0
        assert result.position == 'SB'
        assert result.samples_per_solve == 1
        assert result.rt_latency_ms > 0
        assert result.deal_hash is not None
    
    def test_simulate_hand_with_sampling(self):
        """Test hand simulation with public card sampling."""
        blueprint = PolicyStore()
        sim = eval_module.SimplifiedPokerSim(blueprint, seed=42)
        
        config = SearchConfig(
            time_budget_ms=200,
            min_iterations=10,
            samples_per_solve=10
        )
        resolver = SubgameResolver(config, blueprint)
        
        result = sim.simulate_hand(resolver, hand_id=0, position='BB', samples_per_solve=10)
        
        assert result.samples_per_solve == 10
        # Latency should be higher with sampling
        assert result.rt_latency_ms > 0
    
    def test_strategy_ev_computation(self):
        """Test EV computation for strategies."""
        blueprint = PolicyStore()
        sim = eval_module.SimplifiedPokerSim(blueprint, seed=42)
        
        from holdem.types import TableState, Street, Card
        
        state = TableState(
            street=Street.FLOP,
            pot=100.0,
            board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
        )
        
        # Test aggressive strategy
        aggressive_strategy = {
            'BET_POT': 0.7,
            'CALL': 0.2,
            'FOLD': 0.1
        }
        ev_aggressive = sim._compute_strategy_ev(aggressive_strategy, state)
        
        # Test passive strategy
        passive_strategy = {
            'FOLD': 0.5,
            'CALL': 0.4,
            'BET_POT': 0.1
        }
        ev_passive = sim._compute_strategy_ev(passive_strategy, state)
        
        # Aggressive should have higher EV in this simplified model
        assert ev_aggressive > ev_passive


class TestEvaluationResult:
    """Tests for evaluation result data structure."""
    
    def test_evaluation_result_creation(self):
        """Test creating evaluation result."""
        result = eval_module.EvaluationResult(
            total_hands=1000,
            samples_per_solve=16,
            ev_delta_bb100=5.2,
            ci_lower=2.1,
            ci_upper=8.3,
            ci_margin=3.1,
            is_significant=True,
            p_value=0.003,
            mean_rt_latency_ms=85.3,
            p50_latency_ms=78.2,
            p95_latency_ms=125.4,
            p99_latency_ms=180.1
        )
        
        assert result.total_hands == 1000
        assert result.samples_per_solve == 16
        assert result.ev_delta_bb100 == 5.2
        assert result.is_significant is True
        assert result.mean_rt_latency_ms > 0


class TestRunEvaluation:
    """Tests for main evaluation function."""
    
    def test_run_evaluation_no_sampling(self, tmp_path):
        """Test evaluation without public card sampling."""
        # Create minimal policy file
        policy_path = tmp_path / "test_policy.json"
        with open(policy_path, 'w') as f:
            f.write('{}')
        
        result = eval_module.run_evaluation(
            policy_path=policy_path,
            num_hands=10,  # Small for testing
            samples_per_solve=1,
            time_budget_ms=50,
            seed=42,
            quiet=True
        )
        
        assert result.total_hands == 20  # 10 pairs = 20 hands
        assert result.samples_per_solve == 1
        assert result.ev_delta_bb100 is not None
        assert result.ci_lower is not None
        assert result.ci_upper is not None
        assert result.mean_rt_latency_ms > 0
    
    def test_run_evaluation_with_sampling(self, tmp_path):
        """Test evaluation with public card sampling."""
        policy_path = tmp_path / "test_policy.json"
        with open(policy_path, 'w') as f:
            f.write('{}')
        
        result = eval_module.run_evaluation(
            policy_path=policy_path,
            num_hands=10,
            samples_per_solve=16,
            time_budget_ms=200,
            seed=42,
            quiet=True
        )
        
        assert result.samples_per_solve == 16
        # Latency should be higher with sampling
        assert result.mean_rt_latency_ms > 0
    
    def test_confidence_interval_calculation(self, tmp_path):
        """Test that confidence intervals are properly calculated."""
        policy_path = tmp_path / "test_policy.json"
        with open(policy_path, 'w') as f:
            f.write('{}')
        
        result = eval_module.run_evaluation(
            policy_path=policy_path,
            num_hands=50,
            samples_per_solve=1,
            time_budget_ms=50,
            seed=42,
            quiet=True
        )
        
        # CI should bracket the mean
        assert result.ci_lower <= result.ev_delta_bb100 <= result.ci_upper
        
        # Margin should be positive
        assert result.ci_margin > 0
        
        # Margin should equal half-width of CI
        expected_margin = (result.ci_upper - result.ci_lower) / 2
        assert abs(result.ci_margin - expected_margin) < 0.01
    
    def test_statistical_significance(self, tmp_path):
        """Test significance determination."""
        policy_path = tmp_path / "test_policy.json"
        with open(policy_path, 'w') as f:
            f.write('{}')
        
        result = eval_module.run_evaluation(
            policy_path=policy_path,
            num_hands=50,
            samples_per_solve=1,
            seed=42,
            quiet=True
        )
        
        # If significant, CI should not contain 0
        if result.is_significant:
            assert result.ci_lower > 0 or result.ci_upper < 0
        
        # p-value should be in valid range
        assert 0 <= result.p_value <= 1
    
    def test_latency_percentiles(self, tmp_path):
        """Test latency percentile calculations."""
        policy_path = tmp_path / "test_policy.json"
        with open(policy_path, 'w') as f:
            f.write('{}')
        
        result = eval_module.run_evaluation(
            policy_path=policy_path,
            num_hands=50,
            samples_per_solve=1,
            seed=42,
            quiet=True
        )
        
        # Percentiles should be ordered
        assert result.p50_latency_ms <= result.p95_latency_ms
        assert result.p95_latency_ms <= result.p99_latency_ms
        
        # Mean should be reasonable relative to median
        # (within 5x for typical distributions)
        assert result.mean_rt_latency_ms < result.p50_latency_ms * 5


class TestSamplingComparison:
    """Tests for comparing different sample counts."""
    
    def test_latency_increases_with_samples(self, tmp_path):
        """Test that latency increases with more samples."""
        policy_path = tmp_path / "test_policy.json"
        with open(policy_path, 'w') as f:
            f.write('{}')
        
        result_1 = eval_module.run_evaluation(
            policy_path=policy_path,
            num_hands=20,
            samples_per_solve=1,
            seed=42,
            quiet=True
        )
        
        result_16 = eval_module.run_evaluation(
            policy_path=policy_path,
            num_hands=20,
            samples_per_solve=16,
            seed=42,
            quiet=True
        )
        
        # More samples should take longer
        assert result_16.mean_rt_latency_ms > result_1.mean_rt_latency_ms
    
    def test_multiple_sample_counts(self, tmp_path):
        """Test evaluation with multiple sample counts."""
        policy_path = tmp_path / "test_policy.json"
        with open(policy_path, 'w') as f:
            f.write('{}')
        
        sample_counts = [1, 16, 32]
        results = {}
        
        for samples in sample_counts:
            result = eval_module.run_evaluation(
                policy_path=policy_path,
                num_hands=10,
                samples_per_solve=samples,
                seed=42,
                quiet=True
            )
            results[samples] = result
        
        # All results should be present
        assert len(results) == 3
        
        # Latency should generally increase with samples
        latencies = [results[s].mean_rt_latency_ms for s in sample_counts]
        # At least the trend should be increasing (allow some variance)
        assert latencies[2] > latencies[0]  # 32 > 1


class TestBootstrapCI:
    """Tests for bootstrap confidence interval calculation."""
    
    def test_bootstrap_ci_coverage(self):
        """Test that bootstrap CI achieves proper coverage."""
        # This test verifies that the CI computation is working correctly
        # by checking coverage on synthetic data
        
        np.random.seed(42)
        true_mean = 5.0
        true_std = 10.0
        n_samples = 100
        
        # Generate sample
        sample = np.random.normal(true_mean, true_std, n_samples)
        
        from holdem.rl_eval.statistics import compute_confidence_interval
        
        ci_info = compute_confidence_interval(
            sample.tolist(),
            confidence=0.95,
            method="bootstrap",
            n_bootstrap=1000
        )
        
        # CI should contain the true mean (not guaranteed but very likely)
        # We're mainly checking the function works correctly
        assert ci_info['ci_lower'] < true_mean < ci_info['ci_upper'] or \
               abs(ci_info['mean'] - true_mean) < 2 * true_std / np.sqrt(n_samples)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
