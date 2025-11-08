"""Tests for external sampling MCCFR."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.external_sampling import ExternalSampler


def test_external_sampler_initialization():
    """Test ExternalSampler initialization."""
    bucketing = HandBucketing(BucketConfig())
    
    sampler = ExternalSampler(
        bucketing=bucketing,
        num_players=2,
        use_linear_weighting=True,
        enable_nrp=True,
        nrp_coefficient=1.0,
        strategy_freezing=False
    )
    
    assert sampler.num_players == 2
    assert sampler.use_linear_weighting == True
    assert sampler.enable_nrp == True
    assert sampler.nrp_coefficient == 1.0
    print("✓ ExternalSampler initialization works")


def test_nrp_threshold_calculation():
    """Test NRP threshold τ(t) = c / √t."""
    bucketing = HandBucketing(BucketConfig())
    
    # Test with c = 1.0
    sampler = ExternalSampler(
        bucketing=bucketing,
        num_players=2,
        nrp_coefficient=1.0
    )
    
    # Test at different iterations
    threshold_100 = sampler.get_nrp_threshold(100)
    threshold_1000 = sampler.get_nrp_threshold(1000)
    threshold_10000 = sampler.get_nrp_threshold(10000)
    
    # Thresholds should be negative and decrease in magnitude as t increases
    assert threshold_100 < 0
    assert threshold_1000 < 0
    assert threshold_10000 < 0
    assert abs(threshold_100) > abs(threshold_1000) > abs(threshold_10000)
    
    print(f"✓ NRP thresholds: t=100: {threshold_100:.4f}, t=1000: {threshold_1000:.4f}, t=10000: {threshold_10000:.4f}")


def test_nrp_coefficient_range():
    """Test NRP with different coefficients c ∈ [0.5, 2.0]."""
    bucketing = HandBucketing(BucketConfig())
    
    for c in [0.5, 1.0, 1.5, 2.0]:
        sampler = ExternalSampler(
            bucketing=bucketing,
            num_players=2,
            nrp_coefficient=c
        )
        
        threshold = sampler.get_nrp_threshold(1000)
        expected = -c / (1000 ** 0.5)
        
        assert abs(threshold - expected) < 1e-6, \
            f"Threshold mismatch for c={c}: {threshold} != {expected}"
    
    print("✓ NRP coefficient range [0.5, 2.0] works correctly")


def test_player_alternation():
    """Test that external sampling alternates player updates."""
    bucketing = HandBucketing(BucketConfig())
    
    sampler = ExternalSampler(
        bucketing=bucketing,
        num_players=2,
        use_linear_weighting=True
    )
    
    # Run a few iterations with alternating players
    for iteration in range(10):
        updating_player = iteration % 2
        utility = sampler.sample_iteration(iteration, updating_player=updating_player)
        
        # Just check that it runs without error
        assert utility is not None
    
    print("✓ Player alternation works")


def test_strategy_freezing():
    """Test strategy freezing mode."""
    bucketing = HandBucketing(BucketConfig())
    
    # Without freezing
    sampler_normal = ExternalSampler(
        bucketing=bucketing,
        num_players=2,
        strategy_freezing=False
    )
    
    # With freezing
    sampler_frozen = ExternalSampler(
        bucketing=bucketing,
        num_players=2,
        strategy_freezing=True
    )
    
    assert sampler_normal.strategy_freezing == False
    assert sampler_frozen.strategy_freezing == True
    
    print("✓ Strategy freezing mode works")


def test_linear_weighting():
    """Test linear MCCFR weighting."""
    bucketing = HandBucketing(BucketConfig())
    
    # With linear weighting
    sampler_linear = ExternalSampler(
        bucketing=bucketing,
        num_players=2,
        use_linear_weighting=True
    )
    
    # Without linear weighting
    sampler_uniform = ExternalSampler(
        bucketing=bucketing,
        num_players=2,
        use_linear_weighting=False
    )
    
    assert sampler_linear.use_linear_weighting == True
    assert sampler_uniform.use_linear_weighting == False
    
    print("✓ Linear weighting configuration works")


if __name__ == "__main__":
    print("Testing ExternalSampler...")
    print()
    
    test_external_sampler_initialization()
    print()
    
    test_nrp_threshold_calculation()
    print()
    
    test_nrp_coefficient_range()
    print()
    
    test_player_alternation()
    print()
    
    test_strategy_freezing()
    print()
    
    test_linear_weighting()
    print()
    
    print("All tests passed! ✓")
