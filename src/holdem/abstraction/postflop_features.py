"""Comprehensive postflop feature extraction for hand bucketing.

This module implements a ~34-dimensional feature vector for postflop situations:
- Hand categories (12 dims, one-hot)
- Flush draws (4 dims, one-hot)  
- Straight draws (5 dims)
- Combo draw (1 dim)
- Board texture (6 dims, binary flags)
- Context (6 dims: equity now/future, SPR bins, position)
"""

import eval7
import numpy as np
from typing import List, Tuple, Optional
from collections import Counter
from holdem.types import Card, Street
from holdem.abstraction.features import card_to_eval7, calculate_equity
from holdem.utils.logging import get_logger

logger = get_logger("abstraction.postflop_features")


# Hand category enum for clarity
class HandCategory:
    """Hand category indices for one-hot encoding."""
    HIGH_CARD = 0
    UNDERPAIR = 1  # Underpair / 3rd pair or less
    SECOND_PAIR = 2
    TOP_PAIR = 3
    OVERPAIR = 4
    TWO_PAIR_BOARD_HAND = 5  # Two pair with 1 board + 1 hand card
    TWO_PAIR_POCKET = 6  # Two pair with both pocket cards
    TRIPS = 7
    STRAIGHT = 8
    FLUSH = 9
    FULL_HOUSE = 10
    QUADS_OR_STRAIGHT_FLUSH = 11


class FlushDrawType:
    """Flush draw type indices for one-hot encoding."""
    NONE = 0
    BACKDOOR = 1
    DIRECT_NON_NUT = 2
    DIRECT_NUT = 3


class StraightDrawType:
    """Straight draw type indices."""
    NONE = 0
    GUTSHOT = 1
    OESD = 2
    DOUBLE = 3


def get_rank_value(rank: str) -> int:
    """Convert rank to numeric value (2=2, ..., T=10, J=11, Q=12, K=13, A=14)."""
    rank_map = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
        '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }
    return rank_map.get(rank, 0)


def classify_hand_category(hole_cards: List[Card], board: List[Card]) -> int:
    """Classify hand into one of 12 categories.
    
    Returns index 0-11 for one-hot encoding.
    """
    if not hole_cards or len(hole_cards) != 2 or not board:
        return HandCategory.HIGH_CARD
    
    try:
        # Convert to eval7
        hand = [card_to_eval7(c) for c in hole_cards]
        board_eval7 = [card_to_eval7(c) for c in board]
        
        # Evaluate hand strength
        hand_value = eval7.evaluate(hand + board_eval7)
        hand_type = eval7.handtype(hand_value)
        
        # Get board ranks sorted (high to low)
        board_ranks = sorted([get_rank_value(c.rank) for c in board], reverse=True)
        hole_ranks = [get_rank_value(c.rank) for c in hole_cards]
        
        # Count ranks in full hand (board + hole)
        all_cards = board + hole_cards
        rank_counts = Counter([c.rank for c in all_cards])
        suit_counts = Counter([c.suit for c in all_cards])
        
        # Check for straight flush or quads
        if hand_type == 'Straight Flush' or hand_type == 'Quads':
            return HandCategory.QUADS_OR_STRAIGHT_FLUSH
        
        # Check for full house
        if hand_type == 'Full House':
            return HandCategory.FULL_HOUSE
        
        # Check for flush
        if hand_type == 'Flush':
            return HandCategory.FLUSH
        
        # Check for straight
        if hand_type == 'Straight':
            return HandCategory.STRAIGHT
        
        # Check for trips
        if hand_type == 'Trips':
            return HandCategory.TRIPS
        
        # Check for two pair
        if hand_type == 'Two Pair':
            # Determine if it's pocket pair + board pair or mixed
            if hole_cards[0].rank == hole_cards[1].rank:
                # Pocket pair + board pair
                return HandCategory.TWO_PAIR_POCKET
            else:
                # Mixed (one from hand, one from board)
                return HandCategory.TWO_PAIR_BOARD_HAND
        
        # Check for pair
        if hand_type == 'Pair':
            # Determine pair type
            if hole_cards[0].rank == hole_cards[1].rank:
                # Pocket pair
                pair_rank = get_rank_value(hole_cards[0].rank)
                if pair_rank > board_ranks[0]:
                    return HandCategory.OVERPAIR
                elif pair_rank < board_ranks[0]:
                    if len(board_ranks) >= 3 and pair_rank <= board_ranks[2]:
                        return HandCategory.UNDERPAIR
                    else:
                        return HandCategory.UNDERPAIR
            else:
                # Paired with board
                paired_rank = None
                for h_card in hole_cards:
                    if any(b_card.rank == h_card.rank for b_card in board):
                        paired_rank = get_rank_value(h_card.rank)
                        break
                
                if paired_rank:
                    if paired_rank == board_ranks[0]:
                        return HandCategory.TOP_PAIR
                    elif len(board_ranks) >= 2 and paired_rank == board_ranks[1]:
                        return HandCategory.SECOND_PAIR
                    else:
                        return HandCategory.UNDERPAIR
        
        # High card
        return HandCategory.HIGH_CARD
        
    except Exception as e:
        logger.warning(f"Error classifying hand: {e}")
        return HandCategory.HIGH_CARD


