"""Build river card abstraction with k-medoids clustering.

Creates 200-500 buckets based on:
- Exact equity calculation
- Hand ranking with kickers
- Simplified classification (no need for draws)

Uses fixed seed for reproducibility and SHA-256 checksums.
"""

import sys
import numpy as np
import hashlib
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import Card, Street
from holdem.abstraction.postflop_features import extract_postflop_features
from holdem.utils.rng import get_rng
from holdem.utils.logging import get_logger

logger = get_logger("abstraction.build_river")


def sample_river_situations(num_samples: int, seed: int = 42) -> List[Tuple[List[Card], List[Card]]]:
    """Sample random river situations."""
    rng = get_rng(seed)
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    suits = ['h', 'd', 'c', 's']
    
    samples = []
    for _ in range(num_samples):
        deck = [Card(rank, suit) for rank in ranks for suit in suits]
        rng.shuffle(deck)
        
        hole_cards = [deck[0], deck[1]]
        board = [deck[2], deck[3], deck[4], deck[5], deck[6]]  # Flop + Turn + River
        
        samples.append((hole_cards, board))
    
    return samples


def build_river_abstraction(
    num_buckets: int = 400,
    num_samples: int = 20000,
    seed: int = 42,
    output_dir: Path = None
):
    """Build river card abstraction."""
    logger.info(f"Building river abstraction: {num_buckets} buckets from {num_samples} samples")
    
    try:
        from sklearn_extra.cluster import KMedoids
    except ImportError:
        from sklearn.cluster import KMeans as KMedoids
    
    samples = sample_river_situations(num_samples, seed)
    
    logger.info(f"Extracting features for {len(samples)} river situations...")
    features_list = []
    for hole_cards, board in samples:
        features = extract_postflop_features(
            hole_cards=hole_cards,
            board=board,
            street=Street.RIVER,
            pot=100.0,
            stack=200.0,
            is_in_position=True,
            num_opponents=1,
            equity_samples=100,
            future_equity_samples=0  # No future cards on river
        )
        features_list.append(features)
    
    features = np.array(features_list, dtype=np.float32)
    
    feature_mean = features.mean(axis=0)
    feature_std = features.std(axis=0) + 1e-8
    features_normalized = (features - feature_mean) / feature_std
    
    logger.info(f"Feature matrix shape: {features.shape}")
    logger.info(f"Running clustering with {num_buckets} clusters...")
    
    try:
        clusterer = KMedoids(
            n_clusters=num_buckets,
            random_state=seed,
            method='pam',
            init='k-medoids++',
            max_iter=300
        )
    except TypeError:
        clusterer = KMedoids(
            n_clusters=num_buckets,
            random_state=seed,
            n_init=10,
            max_iter=300
        )
    
    clusterer.fit(features_normalized)
    logger.info(f"Clustering complete")
    
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        np.save(output_dir / f"river_medoids_{num_buckets}.npy", 
                clusterer.cluster_centers_.astype(np.float32))
        np.savez(output_dir / f"river_normalization_{num_buckets}.npz",
                mean=feature_mean, std=feature_std)
        
        checksum = hashlib.sha256(
            clusterer.cluster_centers_.astype(np.float32).tobytes()
        ).hexdigest()
        
        with open(output_dir / f"river_checksum_{num_buckets}.txt", 'w') as f:
            f.write(f"{checksum}\n")
            f.write(f"num_buckets: {num_buckets}\n")
            f.write(f"num_samples: {num_samples}\n")
            f.write(f"seed: {seed}\n")
        
        logger.info(f"Saved river abstraction to {output_dir}")
        logger.info(f"SHA-256 checksum: {checksum}")
    
    return clusterer, feature_mean, feature_std


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build river card abstraction")
    parser.add_argument("--buckets", type=int, default=400,
                       help="Number of buckets (200-500 recommended)")
    parser.add_argument("--samples", type=int, default=20000,
                       help="Number of samples for clustering")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")
    parser.add_argument("--output", type=str, default="data/abstractions/river",
                       help="Output directory")
    
    args = parser.parse_args()
    
    build_river_abstraction(
        num_buckets=args.buckets,
        num_samples=args.samples,
        seed=args.seed,
        output_dir=Path(args.output)
    )
