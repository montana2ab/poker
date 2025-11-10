#!/usr/bin/env python3
"""Integration test for chunked training mode.

This test creates a minimal training setup and runs through multiple chunks
to verify that state is correctly preserved across chunk boundaries.
"""

import tempfile
import subprocess
import sys
from pathlib import Path


def test_chunked_training_integration():
    """Test chunked training end-to-end."""
    print("=" * 80)
    print("Integration Test: Chunked Training Mode")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create minimal bucket configuration
        print("\n1. Creating minimal buckets for testing...")
        bucket_config = tmpdir / "bucket_config.yaml"
        bucket_config.write_text("""
k_preflop: 4
k_flop: 4
k_turn: 4
k_river: 4
num_samples: 100
seed: 42
""")
        
        buckets_file = tmpdir / "test_buckets.pkl"
        
        # Build buckets
        result = subprocess.run([
            sys.executable, "-m", "holdem.cli.build_buckets",
            "--config", str(bucket_config),
            "--output", str(buckets_file)
        ], cwd="/home/runner/work/poker/poker", capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Failed to build buckets: {result.stderr}")
            return False
        
        print("✓ Buckets created")
        
        # Run first chunk (should train 50 iterations and exit)
        print("\n2. Running first chunk (0 -> 50 iterations)...")
        logdir = tmpdir / "training"
        
        result = subprocess.run([
            sys.executable, "-m", "holdem.cli.train_blueprint",
            "--buckets", str(buckets_file),
            "--logdir", str(logdir),
            "--iters", "100",
            "--chunked",
            "--chunk-iterations", "50",
            "--checkpoint-interval", "25",
            "--no-tensorboard"
        ], cwd="/home/runner/work/poker/poker", capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"First chunk failed: {result.stderr}")
            return False
        
        # Check that output mentions chunk completion
        if "Chunk Complete" not in result.stdout and "Chunk Complete" not in result.stderr:
            print("Warning: Expected 'Chunk Complete' message not found")
        
        print("✓ First chunk completed")
        
        # Verify checkpoint exists
        checkpoint_dir = logdir / "checkpoints"
        if not checkpoint_dir.exists():
            print("✗ Checkpoint directory not created")
            return False
        
        checkpoints = list(checkpoint_dir.glob("checkpoint_*.pkl"))
        if not checkpoints:
            print("✗ No checkpoints found")
            return False
        
        print(f"✓ Checkpoint created: {checkpoints[0].name}")
        
        # Run second chunk (should resume from 50 and train to 100)
        print("\n3. Running second chunk (50 -> 100 iterations)...")
        
        result = subprocess.run([
            sys.executable, "-m", "holdem.cli.train_blueprint",
            "--buckets", str(buckets_file),
            "--logdir", str(logdir),
            "--iters", "100",
            "--chunked",
            "--chunk-iterations", "50",
            "--checkpoint-interval", "25",
            "--no-tensorboard"
        ], cwd="/home/runner/work/poker/poker", capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"Second chunk failed: {result.stderr}")
            return False
        
        # Check that output mentions resuming
        if "Resuming from checkpoint" not in result.stdout and "Resuming from checkpoint" not in result.stderr:
            print("Warning: Expected 'Resuming from checkpoint' message not found")
        
        # Check that output mentions completion
        if "Training Complete" not in result.stdout and "Training Complete" not in result.stderr:
            print("Warning: Expected 'Training Complete' message not found")
        
        print("✓ Second chunk completed")
        
        # Verify final checkpoint
        checkpoints = sorted(checkpoint_dir.glob("checkpoint_*.pkl"))
        if len(checkpoints) < 2:
            print("✗ Expected at least 2 checkpoints")
            return False
        
        print(f"✓ Total checkpoints: {len(checkpoints)}")
        
        # Verify metadata
        import json
        last_checkpoint = checkpoints[-1]
        metadata_file = checkpoint_dir / f"{last_checkpoint.stem}_metadata.json"
        
        if not metadata_file.exists():
            print("✗ Metadata file not found")
            return False
        
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        iteration = metadata.get('iteration', 0)
        if iteration < 100:
            print(f"✗ Expected iteration >= 100, got {iteration}")
            return False
        
        print(f"✓ Final iteration: {iteration}")
        
        # Verify cumulative time tracking
        if 'elapsed_seconds' not in metadata:
            print("✗ Cumulative elapsed time not tracked")
            return False
        
        if 'chunk_elapsed_seconds' not in metadata:
            print("✗ Chunk elapsed time not tracked")
            return False
        
        print(f"✓ Cumulative time: {metadata['elapsed_seconds']:.2f}s")
        print(f"✓ Chunk time: {metadata['chunk_elapsed_seconds']:.2f}s")
        
        # Verify RNG state is saved
        if 'rng_state' not in metadata:
            print("✗ RNG state not saved")
            return False
        
        print("✓ RNG state preserved")
        
        # Verify epsilon is saved
        if 'epsilon' not in metadata:
            print("✗ Epsilon not saved")
            return False
        
        print(f"✓ Epsilon: {metadata['epsilon']}")
        
        print("\n" + "=" * 80)
        print("✓ Integration test PASSED")
        print("=" * 80)
        
        return True


if __name__ == "__main__":
    try:
        success = test_chunked_training_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Integration test FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
