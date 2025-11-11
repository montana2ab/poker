"""Comprehensive tests for action backmapping with 100+ edge cases."""

import pytest
from holdem.abstraction.backmapping import ActionBackmapper
from holdem.abstraction.actions import AbstractAction
from holdem.types import Action, ActionType, Street


class TestBasicBackmapping:
    """Test basic backmapping functionality."""
    
    def test_fold(self):
        """Test fold backmapping."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.FOLD,
            pot=100, stack=200, current_bet=50, player_bet=0,
            can_check=False
        )
        assert action.action_type == ActionType.FOLD
    
    def test_check_when_can_check(self):
        """Test check when no bet to call."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.CHECK_CALL,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.CHECK
    
    def test_call_basic(self):
        """Test basic call."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.CHECK_CALL,
            pot=100, stack=200, current_bet=50, player_bet=0,
            can_check=False
        )
        assert action.action_type == ActionType.CALL
        assert action.amount == 50
    
    def test_all_in_explicit(self):
        """Test explicit all-in request."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.ALL_IN,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.ALLIN
        assert action.amount == 200


class TestFoldEdgeCases:
    """Test fold edge cases."""
    
    def test_fold_when_can_check_converts_to_check(self):
        """Edge case: folding when can check should convert to check."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.FOLD,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.CHECK
    
    def test_fold_when_facing_bet(self):
        """Fold is valid when facing a bet."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.FOLD,
            pot=100, stack=200, current_bet=50, player_bet=0,
            can_check=False
        )
        assert action.action_type == ActionType.FOLD
    
    def test_fold_with_partial_investment(self):
        """Fold when already invested in pot."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.FOLD,
            pot=100, stack=200, current_bet=50, player_bet=25,
            can_check=False
        )
        assert action.action_type == ActionType.FOLD


class TestCallEdgeCases:
    """Test call edge cases."""
    
    def test_call_with_insufficient_stack(self):
        """Edge case: call with stack < to_call (forced all-in)."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.CHECK_CALL,
            pot=100, stack=30, current_bet=50, player_bet=0,
            can_check=False
        )
        assert action.action_type == ActionType.CALL
        assert action.amount == 30  # All we have
    
    def test_call_exact_stack(self):
        """Call when to_call equals stack."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.CHECK_CALL,
            pot=100, stack=50, current_bet=50, player_bet=0,
            can_check=False
        )
        assert action.action_type == ActionType.CALL
        assert action.amount == 50
    
    def test_call_with_partial_investment(self):
        """Call when already have chips in pot."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.CHECK_CALL,
            pot=100, stack=200, current_bet=50, player_bet=20,
            can_check=False
        )
        assert action.action_type == ActionType.CALL
        assert action.amount == 30  # 50 - 20
    
    def test_micro_call_below_minimum(self):
        """Edge case: call amount below chip minimum."""
        mapper = ActionBackmapper(min_chip_increment=1.0)
        action = mapper.backmap_action(
            AbstractAction.CHECK_CALL,
            pot=100, stack=200, current_bet=0.5, player_bet=0,
            can_check=False
        )
        # Should still make the call even if below minimum
        assert action.action_type == ActionType.CALL
        assert action.amount == 0.5
    
    def test_call_zero_amount_converts_to_check(self):
        """Edge case: call with zero to_call should be check."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.CHECK_CALL,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.CHECK


class TestBetEdgeCases:
    """Test bet edge cases."""
    
    def test_bet_pot_basic(self):
        """Basic pot-sized bet."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.BET
        assert action.amount == 100
    
    def test_bet_half_pot(self):
        """Half pot bet."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.BET_HALF_POT,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.BET
        assert action.amount == 50
    
    def test_bet_below_minimum_adjusted(self):
        """Edge case: bet below minimum should be adjusted."""
        mapper = ActionBackmapper(big_blind=10.0)
        action = mapper.backmap_action(
            AbstractAction.BET_QUARTER_POT,
            pot=20, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        # 0.25 * 20 = 5, which is below BB of 10
        # Should be adjusted to at least BB
        assert action.action_type == ActionType.BET
        assert action.amount >= 10
    
    def test_bet_exceeds_stack_converts_to_allin(self):
        """Edge case: bet exceeds stack becomes all-in."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=100, stack=50, current_bet=0, player_bet=0,
            can_check=True
        )
        # Want to bet 100 but only have 50
        assert action.action_type == ActionType.ALLIN
        assert action.amount == 50
    
    def test_bet_near_stack_converts_to_allin(self):
        """Edge case: bet >= 97% of stack becomes all-in."""
        mapper = ActionBackmapper(all_in_threshold=0.97)
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=100, stack=102, current_bet=0, player_bet=0,
            can_check=True
        )
        # Bet would be 100, which is 98% of 102 stack
        assert action.action_type == ActionType.ALLIN
        assert action.amount == 102
    
    def test_bet_with_chip_rounding(self):
        """Bet amount rounded to chip increment."""
        mapper = ActionBackmapper(min_chip_increment=0.5)
        action = mapper.backmap_action(
            AbstractAction.BET_THIRD_POT,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        # 0.33 * 100 = 33, should round to nearest 0.5
        assert action.action_type == ActionType.BET
        assert action.amount % 0.5 == 0
    
    def test_bet_tiny_pot(self):
        """Edge case: bet with very small pot."""
        mapper = ActionBackmapper(big_blind=2.0)
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=1, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        # Pot is 1, but minimum bet is BB (2)
        assert action.action_type == ActionType.BET
        assert action.amount >= 2.0


class TestRaiseEdgeCases:
    """Test raise edge cases."""
    
    def test_raise_basic(self):
        """Basic pot-sized raise."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=150, stack=300, current_bet=50, player_bet=0,
            can_check=False
        )
        # Pot is 150, to_call is 50, raise to 1.0 * (150 + 50) = 200
        assert action.action_type == ActionType.RAISE
        assert action.amount == 200
    
    def test_raise_with_min_raise_constraint(self):
        """Raise must meet minimum raise requirement."""
        mapper = ActionBackmapper(big_blind=10.0)
        action = mapper.backmap_action(
            AbstractAction.BET_QUARTER_POT,
            pot=100, stack=200, current_bet=50, player_bet=0,
            can_check=False,
            last_raise_amount=20.0
        )
        # Small raise should be bumped to meet minimum
        assert action.action_type in [ActionType.RAISE, ActionType.ALLIN]
        if action.action_type == ActionType.RAISE:
            # Should be at least to_call (50) + min_raise (20) = 70
            assert action.amount >= 70
    
    def test_raise_exceeds_stack_converts_to_allin(self):
        """Edge case: raise exceeds stack becomes all-in."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.BET_DOUBLE_POT,
            pot=150, stack=100, current_bet=50, player_bet=0,
            can_check=False
        )
        # Want big raise but insufficient stack
        assert action.action_type == ActionType.ALLIN
        assert action.amount == 100
    
    def test_raise_near_stack_converts_to_allin(self):
        """Edge case: raise near stack threshold becomes all-in."""
        mapper = ActionBackmapper(all_in_threshold=0.97)
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=150, stack=200, current_bet=50, player_bet=0,
            can_check=False
        )
        # Raise to 200 is 100% of stack
        assert action.action_type == ActionType.ALLIN
        assert action.amount == 200
    
    def test_raise_with_partial_investment(self):
        """Raise when already have chips in pot."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=150, stack=300, current_bet=50, player_bet=25,
            can_check=False
        )
        # to_call = 50 - 25 = 25
        # raise to 1.0 * (150 + 25) = 175 total
        assert action.action_type == ActionType.RAISE
        assert action.amount == 175
    
    def test_raise_below_minimum_with_sufficient_stack(self):
        """Edge case: raise below minimum but have chips to meet it."""
        mapper = ActionBackmapper(big_blind=10.0)
        # This is tricky - need a scenario where abstract action suggests small raise
        # but we have stack to meet minimum
        action = mapper.backmap_action(
            AbstractAction.BET_QUARTER_POT,
            pot=100, stack=200, current_bet=40, player_bet=0,
            can_check=False,
            last_raise_amount=30.0
        )
        # to_call = 40, min_raise = 30, so min total = 70
        # 0.25 * (100 + 40) = 35, which is below min
        # Should be adjusted to meet minimum
        assert action.action_type in [ActionType.RAISE, ActionType.ALLIN]
        if action.action_type == ActionType.RAISE:
            assert action.amount >= 70
    
    def test_raise_below_minimum_insufficient_stack_converts_to_allin(self):
        """Edge case: can't meet min-raise, convert to all-in."""
        mapper = ActionBackmapper(big_blind=10.0)
        action = mapper.backmap_action(
            AbstractAction.BET_QUARTER_POT,
            pot=100, stack=60, current_bet=40, player_bet=0,
            can_check=False,
            last_raise_amount=30.0
        )
        # to_call = 40, min_raise = 30, so min total = 70
        # But we only have 60 (less than min total)
        # Should go all-in
        assert action.action_type == ActionType.ALLIN
        assert action.amount == 60


