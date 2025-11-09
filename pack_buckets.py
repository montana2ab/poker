#!/usr/bin/env python3
"""Pack street-specific bucket files into a single buckets.pkl file.

This script bridges the gap between the individual street abstraction scripts
(build_flop.py, build_turn.py, build_river.py) and the training system that
expects a single buckets.pkl file.

Usage:
    python pack_buckets.py [options]

Examples:
    # Use default settings (recommended)
    python pack_buckets.py
    
    # Custom configuration
    python pack_buckets.py --flop-buckets 10000 --turn-buckets 3000 --river-buckets 500
    
    # Specify output path
    python pack_buckets.py --output assets/abstraction/buckets.pkl
"""

import sys
import argparse
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from holdem.types import Street, BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.utils.logging import get_logger
from holdem.utils.serialization import save_pickle

logger = get_logger("pack_buckets")


def create_kmeans_from_medoids(medoids: np.ndarray, num_clusters: int, seed: int = 42) -> KMeans:
    """Create a KMeans model from pre-computed cluster centers (medoids).
    
    Args:
        medoids: Cluster centers (n_clusters, n_features)
        num_clusters: Number of clusters
        seed: Random seed
        
    Returns:
        KMeans model with the given cluster centers
    """
    # Create a KMeans model
    kmeans = KMeans(n_clusters=num_clusters, random_state=seed, n_init=1, max_iter=1)
    
    # Set the cluster centers directly
    # Note: We need to set the internal state without fitting
    kmeans.cluster_centers_ = medoids.astype(np.float64)
    kmeans._n_threads = 1
    kmeans.n_features_in_ = medoids.shape[1]
    
    # Mark as fitted (sklearn internal attribute)
    kmeans._n_init = 1
    
    return kmeans


