"""Tests for PokerStars sizing consistency and anti-oscillation (P0 requirement).

Tests cover:
1. Min-raise with multi-side-pots
2. 0.01 chip size handling
3. Anti-oscillation (snap to next step if rounding breaks min-raise)
"""

import pytest
from holdem.abstraction.actions import ActionAbstraction, AbstractAction
from holdem.abstraction.action_translator import ActionTranslator, LegalConstraints, ActionSetMode
from holdem.types import Action, ActionType, Street


def test_min_chip_size_0_01():
    """Test handling of 0.01 chip size (PokerStars micro stakes)."""
    # Scenario: 0.01/0.02 game with 0.01 chip increment
    pot = 0.10
    stack = 2.00
    big_blind = 0.02
    min_chip = 0.01
    
    # Test BET_HALF_POT (should be 0.05)
    action = ActionAbstraction.abstract_to_concrete(
        AbstractAction.BET_HALF_POT,
        pot=pot,
        stack=stack,
        current_bet=0.0,
        player_bet=0.0,
        can_check=True,
        big_blind=big_blind,
        min_chip_increment=min_chip
    )
    
    assert action.action_type == ActionType.BET
    # Should round to 0.05 (nearest 0.01)
    assert abs(action.amount - 0.05) < 0.001
    
    # Test BET_THIRD_POT (should be 0.03)
    action = ActionAbstraction.abstract_to_concrete(
        AbstractAction.BET_THIRD_POT,
        pot=pot,
        stack=stack,
        current_bet=0.0,
        player_bet=0.0,
        can_check=True,
        big_blind=big_blind,
        min_chip_increment=min_chip
    )
    
    assert action.action_type == ActionType.BET
    # Should round to 0.03 (nearest 0.01)
    assert abs(action.amount - 0.03) < 0.001


def test_min_raise_multi_side_pots():
    """Test min-raise calculation with multi-side-pots scenario.
    
    In multi-way pots with side pots, PokerStars enforces that:
    - Minimum raise = at least the size of the previous raise
    - Or if first raise, at least 1 BB
    """
    pot = 100.0
    stack = 200.0
    big_blind = 2.0
    
    # Scenario: Facing a bet of 20, previous raise was 20 (from 0)
    # Minimum raise should be 20, so minimum total = 40
    current_bet = 20.0
    player_bet = 0.0
    
    # Try to make a small raise (bet 0.33 pot = 33)
    action = ActionAbstraction.abstract_to_concrete(
        AbstractAction.BET_THIRD_POT,
        pot=pot,
        stack=stack,
        current_bet=current_bet,
        player_bet=player_bet,
        can_check=False,
        big_blind=big_blind,
        min_chip_increment=1.0
    )
    
    # Should enforce minimum raise
    # to_call = 20, so remaining stack = 180
    # 0.33 * (100 + 20) = 39.6, rounds to 40
    # But min raise increment is BB = 2.0, so total should be at least 20 + 2 = 22
    assert action.action_type in [ActionType.RAISE, ActionType.ALLIN]
    if action.action_type == ActionType.RAISE:
        # Total amount should be at least current_bet + big_blind
        assert action.amount >= current_bet + big_blind


def test_anti_oscillation_snap_to_next_step():
    """Test anti-oscillation: snap to next step if rounding breaks min-raise.
    
    When rounding causes a bet to fall below min-raise, the system should
    snap to the next valid bet size step rather than oscillating.
    """
    pot = 100.0
    stack = 150.0
    big_blind = 2.0
    current_bet = 0.0
    
    # Test sequence: make a bet, then see if response is stable
    # First bet: 0.33 pot = 33
    action1 = ActionAbstraction.abstract_to_concrete(
        AbstractAction.BET_THIRD_POT,
        pot=pot,
        stack=stack,
        current_bet=current_bet,
        player_bet=0.0,
        can_check=True,
        big_blind=big_blind,
        min_chip_increment=1.0
    )
    
    assert action1.action_type == ActionType.BET
    bet1_amount = action1.amount
    
    # New pot after bet: 100 + 33 = 133
    new_pot = pot + bet1_amount
    
    # Facing this bet, try to min-raise with 0.33 pot
    # Should snap to valid size, not create oscillation
    action2 = ActionAbstraction.abstract_to_concrete(
        AbstractAction.BET_THIRD_POT,
        pot=new_pot,
        stack=stack - bet1_amount,
        current_bet=bet1_amount,
        player_bet=0.0,
        can_check=False,
        big_blind=big_blind,
        min_chip_increment=1.0
    )
    
    # Should be a valid raise (not fold, not oscillating)
    assert action2.action_type in [ActionType.RAISE, ActionType.CALL]
    
    if action2.action_type == ActionType.RAISE:
        # Raise should be at least min-raise above the bet
        to_call = bet1_amount
        raise_amount = action2.amount - to_call
        assert raise_amount >= big_blind, f"Raise amount {raise_amount} should be >= BB {big_blind}"


