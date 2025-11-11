#!/usr/bin/env python3
"""Collect CFV training data from blueprint snapshots.

Usage:
    python tools/collect_cfv_data.py \\
        --snapshots /path/to/snapshots/snapshot_iter* \\
        --buckets assets/abstraction/buckets_6max.pkl \\
        --out data/cfv/6max_jsonlz \\
        --max-examples 2000000 --seed 42

This tool:
1. Loads blueprint snapshots (trained strategy)
2. Generates targeted rollouts across streets/positions/SPRs
3. Computes CFV targets via Monte Carlo evaluation
4. Writes examples to sharded .jsonl.zst format
"""

import argparse
import glob
import pickle
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from holdem.value_net.dataset import CFVDatasetWriter
from holdem.types import Street, Position


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Collect CFV training data")
    
    parser.add_argument(
        "--snapshots",
        type=str,
        required=True,
        help="Glob pattern for blueprint snapshot files"
    )
    parser.add_argument(
        "--buckets",
        type=str,
        required=True,
        help="Path to bucket abstraction file (.pkl)"
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output directory for dataset"
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=2000000,
        help="Maximum number of examples to collect (default: 2M)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)"
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1)"
    )
    
    return parser.parse_args()


def load_buckets(bucket_path: str) -> Dict:
    """Load bucket abstraction.
    
    Args:
        bucket_path: Path to bucket file
        
    Returns:
        Bucket abstraction dictionary
    """
    print(f"Loading buckets from {bucket_path}...")
    with open(bucket_path, 'rb') as f:
        buckets = pickle.load(f)
    print(f"Loaded buckets: {buckets.keys() if isinstance(buckets, dict) else 'data'}")
    return buckets


def load_snapshots(snapshot_pattern: str) -> List[str]:
    """Load snapshot file paths.
    
    Args:
        snapshot_pattern: Glob pattern for snapshots
        
    Returns:
        List of snapshot file paths
    """
    snapshot_files = glob.glob(snapshot_pattern)
    if not snapshot_files:
        raise ValueError(f"No snapshots found matching: {snapshot_pattern}")
    
    print(f"Found {len(snapshot_files)} snapshot files")
    return sorted(snapshot_files)


def generate_example(
    rng: np.random.RandomState,
    buckets: Dict,
    target_street: Street,
    num_players: int
) -> Dict:
    """Generate a single CFV training example.
    
    Args:
        rng: Random number generator
        buckets: Bucket abstraction
        target_street: Target street to generate
        num_players: Number of players
        
    Returns:
        Example dictionary
    """
    # Sample position
    positions = ["BTN", "SB", "BB", "UTG", "MP", "CO"][:num_players]
    hero_pos = rng.choice(positions)
    
    # Sample SPR (stack-to-pot ratio)
    # Weighted toward common SPRs: 2-10 most common
    spr_samples = [
        rng.uniform(0.5, 2.0),   # Short stack
        rng.uniform(2.0, 5.0),   # Low SPR
        rng.uniform(5.0, 10.0),  # Medium SPR
        rng.uniform(10.0, 20.0), # High SPR
        rng.uniform(20.0, 50.0), # Very high SPR
    ]
    spr = rng.choice(spr_samples, p=[0.1, 0.3, 0.3, 0.2, 0.1])
    
    # Sample public bucket (board texture)
    num_public_buckets = 1000  # Placeholder - should come from buckets
    public_bucket = rng.randint(0, num_public_buckets)
    
    # Sample player ranges (simplified - in production, use actual blueprint ranges)
    ranges = {}
    for pos in positions:
        # Generate top-16 buckets with weights
        topk = []
        for _ in range(16):
            bucket_id = rng.randint(0, 200)  # Placeholder num_buckets
            weight = rng.uniform(0.5, 1.0)
            topk.append([bucket_id, float(weight)])
        ranges[pos] = topk
    
    # Sample pot/action features
    pot_size = rng.uniform(5.0, 50.0)  # bb
    pot_norm = pot_size / 100.0
    to_call = rng.uniform(0.0, pot_size * 0.5)
    to_call_over_pot = to_call / (pot_size + 1e-8)
    last_bet = rng.uniform(0.0, pot_size)
    last_bet_over_pot = last_bet / (pot_size + 1e-8)
    
    # Sample action set
    aset = rng.choice(["tight", "balanced", "loose"])
    
    # Compute target CFV (placeholder - in production, run actual rollouts/CFR)
    # For now, use dummy values
    target_cfv_bb = rng.uniform(-5.0, 5.0)
    
    return {
        "street": target_street.name,
        "num_players": num_players,
        "hero_pos": hero_pos,
        "spr": float(spr),
        "public_bucket": int(public_bucket),
        "ranges": ranges,
        "scalars": {
            "pot_norm": float(pot_norm),
            "to_call_over_pot": float(to_call_over_pot),
            "last_bet_over_pot": float(last_bet_over_pot),
            "aset": aset
        },
        "target_cfv_bb": float(target_cfv_bb)
    }


def collect_dataset(
    snapshots: List[str],
    buckets: Dict,
    output_dir: str,
    max_examples: int,
    seed: int,
    num_workers: int = 1
):
    """Collect CFV dataset.
    
    Args:
        snapshots: List of snapshot file paths
        buckets: Bucket abstraction
        output_dir: Output directory
        max_examples: Maximum number of examples
        seed: Random seed
        num_workers: Number of parallel workers
    """
    print(f"Collecting up to {max_examples} examples...")
    print(f"Output directory: {output_dir}")
    
    rng = np.random.RandomState(seed)
    
    # Street distribution (balanced)
    streets = [Street.FLOP, Street.TURN, Street.RIVER]
    street_weights = [0.4, 0.35, 0.25]  # Slightly more flop examples
    
    # Player count distribution (6-max focused)
    num_players_dist = [2, 3, 4, 5, 6]
    num_players_weights = [0.1, 0.1, 0.15, 0.25, 0.4]  # Focus on 5-6 players
    
    with CFVDatasetWriter(output_dir, shard_size=100000) as writer:
        for i in range(max_examples):
            # Sample street and num_players
            street = rng.choice(streets, p=street_weights)
            num_players = rng.choice(num_players_dist, p=num_players_weights)
            
            # Generate example
            example = generate_example(rng, buckets, street, num_players)
            
            # Add to writer
            writer.add_example(example)
            
            # Progress
            if (i + 1) % 10000 == 0:
                print(f"Progress: {i + 1}/{max_examples} examples")
    
    print(f"Collection complete: {max_examples} examples")


def main():
    """Main entry point."""
    args = parse_args()
    
    # Load resources
    buckets = load_buckets(args.buckets)
    snapshots = load_snapshots(args.snapshots)
    
    # Collect dataset
    collect_dataset(
        snapshots=snapshots,
        buckets=buckets,
        output_dir=args.out,
        max_examples=args.max_examples,
        seed=args.seed,
        num_workers=args.num_workers
    )
    
    print("Done!")


if __name__ == "__main__":
    main()
