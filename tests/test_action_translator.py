"""Tests for action translation and abstraction."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import Action, ActionType, Street
from holdem.abstraction.action_translator import ActionTranslator, ActionSetMode, LegalConstraints


def test_action_translator_basic():
    """Test basic action translation."""
    translator = ActionTranslator(mode=ActionSetMode.BALANCED)
    
    # Test fold
    action = translator.to_client(
        action_id=0,
        pot=100.0,
        stack=200.0,
        constraints=LegalConstraints(min_raise=2.0, max_bet=200.0, min_chip=0.01),
        street=Street.FLOP
    )
    assert action.action_type == ActionType.FOLD
    print("✓ Fold translation works")
    
    # Test check/call
    action = translator.to_client(
        action_id=1,
        pot=100.0,
        stack=200.0,
        constraints=LegalConstraints(min_raise=2.0, max_bet=200.0, min_chip=0.01),
        street=Street.FLOP,
        current_bet=0.0,
        player_bet=0.0
    )
    assert action.action_type == ActionType.CHECK
    print("✓ Check translation works")
    
    # Test call with bet to match
    action = translator.to_client(
        action_id=1,
        pot=100.0,
        stack=200.0,
        constraints=LegalConstraints(min_raise=2.0, max_bet=200.0, min_chip=0.01),
        street=Street.FLOP,
        current_bet=20.0,
        player_bet=0.0
    )
    assert action.action_type == ActionType.CALL
    assert action.amount == 20.0
    print("✓ Call translation works")
    
    # Test pot-sized bet
    action = translator.to_client(
        action_id=3,  # Usually pot-sized bet
        pot=100.0,
        stack=200.0,
        constraints=LegalConstraints(min_raise=2.0, max_bet=200.0, min_chip=0.01),
        street=Street.FLOP,
        current_bet=0.0,
        player_bet=0.0
    )
    assert action.action_type in [ActionType.BET, ActionType.RAISE]
    print(f"✓ Pot-sized bet translation works: {action}")


def test_min_raise_compliance():
    """Test that min-raise rules are respected."""
    translator = ActionTranslator(mode=ActionSetMode.BALANCED)
    
    # Test min-raise when facing a bet
    constraints = LegalConstraints(min_raise=10.0, max_bet=200.0, min_chip=1.0)
    
    action = translator.to_client(
        action_id=2,  # Small bet
        pot=50.0,
        stack=200.0,
        constraints=constraints,
        street=Street.RIVER,
        current_bet=20.0,
        player_bet=0.0
    )
    
    # Should respect min-raise
    if action.action_type in [ActionType.RAISE, ActionType.BET]:
        assert action.amount >= 20.0 + constraints.min_raise, \
            f"Min-raise violated: {action.amount} < {20.0 + constraints.min_raise}"
    
    print("✓ Min-raise compliance works")


def test_all_in_capping():
    """Test that all-in is correctly identified."""
    translator = ActionTranslator(mode=ActionSetMode.BALANCED)
    
    # Test all-in when bet >= 97% of stack
    action = translator.to_client(
        action_id=5,  # Large bet
        pot=100.0,
        stack=100.0,
        constraints=LegalConstraints(min_raise=2.0, max_bet=100.0, min_chip=0.01),
        street=Street.RIVER,
        current_bet=0.0,
        player_bet=0.0
    )
    
    assert action.action_type == ActionType.ALLIN
    assert action.amount == 100.0
    print("✓ All-in capping works")


def test_chip_rounding():
    """Test that chip rounding works correctly."""
    translator = ActionTranslator(mode=ActionSetMode.BALANCED)
    
    # Test rounding to 0.01 chips
    constraints = LegalConstraints(min_raise=2.0, max_bet=200.0, min_chip=0.01)
    
    action = translator.to_client(
        action_id=2,
        pot=33.333,  # Will create fractional bet size
        stack=200.0,
        constraints=constraints,
        street=Street.FLOP,
        current_bet=0.0,
        player_bet=0.0
    )
    
    if action.action_type in [ActionType.BET, ActionType.RAISE]:
        # Check that amount is rounded to 0.01
        assert action.amount == round(action.amount / 0.01) * 0.01
    
    print("✓ Chip rounding works")


def test_action_set_modes():
    """Test different action set modes."""
    # Tight mode
    tight = ActionTranslator(mode=ActionSetMode.TIGHT)
    tight_actions = tight.get_action_set(Street.FLOP)
    assert len(tight_actions) == 3
    print(f"✓ Tight mode: {len(tight_actions)} actions")
    
    # Balanced mode
    balanced = ActionTranslator(mode=ActionSetMode.BALANCED)
    balanced_actions = balanced.get_action_set(Street.FLOP)
    assert len(balanced_actions) == 4
    print(f"✓ Balanced mode: {len(balanced_actions)} actions")
    
    # Loose mode
    loose = ActionTranslator(mode=ActionSetMode.LOOSE)
    loose_actions = loose.get_action_set(Street.FLOP)
    assert len(loose_actions) >= 6
    print(f"✓ Loose mode: {len(loose_actions)} actions")


def test_round_trip_idempotence():
    """Test that round-trip conversion maintains EV."""
    translator = ActionTranslator(mode=ActionSetMode.BALANCED)
    
    # Test with a pot-sized bet
    original_action = Action(ActionType.BET, amount=100.0)
    pot = 100.0
    stack = 200.0
    constraints = LegalConstraints(min_raise=2.0, max_bet=200.0, min_chip=0.01)
    
    is_close, ev_distance = translator.round_trip_test(
        original_action,
        pot,
        stack,
        constraints,
        street=Street.FLOP,
        epsilon=0.05
    )
    
    print(f"✓ Round-trip test: is_close={is_close}, ev_distance={ev_distance:.4f}")
    assert ev_distance < 0.1, f"EV distance too large: {ev_distance}"


if __name__ == "__main__":
    print("Testing ActionTranslator...")
    print()
    
    test_action_translator_basic()
    print()
    
    test_min_raise_compliance()
    print()
    
    test_all_in_capping()
    print()
    
    test_chip_rounding()
    print()
    
    test_action_set_modes()
    print()
    
    test_round_trip_idempotence()
    print()
    
    print("All tests passed! ✓")
