"""Feature construction for CFV Net.

Builds ≈550-650 dimensional feature vectors from poker states:
- Public features: street, num_players, hero_position, SPR, pot, action_set_id
- Range features: top-K=16 buckets per player with embeddings
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from holdem.types import Street, Position


@dataclass
class FeatureStats:
    """Statistics for feature normalization (z-score)."""
    mean: np.ndarray
    std: np.ndarray
    
    def normalize(self, features: np.ndarray) -> np.ndarray:
        """Apply z-score normalization."""
        return (features - self.mean) / (self.std + 1e-8)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'mean': self.mean.tolist(),
            'std': self.std.tolist()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FeatureStats':
        """Load from dictionary."""
        return cls(
            mean=np.array(data['mean']),
            std=np.array(data['std'])
        )


@dataclass
class CFVFeatures:
    """Structured CFV features."""
    # Public features (scalars)
    street_onehot: np.ndarray  # [4] - PREFLOP, FLOP, TURN, RIVER
    num_players: int  # 2-6
    hero_position_onehot: np.ndarray  # [6] - BTN, SB, BB, UTG, MP, CO
    spr_continuous: float  # Stack-to-pot ratio
    spr_bins: np.ndarray  # [6] - binned SPR
    pot_norm: float  # Normalized pot size
    to_call_over_pot: float  # Ratio of call amount to pot
    last_bet_over_pot: float  # Ratio of last bet to pot
    action_set_id: int  # 0=tight, 1=balanced, 2=loose
    public_bucket_embedding: np.ndarray  # [64] - embedding of public card bucket
    
    # Range features (per player)
    range_embeddings: np.ndarray  # [6, 64] - weighted sum of top-K bucket embeddings
    
    def to_vector(self) -> np.ndarray:
        """Concatenate all features into a single vector."""
        features = []
        
        # Public features
        features.append(self.street_onehot)  # 4
        features.append([self.num_players / 6.0])  # 1 (normalized)
        features.append(self.hero_position_onehot)  # 6
        features.append([self.spr_continuous])  # 1
        features.append(self.spr_bins)  # 6
        features.append([self.pot_norm])  # 1
        features.append([self.to_call_over_pot])  # 1
        features.append([self.last_bet_over_pot])  # 1
        features.append([self.action_set_id / 2.0])  # 1 (normalized)
        features.append(self.public_bucket_embedding)  # 64
        
        # Range features (flattened)
        features.append(self.range_embeddings.flatten())  # 6 * 64 = 384
        
        return np.concatenate([np.atleast_1d(f) for f in features])


class CFVFeatureBuilder:
    """Builds CFV features from poker state."""
    
    def __init__(
        self,
        bucket_embeddings: np.ndarray,  # [num_buckets, embed_dim]
        topk_range: int = 16,
        embed_dim: int = 64
    ):
        """Initialize feature builder.
        
        Args:
            bucket_embeddings: Learned embeddings for bucket IDs
            topk_range: Number of top buckets to keep per player range
            embed_dim: Embedding dimension
        """
        self.bucket_embeddings = bucket_embeddings
        self.topk_range = topk_range
        self.embed_dim = embed_dim
        self.num_buckets = bucket_embeddings.shape[0]
        
    def build_features(
        self,
        street: Street,
        num_players: int,
        hero_position: Position,
        spr: float,
        pot_size: float,
        to_call: float,
        last_bet: float,
        action_set: str,  # "tight", "balanced", or "loose"
        public_bucket: int,
        ranges: Dict[Position, List[Tuple[int, float]]]  # Position -> [(bucket_id, weight), ...]
    ) -> CFVFeatures:
        """Build features from poker state.
        
        Args:
            street: Current street
            num_players: Number of active players (2-6)
            hero_position: Hero's position
            spr: Stack-to-pot ratio
            pot_size: Current pot size (in bb)
            to_call: Amount to call (in bb)
            last_bet: Last bet/raise amount (in bb)
            action_set: Action abstraction ("tight", "balanced", "loose")
            public_bucket: Public card bucket ID
            ranges: Player ranges as top-K (bucket_id, weight) pairs
            
        Returns:
            CFVFeatures object
        """
        # Street one-hot
        street_onehot = np.zeros(4, dtype=np.float32)
        street_onehot[street.value] = 1.0
        
        # Hero position one-hot
        hero_pos_onehot = np.zeros(6, dtype=np.float32)
        hero_pos_onehot[hero_position.value] = 1.0
        
        # SPR continuous and bins
        spr_continuous = float(spr)
        spr_bins = self._bin_spr(spr)
        
        # Pot-normalized features
        pot_norm = pot_size / 100.0  # Normalize by typical pot size
        to_call_over_pot = to_call / (pot_size + 1e-8)
        last_bet_over_pot = last_bet / (pot_size + 1e-8)
        
        # Action set ID
        action_set_map = {"tight": 0, "balanced": 1, "loose": 2}
        action_set_id = action_set_map.get(action_set, 1)
        
        # Public bucket embedding
        public_bucket_embedding = self._get_bucket_embedding(public_bucket)
        
        # Range embeddings (weighted sum of top-K buckets per player)
        range_embeddings = self._build_range_embeddings(ranges, num_players)
        
        return CFVFeatures(
            street_onehot=street_onehot,
            num_players=num_players,
            hero_position_onehot=hero_pos_onehot,
            spr_continuous=spr_continuous,
            spr_bins=spr_bins,
            pot_norm=pot_norm,
            to_call_over_pot=to_call_over_pot,
            last_bet_over_pot=last_bet_over_pot,
            action_set_id=action_set_id,
            public_bucket_embedding=public_bucket_embedding,
            range_embeddings=range_embeddings
        )
    
    def _bin_spr(self, spr: float) -> np.ndarray:
        """Bin SPR into 6 categories.
        
        Bins: [0-2), [2-5), [5-10), [10-20), [20-50), [50+)
        """
        bins = np.array([0, 2, 5, 10, 20, 50], dtype=np.float32)
        binned = np.zeros(6, dtype=np.float32)
        
        for i in range(len(bins)):
            if i == len(bins) - 1:
                # Last bin: [50+)
                if spr >= bins[i]:
                    binned[i] = 1.0
            else:
                # Check if SPR falls in [bins[i], bins[i+1])
                if bins[i] <= spr < bins[i + 1]:
                    binned[i] = 1.0
                    break
        
        return binned
    
    def _get_bucket_embedding(self, bucket_id: int) -> np.ndarray:
        """Get embedding for a bucket ID."""
        if 0 <= bucket_id < self.num_buckets:
            return self.bucket_embeddings[bucket_id].copy()
        else:
            # Out of range - return zero embedding
            return np.zeros(self.embed_dim, dtype=np.float32)
    
    def _build_range_embeddings(
        self,
        ranges: Dict[Position, List[Tuple[int, float]]],
        num_players: int
    ) -> np.ndarray:
        """Build range embeddings for all players.
        
        Creates [6, embed_dim] array where each row is the weighted sum of
        top-K bucket embeddings for that position. Positions ordered BTN→CO.
        Zero-padding for missing positions.
        
        Args:
            ranges: Position -> [(bucket_id, weight), ...]
            num_players: Number of active players
            
        Returns:
            Array of shape [6, embed_dim]
        """
        # Position order: BTN, SB, BB, UTG, MP, CO
        position_order = [Position.BTN, Position.SB, Position.BB, 
                         Position.UTG, Position.MP, Position.CO]
        
        range_embeddings = np.zeros((6, self.embed_dim), dtype=np.float32)
        
        for i, pos in enumerate(position_order):
            if pos in ranges and ranges[pos]:
                # Get top-K buckets for this position
                topk_buckets = ranges[pos][:self.topk_range]
                
                # Weighted sum of embeddings
                weighted_sum = np.zeros(self.embed_dim, dtype=np.float32)
                total_weight = 0.0
                
                for bucket_id, weight in topk_buckets:
                    if 0 <= bucket_id < self.num_buckets:
                        weighted_sum += self.bucket_embeddings[bucket_id] * weight
                        total_weight += weight
                
                # Normalize by total weight
                if total_weight > 1e-8:
                    range_embeddings[i] = weighted_sum / total_weight
        
        return range_embeddings


def get_feature_dimension(embed_dim: int = 64) -> int:
    """Calculate total feature dimension.
    
    Args:
        embed_dim: Embedding dimension
        
    Returns:
        Total feature dimension
    """
    # Public features: 4 + 1 + 6 + 1 + 6 + 1 + 1 + 1 + 1 + 64 = 86
    # Range features: 6 * embed_dim = 6 * 64 = 384
    # Total: 86 + 384 = 470
    public_dim = 4 + 1 + 6 + 1 + 6 + 1 + 1 + 1 + 1 + embed_dim
    range_dim = 6 * embed_dim
    return public_dim + range_dim


def create_bucket_embeddings(num_buckets: int, embed_dim: int = 64, seed: int = 42) -> np.ndarray:
    """Create random bucket embeddings (to be learned during training).
    
    Args:
        num_buckets: Total number of buckets
        embed_dim: Embedding dimension
        seed: Random seed
        
    Returns:
        Array of shape [num_buckets, embed_dim]
    """
    rng = np.random.RandomState(seed)
    # Xavier/Glorot initialization
    scale = np.sqrt(2.0 / (num_buckets + embed_dim))
    embeddings = rng.randn(num_buckets, embed_dim).astype(np.float32) * scale
    return embeddings
