"""Tests for No-Limit Texas Hold'em rules validation.

This test suite validates the centralized rules logic in holdem_rules.py,
covering action legality, bet sizing, pot consistency, and street transitions.
"""

import pytest
from holdem.game.holdem_rules import (
    ActionContext,
    BetValidation,
    is_action_legal,
    validate_bet_amount,
    check_pot_consistency,
    check_stack_consistency,
    check_folded_players_inactive,
    can_advance_to_next_street,
    get_next_street,
    suggest_corrected_action,
)
from holdem.types import ActionType, Street, PlayerState


class TestActionLegality:
    """Test action legality validation."""
    
    def test_fold_always_legal(self):
        """FOLD is always legal for active players."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        is_legal, errors = is_action_legal(ActionType.FOLD, context)
        assert is_legal
        assert len(errors) == 0
    
    def test_check_legal_no_bet(self):
        """CHECK is legal when there's no bet to call."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        is_legal, errors = is_action_legal(ActionType.CHECK, context)
        assert is_legal
        assert len(errors) == 0
    
    def test_check_illegal_with_bet(self):
        """CHECK is illegal when facing a bet."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        is_legal, errors = is_action_legal(ActionType.CHECK, context)
        assert not is_legal
        assert len(errors) > 0
        assert "cannot check" in errors[0].lower()
    
    def test_call_legal_with_bet(self):
        """CALL is legal when facing a bet."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        is_legal, errors = is_action_legal(ActionType.CALL, context)
        assert is_legal
        assert len(errors) == 0
    
    def test_call_illegal_no_bet(self):
        """CALL is illegal when there's no bet."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        is_legal, errors = is_action_legal(ActionType.CALL, context)
        assert not is_legal
        assert "cannot call" in errors[0].lower()
    
    def test_bet_legal_no_current_bet(self):
        """BET is legal when there's no current bet."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        is_legal, errors = is_action_legal(ActionType.BET, context)
        assert is_legal
        assert len(errors) == 0
    
    def test_bet_illegal_with_current_bet(self):
        """BET is illegal when there's already a bet."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        is_legal, errors = is_action_legal(ActionType.BET, context)
        assert not is_legal
        assert "cannot bet" in errors[0].lower()
    
    def test_raise_legal_with_bet(self):
        """RAISE is legal when there's a bet to raise."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        is_legal, errors = is_action_legal(ActionType.RAISE, context)
        assert is_legal
        assert len(errors) == 0
    
    def test_raise_illegal_no_bet(self):
        """RAISE is illegal when there's no bet."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        is_legal, errors = is_action_legal(ActionType.RAISE, context)
        assert not is_legal
        assert "cannot raise" in errors[0].lower()
    
    def test_allin_legal_with_chips(self):
        """ALL_IN is legal when player has chips."""
        context = ActionContext(
            player_pos=0,
            player_stack=50.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=100.0,
            big_blind=2.0,
            last_raise_amount=50.0
        )
        
        is_legal, errors = is_action_legal(ActionType.ALLIN, context)
        assert is_legal
        assert len(errors) == 0
    
    def test_folded_player_cannot_act(self):
        """Folded players cannot take actions."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=True,  # Already folded
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        is_legal, errors = is_action_legal(ActionType.CALL, context)
        assert not is_legal
        assert "already folded" in errors[0].lower()
    
    def test_allin_player_cannot_act(self):
        """All-in players cannot take further actions."""
        context = ActionContext(
            player_pos=0,
            player_stack=0.0,
            player_bet_this_round=50.0,
            player_folded=False,
            player_all_in=True,  # Already all-in
            current_bet=100.0,
            big_blind=2.0,
            last_raise_amount=50.0
        )
        
        is_legal, errors = is_action_legal(ActionType.CALL, context)
        assert not is_legal
        assert "all-in" in errors[0].lower()