def pack_buckets(
    flop_dir: Path,
    turn_dir: Path, 
    river_dir: Path,
    output_path: Path,
    k_preflop: int = 24,
    k_flop: int = 8000,
    k_turn: int = 2000,
    k_river: int = 400,
    preflop_samples: int = 100000,
    seed: int = 42
):
    """Pack street-specific bucket files into a single buckets.pkl file.
    
    Args:
        flop_dir: Directory containing flop abstraction files
        turn_dir: Directory containing turn abstraction files
        river_dir: Directory containing river abstraction files
        output_path: Output path for buckets.pkl
        k_preflop: Number of preflop buckets
        k_flop: Number of flop buckets
        k_turn: Number of turn buckets
        k_river: Number of river buckets
        preflop_samples: Number of samples for preflop bucketing
        seed: Random seed
    """
    logger.info("=" * 80)
    logger.info("Packing street-specific buckets into buckets.pkl")
    logger.info("=" * 80)
    
    # Create configuration
    config = BucketConfig(
        k_preflop=k_preflop,
        k_flop=k_flop,
        k_turn=k_turn,
        k_river=k_river,
        num_samples=preflop_samples,  # Only used for preflop
        seed=seed
    )
    
    logger.info(f"Configuration:")
    logger.info(f"  Preflop: {k_preflop} buckets")
    logger.info(f"  Flop: {k_flop} buckets")
    logger.info(f"  Turn: {k_turn} buckets")
    logger.info(f"  River: {k_river} buckets")
    logger.info(f"  Preflop samples: {preflop_samples}")
    logger.info(f"  Seed: {seed}")
    logger.info("")
    
    models = {}
    
    # Build preflop buckets using HandBucketing
    logger.info("Building preflop buckets...")
    bucketing_preflop = HandBucketing(config, preflop_equity_samples=100)
    
    # Sample and cluster preflop hands
    from holdem.abstraction.preflop_features import extract_preflop_features
    from holdem.utils.rng import get_rng
    from holdem.types import Card
    from holdem.utils.arrays import prepare_for_sklearn
    
    rng = get_rng(seed)
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    suits = ['h', 'd', 'c', 's']
    
    features_list = []
    for _ in range(preflop_samples):
        deck = [Card(rank, suit) for rank in ranks for suit in suits]
        rng.shuffle(deck)
        hole_cards = deck[:2]
        features = extract_preflop_features(hole_cards, equity_samples=100)
        features_list.append(features)
    
    X = prepare_for_sklearn(np.array(features_list))
    logger.info(f"  Feature matrix shape: {X.shape}")
    
    kmeans_preflop = KMeans(n_clusters=k_preflop, random_state=seed, n_init=10, max_iter=300)
    kmeans_preflop.fit(X)
    models[Street.PREFLOP] = kmeans_preflop
    logger.info(f"  Completed: inertia={kmeans_preflop.inertia_:.2f}")
    logger.info("")
    
    # Load flop abstraction
    logger.info(f"Loading flop abstraction from {flop_dir}...")
    flop_medoids_file = flop_dir / f"flop_medoids_{k_flop}.npy"
    flop_norm_file = flop_dir / f"flop_normalization_{k_flop}.npz"
    
    if not flop_medoids_file.exists():
        raise FileNotFoundError(
            f"Flop medoids file not found: {flop_medoids_file}\n"
            f"Run: python abstraction/build_flop.py --buckets {k_flop} --output {flop_dir}"
        )
    
    flop_medoids = np.load(flop_medoids_file)
    logger.info(f"  Loaded medoids shape: {flop_medoids.shape}")
    
    models[Street.FLOP] = create_kmeans_from_medoids(flop_medoids, k_flop, seed)
    logger.info(f"  Created KMeans model with {k_flop} clusters")
    logger.info("")
    
    # Load turn abstraction
    logger.info(f"Loading turn abstraction from {turn_dir}...")
    turn_medoids_file = turn_dir / f"turn_medoids_{k_turn}.npy"
    turn_norm_file = turn_dir / f"turn_normalization_{k_turn}.npz"
    
    if not turn_medoids_file.exists():
        raise FileNotFoundError(
            f"Turn medoids file not found: {turn_medoids_file}\n"
            f"Run: python abstraction/build_turn.py --buckets {k_turn} --output {turn_dir}"
        )
    
    turn_medoids = np.load(turn_medoids_file)
    logger.info(f"  Loaded medoids shape: {turn_medoids.shape}")
    
    models[Street.TURN] = create_kmeans_from_medoids(turn_medoids, k_turn, seed)
    logger.info(f"  Created KMeans model with {k_turn} clusters")
    logger.info("")
    
    # Load river abstraction
    logger.info(f"Loading river abstraction from {river_dir}...")
    river_medoids_file = river_dir / f"river_medoids_{k_river}.npy"
    river_norm_file = river_dir / f"river_normalization_{k_river}.npz"
    
    if not river_medoids_file.exists():
        raise FileNotFoundError(
            f"River medoids file not found: {river_medoids_file}\n"
            f"Run: python abstraction/build_river.py --buckets {k_river} --output {river_dir}"
        )
    
    river_medoids = np.load(river_medoids_file)
    logger.info(f"  Loaded medoids shape: {river_medoids.shape}")
    
    models[Street.RIVER] = create_kmeans_from_medoids(river_medoids, k_river, seed)
    logger.info(f"  Created KMeans model with {k_river} clusters")
    logger.info("")
    
    # Pack into buckets.pkl format
    logger.info(f"Packing into {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        'config': vars(config),
        'models': models,
        'fitted': True
    }
    
    save_pickle(data, output_path)
    
    logger.info(f"✓ Successfully created {output_path}")
    logger.info("")
    logger.info("Summary:")
    logger.info(f"  - Preflop: {k_preflop} buckets (built from scratch)")
    logger.info(f"  - Flop: {k_flop} buckets (from {flop_medoids_file.name})")
    logger.info(f"  - Turn: {k_turn} buckets (from {turn_medoids_file.name})")
    logger.info(f"  - River: {k_river} buckets (from {river_medoids_file.name})")
    logger.info("")
    logger.info("The buckets.pkl file is now ready for training!")
    logger.info("=" * 80)


def build_and_pack(
    k_preflop: int = 24,
    k_flop: int = 8000,
    k_turn: int = 2000,
    k_river: int = 400,
    flop_samples: int = 50000,
    turn_samples: int = 30000,
    river_samples: int = 20000,
    preflop_samples: int = 100000,
    seed: int = 42,
    output_dir: Path = None,
    output_path: Path = None
):
    """Build all street abstractions and pack them into buckets.pkl.
    
    Args:
        k_preflop: Number of preflop buckets
        k_flop: Number of flop buckets
        k_turn: Number of turn buckets
        k_river: Number of river buckets
        flop_samples: Number of samples for flop clustering
        turn_samples: Number of samples for turn clustering
        river_samples: Number of samples for river clustering
        preflop_samples: Number of samples for preflop clustering
        seed: Random seed
        output_dir: Directory for intermediate abstraction files
        output_path: Path for final buckets.pkl file
    """
    if output_dir is None:
        output_dir = Path("data/abstractions")
    
    if output_path is None:
        output_path = Path("assets/abstraction/buckets.pkl")
    
    flop_dir = output_dir / "flop"
    turn_dir = output_dir / "turn"
    river_dir = output_dir / "river"
    
    # Import build functions
    from abstraction.build_flop import build_flop_abstraction
    from abstraction.build_turn import build_turn_abstraction
    from abstraction.build_river import build_river_abstraction
    
    logger.info("=" * 80)
    logger.info("Building and packing street abstractions")
    logger.info("=" * 80)
    logger.info("")
    
    # Build flop abstraction
    logger.info("Step 1/4: Building flop abstraction...")
    build_flop_abstraction(
        num_buckets=k_flop,
        num_samples=flop_samples,
        seed=seed,
        output_dir=flop_dir
    )
    logger.info("")
    
    # Build turn abstraction
    logger.info("Step 2/4: Building turn abstraction...")
    build_turn_abstraction(
        num_buckets=k_turn,
        num_samples=turn_samples,
        seed=seed,
        output_dir=turn_dir
    )
    logger.info("")
    
    # Build river abstraction
    logger.info("Step 3/4: Building river abstraction...")
    build_river_abstraction(
        num_buckets=k_river,
        num_samples=river_samples,
        seed=seed,
        output_dir=river_dir
    )
    logger.info("")
    
    # Pack everything
    logger.info("Step 4/4: Packing into buckets.pkl...")
    pack_buckets(
        flop_dir=flop_dir,
        turn_dir=turn_dir,
        river_dir=river_dir,
        output_path=output_path,
        k_preflop=k_preflop,
        k_flop=k_flop,
        k_turn=k_turn,
        k_river=k_river,
        preflop_samples=preflop_samples,
        seed=seed
    )


