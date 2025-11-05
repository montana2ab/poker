"""Feature extraction for hand evaluation."""

import eval7
import numpy as np
from typing import List, Tuple
from holdem.types import Card, Street, TableState
from holdem.utils.logging import get_logger

logger = get_logger("abstraction.features")


def card_to_eval7(card: Card) -> eval7.Card:
    """Convert our Card type to eval7.Card."""
    # eval7 uses the simple format: rank + suit (e.g., "As", "Kh", "Td")
    # Our Card already has rank and suit in compatible format
    return eval7.Card(f"{card.rank}{card.suit}")


def calculate_equity(hole_cards: List[Card], board: List[Card], num_opponents: int = 1, num_samples: int = 1000) -> float:
    """Calculate hand equity using Monte Carlo simulation."""
    if not hole_cards or len(hole_cards) != 2:
        return 0.0
    
    try:
        # Convert to eval7 cards
        hand = [card_to_eval7(c) for c in hole_cards]
        board_eval7 = [card_to_eval7(c) for c in board] if board else []
        
        # Validate board size
        if len(board_eval7) > 5:
            logger.warning(f"Invalid board size: {len(board_eval7)} cards (max 5)")
            return 0.5
        
        # Create deck
        deck = eval7.Deck()
        for card in hand + board_eval7:
            deck.cards.remove(card)
        
        wins = 0
        ties = 0
        
        for _ in range(num_samples):
            deck.shuffle()
            
            # Deal community cards and track them
            needed_board_cards = max(0, 5 - len(board_eval7))
            dealt_board_cards = deck.deal(needed_board_cards) if needed_board_cards > 0 else []
            sim_board = board_eval7 + dealt_board_cards
            
            # Evaluate our hand
            our_hand_value = eval7.evaluate(hand + sim_board)
            
            # Simulate opponents and track dealt cards
            opponent_better = False
            opponent_tie = False
            dealt_opp_cards = []
            
            for _ in range(num_opponents):
                opp_cards = deck.deal(2)
                dealt_opp_cards.extend(opp_cards)
                opp_value = eval7.evaluate(opp_cards + sim_board)
                
                if opp_value > our_hand_value:
                    opponent_better = True
                    break
                elif opp_value == our_hand_value:
                    opponent_tie = True
            
            if not opponent_better:
                if opponent_tie:
                    ties += 1
                else:
                    wins += 1
            
            # Return dealt cards to deck
            for card in dealt_board_cards + dealt_opp_cards:
                deck.cards.append(card)
        
        equity = (wins + ties * 0.5) / num_samples
        return equity
        
    except Exception as e:
        logger.warning(f"Error calculating equity: {e}")
        return 0.5  # Default to 50% if calculation fails


def extract_features(
    hole_cards: List[Card],
    board: List[Card],
    street: Street,
    position: int,
    pot: float,
    stack: float,
    num_opponents: int = 1
) -> np.ndarray:
    """Extract features for hand bucketing."""
    features = []
    
    # Equity (most important feature)
    equity = calculate_equity(hole_cards, board, num_opponents, num_samples=500)
    features.append(equity)
    
    # Position (normalized)
    features.append(position / 9.0)  # Assuming max 9 players
    
    # Stack-to-pot ratio (SPR)
    spr = stack / max(pot, 1.0)
    spr = min(spr, 20.0) / 20.0  # Normalize and cap
    features.append(spr)
    
    # Street (one-hot encoded)
    street_features = [0.0] * 4
    street_features[street.value] = 1.0
    features.extend(street_features)
    
    # Hand strength features (simplified)
    if hole_cards and len(hole_cards) == 2:
        # Pair
        is_pair = 1.0 if hole_cards[0].rank == hole_cards[1].rank else 0.0
        features.append(is_pair)
        
        # Suited
        is_suited = 1.0 if hole_cards[0].suit == hole_cards[1].suit else 0.0
        features.append(is_suited)
        
        # High card value
        rank_values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                      '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        high_card = max(rank_values.get(hole_cards[0].rank, 0), 
                       rank_values.get(hole_cards[1].rank, 0))
        features.append(high_card / 14.0)
    else:
        features.extend([0.0, 0.0, 0.0])
    
    # Draw potential (simplified - would need more sophisticated analysis)
    draw_potential = 0.0
    if street in [Street.FLOP, Street.TURN] and board:
        # Placeholder for flush/straight draw detection
        draw_potential = 0.0
    features.append(draw_potential)
    
    return np.array(features, dtype=np.float64)


def extract_simple_features(hole_cards: List[Card], board: List[Card]) -> np.ndarray:
    """Extract simplified features for faster bucketing."""
    features = []
    
    if not hole_cards or len(hole_cards) != 2:
        return np.zeros(5, dtype=np.float64)
    
    rank_values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                  '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
    
    # High card
    high = max(rank_values.get(hole_cards[0].rank, 0), 
              rank_values.get(hole_cards[1].rank, 0))
    features.append(high / 14.0)
    
    # Low card
    low = min(rank_values.get(hole_cards[0].rank, 0), 
             rank_values.get(hole_cards[1].rank, 0))
    features.append(low / 14.0)
    
    # Pair
    features.append(1.0 if hole_cards[0].rank == hole_cards[1].rank else 0.0)
    
    # Suited
    features.append(1.0 if hole_cards[0].suit == hole_cards[1].suit else 0.0)
    
    # Gap
    gap = abs(rank_values.get(hole_cards[0].rank, 0) - 
             rank_values.get(hole_cards[1].rank, 0))
    features.append(min(gap, 12) / 12.0)
    
    return np.array(features, dtype=np.float64)