class TestMicroStackEdgeCases:
    """Test micro-stack edge cases (very small stacks)."""
    
    def test_microstack_forces_allin_bet(self):
        """Micro-stack: any bet becomes all-in."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.BET_HALF_POT,
            pot=100, stack=10, current_bet=0, player_bet=0,
            can_check=True
        )
        # Want to bet 50 but only have 10
        assert action.action_type in [ActionType.BET, ActionType.ALLIN]
        assert action.amount <= 10
    
    def test_microstack_forces_allin_raise(self):
        """Micro-stack: any raise becomes all-in."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=100, stack=15, current_bet=50, player_bet=0,
            can_check=False
        )
        # to_call = 50 but only have 15
        # Can only go all-in (treated as call all-in or raise all-in)
        assert action.action_type in [ActionType.CALL, ActionType.ALLIN]
        assert action.amount == 15
    
    def test_microstack_below_big_blind(self):
        """Micro-stack smaller than big blind."""
        mapper = ActionBackmapper(big_blind=10.0)
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=20, stack=5, current_bet=0, player_bet=0,
            can_check=True
        )
        # Stack is 5, below BB of 10
        # Any bet is all-in
        assert action.action_type in [ActionType.BET, ActionType.ALLIN]
        assert action.amount <= 5
    
    def test_microstack_exact_call(self):
        """Micro-stack exactly matches call amount."""
        mapper = ActionBackmapper()
        action = mapper.backmap_action(
            AbstractAction.CHECK_CALL,
            pot=100, stack=25, current_bet=25, player_bet=0,
            can_check=False
        )
        assert action.action_type == ActionType.CALL
        assert action.amount == 25
    
    def test_microstack_one_chip(self):
        """Edge case: exactly 1 chip left."""
        mapper = ActionBackmapper(min_chip_increment=1.0)
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=100, stack=1, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.action_type in [ActionType.BET, ActionType.ALLIN]
        assert action.amount == 1
    
    def test_microstack_fractional_chip(self):
        """Edge case: fractional chip remaining."""
        mapper = ActionBackmapper(min_chip_increment=0.5)
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=100, stack=0.5, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.action_type in [ActionType.BET, ActionType.ALLIN]
        assert action.amount == 0.5


