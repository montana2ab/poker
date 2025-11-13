"""Centralized No-Limit Texas Hold'em rules validation module.

This module provides utilities for validating actions, bets, and game state
according to standard No-Limit Texas Hold'em rules. It ensures:
- Legal action validation in context
- Bet consistency checking
- Pot accounting validation
- Street transition rules
- Stack management

All functions are pure and testable, making this a robust foundation for
game logic in both training and real-time play.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass, field
import logging

from holdem.types import ActionType, Street, PlayerState

logger = logging.getLogger(__name__)


@dataclass
class ActionContext:
    """Context information needed to validate an action."""
    player_pos: int
    player_stack: float
    player_bet_this_round: float
    player_folded: bool
    player_all_in: bool
    current_bet: float
    big_blind: float
    last_raise_amount: float
    
    def to_call(self) -> float:
        """Calculate amount needed to call."""
        return max(0.0, self.current_bet - self.player_bet_this_round)


@dataclass
class BetValidation:
    """Result of bet amount validation."""
    is_valid: bool
    corrected_amount: Optional[float] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def is_action_legal(
    action: ActionType,
    context: ActionContext
) -> Tuple[bool, List[str]]:
    """Check if an action is legal in the given context.
    
    Args:
        action: The action type to validate
        context: The action context with player and game state
        
    Returns:
        Tuple of (is_legal, list of error messages)
    """
    errors = []
    
    # Folded players cannot act
    if context.player_folded:
        errors.append("Cannot act - player has already folded")
        return False, errors
    
    # All-in players cannot act (unless they can still make decisions)
    if context.player_all_in:
        errors.append("Cannot act - player is all-in")
        return False, errors
    
    to_call = context.to_call()
    
    # FOLD is always legal (if player hasn't already folded)
    if action == ActionType.FOLD:
        return True, []
    
    # CHECK is only legal when there's no bet to call
    if action == ActionType.CHECK:
        if to_call > 0.01:  # Small epsilon for floating point
            errors.append(f"Cannot CHECK when facing a bet of {to_call:.2f} - must CALL, RAISE, or FOLD")
            return False, errors
        return True, []
    
    # CALL is only legal when there's a bet to call
    if action == ActionType.CALL:
        if to_call < 0.01:
            errors.append("Cannot CALL when there's no bet - use CHECK instead")
            return False, errors
        return True, []
    
    # BET is only legal when there's no current bet
    if action == ActionType.BET:
        if context.current_bet > 0.01:
            errors.append(f"Cannot BET when there's already a bet of {context.current_bet:.2f} - use RAISE instead")
            return False, errors
        return True, []
    
    # RAISE is only legal when there's a bet to raise
    if action == ActionType.RAISE:
        if context.current_bet < 0.01:
            errors.append("Cannot RAISE when there's no bet - use BET instead")
            return False, errors
        return True, []
    
    # ALL_IN is always legal (if player has chips)
    if action == ActionType.ALLIN:
        if context.player_stack < 0.01:
            errors.append("Cannot go ALL_IN with no chips remaining")
            return False, errors
        return True, []
    
    # Unknown action
    errors.append(f"Unknown action type: {action}")
    return False, errors


def validate_bet_amount(
    action: ActionType,
    amount: float,
    context: ActionContext
) -> BetValidation:
    """Validate and potentially correct a bet amount.
    
    Args:
        action: The action type
        amount: The proposed bet/raise amount
        context: The action context
        
    Returns:
        BetValidation with validity, corrections, and messages
    """
    errors = []
    warnings = []
    corrected_amount = None
    
    # FOLD, CHECK don't require amount validation
    if action in [ActionType.FOLD, ActionType.CHECK]:
        return BetValidation(is_valid=True)
    
    to_call = context.to_call()
    
    # Validate CALL amount
    if action == ActionType.CALL:
        expected_call = min(to_call, context.player_stack)
        if abs(amount - expected_call) > 0.01:
            warnings.append(
                f"CALL amount {amount:.2f} adjusted to {expected_call:.2f} "
                f"(to_call={to_call:.2f}, stack={context.player_stack:.2f})"
            )
            corrected_amount = expected_call
        return BetValidation(is_valid=True, corrected_amount=corrected_amount, warnings=warnings)
    
    # Validate BET amount
    if action == ActionType.BET:
        min_bet = context.big_blind
        
        # Check if amount exceeds stack
        if amount > context.player_stack + 0.01:
            errors.append(
                f"BET amount {amount:.2f} exceeds stack {context.player_stack:.2f}"
            )
            corrected_amount = context.player_stack
            warnings.append(f"BET amount clamped to stack: {corrected_amount:.2f}")
            # Allow with correction
            return BetValidation(
                is_valid=True,
                corrected_amount=corrected_amount,
                warnings=warnings
            )
        
        # Check minimum bet (but allow all-in below minimum)
        if amount < min_bet - 0.01 and amount < context.player_stack - 0.01:
            errors.append(
                f"BET amount {amount:.2f} is below minimum {min_bet:.2f} and not an all-in"
            )
            return BetValidation(is_valid=False, errors=errors)
        
        return BetValidation(is_valid=True)
    
    # Validate RAISE amount
    if action == ActionType.RAISE:
        # Calculate minimum raise
        if context.last_raise_amount > 0.01:
            min_raise = context.current_bet + context.last_raise_amount
        else:
            # First raise on this street
            min_raise = context.current_bet + context.big_blind
        
        # Check if amount exceeds stack
        if amount > context.player_stack + 0.01:
            errors.append(
                f"RAISE to {amount:.2f} exceeds stack {context.player_stack:.2f}"
            )
            corrected_amount = context.player_stack
            warnings.append(f"RAISE amount clamped to stack: {corrected_amount:.2f}")
            return BetValidation(
                is_valid=True,
                corrected_amount=corrected_amount,
                warnings=warnings
            )
        
        # Check minimum raise (but allow all-in below minimum)
        if amount < min_raise - 0.01 and amount < context.player_stack - 0.01:
            errors.append(
                f"RAISE to {amount:.2f} is below minimum {min_raise:.2f} and not an all-in"
            )
            return BetValidation(is_valid=False, errors=errors)
        
        return BetValidation(is_valid=True)
    
    # Validate ALL_IN amount
    if action == ActionType.ALLIN:
        # All-in should be player's entire stack
        if abs(amount - context.player_stack) > 0.01:
            warnings.append(
                f"ALL_IN amount {amount:.2f} adjusted to full stack {context.player_stack:.2f}"
            )
            corrected_amount = context.player_stack
        return BetValidation(is_valid=True, corrected_amount=corrected_amount, warnings=warnings)
    
    # Unknown action
    return BetValidation(is_valid=False, errors=[f"Unknown action type: {action}"])


def check_pot_consistency(
    pot: float,
    players: List[PlayerState],
    tolerance: float = 0.1
) -> Tuple[bool, List[str]]:
    """Check if pot is consistent with player bets this round.
    
    Note: This is a consistency check, not an exact equality, because:
    - Pot accumulates across streets
    - Side pots may exist
    - Rounding errors can occur
    
    Args:
        pot: Current pot size
        players: List of player states
        tolerance: Tolerance for pot discrepancy
        
    Returns:
        Tuple of (is_consistent, list of warnings)
    """
    warnings = []
    
    if pot < 0:
        warnings.append(f"Pot is negative: {pot:.2f}")
        return False, warnings
    
    # Calculate total bets this round
    total_bets_this_round = sum(p.bet_this_round for p in players)
    
    # Pot should be >= total bets this round (it accumulates)
    # But if it's much less, something is wrong
    if pot < total_bets_this_round - tolerance:
        warnings.append(
            f"Pot ({pot:.2f}) is less than current round bets ({total_bets_this_round:.2f})"
        )
        return False, warnings
    
    return True, []


def check_stack_consistency(players: List[PlayerState]) -> Tuple[bool, List[str]]:
    """Check if all player stacks are valid.
    
    Args:
        players: List of player states
        
    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors = []
    
    for i, player in enumerate(players):
        if player.stack < -0.01:  # Allow tiny negative due to floating point
            errors.append(
                f"Player {i} ({player.name}) has negative stack: {player.stack:.2f}"
            )
        
        if player.bet_this_round < -0.01:
            errors.append(
                f"Player {i} ({player.name}) has negative bet: {player.bet_this_round:.2f}"
            )
        
        # Check if bet exceeds original stack (should be impossible)
        # We can't check this without knowing original stack, so we skip
    
    is_valid = len(errors) == 0
    return is_valid, errors


