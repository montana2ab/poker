#!/usr/bin/env python3
"""Manual test script for checkpoint validation."""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from holdem.types import BucketConfig, MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.utils.serialization import save_json, save_pickle


def test_checkpoint_validation():
    """Test checkpoint validation logic."""
    print("=" * 60)
    print("Testing Checkpoint Validation")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        print("\n1. Creating a complete checkpoint...")
        
        # Create small bucketing and solver
        config = BucketConfig(
            k_preflop=4,
            k_flop=8,
            k_turn=8,
            k_river=4,
            num_samples=100,
            seed=42
        )
        
        bucketing = HandBucketing(config)
        bucketing.build(num_samples=100)
        
        mccfr_config = MCCFRConfig(num_iterations=10)
        solver = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        
        # Run a few iterations
        print("   Running 5 training iterations...")
        for i in range(5):
            solver.sampler.sample_iteration(i + 1)
            solver.iteration = i + 1
        
        # Save complete checkpoint
        print("   Saving checkpoint...")
        solver.save_checkpoint(tmpdir, iteration=5, elapsed_seconds=1.0)
        
        checkpoint_path = tmpdir / "checkpoints" / "checkpoint_iter5_t1s.pkl"
        
        # Test completeness check
        print("\n2. Testing is_checkpoint_complete()...")
        is_complete = MCCFRSolver.is_checkpoint_complete(checkpoint_path)
        print(f"   Complete checkpoint recognized: {'✓' if is_complete else '✗'}")
        assert is_complete, "Complete checkpoint should be recognized"
        
        # Test loading complete checkpoint
        print("\n3. Testing load_checkpoint() with complete checkpoint...")
        solver2 = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        try:
            iteration = solver2.load_checkpoint(checkpoint_path, validate_buckets=True)
            print(f"   Checkpoint loaded successfully at iteration {iteration}")
            assert iteration == 5, f"Expected iteration 5, got {iteration}"
        except Exception as e:
            print(f"   ✗ Failed to load: {e}")
            raise
        
        # Test incomplete checkpoint detection
        print("\n4. Testing incomplete checkpoint detection...")
        
        # Create incomplete checkpoint (only main .pkl file)
        incomplete_dir = tmpdir / "incomplete_checkpoints"
        incomplete_dir.mkdir()
        incomplete_path = incomplete_dir / "checkpoint_iter10.pkl"
        save_pickle({"dummy": "data"}, incomplete_path)
        
        is_complete = MCCFRSolver.is_checkpoint_complete(incomplete_path)
        print(f"   Incomplete checkpoint detected: {'✓' if not is_complete else '✗'}")
        assert not is_complete, "Incomplete checkpoint should be detected"
        
        # Test loading incomplete checkpoint (should raise ValueError)
        print("\n5. Testing load_checkpoint() with incomplete checkpoint...")
        solver3 = MCCFRSolver(mccfr_config, bucketing, num_players=2)
        try:
            solver3.load_checkpoint(incomplete_path, validate_buckets=True)
            print("   ✗ Should have raised ValueError for incomplete checkpoint")
            raise AssertionError("Expected ValueError for incomplete checkpoint")
        except ValueError as e:
            print(f"   ✓ Correctly rejected incomplete checkpoint")
            print(f"   Error message: {str(e)[:100]}...")
        
        # Test partially incomplete checkpoint (with metadata but no regrets)
        print("\n6. Testing partially incomplete checkpoint (metadata only)...")
        partial_path = incomplete_dir / "checkpoint_iter20.pkl"
        save_pickle({"dummy": "data"}, partial_path)
        save_json({"iteration": 20}, incomplete_dir / "checkpoint_iter20_metadata.json")
        
        is_complete = MCCFRSolver.is_checkpoint_complete(partial_path)
        print(f"   Partial checkpoint detected as incomplete: {'✓' if not is_complete else '✗'}")
        assert not is_complete, "Partial checkpoint should be detected as incomplete"
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)


if __name__ == "__main__":
    test_checkpoint_validation()