def detect_flush_draw(hole_cards: List[Card], board: List[Card]) -> int:
    """Detect flush draw type.
    
    Returns index 0-3 for one-hot encoding:
    - 0: No flush draw
    - 1: Backdoor flush draw (2 cards needed)
    - 2: Direct flush draw, non-nut
    - 3: Direct flush draw, nut
    """
    if not hole_cards or not board:
        return FlushDrawType.NONE
    
    # Count suits in board
    board_suits = Counter([c.suit for c in board])
    
    # Check each suit
    for suit, board_count in board_suits.items():
        # Count hole cards of this suit
        hole_count = sum(1 for c in hole_cards if c.suit == suit)
        total = board_count + hole_count
        
        # Direct flush draw (4 cards of same suit, need 1 more)
        if total == 4:
            # Check if we have the Ace for nut flush draw
            has_ace = any(c.rank == 'A' and c.suit == suit for c in hole_cards)
            if has_ace:
                return FlushDrawType.DIRECT_NUT
            else:
                return FlushDrawType.DIRECT_NON_NUT
    
    # Backdoor flush draw (3 cards of same suit, need 2 more)
    for suit, board_count in board_suits.items():
        hole_count = sum(1 for c in hole_cards if c.suit == suit)
        total = board_count + hole_count
        
        if total == 3:
            return FlushDrawType.BACKDOOR
    
    return FlushDrawType.NONE


def detect_straight_draw(hole_cards: List[Card], board: List[Card]) -> Tuple[int, int]:
    """Detect straight draw type.
    
    Returns:
        - draw_type: 0=none, 1=gutshot, 2=OESD, 3=double
        - is_high: 1 if targeting high end of board, 0 otherwise
    """
    if not hole_cards or not board:
        return StraightDrawType.NONE, 0
    
    # Get all rank values
    all_ranks = [get_rank_value(c.rank) for c in (hole_cards + board)]
    unique_ranks = sorted(set(all_ranks), reverse=True)
    
    # Check for existing straight (no draw)
    if _has_straight(unique_ranks):
        return StraightDrawType.NONE, 0
    
    # Count outs for straight
    outs = _count_straight_outs(unique_ranks)
    
    # Determine draw type
    draw_type = StraightDrawType.NONE
    if outs >= 8:  # Double gutshot or better
        draw_type = StraightDrawType.DOUBLE
    elif outs >= 7:  # OESD (8 outs typical, allow 7+ for edge cases)
        draw_type = StraightDrawType.OESD
    elif outs >= 3:  # Gutshot (4 outs typical, allow 3+ for edge cases)
        draw_type = StraightDrawType.GUTSHOT
    
    # Determine if high draw (targeting ranks above board median)
    is_high = _is_high_straight_draw(hole_cards, board)
    
    return draw_type, is_high


def _has_straight(unique_ranks: List[int]) -> bool:
    """Check if ranks contain a straight."""
    if len(unique_ranks) < 5:
        return False
    
    # Check normal straights
    for i in range(len(unique_ranks) - 4):
        if unique_ranks[i] - unique_ranks[i+4] == 4:
            return True
    
    # Check wheel (A-2-3-4-5)
    if 14 in unique_ranks and set([2, 3, 4, 5]).issubset(set(unique_ranks)):
        return True
    
    return False


def _count_straight_outs(unique_ranks: List[int]) -> int:
    """Count approximate number of outs to make a straight."""
    outs = 0
    
    # For each possible rank we could add
    for new_rank in range(2, 15):
        if new_rank in unique_ranks:
            continue
        
        test_ranks = sorted(set(unique_ranks + [new_rank]), reverse=True)
        if _has_straight(test_ranks):
            outs += 4  # 4 cards of each rank
    
    return outs