def check_folded_players_inactive(
    players: List[PlayerState],
    players_acted: List[bool]
) -> Tuple[bool, List[str]]:
    """Check that folded players are not marked as needing to act.
    
    Args:
        players: List of player states
        players_acted: List indicating which players have acted
        
    Returns:
        Tuple of (is_consistent, list of warnings)
    """
    warnings = []
    
    for i, player in enumerate(players):
        if player.folded and not players_acted[i]:
            warnings.append(
                f"Player {i} ({player.name}) is folded but marked as not acted"
            )
    
    is_consistent = len(warnings) == 0
    return is_consistent, warnings


def can_advance_to_next_street(
    players: List[PlayerState],
    players_acted: List[bool],
    current_bet: float
) -> Tuple[bool, Optional[str]]:
    """Determine if betting round is complete and can advance to next street.
    
    A betting round is complete when:
    1. Only one player remains (others folded), OR
    2. All active players have acted AND all bets are equalized
    
    Args:
        players: List of player states
        players_acted: List indicating which players have acted
        current_bet: Current bet for this round
        
    Returns:
        Tuple of (can_advance, reason)
    """
    active_players = [i for i, p in enumerate(players) if not p.folded]
    
    # Only one player left - hand is over
    if len(active_players) <= 1:
        return True, "Only one player remains"
    
    # Check if all active players have acted
    for pos in active_players:
        if not players_acted[pos]:
            return False, f"Player {pos} has not acted yet"
    
    # Check if all bets are equalized (considering all-ins)
    non_allin_active = [
        p for p in players
        if not p.folded and not p.all_in
    ]
    
    if non_allin_active:
        # All non-all-in players must have matching bets
        for player in non_allin_active:
            if abs(player.bet_this_round - current_bet) > 0.01:
                return False, f"Player {player.name} bet ({player.bet_this_round:.2f}) doesn't match current bet ({current_bet:.2f})"
    
    return True, "All players acted and bets equalized"


