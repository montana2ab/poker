"""Hand bucketing using k-means clustering."""

import numpy as np
from sklearn.cluster import KMeans
from pathlib import Path
from typing import Dict, List, Tuple
from holdem.types import Card, Street, BucketConfig
from holdem.abstraction.features import extract_features, extract_simple_features
from holdem.utils.rng import get_rng
from holdem.utils.serialization import save_pickle, load_pickle
from holdem.utils.logging import get_logger

logger = get_logger("abstraction.bucketing")


class HandBucketing:
    """K-means clustering for hand abstraction."""
    
    def __init__(self, config: BucketConfig):
        self.config = config
        self.models: Dict[Street, KMeans] = {}
        self.fitted = False
    
    def build(self, num_samples: int = None):
        """Build buckets by clustering sampled hands."""
        if num_samples is None:
            num_samples = self.config.num_samples
        
        rng = get_rng(self.config.seed)
        logger.info(f"Building buckets with {num_samples} samples per street")
        
        # Build buckets for each street
        for street in Street:
            k = self._get_k_for_street(street)
            logger.info(f"Building {k} buckets for {street.name}")
            
            # Generate samples
            features_list = []
            for _ in range(num_samples):
                hole_cards, board = self._sample_hand(street, rng)
                features = extract_simple_features(hole_cards, board)
                features_list.append(features)
            
            X = np.array(features_list)
            
            # Fit k-means
            kmeans = KMeans(n_clusters=k, random_state=self.config.seed, n_init=10)
            kmeans.fit(X)
            self.models[street] = kmeans
            
            logger.info(f"  Completed {street.name}: inertia={kmeans.inertia_:.2f}")
        
        self.fitted = True
        logger.info("Bucketing complete")
    
    def _get_k_for_street(self, street: Street) -> int:
        """Get number of clusters for a street."""
        k_map = {
            Street.PREFLOP: self.config.k_preflop,
            Street.FLOP: self.config.k_flop,
            Street.TURN: self.config.k_turn,
            Street.RIVER: self.config.k_river
        }
        return k_map[street]
    
    def _sample_hand(self, street: Street, rng) -> Tuple[List[Card], List[Card]]:
        """Sample a random hand for a given street."""
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
        suits = ['h', 'd', 'c', 's']
        
        # Create deck
        deck = [Card(rank, suit) for rank in ranks for suit in suits]
        rng.shuffle(deck)
        
        # Deal hole cards
        hole_cards = deck[:2]
        
        # Deal board based on street
        num_board_cards = {
            Street.PREFLOP: 0,
            Street.FLOP: 3,
            Street.TURN: 4,
            Street.RIVER: 5
        }[street]
        
        board = deck[2:2+num_board_cards] if num_board_cards > 0 else []
        
        return hole_cards, board
    
    def get_bucket(self, hole_cards: List[Card], board: List[Card], street: Street) -> int:
        """Get bucket index for a hand."""
        if not self.fitted:
            raise RuntimeError("Buckets not built yet. Call build() first.")
        
        if street not in self.models:
            raise ValueError(f"No model for street {street}")
        
        features = extract_simple_features(hole_cards, board)
        bucket = self.models[street].predict([features])[0]
        return int(bucket)
    
    def save(self, path: Path):
        """Save bucketing models."""
        if not self.fitted:
            raise RuntimeError("Cannot save unfitted buckets")
        
        data = {
            'config': vars(self.config),
            'models': self.models,
            'fitted': self.fitted
        }
        save_pickle(data, path)
        logger.info(f"Saved buckets to {path}")
    
    @classmethod
    def load(cls, path: Path) -> "HandBucketing":
        """Load bucketing models."""
        data = load_pickle(path)
        config = BucketConfig(**data['config'])
        bucketing = cls(config)
        bucketing.models = data['models']
        bucketing.fitted = data['fitted']
        logger.info(f"Loaded buckets from {path}")
        return bucketing


def generate_random_hands(num_hands: int, street: Street, seed: int = 42) -> List[Tuple[List[Card], List[Card]]]:
    """Generate random hands for testing."""
    rng = get_rng(seed)
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    suits = ['h', 'd', 'c', 's']
    
    hands = []
    for _ in range(num_hands):
        deck = [Card(rank, suit) for rank in ranks for suit in suits]
        rng.shuffle(deck)
        
        hole_cards = deck[:2]
        
        num_board_cards = {
            Street.PREFLOP: 0,
            Street.FLOP: 3,
            Street.TURN: 4,
            Street.RIVER: 5
        }[street]
        
        board = deck[2:2+num_board_cards] if num_board_cards > 0 else []
        hands.append((hole_cards, board))
    
    return hands