def main():
    parser = argparse.ArgumentParser(
        description="Pack street-specific bucket files into buckets.pkl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pack existing abstraction files (fast if files exist)
  python pack_buckets.py --pack-only
  
  # Build all abstractions and pack (takes 30-60 minutes)
  python pack_buckets.py --build-all
  
  # Custom configuration
  python pack_buckets.py --build-all --flop-buckets 10000 --turn-buckets 3000
  
  # Specify custom directories
  python pack_buckets.py --pack-only --flop-dir data/abstractions/flop \\
                         --output assets/abstraction/buckets.pkl
        """
    )
    
    parser.add_argument("--pack-only", action="store_true",
                       help="Only pack existing abstraction files (don't build)")
    parser.add_argument("--build-all", action="store_true",
                       help="Build all street abstractions then pack")
    
    # Bucket counts
    parser.add_argument("--preflop-buckets", type=int, default=24,
                       help="Number of preflop buckets (default: 24)")
    parser.add_argument("--flop-buckets", type=int, default=8000,
                       help="Number of flop buckets (default: 8000)")
    parser.add_argument("--turn-buckets", type=int, default=2000,
                       help="Number of turn buckets (default: 2000)")
    parser.add_argument("--river-buckets", type=int, default=400,
                       help="Number of river buckets (default: 400)")
    
    # Sample counts (only used with --build-all)
    parser.add_argument("--preflop-samples", type=int, default=100000,
                       help="Number of preflop samples (default: 100000)")
    parser.add_argument("--flop-samples", type=int, default=50000,
                       help="Number of flop samples (default: 50000)")
    parser.add_argument("--turn-samples", type=int, default=30000,
                       help="Number of turn samples (default: 30000)")
    parser.add_argument("--river-samples", type=int, default=20000,
                       help="Number of river samples (default: 20000)")
    
    # Paths
    parser.add_argument("--flop-dir", type=Path, default=Path("data/abstractions/flop"),
                       help="Directory with flop abstraction files")
    parser.add_argument("--turn-dir", type=Path, default=Path("data/abstractions/turn"),
                       help="Directory with turn abstraction files")
    parser.add_argument("--river-dir", type=Path, default=Path("data/abstractions/river"),
                       help="Directory with river abstraction files")
    parser.add_argument("--output", type=Path, default=Path("assets/abstraction/buckets.pkl"),
                       help="Output path for buckets.pkl")
    
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed (default: 42)")
    
    args = parser.parse_args()
    
    if not args.pack_only and not args.build_all:
        parser.error("Must specify either --pack-only or --build-all")
    
    if args.build_all:
        # Build all abstractions and pack
        build_and_pack(
            k_preflop=args.preflop_buckets,
            k_flop=args.flop_buckets,
            k_turn=args.turn_buckets,
            k_river=args.river_buckets,
            flop_samples=args.flop_samples,
            turn_samples=args.turn_samples,
            river_samples=args.river_samples,
            preflop_samples=args.preflop_samples,
            seed=args.seed,
            output_dir=Path("data/abstractions"),
            output_path=args.output
        )
    else:
        # Pack only
        pack_buckets(
            flop_dir=args.flop_dir,
            turn_dir=args.turn_dir,
            river_dir=args.river_dir,
            output_path=args.output,
            k_preflop=args.preflop_buckets,
            k_flop=args.flop_buckets,
            k_turn=args.turn_buckets,
            k_river=args.river_buckets,
            preflop_samples=args.preflop_samples,
            seed=args.seed
        )


if __name__ == "__main__":
    main()