def get_next_street(current_street: Street) -> Optional[Street]:
    """Get the next street in sequence.
    
    Args:
        current_street: Current street
        
    Returns:
        Next street, or None if hand is complete (after RIVER)
    """
    if current_street == Street.PREFLOP:
        return Street.FLOP
    elif current_street == Street.FLOP:
        return Street.TURN
    elif current_street == Street.TURN:
        return Street.RIVER
    elif current_street == Street.RIVER:
        return None  # Hand is over
    
    return None


def suggest_corrected_action(
    action: ActionType,
    context: ActionContext
) -> Optional[ActionType]:
    """Suggest a corrected action when the proposed action is illegal.
    
    Args:
        action: The illegal action
        context: The action context
        
    Returns:
        Suggested corrected action, or None if no clear correction
    """
    to_call = context.to_call()
    
    if action == ActionType.CHECK and to_call > 0.01:
        # Tried to check with a bet - suggest call
        return ActionType.CALL
    
    if action == ActionType.CALL and to_call < 0.01:
        # Tried to call with no bet - suggest check
        return ActionType.CHECK
    
    if action == ActionType.BET and context.current_bet > 0.01:
        # Tried to bet when there's already a bet - suggest raise
        return ActionType.RAISE
    
    if action == ActionType.RAISE and context.current_bet < 0.01:
        # Tried to raise with no bet - suggest bet
        return ActionType.BET
    
    return None
