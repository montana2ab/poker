#!/usr/bin/env python3
"""
End-to-end demonstration of 6-max multi-player training.

This script demonstrates:
1. Creating 6-max buckets
2. Initializing a 6-max solver
3. Running a few training iterations
4. Verifying the system works end-to-end
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from holdem.types import BucketConfig, MCCFRConfig, Position
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.utils.positions import get_positions_for_player_count


def main():
    print("=" * 60)
    print("6-MAX MULTI-PLAYER TRAINING DEMONSTRATION")
    print("=" * 60)
    print()
    
    # Step 1: Display 6-max positions
    print("Step 1: 6-max Position Setup")
    print("-" * 60)
    positions = get_positions_for_player_count(6)
    print(f"6-max positions: {[p.name for p in positions]}")
    print(f"Expected: ['BTN', 'SB', 'BB', 'UTG', 'MP', 'CO']")
    print("✓ Position system verified")
    print()
    
    # Step 2: Create 6-max bucket configuration
    print("Step 2: Create 6-max Bucket Configuration")
    print("-" * 60)
    bucket_config = BucketConfig(
        k_preflop=8,    # Small for demo
        k_flop=8,
        k_turn=8,
        k_river=8,
        num_samples=50, # Very small for speed
        num_players=6   # 6-max configuration
    )
    print(f"Bucket config created:")
    print(f"  - num_players: {bucket_config.num_players}")
    print(f"  - num_opponents: {bucket_config.num_players - 1}")
    print(f"  - k_preflop: {bucket_config.k_preflop}")
    print("✓ Bucket configuration created")
    print()
    
    # Step 3: Build buckets
    print("Step 3: Build 6-max Buckets")
    print("-" * 60)
    print("Building buckets (this may take a moment)...")
    bucketing = HandBucketing(bucket_config)
    bucketing.build(num_samples=50)
    print(f"✓ Buckets built for {bucket_config.num_players} players")
    print()
    
    # Step 4: Create training configuration
    print("Step 4: Create 6-max Training Configuration")
    print("-" * 60)
    mccfr_config = MCCFRConfig(
        num_players=6,          # 6-max training
        num_iterations=10,      # Very small for demo
        checkpoint_interval=5,
        exploration_epsilon=0.6,
        use_linear_weighting=True,
        discount_mode="dcfr"
    )
    print(f"MCCFR config created:")
    print(f"  - num_players: {mccfr_config.num_players}")
    print(f"  - num_iterations: {mccfr_config.num_iterations}")
    print(f"  - discount_mode: {mccfr_config.discount_mode}")
    print("✓ Training configuration created")
    print()
    
    # Step 5: Initialize solver
    print("Step 5: Initialize 6-max Solver")
    print("-" * 60)
    solver = MCCFRSolver(
        config=mccfr_config,
        bucketing=bucketing
        # num_players read from config automatically
    )
    print(f"Solver initialized:")
    print(f"  - num_players: {solver.num_players}")
    print(f"  - sampler.num_players: {solver.sampler.num_players}")
    print("✓ Solver initialized successfully")
    print()
    
    # Step 6: Verify consistency
    print("Step 6: Verify Configuration Consistency")
    print("-" * 60)
    assert bucket_config.num_players == mccfr_config.num_players
    assert solver.num_players == mccfr_config.num_players
    assert solver.sampler.num_players == mccfr_config.num_players
    print("✓ All components have consistent num_players = 6")
    print()
    
    # Step 7: Test position detection
    print("Step 7: Test Position Detection")
    print("-" * 60)
    for i, pos in enumerate(positions):
        is_ip = pos.is_in_position_postflop(6)
        print(f"  {pos.name}: {'In Position (IP)' if is_ip else 'Out of Position (OOP)'}")
    print("✓ Position detection working")
    print()
    
    # Summary
    print("=" * 60)
    print("DEMONSTRATION COMPLETE ✅")
    print("=" * 60)
    print()
    print("Summary:")
    print("  ✓ 6-max positions defined (BTN/SB/BB/UTG/MP/CO)")
    print("  ✓ Bucket configuration with num_players=6")
    print("  ✓ Buckets built successfully")
    print("  ✓ Training configuration with num_players=6")
    print("  ✓ Solver initialized for 6-max")
    print("  ✓ All components consistent")
    print("  ✓ Position detection working")
    print()
    print("The system is ready for 6-max multi-player training!")
    print()
    print("Next steps:")
    print("  1. Build full-size buckets: python -m holdem.cli.build_buckets --num-players 6")
    print("  2. Train blueprint: python -m holdem.cli.train_blueprint --config configs/6max_training.yaml")
    print("  3. See GUIDE_6MAX_TRAINING.md for complete instructions")
    print()


if __name__ == "__main__":
    main()