def _is_high_straight_draw(hole_cards: List[Card], board: List[Card]) -> int:
    """Determine if straight draw targets high end (1) or not (0)."""
    board_ranks = sorted([get_rank_value(c.rank) for c in board], reverse=True)
    hole_ranks = [get_rank_value(c.rank) for c in hole_cards]
    
    if not board_ranks:
        return 0
    
    board_median = board_ranks[len(board_ranks) // 2]
    avg_hole = sum(hole_ranks) / len(hole_ranks) if hole_ranks else 0
    
    # If average hole card rank > board median, consider it a high draw
    return 1 if avg_hole > board_median else 0


def has_combo_draw(flush_draw_type: int, straight_draw_type: int) -> int:
    """Check if hand has combo draw (flush + straight draw).
    
    Returns 1 if both direct flush draw and straight draw, 0 otherwise.
    """
    has_flush = flush_draw_type in [FlushDrawType.DIRECT_NON_NUT, FlushDrawType.DIRECT_NUT]
    has_straight = straight_draw_type in [StraightDrawType.GUTSHOT, StraightDrawType.OESD, StraightDrawType.DOUBLE]
    
    return 1 if (has_flush and has_straight) else 0


def analyze_board_texture(board: List[Card]) -> np.ndarray:
    """Analyze board texture, returning 6 binary features.
    
    Returns array of 6 binary flags:
    - board_paired: Board contains at least one pair
    - board_trips_or_more: Board is trips or better
    - board_monotone: At least 3 cards of same suit
    - board_two_suited: Exactly 2 cards of same suit (and not monotone)
    - board_ace_high: Highest card is Ace
    - board_low: All cards <= 9
    """
    features = np.zeros(6, dtype=np.float64)
    
    if not board or len(board) < 3:
        return features
    
    # Count ranks and suits
    rank_counts = Counter([c.rank for c in board])
    suit_counts = Counter([c.suit for c in board])
    ranks = [get_rank_value(c.rank) for c in board]
    
    # board_paired (index 0)
    if any(count >= 2 for count in rank_counts.values()):
        features[0] = 1.0
    
    # board_trips_or_more (index 1)
    if any(count >= 3 for count in rank_counts.values()):
        features[1] = 1.0
    # Also check for two pair on board
    elif sum(1 for count in rank_counts.values() if count >= 2) >= 2:
        features[1] = 1.0
    
    # board_monotone (index 2)
    if any(count >= 3 for count in suit_counts.values()):
        features[2] = 1.0
    
    # board_two_suited (index 3)
    if any(count == 2 for count in suit_counts.values()) and features[2] == 0:
        features[3] = 1.0
    
    # board_ace_high (index 4)
    if max(ranks) == 14:
        features[4] = 1.0
    
    # board_low (index 5)
    if max(ranks) <= 9:
        features[5] = 1.0
    
    return features


def calculate_future_equity(
    hole_cards: List[Card],
    board: List[Card],
    street: Street,
    num_samples: int = 100
) -> float:
    """Calculate average equity on future streets.
    
    For flop: average equity over sampled turns
    For turn: average equity over sampled rivers
    For river: return 0 (no future street)
    """
    if street == Street.RIVER or street == Street.PREFLOP:
        return 0.0
    
    if not hole_cards or not board:
        return 0.0
    
    try:
        # Convert to eval7
        hand = [card_to_eval7(c) for c in hole_cards]
        board_eval7 = [card_to_eval7(c) for c in board]
        
        # Create deck without dealt cards
        deck = eval7.Deck()
        for card in hand + board_eval7:
            deck.cards.remove(card)
        
        equity_sum = 0.0
        cards_to_deal = 1  # Deal 1 turn or 1 river
        
        # eval7 evaluation value ranges (empirically determined)
        # eval7.evaluate() returns higher values for better hands
        # Observed range: ~500k (worst high card) to ~135M (royal flush)
        # These constants provide a reasonable normalization to [0, 1] range
        EVAL7_MIN_VALUE = 500_000
        EVAL7_MAX_VALUE = 135_000_000
        
        for _ in range(num_samples):
            deck.shuffle()
            
            # Deal next card(s)
            future_cards = deck.deal(cards_to_deal)
            future_board = board_eval7 + future_cards
            
            # Calculate equity on this future board (simplified: just evaluate strength)
            # For speed, we approximate with hand strength rather than full equity calc
            if len(future_board) < 5:
                # Pad to 5 cards for evaluation
                remaining_needed = 5 - len(future_board)
                extra_cards = deck.deal(remaining_needed) if remaining_needed > 0 else []
                eval_board = future_board + extra_cards
                
                # Return cards for next iteration
                for card in extra_cards:
                    deck.cards.append(card)
            else:
                eval_board = future_board[:5]
            
            # Evaluate hand strength (normalized to 0-1)
            hand_value = eval7.evaluate(hand + eval_board)
            # eval7 uses higher values for better hands
            # Normalize to 0-1 range using empirically determined constants
            equity_approx = (hand_value - EVAL7_MIN_VALUE) / (EVAL7_MAX_VALUE - EVAL7_MIN_VALUE)
            equity_approx = max(0.0, min(1.0, equity_approx))  # Clamp to [0, 1]
            equity_sum += equity_approx
            
            # Return dealt cards
            for card in future_cards:
                deck.cards.append(card)
        
        return equity_sum / num_samples
        
    except Exception as e:
        logger.warning(f"Error calculating future equity: {e}")
        return 0.5


def bin_spr(spr: float) -> np.ndarray:
    """Bin SPR into 3 categories (one-hot).
    
    Returns 3-dim one-hot vector:
    - [1, 0, 0]: SPR < 3 (low)
    - [0, 1, 0]: 3 <= SPR <= 8 (mid)
    - [0, 0, 1]: SPR > 8 (high)
    """
    bins = np.zeros(3, dtype=np.float64)
    
    if spr < 3:
        bins[0] = 1.0
    elif spr <= 8:
        bins[1] = 1.0
    else:
        bins[2] = 1.0
    
    return bins


def extract_postflop_features(
    hole_cards: List[Card],
    board: List[Card],
    street: Street,
    pot: float = 100.0,
    stack: float = 200.0,
    is_in_position: bool = True,
    num_opponents: int = 1,
    equity_samples: int = 500,
    future_equity_samples: int = 100
) -> np.ndarray:
    """Extract comprehensive postflop features (~34 dimensions).
    
    Feature structure:
    - Hand category (12 dims, one-hot)
    - Flush draw (4 dims, one-hot)
    - Straight draw (5 dims: 4 one-hot + 1 is_high flag)
    - Combo draw (1 dim)
    - Board texture (6 dims, binary flags)
    - Context (6 dims: equity_now, equity_future, SPR bins (3), is_ip)
    
    Total: 12 + 4 + 5 + 1 + 6 + 6 = 34 dimensions
    """
    features = []
    
    # 1. Hand category (12 dims, one-hot)
    hand_cat = classify_hand_category(hole_cards, board)
    hand_cat_onehot = np.zeros(12, dtype=np.float64)
    hand_cat_onehot[hand_cat] = 1.0
    features.extend(hand_cat_onehot)
    
    # 2. Flush draw (4 dims, one-hot)
    flush_draw = detect_flush_draw(hole_cards, board)
    flush_onehot = np.zeros(4, dtype=np.float64)
    flush_onehot[flush_draw] = 1.0
    features.extend(flush_onehot)
    
    # 3. Straight draw (5 dims: 4 one-hot for type + 1 flag for is_high)
    straight_draw, is_high = detect_straight_draw(hole_cards, board)
    straight_onehot = np.zeros(4, dtype=np.float64)
    straight_onehot[straight_draw] = 1.0
    features.extend(straight_onehot)
    features.append(float(is_high))
    
    # 4. Combo draw (1 dim)
    combo = has_combo_draw(flush_draw, straight_draw)
    features.append(float(combo))
    
    # 5. Board texture (6 dims)
    board_tex = analyze_board_texture(board)
    features.extend(board_tex)
    
    # 6. Context (6 dims)
    # Equity now
    equity_now = calculate_equity(hole_cards, board, num_opponents, equity_samples)
    features.append(equity_now)
    
    # Equity future (average on next street)
    equity_future = calculate_future_equity(hole_cards, board, street, future_equity_samples)
    features.append(equity_future)
    
    # SPR binned (3 dims)
    spr = stack / max(pot, 1.0)
    spr_bins = bin_spr(spr)
    features.extend(spr_bins)
    
    # Position (1 dim)
    features.append(1.0 if is_in_position else 0.0)
    
    return np.array(features, dtype=np.float64)