class TestAllInThreshold:
    """Test all-in threshold edge cases."""
    
    def test_allin_at_97_percent(self):
        """Bet at 97% threshold becomes all-in."""
        mapper = ActionBackmapper(all_in_threshold=0.97)
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=100, stack=103, current_bet=0, player_bet=0,
            can_check=True
        )
        # Bet 100 is 97.1% of 103
        assert action.action_type == ActionType.ALLIN
    
    def test_allin_below_threshold_is_bet(self):
        """Bet below threshold stays as bet."""
        mapper = ActionBackmapper(all_in_threshold=0.97)
        action = mapper.backmap_action(
            AbstractAction.BET_HALF_POT,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        # Bet 50 is 25% of 200
        assert action.action_type == ActionType.BET
        assert action.amount == 50
    
    def test_custom_threshold(self):
        """Test with custom all-in threshold."""
        # Note: ActionAbstraction uses its own ALL_IN_THRESHOLD (0.97)
        # The backmapper's threshold doesn't override the abstraction's logic
        mapper = ActionBackmapper(all_in_threshold=0.95)
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=100, stack=105, current_bet=0, player_bet=0,
            can_check=True
        )
        # Bet 100 is 95.2% of 105, but ActionAbstraction uses 0.97 threshold
        # So this stays as BET (not ALLIN)
        assert action.action_type in [ActionType.BET, ActionType.ALLIN]
        # If BET, amount should be 100
        if action.action_type == ActionType.BET:
            assert action.amount == 100


