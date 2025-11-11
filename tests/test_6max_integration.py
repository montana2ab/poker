"""Integration test for 6-max training setup."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import BucketConfig, MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver


def test_6max_bucketing_initialization():
    """Test that 6-max buckets can be built."""
    config = BucketConfig(
        k_preflop=8,
        k_flop=8,
        k_turn=8,
        k_river=8,
        num_samples=50,  # Very small for fast test
        num_players=6
    )
    
    bucketing = HandBucketing(config)
    assert bucketing.config.num_players == 6
    
    # Build buckets (small sample for speed)
    bucketing.build(num_samples=50)
    assert bucketing.fitted
    
    print("✓ 6-max bucketing builds successfully")


def test_6max_solver_initialization():
    """Test that 6-max solver can be initialized."""
    # Create small buckets for testing
    bucket_config = BucketConfig(
        k_preflop=8,
        k_flop=8,
        k_turn=8,
        k_river=8,
        num_samples=50,
        num_players=6
    )
    bucketing = HandBucketing(bucket_config)
    bucketing.build(num_samples=50)
    
    # Create 6-max training config
    mccfr_config = MCCFRConfig(
        num_players=6,
        num_iterations=100,  # Very small for testing
        checkpoint_interval=50
    )
    
    # Initialize solver
    solver = MCCFRSolver(
        config=mccfr_config,
        bucketing=bucketing
    )
    
    assert solver.num_players == 6
    assert solver.sampler.num_players == 6
    
    print("✓ 6-max solver initializes successfully")


def test_6max_solver_uses_config_num_players():
    """Test that solver uses config.num_players if not explicitly provided."""
    bucket_config = BucketConfig(
        k_preflop=8,
        k_flop=8,
        k_turn=8,
        k_river=8,
        num_samples=50,
        num_players=6
    )
    bucketing = HandBucketing(bucket_config)
    bucketing.build(num_samples=50)
    
    mccfr_config = MCCFRConfig(
        num_players=6,
        num_iterations=100
    )
    
    # Don't pass num_players - should use from config
    solver = MCCFRSolver(
        config=mccfr_config,
        bucketing=bucketing
    )
    
    assert solver.num_players == 6
    print("✓ Solver correctly reads num_players from config")


def test_2player_backward_compatibility():
    """Test that 2-player (heads-up) still works by default."""
    # Default configs should be 2-player
    bucket_config = BucketConfig(
        k_preflop=8,
        k_flop=8,
        k_turn=8,
        k_river=8,
        num_samples=50
    )
    assert bucket_config.num_players == 2
    
    bucketing = HandBucketing(bucket_config)
    bucketing.build(num_samples=50)
    
    mccfr_config = MCCFRConfig(num_iterations=100)
    assert mccfr_config.num_players == 2
    
    solver = MCCFRSolver(
        config=mccfr_config,
        bucketing=bucketing
    )
    
    assert solver.num_players == 2
    print("✓ 2-player (heads-up) backward compatibility maintained")


def test_config_num_players_consistency():
    """Test that bucket and MCCFR configs should have consistent num_players."""
    # Create configs with same num_players
    bucket_config = BucketConfig(
        k_preflop=8,
        k_flop=8,
        k_turn=8,
        k_river=8,
        num_samples=50,
        num_players=6
    )
    
    mccfr_config = MCCFRConfig(
        num_players=6,
        num_iterations=100
    )
    
    assert bucket_config.num_players == mccfr_config.num_players
    print("✓ Config consistency check passes")


if __name__ == "__main__":
    print("Testing 6-max training integration...")
    print()
    
    test_6max_bucketing_initialization()
    print()
    
    test_6max_solver_initialization()
    print()
    
    test_6max_solver_uses_config_num_players()
    print()
    
    test_2player_backward_compatibility()
    print()
    
    test_config_num_players_consistency()
    print()
    
    print("All 6-max integration tests passed! ✓")
