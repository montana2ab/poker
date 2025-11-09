"""Build flop card abstraction with k-medoids clustering.

Creates 5k-10k buckets based on:
- E[HS] (expected hand strength)
- E[HS²] (hand strength variance)
- Texture bins (paired, monotone, connected)
- Draw potential

Uses k-medoids for better centroid interpretability and fixed seed for reproducibility.
Outputs float32 tables with SHA-256 checksums.
"""

import sys
import numpy as np
import hashlib
from pathlib import Path
from typing import List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import Card, Street
from holdem.abstraction.postflop_features import extract_postflop_features
from holdem.utils.rng import get_rng
from holdem.utils.logging import get_logger

logger = get_logger("abstraction.build_flop")


def sample_flop_situations(num_samples: int, seed: int = 42) -> List[Tuple[List[Card], List[Card]]]:
    """Sample random flop situations.
    
    Args:
        num_samples: Number of samples to generate
        seed: Random seed for reproducibility
        
    Returns:
        List of (hole_cards, board) tuples
    """
    rng = get_rng(seed)
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    suits = ['h', 'd', 'c', 's']
    
    samples = []
    for _ in range(num_samples):
        # Create deck
        deck = [Card(rank, suit) for rank in ranks for suit in suits]
        rng.shuffle(deck)
        
        # Deal hole cards and flop
        hole_cards = [deck[0], deck[1]]
        board = [deck[2], deck[3], deck[4]]
        
        samples.append((hole_cards, board))
    
    return samples


def extract_flop_features_batch(samples: List[Tuple[List[Card], List[Card]]]) -> np.ndarray:
    """Extract features for all flop samples.
    
    Args:
        samples: List of (hole_cards, board) tuples
        
    Returns:
        Feature matrix (num_samples x num_features)
    """
    logger.info(f"Extracting features for {len(samples)} flop situations...")
    
    features_list = []
    for hole_cards, board in samples:
        features = extract_postflop_features(
            hole_cards=hole_cards,
            board=board,
            street=Street.FLOP,
            pot=100.0,
            stack=200.0,
            is_in_position=True,
            num_opponents=1,
            equity_samples=100,
            future_equity_samples=50
        )
        features_list.append(features)
    
    return np.array(features_list, dtype=np.float32)


def build_flop_abstraction(
    num_buckets: int = 8000,
    num_samples: int = 50000,
    seed: int = 42,
    output_dir: Path = None
):
    """Build flop card abstraction using k-medoids.
    
    Args:
        num_buckets: Number of buckets (5k-10k recommended)
        num_samples: Number of samples for clustering
        seed: Random seed
        output_dir: Output directory for abstraction files
    """
    logger.info(f"Building flop abstraction: {num_buckets} buckets from {num_samples} samples")
    
    # Import sklearn_extra here to avoid dependency if not needed
    try:
        from sklearn_extra.cluster import KMedoids
    except ImportError:
        logger.error("sklearn-extra not installed. Install with: pip install scikit-learn-extra")
        logger.info("Falling back to KMeans from scikit-learn")
        from sklearn.cluster import KMeans as KMedoids
    
    # Sample situations
    samples = sample_flop_situations(num_samples, seed)
    
    # Extract features
    features = extract_flop_features_batch(samples)
    
    # Normalize features (important for clustering)
    feature_mean = features.mean(axis=0)
    feature_std = features.std(axis=0) + 1e-8
    features_normalized = (features - feature_mean) / feature_std
    
    logger.info(f"Feature matrix shape: {features.shape}")
    logger.info(f"Running k-medoids clustering with {num_buckets} clusters...")
    
    # K-medoids clustering (or KMeans fallback)
    try:
        clusterer = KMedoids(
            n_clusters=num_buckets,
            random_state=seed,
            method='pam',
            init='k-medoids++',
            max_iter=300
        )
    except TypeError:
        # KMeans fallback
        clusterer = KMedoids(
            n_clusters=num_buckets,
            random_state=seed,
            n_init=10,
            max_iter=300
        )
    
    cluster_labels = clusterer.fit_predict(features_normalized)
    
    inertia = clusterer.inertia_ if hasattr(clusterer, 'inertia_') else 0.0
    logger.info(f"Clustering complete. Inertia: {inertia:.2f}")
    
    # Save results
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save cluster centers (medoids)
        medoids_file = output_dir / f"flop_medoids_{num_buckets}.npy"
        np.save(medoids_file, clusterer.cluster_centers_.astype(np.float32))
        
        # Save normalization parameters
        norm_file = output_dir / f"flop_normalization_{num_buckets}.npz"
        np.savez(norm_file, mean=feature_mean, std=feature_std)
        
        # Compute SHA-256 checksum
        medoids_data = clusterer.cluster_centers_.astype(np.float32).tobytes()
        checksum = hashlib.sha256(medoids_data).hexdigest()
        
        checksum_file = output_dir / f"flop_checksum_{num_buckets}.txt"
        with open(checksum_file, 'w') as f:
            f.write(f"{checksum}\n")
            f.write(f"num_buckets: {num_buckets}\n")
            f.write(f"num_samples: {num_samples}\n")
            f.write(f"seed: {seed}\n")
        
        logger.info(f"Saved flop abstraction to {output_dir}")
        logger.info(f"SHA-256 checksum: {checksum}")
    
    return clusterer, feature_mean, feature_std


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build flop card abstraction")
    parser.add_argument("--buckets", type=int, default=8000,
                       help="Number of buckets (5k-10k recommended)")
    parser.add_argument("--samples", type=int, default=50000,
                       help="Number of samples for clustering")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")
    parser.add_argument("--output", type=str, default="data/abstractions/flop",
                       help="Output directory")
    
    args = parser.parse_args()
    
    build_flop_abstraction(
        num_buckets=args.buckets,
        num_samples=args.samples,
        seed=args.seed,
        output_dir=Path(args.output)
    )
