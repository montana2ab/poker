"""Tests for statistical functions in rl_eval.statistics module."""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
import pytest
from holdem.rl_eval.statistics import (
    compute_confidence_interval,
    required_sample_size,
    check_margin_adequacy,
    format_ci_result,
    estimate_variance_reduction
)


class TestConfidenceInterval:
    """Tests for confidence interval calculation."""
    
    def test_compute_ci_bootstrap_basic(self):
        """Test basic bootstrap CI computation."""
        np.random.seed(42)
        results = [1.0, 2.0, 3.0, 4.0, 5.0] * 20  # 100 samples
        
        ci_info = compute_confidence_interval(results, confidence=0.95, method="bootstrap")
        
        assert 'mean' in ci_info
        assert 'ci_lower' in ci_info
        assert 'ci_upper' in ci_info
        assert 'margin' in ci_info
        assert ci_info['confidence'] == 0.95
        assert ci_info['method'] == "bootstrap"
        
        # Check that mean is reasonable
        assert abs(ci_info['mean'] - 3.0) < 0.1
        
        # Check that CI contains the mean
        assert ci_info['ci_lower'] <= ci_info['mean'] <= ci_info['ci_upper']
        
        # Margin should be positive
        assert ci_info['margin'] > 0
    
    def test_compute_ci_analytical_basic(self):
        """Test basic analytical CI computation."""
        np.random.seed(42)
        results = [1.0, 2.0, 3.0, 4.0, 5.0] * 20
        
        ci_info = compute_confidence_interval(results, confidence=0.95, method="analytical")
        
        assert ci_info['method'] == "analytical"
        assert abs(ci_info['mean'] - 3.0) < 0.1
        assert ci_info['ci_lower'] <= ci_info['mean'] <= ci_info['ci_upper']
    
    def test_ci_coverage_empirical(self):
        """Test that 95% CI achieves approximately 95% coverage."""
        np.random.seed(42)
        
        true_mean = 5.0
        true_std = 2.0
        n_samples = 100
        n_trials = 500  # Number of experiments
        
        coverage_count = 0
        
        for _ in range(n_trials):
            # Generate sample from known distribution
            sample = np.random.normal(true_mean, true_std, n_samples)
            
            # Compute CI
            ci_info = compute_confidence_interval(sample, confidence=0.95, method="bootstrap", n_bootstrap=1000)
            
            # Check if true mean is within CI
            if ci_info['ci_lower'] <= true_mean <= ci_info['ci_upper']:
                coverage_count += 1
        
        coverage_rate = coverage_count / n_trials
        
        # Should be approximately 95% (allow some variation)
        # Using 90-98% range to account for random variation
        assert 0.90 <= coverage_rate <= 0.98, f"Coverage rate {coverage_rate:.2%} outside acceptable range"
    
    def test_ci_width_decreases_with_sample_size(self):
        """Test that CI width decreases as sample size increases."""
        np.random.seed(42)
        
        true_mean = 10.0
        true_std = 5.0
        
        # Small sample
        small_sample = np.random.normal(true_mean, true_std, 50)
        ci_small = compute_confidence_interval(small_sample, method="bootstrap", n_bootstrap=1000)
        
        # Large sample
        large_sample = np.random.normal(true_mean, true_std, 500)
        ci_large = compute_confidence_interval(large_sample, method="bootstrap", n_bootstrap=1000)
        
        # Larger sample should have narrower CI
        assert ci_large['margin'] < ci_small['margin']
    
    def test_ci_empty_results_raises_error(self):
        """Test that empty results raise ValueError."""
        with pytest.raises(ValueError, match="empty results"):
            compute_confidence_interval([], confidence=0.95)
    
    def test_ci_invalid_method_raises_error(self):
        """Test that invalid method raises ValueError."""
        results = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="Unknown method"):
            compute_confidence_interval(results, method="invalid_method")
    
    def test_ci_different_confidence_levels(self):
        """Test CI computation with different confidence levels."""
        np.random.seed(42)
        results = np.random.normal(5.0, 2.0, 100)
        
        ci_90 = compute_confidence_interval(results, confidence=0.90, method="bootstrap", n_bootstrap=1000)
        ci_95 = compute_confidence_interval(results, confidence=0.95, method="bootstrap", n_bootstrap=1000)
        ci_99 = compute_confidence_interval(results, confidence=0.99, method="bootstrap", n_bootstrap=1000)
        
        # Higher confidence should lead to wider intervals
        assert ci_90['margin'] < ci_95['margin'] < ci_99['margin']