class TestBetAmountValidation:
    """Test bet amount validation and correction."""
    
    def test_call_amount_correct(self):
        """CALL with correct amount is valid."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        validation = validate_bet_amount(ActionType.CALL, 10.0, context)
        assert validation.is_valid
        assert validation.corrected_amount is None
    
    def test_call_amount_adjusted_to_stack(self):
        """CALL amount is adjusted when exceeding stack."""
        context = ActionContext(
            player_pos=0,
            player_stack=5.0,  # Can only call 5
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        validation = validate_bet_amount(ActionType.CALL, 10.0, context)
        assert validation.is_valid
        assert validation.corrected_amount == 5.0
        assert len(validation.warnings) > 0
    
    def test_bet_below_minimum_invalid(self):
        """BET below minimum (not all-in) is invalid."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        validation = validate_bet_amount(ActionType.BET, 1.0, context)  # Below BB
        assert not validation.is_valid
        assert len(validation.errors) > 0
    
    def test_bet_all_in_below_minimum_allowed(self):
        """BET all-in below minimum is allowed."""
        context = ActionContext(
            player_pos=0,
            player_stack=1.0,  # All-in for 1, below BB of 2
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        validation = validate_bet_amount(ActionType.BET, 1.0, context)
        assert validation.is_valid  # All-in is allowed
    
    def test_bet_exceeds_stack_clamped(self):
        """BET exceeding stack is clamped to stack."""
        context = ActionContext(
            player_pos=0,
            player_stack=50.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        validation = validate_bet_amount(ActionType.BET, 100.0, context)
        assert validation.is_valid
        assert validation.corrected_amount == 50.0
        assert len(validation.warnings) > 0
    
    def test_raise_minimum_validation(self):
        """RAISE must meet minimum raise amount."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        # Min raise would be 10 + 10 = 20
        validation = validate_bet_amount(ActionType.RAISE, 15.0, context)
        assert not validation.is_valid
        assert len(validation.errors) > 0
    
    def test_raise_all_in_below_minimum_allowed(self):
        """RAISE all-in below minimum is allowed."""
        context = ActionContext(
            player_pos=0,
            player_stack=15.0,  # All-in for 15, below min raise of 20
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        validation = validate_bet_amount(ActionType.RAISE, 15.0, context)
        assert validation.is_valid  # All-in is allowed
    
    def test_raise_exceeds_stack_clamped(self):
        """RAISE exceeding stack is clamped to stack."""
        context = ActionContext(
            player_pos=0,
            player_stack=50.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        validation = validate_bet_amount(ActionType.RAISE, 100.0, context)
        assert validation.is_valid
        assert validation.corrected_amount == 50.0
        assert len(validation.warnings) > 0
    
    def test_allin_amount_adjusted_to_stack(self):
        """ALL_IN amount is adjusted to exact stack."""
        context = ActionContext(
            player_pos=0,
            player_stack=50.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        validation = validate_bet_amount(ActionType.ALLIN, 45.0, context)
        assert validation.is_valid
        assert validation.corrected_amount == 50.0
        assert len(validation.warnings) > 0


class TestPotAndStackConsistency:
    """Test pot and stack consistency checks."""
    
    def test_pot_consistency_valid(self):
        """Valid pot is consistent with player bets."""
        players = [
            PlayerState("P1", stack=90.0, bet_this_round=10.0),
            PlayerState("P2", stack=90.0, bet_this_round=10.0),
        ]
        
        is_consistent, warnings = check_pot_consistency(20.0, players)
        assert is_consistent
        assert len(warnings) == 0
    
    def test_pot_negative_inconsistent(self):
        """Negative pot is inconsistent."""
        players = [
            PlayerState("P1", stack=100.0, bet_this_round=0.0),
        ]
        
        is_consistent, warnings = check_pot_consistency(-10.0, players)
        assert not is_consistent
        assert len(warnings) > 0
    
    def test_pot_less_than_bets_inconsistent(self):
        """Pot less than current bets is inconsistent."""
        players = [
            PlayerState("P1", stack=90.0, bet_this_round=10.0),
            PlayerState("P2", stack=90.0, bet_this_round=10.0),
        ]
        
        is_consistent, warnings = check_pot_consistency(5.0, players, tolerance=0.1)
        assert not is_consistent
        assert len(warnings) > 0
    
    def test_pot_accumulates_across_streets(self):
        """Pot can be larger than current round bets (accumulates)."""
        players = [
            PlayerState("P1", stack=90.0, bet_this_round=5.0),
            PlayerState("P2", stack=90.0, bet_this_round=5.0),
        ]
        
        # Pot is 30 but current bets only 10 (previous streets contributed)
        is_consistent, warnings = check_pot_consistency(30.0, players)
        assert is_consistent
        assert len(warnings) == 0
    
    def test_stack_consistency_valid(self):
        """All stacks are valid and non-negative."""
        players = [
            PlayerState("P1", stack=100.0, bet_this_round=10.0),
            PlayerState("P2", stack=50.0, bet_this_round=20.0),
        ]
        
        is_valid, errors = check_stack_consistency(players)
        assert is_valid
        assert len(errors) == 0
    
    def test_stack_negative_invalid(self):
        """Negative stack is invalid."""
        players = [
            PlayerState("P1", stack=-10.0, bet_this_round=0.0),
        ]
        
        is_valid, errors = check_stack_consistency(players)
        assert not is_valid
        assert len(errors) > 0
    
    def test_bet_negative_invalid(self):
        """Negative bet is invalid."""
        players = [
            PlayerState("P1", stack=100.0, bet_this_round=-5.0),
        ]
        
        is_valid, errors = check_stack_consistency(players)
        assert not is_valid
        assert len(errors) > 0


class TestFoldedPlayersInactive:
    """Test that folded players are properly inactive."""
    
    def test_folded_players_marked_acted(self):
        """Folded players should be marked as acted."""
        players = [
            PlayerState("P1", stack=100.0, folded=True),
            PlayerState("P2", stack=100.0, folded=False),
        ]
        players_acted = [True, False]
        
        is_consistent, warnings = check_folded_players_inactive(players, players_acted)
        assert is_consistent
        assert len(warnings) == 0
    
    def test_folded_player_not_acted_inconsistent(self):
        """Folded player marked as not acted is inconsistent."""
        players = [
            PlayerState("P1", stack=100.0, folded=True),
            PlayerState("P2", stack=100.0, folded=False),
        ]
        players_acted = [False, False]  # P1 folded but marked as not acted
        
        is_consistent, warnings = check_folded_players_inactive(players, players_acted)
        assert not is_consistent
        assert len(warnings) > 0


class TestStreetAdvancement:
    """Test street advancement logic."""
    
    def test_can_advance_only_one_player(self):
        """Can advance when only one player remains."""
        players = [
            PlayerState("P1", stack=100.0, folded=False, bet_this_round=10.0),
            PlayerState("P2", stack=100.0, folded=True, bet_this_round=5.0),
        ]
        players_acted = [True, True]
        
        can_advance, reason = can_advance_to_next_street(players, players_acted, 10.0)
        assert can_advance
        assert "one player" in reason.lower()
    
    def test_can_advance_all_acted_bets_equal(self):
        """Can advance when all acted and bets are equal."""
        players = [
            PlayerState("P1", stack=90.0, folded=False, bet_this_round=10.0),
            PlayerState("P2", stack=90.0, folded=False, bet_this_round=10.0),
        ]
        players_acted = [True, True]
        
        can_advance, reason = can_advance_to_next_street(players, players_acted, 10.0)
        assert can_advance
        assert "equalized" in reason.lower()
    
    def test_cannot_advance_player_not_acted(self):
        """Cannot advance when a player hasn't acted."""
        players = [
            PlayerState("P1", stack=90.0, folded=False, bet_this_round=10.0),
            PlayerState("P2", stack=100.0, folded=False, bet_this_round=0.0),
        ]
        players_acted = [True, False]  # P2 hasn't acted
        
        can_advance, reason = can_advance_to_next_street(players, players_acted, 10.0)
        assert not can_advance
        assert "not acted" in reason.lower()
    
    def test_cannot_advance_unequal_bets(self):
        """Cannot advance when bets are unequal."""
        players = [
            PlayerState("P1", stack=90.0, folded=False, bet_this_round=10.0),
            PlayerState("P2", stack=95.0, folded=False, bet_this_round=5.0),
        ]
        players_acted = [True, True]
        
        can_advance, reason = can_advance_to_next_street(players, players_acted, 10.0)
        assert not can_advance
        assert "doesn't match" in reason.lower()
    
    def test_can_advance_with_allin_players(self):
        """Can advance when active players have equal bets, even with all-ins."""
        players = [
            PlayerState("P1", stack=90.0, folded=False, all_in=False, bet_this_round=10.0),
            PlayerState("P2", stack=0.0, folded=False, all_in=True, bet_this_round=5.0),
        ]
        players_acted = [True, True]
        
        # P2 is all-in with less, P1 matched what they can
        can_advance, reason = can_advance_to_next_street(players, players_acted, 10.0)
        assert can_advance
    
    def test_get_next_street_sequence(self):
        """Test street progression sequence."""
        assert get_next_street(Street.PREFLOP) == Street.FLOP
        assert get_next_street(Street.FLOP) == Street.TURN
        assert get_next_street(Street.TURN) == Street.RIVER
        assert get_next_street(Street.RIVER) is None  # Hand over


class TestActionSuggestions:
    """Test action correction suggestions."""
    
    def test_suggest_call_for_illegal_check(self):
        """Suggest CALL when CHECK is illegal with a bet."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        suggestion = suggest_corrected_action(ActionType.CHECK, context)
        assert suggestion == ActionType.CALL
    
    def test_suggest_check_for_illegal_call(self):
        """Suggest CHECK when CALL is illegal with no bet."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        suggestion = suggest_corrected_action(ActionType.CALL, context)
        assert suggestion == ActionType.CHECK
    
    def test_suggest_raise_for_illegal_bet(self):
        """Suggest RAISE when BET is illegal with existing bet."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=10.0
        )
        
        suggestion = suggest_corrected_action(ActionType.BET, context)
        assert suggestion == ActionType.RAISE
    
    def test_suggest_bet_for_illegal_raise(self):
        """Suggest BET when RAISE is illegal with no bet."""
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        suggestion = suggest_corrected_action(ActionType.RAISE, context)
        assert suggestion == ActionType.BET


class TestComplexScenarios:
    """Test complex game scenarios."""
    
    def test_open_raise_scenario(self):
        """Test open-raise (first bet on the street)."""
        # Player wants to bet 10 (open-raise)
        context = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        # Action should be BET, not RAISE
        is_legal, _ = is_action_legal(ActionType.BET, context)
        assert is_legal
        
        validation = validate_bet_amount(ActionType.BET, 10.0, context)
        assert validation.is_valid
    
    def test_three_bet_scenario(self):
        """Test 3-bet scenario (re-raise)."""
        # Initial raise to 10, now player wants to 3-bet to 30
        context = ActionContext(
            player_pos=1,
            player_stack=100.0,
            player_bet_this_round=2.0,  # Posted BB
            player_folded=False,
            player_all_in=False,
            current_bet=10.0,
            big_blind=2.0,
            last_raise_amount=8.0  # Raise was from 2 to 10
        )
        
        is_legal, _ = is_action_legal(ActionType.RAISE, context)
        assert is_legal
        
        # Min 3-bet would be 10 + 8 = 18
        validation = validate_bet_amount(ActionType.RAISE, 18.0, context)
        assert validation.is_valid
        
        # 3-bet to 30 is also valid
        validation = validate_bet_amount(ActionType.RAISE, 30.0, context)
        assert validation.is_valid
    
    def test_check_check_scenario(self):
        """Test check-check scenario (both players check)."""
        # First player checks
        context1 = ActionContext(
            player_pos=0,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        is_legal, _ = is_action_legal(ActionType.CHECK, context1)
        assert is_legal
        
        # Second player can also check
        context2 = ActionContext(
            player_pos=1,
            player_stack=100.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=0.0,
            big_blind=2.0,
            last_raise_amount=0.0
        )
        
        is_legal, _ = is_action_legal(ActionType.CHECK, context2)
        assert is_legal
        
        # After both check, can advance street
        players = [
            PlayerState("P1", stack=100.0, folded=False, bet_this_round=0.0),
            PlayerState("P2", stack=100.0, folded=False, bet_this_round=0.0),
        ]
        players_acted = [True, True]
        
        can_advance, _ = can_advance_to_next_street(players, players_acted, 0.0)
        assert can_advance
    
    def test_all_in_scenario(self):
        """Test all-in scenario."""
        # Player has 50, facing bet of 100
        context = ActionContext(
            player_pos=0,
            player_stack=50.0,
            player_bet_this_round=0.0,
            player_folded=False,
            player_all_in=False,
            current_bet=100.0,
            big_blind=2.0,
            last_raise_amount=100.0
        )
        
        # Can only call 50 (all-in)
        validation = validate_bet_amount(ActionType.CALL, 100.0, context)
        assert validation.is_valid
        assert validation.corrected_amount == 50.0
        
        # Can go all-in
        is_legal, _ = is_action_legal(ActionType.ALLIN, context)
        assert is_legal
        
        validation = validate_bet_amount(ActionType.ALLIN, 50.0, context)
        assert validation.is_valid
    
    def test_everyone_folds_except_one(self):
        """Test scenario where everyone folds except one player."""
        players = [
            PlayerState("P1", stack=95.0, folded=False, bet_this_round=5.0),
            PlayerState("P2", stack=100.0, folded=True, bet_this_round=0.0),
            PlayerState("P3", stack=100.0, folded=True, bet_this_round=0.0),
        ]
        players_acted = [True, True, True]
        
        # Hand is over, can "advance" (or award pot)
        can_advance, reason = can_advance_to_next_street(players, players_acted, 5.0)
        assert can_advance
        assert "one player" in reason.lower()
