"""Card deck utilities for sampling and management."""

from typing import List, Set
from holdem.types import Card


# Full 52-card deck
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
SUITS = ['h', 'd', 'c', 's']


def create_full_deck() -> List[Card]:
    """Create a full 52-card deck.
    
    Returns:
        List of all 52 cards
    """
    return [Card(rank=rank, suit=suit) for rank in RANKS for suit in SUITS]


def get_remaining_cards(known_cards: List[Card]) -> List[Card]:
    """Get all cards not in the known set.
    
    Args:
        known_cards: Cards that are already dealt (board, hole cards, etc.)
        
    Returns:
        List of remaining cards in the deck
    """
    full_deck = create_full_deck()
    known_set = {(c.rank, c.suit) for c in known_cards}
    return [card for card in full_deck if (card.rank, card.suit) not in known_set]


def cards_to_set(cards: List[Card]) -> Set[tuple]:
    """Convert list of cards to set of (rank, suit) tuples.
    
    Args:
        cards: List of Card objects
        
    Returns:
        Set of (rank, suit) tuples
    """
    return {(c.rank, c.suit) for c in cards}


def sample_public_cards(
    num_samples: int,
    current_board: List[Card],
    known_cards: List[Card],
    target_street_cards: int,
    rng
) -> List[List[Card]]:
    """Sample future public cards uniformly from remaining deck.
    
    This implements the Pluribus public card sampling technique to reduce
    variance in subgame solving by solving on multiple possible future boards
    and averaging the resulting strategies.
    
    Args:
        num_samples: Number of board samples to generate
        current_board: Current board cards
        known_cards: All known cards (board + hole cards)
        target_street_cards: Total cards on board after sampling (3=flop, 4=turn, 5=river)
        rng: Random number generator (from holdem.utils.rng.get_rng())
        
    Returns:
        List of sampled boards, where each board is a list of Cards
        
    Example:
        # Sample 10 possible turn cards given a flop
        current_board = [Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
        known_cards = current_board + [Card('J', 'c'), Card('T', 'c')]  # + hole cards
        samples = sample_public_cards(10, current_board, known_cards, 4, rng)
        # Returns 10 different 4-card boards
    """
    if len(current_board) >= target_street_cards:
        # Already at or past target street, return current board
        return [current_board.copy() for _ in range(num_samples)]
    
    # Get remaining cards in deck
    remaining = get_remaining_cards(known_cards)
    
    # Number of cards to sample
    cards_to_sample = target_street_cards - len(current_board)
    
    if len(remaining) < cards_to_sample:
        raise ValueError(
            f"Not enough cards in deck: need {cards_to_sample}, "
            f"but only {len(remaining)} remaining"
        )
    
    # Sample boards
    sampled_boards = []
    for _ in range(num_samples):
        # Sample cards uniformly without replacement
        sampled_cards = rng.choice(remaining, size=cards_to_sample, replace=False)
        new_board = current_board + [
            Card(rank=c.rank, suit=c.suit) for c in sampled_cards
        ]
        sampled_boards.append(new_board)
    
    return sampled_boards