class TestSampleSizeCalculation:
    """Tests for sample size calculation."""
    
    def test_required_sample_size_basic(self):
        """Test basic sample size calculation."""
        # Example: Want ±1 margin with variance=100 (std=10)
        n = required_sample_size(target_margin=1.0, estimated_variance=100.0, confidence=0.95)
        
        assert isinstance(n, int)
        assert n > 0
        
        # Should be approximately (1.96 * 10 / 1)² ≈ 384
        assert 350 <= n <= 420
    
    def test_required_sample_size_smaller_margin_needs_more_samples(self):
        """Test that smaller target margin requires more samples."""
        variance = 100.0
        
        n_large_margin = required_sample_size(target_margin=2.0, estimated_variance=variance)
        n_small_margin = required_sample_size(target_margin=1.0, estimated_variance=variance)
        
        # Smaller margin needs more samples
        assert n_small_margin > n_large_margin
    
    def test_required_sample_size_higher_variance_needs_more_samples(self):
        """Test that higher variance requires more samples."""
        margin = 1.0
        
        n_low_var = required_sample_size(target_margin=margin, estimated_variance=25.0)
        n_high_var = required_sample_size(target_margin=margin, estimated_variance=100.0)
        
        # Higher variance needs more samples
        assert n_high_var > n_low_var
    
    def test_required_sample_size_validation(self):
        """Test input validation for sample size calculation."""
        with pytest.raises(ValueError, match="must be positive"):
            required_sample_size(target_margin=0.0, estimated_variance=100.0)
        
        with pytest.raises(ValueError, match="must be positive"):
            required_sample_size(target_margin=-1.0, estimated_variance=100.0)
        
        with pytest.raises(ValueError, match="must be non-negative"):
            required_sample_size(target_margin=1.0, estimated_variance=-10.0)
    
    def test_required_sample_size_accuracy(self):
        """Test that calculated sample size actually achieves target margin."""
        np.random.seed(42)
        
        true_std = 10.0
        target_margin = 1.0
        
        # Calculate required n
        n = required_sample_size(target_margin=target_margin, estimated_variance=true_std**2)
        
        # Simulate multiple trials
        margins = []
        for _ in range(100):
            sample = np.random.normal(0, true_std, n)
            ci_info = compute_confidence_interval(sample, confidence=0.95, method="analytical")
            margins.append(ci_info['margin'])
        
        # Average margin should be close to target (within 20%)
        avg_margin = np.mean(margins)
        assert avg_margin <= target_margin * 1.2


class TestMarginAdequacy:
    """Tests for margin adequacy checking."""
    
    def test_check_margin_adequate(self):
        """Test adequacy check when margin is adequate."""
        result = check_margin_adequacy(
            current_margin=0.8,
            target_margin=1.0,
            current_n=1000,
            estimated_variance=100.0
        )
        
        assert result['is_adequate'] is True
        assert result['current_margin'] == 0.8
        assert result['target_margin'] == 1.0
        assert 'adequate' in result['recommendation'].lower()
    
    def test_check_margin_inadequate(self):
        """Test adequacy check when margin is inadequate."""
        result = check_margin_adequacy(
            current_margin=2.0,
            target_margin=1.0,
            current_n=100,
            estimated_variance=100.0
        )
        
        assert result['is_adequate'] is False
        assert 'additional samples' in result['recommendation'].lower()
    
    def test_check_margin_recommends_correct_additional_samples(self):
        """Test that recommendation includes correct additional sample count."""
        current_n = 100
        result = check_margin_adequacy(
            current_margin=2.0,
            target_margin=1.0,
            current_n=current_n,
            estimated_variance=100.0
        )
        
        # Should recommend additional samples
        assert not result['is_adequate']
        
        # The recommendation should include a number
        assert 'additional' in result['recommendation'].lower()


