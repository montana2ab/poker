#!/usr/bin/env python3
"""
Example workflow for creating buckets.pkl using pack_buckets.py

This demonstrates the recommended two-step process:
1. Build street abstractions (expensive, done once)
2. Pack into buckets.pkl (fast, repeatable)
"""

import subprocess
from pathlib import Path


def main():
    print("=" * 80)
    print("Example: Building buckets.pkl with pack_buckets.py")
    print("=" * 80)
    print()
    
    # Configuration
    flop_buckets = 8000
    turn_buckets = 2000
    river_buckets = 400
    preflop_buckets = 24
    
    flop_samples = 50000
    turn_samples = 30000
    river_samples = 20000
    preflop_samples = 100000
    
    seed = 42
    
    # Output directories
    abstractions_dir = Path("data/abstractions")
    flop_dir = abstractions_dir / "flop"
    turn_dir = abstractions_dir / "turn"
    river_dir = abstractions_dir / "river"
    
    output_path = Path("assets/abstraction/buckets.pkl")
    
    print("Configuration:")
    print(f"  Flop: {flop_buckets} buckets, {flop_samples} samples")
    print(f"  Turn: {turn_buckets} buckets, {turn_samples} samples")
    print(f"  River: {river_buckets} buckets, {river_samples} samples")
    print(f"  Preflop: {preflop_buckets} buckets, {preflop_samples} samples")
    print(f"  Seed: {seed}")
    print(f"  Output: {output_path}")
    print()
    
    # Check if street abstractions already exist
    flop_exists = (flop_dir / f"flop_medoids_{flop_buckets}.npy").exists()
    turn_exists = (turn_dir / f"turn_medoids_{turn_buckets}.npy").exists()
    river_exists = (river_dir / f"river_medoids_{river_buckets}.npy").exists()
    
    if flop_exists and turn_exists and river_exists:
        print("✓ Street abstractions already exist")
        print("  Using --pack-only mode (fast)")
        print()
        
        # Pack only
        cmd = [
            "python", "pack_buckets.py",
            "--pack-only",
            "--preflop-buckets", str(preflop_buckets),
            "--flop-buckets", str(flop_buckets),
            "--turn-buckets", str(turn_buckets),
            "--river-buckets", str(river_buckets),
            "--preflop-samples", str(preflop_samples),
            "--flop-dir", str(flop_dir),
            "--turn-dir", str(turn_dir),
            "--river-dir", str(river_dir),
            "--output", str(output_path),
            "--seed", str(seed)
        ]
        
    else:
        print("⚠ Street abstractions not found")
        print("  Using --build-all mode (30-60 minutes)")
        print()
        print("  This will:")
        print("  1. Build flop abstraction (longest step)")
        print("  2. Build turn abstraction")
        print("  3. Build river abstraction")
        print("  4. Build preflop abstraction")
        print("  5. Pack everything into buckets.pkl")
        print()
        
        # Build all
        cmd = [
            "python", "pack_buckets.py",
            "--build-all",
            "--preflop-buckets", str(preflop_buckets),
            "--flop-buckets", str(flop_buckets),
            "--turn-buckets", str(turn_buckets),
            "--river-buckets", str(river_buckets),
            "--preflop-samples", str(preflop_samples),
            "--flop-samples", str(flop_samples),
            "--turn-samples", str(turn_samples),
            "--river-samples", str(river_samples),
            "--output", str(output_path),
            "--seed", str(seed)
        ]
    
    print("Command to run:")
    print("  " + " ".join(cmd))
    print()
    
    response = input("Execute now? [y/N]: ")
    if response.lower() == 'y':
        print()
        print("Running...")
        subprocess.run(cmd)
    else:
        print()
        print("Skipped. You can run the command manually:")
        print()
        print(" ".join(cmd))
        print()
    
    print()
    print("After completion, verify with:")
    print("  python validate_buckets.py assets/abstraction/buckets.pkl")
    print()


if __name__ == "__main__":
    main()
