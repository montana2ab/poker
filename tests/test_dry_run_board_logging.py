"""Test board card logging in dry-run mode."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from holdem.types import TableState, Street, Card, PlayerState

def test_board_card_string_representation():
    """Test that board cards are formatted correctly for logging."""
    # Create a table state with board cards
    board = [
        Card('A', 'h'),
        Card('K', 'd'),
        Card('Q', 'c')
    ]
    
    state = TableState(
        street=Street.FLOP,
        pot=150.0,
        board=board,
        players=[]
    )
    
    # Format board cards like in run_dry_run.py
    if state.board:
        board_str = ", ".join([str(c) for c in state.board])
        assert board_str == "Ah, Kd, Qc"


def test_board_cards_on_turn_and_river():
    """Test board cards for turn and river streets."""
    # Test turn (4 cards)
    board_turn = [
        Card('A', 'h'),
        Card('K', 'd'),
        Card('Q', 'c'),
        Card('J', 's')
    ]
    
    state_turn = TableState(
        street=Street.TURN,
        pot=200.0,
        board=board_turn,
        players=[]
    )
    
    board_str = ", ".join([str(c) for c in state_turn.board])
    assert board_str == "Ah, Kd, Qc, Js"
    assert len(state_turn.board) == 4
    
    # Test river (5 cards)
    board_river = [
        Card('A', 'h'),
        Card('K', 'd'),
        Card('Q', 'c'),
        Card('J', 's'),
        Card('T', 'h')
    ]
    
    state_river = TableState(
        street=Street.RIVER,
        pot=300.0,
        board=board_river,
        players=[]
    )
    
    board_str = ", ".join([str(c) for c in state_river.board])
    assert board_str == "Ah, Kd, Qc, Js, Th"
    assert len(state_river.board) == 5


def test_empty_board_preflop():
    """Test that preflop state has no board cards."""
    state = TableState(
        street=Street.PREFLOP,
        pot=3.0,
        board=[],
        players=[]
    )
    
    # Empty board should not log
    assert len(state.board) == 0
    assert not state.board  # Evaluates to False


if __name__ == "__main__":
    # Run tests manually since pytest dependencies may not be available
    print("Testing board card string representation...")
    test_board_card_string_representation()
    print("✓ test_board_card_string_representation passed")
    
    print("\nTesting board cards on turn and river...")
    test_board_cards_on_turn_and_river()
    print("✓ test_board_cards_on_turn_and_river passed")
    
    print("\nTesting empty board preflop...")
    test_empty_board_preflop()
    print("✓ test_empty_board_preflop passed")
    
    print("\nAll tests passed!")