class TestVarianceReduction:
    """Tests for variance reduction estimation."""
    
    def test_estimate_variance_reduction_basic(self):
        """Test basic variance reduction calculation."""
        result = estimate_variance_reduction(
            vanilla_variance=100.0,
            aivat_variance=30.0
        )
        
        assert result['vanilla_variance'] == 100.0
        assert result['aivat_variance'] == 30.0
        assert result['reduction_pct'] == 70.0
        assert result['efficiency_gain'] > 1.0
    
    def test_estimate_variance_reduction_no_reduction(self):
        """Test when there's no variance reduction."""
        result = estimate_variance_reduction(
            vanilla_variance=100.0,
            aivat_variance=100.0
        )
        
        assert result['reduction_pct'] == 0.0
        assert result['efficiency_gain'] == 1.0
    
    def test_estimate_variance_reduction_validation(self):
        """Test input validation for variance reduction."""
        with pytest.raises(ValueError, match="must be positive"):
            estimate_variance_reduction(vanilla_variance=0.0, aivat_variance=10.0)
        
        with pytest.raises(ValueError, match="must be positive"):
            estimate_variance_reduction(vanilla_variance=-10.0, aivat_variance=10.0)


class TestFormatting:
    """Tests for result formatting."""
    
    def test_format_ci_result_basic(self):
        """Test basic CI result formatting."""
        ci_info = {
            'mean': 5.23,
            'margin': 0.45,
            'ci_lower': 4.78,
            'ci_upper': 5.68,
            'confidence': 0.95
        }
        
        formatted = format_ci_result(5.23, ci_info, decimals=2, unit="bb/100")
        
        assert "5.23" in formatted
        assert "0.45" in formatted
        assert "bb/100" in formatted
        assert "95%" in formatted
        assert "[4.78, 5.68]" in formatted
    
    def test_format_ci_result_without_unit(self):
        """Test formatting without unit."""
        ci_info = {
            'mean': 10.5,
            'margin': 1.2,
            'ci_lower': 9.3,
            'ci_upper': 11.7,
            'confidence': 0.99
        }
        
        formatted = format_ci_result(10.5, ci_info, decimals=1)
        
        assert "10.5" in formatted
        assert "1.2" in formatted
        assert "99%" in formatted


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""
    
    def test_evaluation_workflow(self):
        """Test complete evaluation workflow with CI and sample size."""
        np.random.seed(42)
        
        # Simulate evaluation results
        true_winrate = 5.0  # bb/100
        variance = 100.0
        n_episodes = 1000
        
        results = np.random.normal(true_winrate, np.sqrt(variance), n_episodes)
        
        # Compute CI
        ci_info = compute_confidence_interval(results, confidence=0.95, method="bootstrap", n_bootstrap=1000)
        
        # Check if we need more samples for target margin of ±1 bb/100
        adequacy = check_margin_adequacy(
            current_margin=ci_info['margin'],
            target_margin=1.0,
            current_n=n_episodes,
            estimated_variance=variance
        )
        
        # Format for display
        formatted = format_ci_result(ci_info['mean'], ci_info, decimals=2, unit="bb/100")
        
        # Verify complete workflow
        assert ci_info['mean'] is not None
        assert adequacy['is_adequate'] is not None
        assert len(formatted) > 0
    
    def test_aivat_variance_reduction_scenario(self):
        """Test AIVAT variance reduction scenario."""
        vanilla_var = 100.0
        aivat_var = 22.0  # 78% reduction (as in EVAL_PROTOCOL.md)
        
        reduction = estimate_variance_reduction(vanilla_var, aivat_var)
        
        # Should achieve ~78% reduction
        assert reduction['reduction_pct'] >= 75.0
        
        # Calculate sample size savings
        target_margin = 1.0
        n_vanilla = required_sample_size(target_margin, vanilla_var)
        n_aivat = required_sample_size(target_margin, aivat_var)
        
        # AIVAT should require significantly fewer samples
        assert n_aivat < n_vanilla * 0.3  # Should need <30% of samples


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