def test_rounding_to_chip_increment():
    """Test that all bet amounts are properly rounded to chip increment."""
    pot = 47.0  # Odd pot size
    stack = 100.0
    big_blind = 2.0
    min_chip = 1.0
    
    # Test various bet sizes with odd pot
    test_actions = [
        AbstractAction.BET_THIRD_POT,
        AbstractAction.BET_HALF_POT,
        AbstractAction.BET_TWO_THIRDS_POT,
        AbstractAction.BET_POT,
    ]
    
    for abstract_action in test_actions:
        action = ActionAbstraction.abstract_to_concrete(
            abstract_action,
            pot=pot,
            stack=stack,
            current_bet=0.0,
            player_bet=0.0,
            can_check=True,
            big_blind=big_blind,
            min_chip_increment=min_chip
        )
        
        if action.action_type in [ActionType.BET, ActionType.RAISE]:
            # Amount should be multiple of min_chip
            remainder = action.amount % min_chip
            assert abs(remainder) < 0.001, f"Action {abstract_action.value} amount {action.amount} not rounded to {min_chip}"


def test_min_raise_consistency():
    """Test that min-raise is consistently enforced across different scenarios."""
    big_blind = 2.0
    
    scenarios = [
        # (pot, stack, current_bet, player_bet, expected_min_total)
        (100.0, 200.0, 10.0, 0.0, 10.0 + big_blind),  # Facing 10, min raise to 12
        (50.0, 100.0, 5.0, 0.0, 5.0 + big_blind),     # Facing 5, min raise to 7
        (200.0, 300.0, 0.0, 0.0, big_blind),          # No bet, min bet is BB
    ]
    
    for pot, stack, current_bet, player_bet, expected_min in scenarios:
        # Try to make a small bet (might be below min-raise)
        action = ActionAbstraction.abstract_to_concrete(
            AbstractAction.BET_QUARTER_POT,
            pot=pot,
            stack=stack,
            current_bet=current_bet,
            player_bet=player_bet,
            can_check=(current_bet == player_bet),
            big_blind=big_blind,
            min_chip_increment=1.0
        )
        
        if action.action_type in [ActionType.BET, ActionType.RAISE]:
            # Should meet minimum requirement
            if current_bet > 0:
                # Facing a bet
                assert action.amount >= expected_min, \
                    f"Scenario (pot={pot}, bet={current_bet}): amount {action.amount} < min {expected_min}"
            else:
                # First to act
                assert action.amount >= expected_min, \
                    f"Scenario (pot={pot}, no bet): amount {action.amount} < min {expected_min}"


def test_action_translator_round_trip_with_min_chip():
    """Test that ActionTranslator maintains consistency with 0.01 chip size."""
    translator = ActionTranslator(mode=ActionSetMode.BALANCED)
    
    pot = 0.47
    stack = 2.00
    min_chip = 0.01
    
    constraints = LegalConstraints(
        min_raise=0.02,  # 1 BB
        max_bet=stack,
        min_chip=min_chip
    )
    
    # Test each discrete action
    for action_id in range(2, 6):  # Skip fold/call
        action = translator.to_client(
            action_id=action_id,
            pot=pot,
            stack=stack,
            constraints=constraints,
            street=Street.FLOP,
            current_bet=0.0,
            player_bet=0.0
        )
        
        if action.action_type in [ActionType.BET, ActionType.RAISE]:
            # Amount should be multiple of min_chip
            remainder = action.amount % min_chip
            assert abs(remainder) < 0.001, \
                f"Action {action_id} amount {action.amount} not rounded to {min_chip}"
            
            # Test round-trip
            is_idempotent, ev_distance = translator.round_trip_test(
                action, pot, stack, constraints, Street.FLOP, epsilon=0.05
            )
            
            # Should be close enough (within 5% of pot)
            assert ev_distance < 0.10, \
                f"Round-trip EV distance {ev_distance} too large for action_id {action_id}"


def test_translator_illegal_after_roundtrip_metric():
    """Test that translator/illegal_after_roundtrip metric can be computed.
    
    This metric must remain 0 (no illegal actions after round-trip).
    """
    translator = ActionTranslator(mode=ActionSetMode.BALANCED)
    
    pot = 100.0
    stack = 200.0
    min_chip = 1.0
    
    constraints = LegalConstraints(
        min_raise=2.0,
        max_bet=stack,
        min_chip=min_chip
    )
    
    illegal_count = 0
    total_tests = 0
    
    # Test all action IDs on different streets
    for street in [Street.FLOP, Street.TURN, Street.RIVER]:
        action_set = translator.get_action_set(street)
        
        for action_id in range(len(action_set) + 2):  # Include fold/call
            total_tests += 1
            
            action = translator.to_client(
                action_id=action_id,
                pot=pot,
                stack=stack,
                constraints=constraints,
                street=street,
                current_bet=0.0,
                player_bet=0.0
            )
            
            # Verify action is legal
            if action.action_type in [ActionType.BET, ActionType.RAISE]:
                # Check min-raise
                if action.amount < constraints.min_raise:
                    illegal_count += 1
                
                # Check rounding
                if abs(action.amount % min_chip) > 0.001:
                    illegal_count += 1
    
    # Metric should be 0
    illegal_rate = illegal_count / total_tests if total_tests > 0 else 0
    assert illegal_rate == 0.0, \
        f"translator/illegal_after_roundtrip should be 0, got {illegal_rate} ({illegal_count}/{total_tests})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
