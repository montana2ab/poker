"""Preflop feature extraction for hand bucketing.

For preflop, we use simpler features focused on hand quality:
- Pair strength
- Suitedness
- Connectedness
- Broadway cards
- Gap
- High card values
- Approximate equity vs random hand

This gives us enough features to create 24 meaningful buckets.
"""

import numpy as np
from typing import List
from holdem.types import Card
from holdem.abstraction.features import calculate_equity
from holdem.utils.logging import get_logger

logger = get_logger("abstraction.preflop_features")


def get_rank_value(rank: str) -> int:
    """Convert rank to numeric value (2=2, ..., T=10, J=11, Q=12, K=13, A=14)."""
    rank_map = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
        '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }
    return rank_map.get(rank, 0)


def extract_preflop_features(
    hole_cards: List[Card],
    equity_samples: int = 500
) -> np.ndarray:
    """Extract preflop features for bucketing.
    
    Features (10 dimensions):
    - High card value (normalized 0-1)
    - Low card value (normalized 0-1)
    - Is pair (0/1)
    - Is suited (0/1)
    - Gap between cards (normalized 0-1)
    - Is broadway (both cards T+) (0/1)
    - Is suited connectors (0/1)
    - Is premium pair (QQ+) (0/1)
    - Equity vs random hand (0-1)
    - Hand strength score (composite 0-1)
    """
    if not hole_cards or len(hole_cards) != 2:
        return np.zeros(10, dtype=np.float64)
    
    features = []
    
    # Get rank values
    rank1 = get_rank_value(hole_cards[0].rank)
    rank2 = get_rank_value(hole_cards[1].rank)
    high_rank = max(rank1, rank2)
    low_rank = min(rank1, rank2)
    
    # 1. High card value (normalized)
    features.append(high_rank / 14.0)
    
    # 2. Low card value (normalized)
    features.append(low_rank / 14.0)
    
    # 3. Is pair
    is_pair = 1.0 if rank1 == rank2 else 0.0
    features.append(is_pair)
    
    # 4. Is suited
    is_suited = 1.0 if hole_cards[0].suit == hole_cards[1].suit else 0.0
    features.append(is_suited)
    
    # 5. Gap (normalized, max gap is 12 for A-2)
    gap = abs(rank1 - rank2)
    # For pairs, gap is 0
    if not is_pair:
        # Adjust for wheel (A-5 or similar)
        gap = min(gap, 14 - gap)  # Account for circular nature (A can be high or low)
    features.append(min(gap, 12) / 12.0)
    
    # 6. Is broadway (both cards T or higher)
    is_broadway = 1.0 if high_rank >= 10 and low_rank >= 10 else 0.0
    features.append(is_broadway)
    
    # 7. Is suited connectors
    is_connectors = 1.0 if gap <= 1 and not is_pair else 0.0
    is_suited_connectors = 1.0 if is_suited and is_connectors else 0.0
    features.append(is_suited_connectors)
    
    # 8. Is premium pair (QQ, KK, AA)
    is_premium_pair = 1.0 if is_pair and high_rank >= 12 else 0.0
    features.append(is_premium_pair)
    
    # 9. Equity vs random hand (Monte Carlo simulation)
    try:
        equity = calculate_equity(hole_cards, [], num_opponents=1, num_samples=equity_samples)
    except Exception as e:
        logger.warning(f"Error calculating preflop equity: {e}")
        equity = 0.5
    features.append(equity)
    
    # 10. Composite hand strength score
    # This combines multiple factors into a single strength metric
    strength = 0.0
    
    # Pair contribution
    if is_pair:
        strength += (high_rank / 14.0) * 0.5  # Pairs worth up to 0.5
    else:
        # High cards contribution
        strength += (high_rank / 14.0) * 0.2
        strength += (low_rank / 14.0) * 0.15
        
        # Connectedness bonus
        if gap <= 1:
            strength += 0.1
        elif gap == 2:
            strength += 0.05
        
        # Suitedness bonus
        if is_suited:
            strength += 0.1
    
    # Broadway bonus
    if is_broadway:
        strength += 0.1
    
    # Normalize to 0-1
    strength = min(strength, 1.0)
    features.append(strength)
    
    return np.array(features, dtype=np.float64)