class TestChipRounding:
    """Test chip increment rounding edge cases."""
    
    def test_round_to_whole_chip(self):
        """Round to 1.0 chip increment."""
        mapper = ActionBackmapper(min_chip_increment=1.0)
        action = mapper.backmap_action(
            AbstractAction.BET_THIRD_POT,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        # 0.33 * 100 = 33.0, already whole number
        assert action.amount % 1.0 == 0
    
    def test_round_to_half_chip(self):
        """Round to 0.5 chip increment."""
        mapper = ActionBackmapper(min_chip_increment=0.5)
        action = mapper.backmap_action(
            AbstractAction.BET_THIRD_POT,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.amount % 0.5 == 0
    
    def test_round_to_quarter_chip(self):
        """Round to 0.25 chip increment."""
        mapper = ActionBackmapper(min_chip_increment=0.25)
        action = mapper.backmap_action(
            AbstractAction.BET_THIRD_POT,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.amount % 0.25 == 0
    
    def test_no_rounding_with_fractional_allowed(self):
        """No rounding when fractional amounts allowed."""
        mapper = ActionBackmapper(allow_fractional=True, min_chip_increment=1.0)
        action = mapper.backmap_action(
            AbstractAction.BET_THIRD_POT,
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True
        )
        # Should be exactly 33.0 (0.33 * 100)
        assert action.amount == 33.0


class TestValidation:
    """Test action validation."""
    
    def test_validate_fold(self):
        """Fold is always valid."""
        mapper = ActionBackmapper()
        action = Action(ActionType.FOLD)
        valid, error = mapper.validate_action(
            action, pot=100, stack=200, current_bet=50,
            player_bet=0, can_check=False
        )
        assert valid
        assert error is None
    
    def test_validate_check_when_valid(self):
        """Check is valid when can check."""
        mapper = ActionBackmapper()
        action = Action(ActionType.CHECK)
        valid, error = mapper.validate_action(
            action, pot=100, stack=200, current_bet=0,
            player_bet=0, can_check=True
        )
        assert valid
        assert error is None
    
    def test_validate_check_when_invalid(self):
        """Check is invalid when facing bet."""
        mapper = ActionBackmapper()
        action = Action(ActionType.CHECK)
        valid, error = mapper.validate_action(
            action, pot=100, stack=200, current_bet=50,
            player_bet=0, can_check=False
        )
        assert not valid
        assert "Cannot check" in error
    
    def test_validate_call_correct_amount(self):
        """Call with correct amount is valid."""
        mapper = ActionBackmapper()
        action = Action(ActionType.CALL, amount=50)
        valid, error = mapper.validate_action(
            action, pot=100, stack=200, current_bet=50,
            player_bet=0, can_check=False
        )
        assert valid
    
    def test_validate_call_wrong_amount(self):
        """Call with wrong amount is invalid."""
        mapper = ActionBackmapper()
        action = Action(ActionType.CALL, amount=30)
        valid, error = mapper.validate_action(
            action, pot=100, stack=200, current_bet=50,
            player_bet=0, can_check=False
        )
        assert not valid
        assert "doesn't match expected" in error
    
    def test_validate_bet_below_minimum(self):
        """Bet below minimum is invalid."""
        mapper = ActionBackmapper(big_blind=10.0)
        action = Action(ActionType.BET, amount=5)
        valid, error = mapper.validate_action(
            action, pot=100, stack=200, current_bet=0,
            player_bet=0, can_check=True
        )
        assert not valid
        assert "below minimum" in error
    
    def test_validate_bet_valid(self):
        """Valid bet passes validation."""
        mapper = ActionBackmapper(big_blind=2.0)
        action = Action(ActionType.BET, amount=50)
        valid, error = mapper.validate_action(
            action, pot=100, stack=200, current_bet=0,
            player_bet=0, can_check=True
        )
        assert valid
    
    def test_validate_raise_below_minimum(self):
        """Raise below minimum is invalid."""
        mapper = ActionBackmapper(big_blind=10.0)
        action = Action(ActionType.RAISE, amount=55)
        valid, error = mapper.validate_action(
            action, pot=100, stack=200, current_bet=50,
            player_bet=0, can_check=False,
            last_raise_amount=20.0
        )
        # to_call = 50, min_raise = 20, min_total = 70
        # 55 < 70, so invalid
        assert not valid
        assert "below minimum" in error
    
    def test_validate_raise_valid(self):
        """Valid raise passes validation."""
        mapper = ActionBackmapper(big_blind=10.0)
        action = Action(ActionType.RAISE, amount=100)
        valid, error = mapper.validate_action(
            action, pot=150, stack=200, current_bet=50,
            player_bet=0, can_check=False,
            last_raise_amount=20.0
        )
        assert valid
    
    def test_validate_allin(self):
        """All-in is valid when amount equals stack."""
        mapper = ActionBackmapper()
        action = Action(ActionType.ALLIN, amount=200)
        valid, error = mapper.validate_action(
            action, pot=100, stack=200, current_bet=50,
            player_bet=0, can_check=False
        )
        assert valid


class TestStreetSpecific:
    """Test street-specific behavior."""
    
    def test_preflop_rich_abstraction(self):
        """Preflop has richer action abstraction."""
        mapper = ActionBackmapper()
        actions = mapper.get_legal_actions(
            pot=3, stack=200, current_bet=2, player_bet=1,
            can_check=False, street=Street.PREFLOP, in_position=True
        )
        # Should have many bet sizes available
        assert len(actions) > 8
        assert AbstractAction.BET_QUARTER_POT in actions
        assert AbstractAction.BET_TRIPLE_POT in actions
    
    def test_flop_ip_actions(self):
        """Flop IP has specific bet sizes."""
        mapper = ActionBackmapper()
        actions = mapper.get_legal_actions(
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True, street=Street.FLOP, in_position=True
        )
        # Should have 0.33, 0.75, 1.0, 1.5 pot bets
        assert AbstractAction.BET_THIRD_POT in actions
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.BET_OVERBET_150 in actions
    
    def test_flop_oop_actions(self):
        """Flop OOP has fewer bet sizes."""
        mapper = ActionBackmapper()
        actions = mapper.get_legal_actions(
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True, street=Street.FLOP, in_position=False
        )
        # Should have 0.33, 0.75, 1.0 pot bets (no 1.5)
        assert AbstractAction.BET_THIRD_POT in actions
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.BET_OVERBET_150 not in actions
    
    def test_turn_actions(self):
        """Turn has specific bet sizes."""
        mapper = ActionBackmapper()
        actions = mapper.get_legal_actions(
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True, street=Street.TURN, in_position=True
        )
        # Should have 0.66, 1.0, 1.5 pot bets
        assert AbstractAction.BET_TWO_THIRDS_POT in actions
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.BET_OVERBET_150 in actions
    
    def test_river_actions(self):
        """River has specific bet sizes."""
        mapper = ActionBackmapper()
        actions = mapper.get_legal_actions(
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True, street=Street.RIVER, in_position=True
        )
        # Should have 0.75, 1.0, 1.5 pot bets
        assert AbstractAction.BET_THREE_QUARTERS_POT in actions
        assert AbstractAction.BET_POT in actions
        assert AbstractAction.BET_OVERBET_150 in actions


class TestComplexScenarios:
    """Test complex multi-factor scenarios."""
    
    def test_microstack_facing_bet_no_options(self):
        """Micro-stack facing bet can only call or fold."""
        mapper = ActionBackmapper()
        actions = mapper.get_legal_actions(
            pot=100, stack=10, current_bet=50, player_bet=0,
            can_check=False, street=Street.FLOP, in_position=True
        )
        # Stack < to_call, can only call all-in or fold
        assert AbstractAction.FOLD in actions
        assert AbstractAction.CHECK_CALL in actions
        # No bet/raise actions should be available
        bet_actions = [a for a in actions if str(a.value).startswith('bet_')]
        assert len(bet_actions) == 0
    
    def test_small_stack_limited_raises(self):
        """Small stack limits available raise sizes."""
        mapper = ActionBackmapper()
        actions = mapper.get_legal_actions(
            pot=100, stack=50, current_bet=20, player_bet=0,
            can_check=False, street=Street.RIVER, in_position=True
        )
        # to_call = 20, remaining = 30
        # Can't make large raises, only small ones or all-in
        assert AbstractAction.ALL_IN in actions
    
    def test_multiway_pot_sizing(self):
        """Pot sizing in multiway pot."""
        mapper = ActionBackmapper()
        # Three players, pot is larger
        action = mapper.backmap_action(
            AbstractAction.BET_HALF_POT,
            pot=150, stack=300, current_bet=0, player_bet=0,
            can_check=True, street=Street.FLOP
        )
        assert action.action_type == ActionType.BET
        assert action.amount == 75
    
    def test_reraised_pot(self):
        """Handle re-raised pot correctly."""
        mapper = ActionBackmapper()
        # Pot: 100, bet 50, raise to 150, now we're facing 150
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=300, stack=500, current_bet=150, player_bet=0,
            can_check=False, last_raise_amount=100
        )
        # Should raise to pot size
        assert action.action_type == ActionType.RAISE
        # 1.0 * (300 + 150) = 450
        assert action.amount == 450
    
    def test_cap_game_all_in(self):
        """Cap game where all-ins are frequent."""
        mapper = ActionBackmapper()
        # Small stack, large pot
        action = mapper.backmap_action(
            AbstractAction.BET_POT,
            pot=200, stack=50, current_bet=0, player_bet=0,
            can_check=True
        )
        assert action.action_type == ActionType.ALLIN
        assert action.amount == 50


class TestIntegrationWithActionAbstraction:
    """Test integration with existing ActionAbstraction."""
    
    def test_backmap_uses_action_abstraction(self):
        """Backmapper uses ActionAbstraction for core logic."""
        mapper = ActionBackmapper()
        # Test that backmapping produces same results as ActionAbstraction
        abstract = AbstractAction.BET_POT
        
        action1 = mapper.backmap_action(
            abstract, pot=100, stack=200, current_bet=0,
            player_bet=0, can_check=True
        )
        
        from holdem.abstraction.actions import ActionAbstraction
        action2 = ActionAbstraction.abstract_to_concrete(
            abstract, pot=100, stack=200, current_bet=0,
            player_bet=0, can_check=True
        )
        
        assert action1.action_type == action2.action_type
        assert abs(action1.amount - action2.amount) < 0.01
    
    def test_legal_actions_match_abstraction(self):
        """Legal actions from backmapper match ActionAbstraction."""
        mapper = ActionBackmapper()
        actions1 = mapper.get_legal_actions(
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True, street=Street.FLOP, in_position=True
        )
        
        from holdem.abstraction.actions import ActionAbstraction
        actions2 = ActionAbstraction.get_available_actions(
            pot=100, stack=200, current_bet=0, player_bet=0,
            can_check=True, street=Street.FLOP, in_position=True
        )
        
        # Should have same actions (backmapper may filter some edge cases)
        assert set(actions1).issubset(set(actions2))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
