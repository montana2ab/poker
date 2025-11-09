"""Tests for metrics tracking."""

import pytest
from holdem.utils.metrics import MetricsTracker, get_metrics_tracker, reset_metrics


def test_metrics_tracker_initialization():
    """Test that MetricsTracker initializes correctly."""
    tracker = MetricsTracker()
    
    assert len(tracker.rt_decision_times) == 0
    assert tracker.rt_total_solves == 0
    assert tracker.translator_illegal_count == 0


def test_record_rt_solve():
    """Test recording runtime solve metrics."""
    tracker = MetricsTracker()
    
    # Record some solves
    tracker.record_rt_solve(85.0, 450, False, 0.5)
    tracker.record_rt_solve(92.0, 480, False, -0.3)
    tracker.record_rt_solve(5.0, 50, True, 0.0)  # Fallback
    
    assert tracker.rt_total_solves == 3
    assert tracker.rt_fallback_count == 1
    assert len(tracker.rt_decision_times) == 3
    assert len(tracker.rt_iterations_list) == 3
    
    metrics = tracker.get_metrics()
    
    # Check computed metrics
    assert 'rt/decision_time_ms' in metrics
    assert 'rt/iterations' in metrics
    assert 'rt/failsafe_fallback_rate' in metrics
    assert 'rt/ev_delta_bbs' in metrics
    
    # Check values
    assert metrics['rt/failsafe_fallback_rate'] == pytest.approx(1/3)
    assert metrics['rt/iterations'] == pytest.approx((450 + 480 + 50) / 3)


def test_record_translation():
    """Test recording translation metrics."""
    tracker = MetricsTracker()
    
    # Record legal translations
    for _ in range(100):
        tracker.record_translation(is_legal=True)
    
    # Record one illegal translation
    tracker.record_translation(is_legal=False)
    
    metrics = tracker.get_metrics()
    
    assert metrics['translator/illegal_after_roundtrip'] == pytest.approx(1/101)
    
    # Test that all legal gives 0
    tracker2 = MetricsTracker()
    for _ in range(100):
        tracker2.record_translation(is_legal=True)
    
    metrics2 = tracker2.get_metrics()
    assert metrics2['translator/illegal_after_roundtrip'] == 0.0


def test_record_bucket_metrics():
    """Test recording bucket/abstraction metrics."""
    tracker = MetricsTracker()
    
    # Record bucket populations
    flop_populations = [100, 102, 98, 105, 95]  # Relatively balanced
    tracker.record_bucket_assignment('flop', flop_populations)
    
    turn_populations = [50, 150, 60, 140, 100]  # Less balanced
    tracker.record_bucket_assignment('turn', turn_populations)
    
    # Record collisions
    tracker.record_bucket_collision(False)
    tracker.record_bucket_collision(False)
    tracker.record_bucket_collision(True)
    
    metrics = tracker.get_metrics()
    
    assert 'abstraction/bucket_pop_std_flop' in metrics
    assert 'abstraction/bucket_pop_std_turn' in metrics
    assert 'abstraction/collision_rate' in metrics
    
    # Turn should have higher std than flop
    assert metrics['abstraction/bucket_pop_std_turn'] > metrics['abstraction/bucket_pop_std_flop']
    
    # Collision rate should be 1/3
    assert metrics['abstraction/collision_rate'] == pytest.approx(1/3)


def test_record_eval_results():
    """Test recording evaluation results."""
    tracker = MetricsTracker()
    
    # Record some results (in bb/100)
    results = [2.5, 3.0, 2.8, 2.2, 3.5]
    for result in results:
        tracker.record_eval_result(result)
    
    metrics = tracker.get_metrics()
    
    assert 'eval/mbb100_mean' in metrics
    assert 'eval/mbb100_CI95' in metrics
    
    # Mean should be around 2.8 bb/100 = 2800 mbb/100
    expected_mean = sum(results) / len(results) * 1000
    assert metrics['eval/mbb100_mean'] == pytest.approx(expected_mean)


def test_record_policy_metrics():
    """Test recording policy metrics."""
    tracker = MetricsTracker()
    
    # Record KL divergences
    tracker.record_policy_kl(0.15)
    tracker.record_policy_kl(0.18)
    tracker.record_policy_kl(0.12)
    
    # Record entropies by street
    tracker.record_policy_entropy('flop', 1.2)
    tracker.record_policy_entropy('flop', 1.3)
    tracker.record_policy_entropy('turn', 0.9)
    tracker.record_policy_entropy('river', 0.8)
    
    metrics = tracker.get_metrics()
    
    assert 'policy/kl_to_blueprint_root' in metrics
    assert 'policy/entropy_flop' in metrics
    assert 'policy/entropy_turn' in metrics
    assert 'policy/entropy_river' in metrics
    
    # Check values
    assert metrics['policy/kl_to_blueprint_root'] == pytest.approx(0.15)
    assert metrics['policy/entropy_flop'] == pytest.approx(1.25)


def test_global_tracker():
    """Test global metrics tracker singleton."""
    # Reset first
    reset_metrics()
    
    # Get tracker
    tracker1 = get_metrics_tracker()
    tracker2 = get_metrics_tracker()
    
    # Should be same instance
    assert tracker1 is tracker2
    
    # Record something
    tracker1.record_rt_solve(100.0, 500, False, 1.0)
    
    # Should see it in tracker2
    assert tracker2.rt_total_solves == 1
    
    # Reset
    reset_metrics()
    tracker3 = get_metrics_tracker()
    assert tracker3.rt_total_solves == 0


def test_metrics_reset():
    """Test resetting metrics."""
    tracker = MetricsTracker()
    
    # Add some data
    tracker.record_rt_solve(100.0, 500, False, 1.0)
    tracker.record_translation(True)
    tracker.record_eval_result(2.5)
    
    assert tracker.rt_total_solves > 0
    assert tracker.translator_total_translations > 0
    
    # Reset
    tracker.reset()
    
    assert tracker.rt_total_solves == 0
    assert tracker.translator_total_translations == 0
    assert len(tracker.rt_decision_times) == 0
    assert len(tracker.eval_bb_per_100) == 0


def test_percentile_metrics():
    """Test that percentile metrics are computed correctly."""
    tracker = MetricsTracker()
    
    # Add data with known distribution
    for i in range(100):
        tracker.record_rt_solve(float(i), 500, False, 0.0)
    
    metrics = tracker.get_metrics()
    
    assert 'rt/decision_time_p50' in metrics
    assert 'rt/decision_time_p90' in metrics
    assert 'rt/decision_time_p99' in metrics
    
    # Check approximate values
    assert metrics['rt/decision_time_p50'] == pytest.approx(49.5, abs=1.0)
    assert metrics['rt/decision_time_p90'] == pytest.approx(89.5, abs=1.0)
    assert metrics['rt/decision_time_p99'] == pytest.approx(98.5, abs=1.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
