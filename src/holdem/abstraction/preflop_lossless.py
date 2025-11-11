"""Lossless 169 preflop abstraction using iso-hand mapping.

This module implements a perfect (lossless) preflop hand abstraction that maps
every possible hole card combination to exactly one of 169 canonical hand types.

The 169 hand types are organized in a 13×13 grid:
- Diagonal: Pairs (AA, KK, QQ, ..., 22)
- Upper triangle: Suited hands (AKs, AQs, ..., 32s)
- Lower triangle: Offsuit hands (AKo, AQo, ..., 32o)

This is the standard poker hand classification that preserves perfect information
about preflop hand strength while providing exactly one bucket per hand type.
"""

from typing import List, Tuple
from holdem.types import Card


# Rank ordering (high to low)
RANK_ORDER = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
RANK_TO_INDEX = {rank: i for i, rank in enumerate(RANK_ORDER)}


def get_hand_type(hole_cards: List[Card]) -> Tuple[str, str, bool]:
    """Get canonical hand type from hole cards.
    
    Returns a tuple of (high_rank, low_rank, is_suited) that uniquely identifies
    one of the 169 hand types.
    
    Args:
        hole_cards: List of exactly 2 cards
        
    Returns:
        Tuple of (high_rank, low_rank, is_suited) where ranks are ordered high to low
        
    Examples:
        [As, Ah] -> ('A', 'A', False)  # Pair (suited=False for pairs by convention)
        [Ks, Ah] -> ('A', 'K', False)  # AKo
        [Kh, Ah] -> ('A', 'K', False)  # AKo
        [As, Ks] -> ('A', 'K', True)   # AKs
    """
    if not hole_cards or len(hole_cards) != 2:
        raise ValueError("hole_cards must contain exactly 2 cards")
    
    rank1 = hole_cards[0].rank
    rank2 = hole_cards[1].rank
    
    # Order ranks from high to low
    idx1 = RANK_TO_INDEX.get(rank1, 12)
    idx2 = RANK_TO_INDEX.get(rank2, 12)
    
    if idx1 <= idx2:
        high_rank, low_rank = rank1, rank2
    else:
        high_rank, low_rank = rank2, rank1
    
    # Determine if suited
    is_suited = hole_cards[0].suit == hole_cards[1].suit
    
    # For pairs, we conventionally set is_suited=False
    if high_rank == low_rank:
        is_suited = False
    
    return high_rank, low_rank, is_suited


def hand_type_to_bucket(high_rank: str, low_rank: str, is_suited: bool) -> int:
    """Convert hand type to bucket index (0-168).
    
    The 169 buckets are organized as follows:
    - Pairs: AA=0, KK=1, QQ=2, ..., 22=12 (buckets 0-12)
    - Suited hands: AKs=13, AQs=14, ..., 32s=90 (buckets 13-90)
    - Offsuit hands: AKo=91, AQo=92, ..., 32o=168 (buckets 91-168)
    
    Within each category, hands are ordered by their position in the 13×13 grid,
    reading row-by-row from top-left to bottom-right.
    
    Args:
        high_rank: Higher rank (e.g., 'A', 'K', etc.)
        low_rank: Lower rank (e.g., 'K', 'Q', etc.)
        is_suited: Whether the hand is suited
        
    Returns:
        Bucket index from 0 to 168
    """
    high_idx = RANK_TO_INDEX.get(high_rank, 12)
    low_idx = RANK_TO_INDEX.get(low_rank, 12)
    
    # Ensure high_idx <= low_idx (high rank comes before low rank in RANK_ORDER)
    if high_idx > low_idx:
        high_idx, low_idx = low_idx, high_idx
    
    # Pairs (diagonal)
    if high_idx == low_idx:
        return high_idx
    
    # Non-pairs: suited (upper triangle) or offsuit (lower triangle)
    # Calculate position in the 13×13 grid
    
    # For a 13×13 grid with diagonal as pairs:
    # Upper triangle (suited): row < col
    # Lower triangle (offsuit): row > col
    
    # We organize as: for each row, count positions
    # Row 0 (A): 12 suited positions (AKs, AQs, ..., A2s)
    # Row 1 (K): 11 suited positions (KQs, KJs, ..., K2s)
    # etc.
    
    if is_suited:
        # Suited: upper triangle
        # Count how many suited hands come before this one
        # For row i, there are (12-i) suited hands in that row
        count = 0
        for row in range(high_idx):
            count += (12 - row)
        # Add position within current row
        count += (low_idx - high_idx - 1)
        # Offset by 13 for pairs
        return 13 + count
    else:
        # Offsuit: lower triangle
        # For row i, there are i offsuit hands (positions before diagonal)
        # Plus (12-i) offsuit hands (positions after diagonal)
        count = 0
        for row in range(high_idx):
            count += (12 - row)
        # Add position within current row
        count += (low_idx - high_idx - 1)
        # Offset by 13 (pairs) + 78 (suited hands)
        return 91 + count


def get_bucket_169(hole_cards: List[Card]) -> int:
    """Get bucket index (0-168) for hole cards using lossless 169 abstraction.
    
    This is the main entry point for the lossless preflop abstraction.
    
    Args:
        hole_cards: List of exactly 2 cards
        
    Returns:
        Bucket index from 0 to 168
        
    Examples:
        >>> get_bucket_169([Card('A', 's'), Card('A', 'h')])
        0  # AA (pair)
        >>> get_bucket_169([Card('A', 's'), Card('K', 's')])
        13  # AKs (suited)
        >>> get_bucket_169([Card('A', 's'), Card('K', 'h')])
        91  # AKo (offsuit)
    """
    high_rank, low_rank, is_suited = get_hand_type(hole_cards)
    return hand_type_to_bucket(high_rank, low_rank, is_suited)


def bucket_to_hand_type(bucket: int) -> Tuple[str, str, bool]:
    """Convert bucket index back to hand type.
    
    Args:
        bucket: Bucket index from 0 to 168
        
    Returns:
        Tuple of (high_rank, low_rank, is_suited)
    """
    if bucket < 0 or bucket > 168:
        raise ValueError(f"Bucket must be between 0 and 168, got {bucket}")
    
    # Pairs (0-12)
    if bucket <= 12:
        rank = RANK_ORDER[bucket]
        return rank, rank, False
    
    # Suited (13-90) - 78 combinations
    if bucket <= 90:
        suited_offset = bucket - 13
        # Find row and column in upper triangle
        row = 0
        count = 0
        while count + (12 - row) <= suited_offset:
            count += (12 - row)
            row += 1
        col = row + 1 + (suited_offset - count)
        return RANK_ORDER[row], RANK_ORDER[col], True
    
    # Offsuit (91-168) - 78 combinations
    offsuit_offset = bucket - 91
    row = 0
    count = 0
    while count + (12 - row) <= offsuit_offset:
        count += (12 - row)
        row += 1
    col = row + 1 + (offsuit_offset - count)
    return RANK_ORDER[row], RANK_ORDER[col], False


def get_hand_name(bucket: int) -> str:
    """Get human-readable hand name from bucket index.
    
    Args:
        bucket: Bucket index from 0 to 168
        
    Returns:
        Hand name like "AA", "AKs", "AKo", etc.
    """
    high_rank, low_rank, is_suited = bucket_to_hand_type(bucket)
    
    if high_rank == low_rank:
        return f"{high_rank}{low_rank}"
    else:
        suffix = 's' if is_suited else 'o'
        return f"{high_rank}{low_rank}{suffix}"


# Pre-compute all 169 hand names for easy reference
ALL_HAND_NAMES = [get_hand_name(i) for i in range(169)]
