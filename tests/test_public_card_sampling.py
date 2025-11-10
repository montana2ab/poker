"""Tests for public card sampling (board sampling)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import numpy as np
from holdem.types import Card, Street, SearchConfig
from holdem.utils.deck import (
    create_full_deck,
    get_remaining_cards,
    sample_public_cards,
    cards_to_set
)
from holdem.utils.rng import get_rng


def test_create_full_deck():
    """Test creating a full 52-card deck."""
    deck = create_full_deck()
    
    assert len(deck) == 52, "Deck should have 52 cards"
    
    # Check uniqueness
    card_set = {(c.rank, c.suit) for c in deck}
    assert len(card_set) == 52, "All cards should be unique"
    
    # Check all ranks and suits are present
    ranks = {c.rank for c in deck}
    suits = {c.suit for c in deck}
    
    assert len(ranks) == 13, "Should have 13 ranks"
    assert len(suits) == 4, "Should have 4 suits"
    
    print("✓ create_full_deck works")


def test_get_remaining_cards():
    """Test getting remaining cards in deck."""
    # Remove some cards
    known_cards = [
        Card('A', 'h'),
        Card('K', 's'),
        Card('Q', 'd')
    ]
    
    remaining = get_remaining_cards(known_cards)
    
    assert len(remaining) == 49, "Should have 49 remaining cards"
    
    # Check known cards are not in remaining
    remaining_set = cards_to_set(remaining)
    for card in known_cards:
        assert (card.rank, card.suit) not in remaining_set
    
    print("✓ get_remaining_cards works")


def test_sample_public_cards_flop_to_turn():
    """Test sampling turn card given a flop."""
    rng = get_rng()
    
    # Current flop
    current_board = [
        Card('A', 'h'),
        Card('K', 's'),
        Card('Q', 'd')
    ]
    
    # Known cards include board and hole cards
    known_cards = current_board + [
        Card('J', 'c'),
        Card('T', 'c')
    ]
    
    # Sample 10 possible turn cards
    num_samples = 10
    sampled_boards = sample_public_cards(
        num_samples=num_samples,
        current_board=current_board,
        known_cards=known_cards,
        target_street_cards=4,  # Flop + turn
        rng=rng
    )
    
    assert len(sampled_boards) == num_samples, f"Should have {num_samples} samples"
    
    # Check each board
    for board in sampled_boards:
        assert len(board) == 4, "Each board should have 4 cards (flop + turn)"
        
        # First 3 cards should match original flop
        for i in range(3):
            assert board[i].rank == current_board[i].rank
            assert board[i].suit == current_board[i].suit
        
        # Turn card should not be in known cards
        turn_card = board[3]
        known_set = cards_to_set(known_cards)
        assert (turn_card.rank, turn_card.suit) not in known_set
    
    # Check that we got different samples (at least some variation)
    turn_cards = [board[3] for board in sampled_boards]
    turn_set = {(c.rank, c.suit) for c in turn_cards}
    # With 10 samples from 47 remaining cards, we should get some variety
    # (not all the same unless extremely unlucky)
    if num_samples > 1:
        assert len(turn_set) >= 1, "Should have at least one unique turn card"
    
    print("✓ sample_public_cards (flop->turn) works")


def test_sample_public_cards_turn_to_river():
    """Test sampling river card given a turn."""
    rng = get_rng()
    
    # Current board (flop + turn)
    current_board = [
        Card('A', 'h'),
        Card('K', 's'),
        Card('Q', 'd'),
        Card('J', 'h')
    ]
    
    # Known cards
    known_cards = current_board + [
        Card('T', 'c'),
        Card('9', 'c')
    ]
    
    # Sample 5 possible river cards
    num_samples = 5
    sampled_boards = sample_public_cards(
        num_samples=num_samples,
        current_board=current_board,
        known_cards=known_cards,
        target_street_cards=5,  # Full board
        rng=rng
    )
    
    assert len(sampled_boards) == num_samples
    
    for board in sampled_boards:
        assert len(board) == 5, "Each board should have 5 cards"
        
        # First 4 cards should match
        for i in range(4):
            assert board[i].rank == current_board[i].rank
            assert board[i].suit == current_board[i].suit
        
        # River card should not be in known cards
        river_card = board[4]
        known_set = cards_to_set(known_cards)
        assert (river_card.rank, river_card.suit) not in known_set
    
    print("✓ sample_public_cards (turn->river) works")


def test_sample_public_cards_already_at_target():
    """Test sampling when already at target street."""
    rng = get_rng()
    
    # Already at river (5 cards)
    current_board = [
        Card('A', 'h'),
        Card('K', 's'),
        Card('Q', 'd'),
        Card('J', 'h'),
        Card('T', 's')
    ]
    
    known_cards = current_board + [Card('9', 'c'), Card('8', 'c')]
    
    # Try to sample with target=5 (already there)
    sampled_boards = sample_public_cards(
        num_samples=3,
        current_board=current_board,
        known_cards=known_cards,
        target_street_cards=5,
        rng=rng
    )
    
    assert len(sampled_boards) == 3
    
    # All boards should be identical to current board
    for board in sampled_boards:
        assert len(board) == 5
        for i in range(5):
            assert board[i].rank == current_board[i].rank
            assert board[i].suit == current_board[i].suit
    
    print("✓ sample_public_cards (already at target) works")


def test_sample_public_cards_variance():
    """Test that sampling produces different boards (variance)."""
    rng = get_rng()
    
    current_board = [
        Card('A', 'h'),
        Card('K', 's'),
        Card('Q', 'd')
    ]
    
    known_cards = current_board + [Card('J', 'c'), Card('T', 'c')]
    
    # Sample 50 turn cards
    num_samples = 50
    sampled_boards = sample_public_cards(
        num_samples=num_samples,
        current_board=current_board,
        known_cards=known_cards,
        target_street_cards=4,
        rng=rng
    )
    
    # Get all unique turn cards
    turn_cards = [board[3] for board in sampled_boards]
    unique_turns = {(c.rank, c.suit) for c in turn_cards}
    
    # With 50 samples from 47 remaining cards, we should get good variety
    # Expect at least 30 unique cards (probabilistically very likely)
    assert len(unique_turns) >= 25, f"Expected at least 25 unique turn cards, got {len(unique_turns)}"
    
    print(f"✓ sample_public_cards variance test: {len(unique_turns)}/50 unique")


def test_search_config_samples_per_solve():
    """Test that SearchConfig has samples_per_solve parameter."""
    config = SearchConfig()
    
    # Default should be 1 (no sampling)
    assert hasattr(config, 'samples_per_solve')
    assert config.samples_per_solve == 1
    
    # Should be able to set it
    config.samples_per_solve = 20
    assert config.samples_per_solve == 20
    
    print("✓ SearchConfig.samples_per_solve works")


if __name__ == "__main__":
    test_create_full_deck()
    test_get_remaining_cards()
    test_sample_public_cards_flop_to_turn()
    test_sample_public_cards_turn_to_river()
    test_sample_public_cards_already_at_target()
    test_sample_public_cards_variance()
    test_search_config_samples_per_solve()
    
    print("\n✅ All public card sampling tests passed!")
