"""Texas Hold'em game state machine with strict No-Limit rules enforcement.

This module implements a state machine for 2-6 player No-Limit Texas Hold'em
that enforces proper game rules, action validation, and state transitions.
Inspired by Pluribus-level rigor for consistent game state management.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum
import logging

from holdem.types import ActionType, Street, TableState
from holdem.game import holdem_rules

logger = logging.getLogger(__name__)


class BettingRoundState(Enum):
    """State of the current betting round."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


@dataclass
class GameStateValidation:
    """Validation result for game state."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ActionValidation:
    """Validation result for a player action."""
    is_legal: bool
    errors: List[str] = field(default_factory=list)
    suggested_action: Optional[ActionType] = None
    min_raise: Optional[float] = None
    max_raise: Optional[float] = None


class TexasHoldemStateMachine:
    """State machine for Texas Hold'em game logic.
    
    Manages:
    - Button position and speaking order
    - Blind posting (SB, BB)
    - Action validation (legal moves, bet sizing)
    - Street transitions
    - Pot and stack consistency checks
    - Multi-player support (2-6 players)
    """
    
    def __init__(
        self,
        num_players: int,
        small_blind: float = 1.0,
        big_blind: float = 2.0,
        button_position: int = 0
    ):
        """Initialize the state machine.
        
        Args:
            num_players: Number of players (2-6)
            small_blind: Small blind amount
            big_blind: Big blind amount
            button_position: Dealer button position (0-indexed)
        """
        if not 2 <= num_players <= 6:
            raise ValueError(f"num_players must be 2-6, got {num_players}")
        
        self.num_players = num_players
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.button_position = button_position
        
        # Track betting round state
        self.current_street = Street.PREFLOP
        self.betting_round_state = BettingRoundState.NOT_STARTED
        self.current_bet = 0.0
        self.last_raise_amount = 0.0  # Track last raise for min-raise calculation
        self.players_acted: List[bool] = [False] * num_players
        self.action_reopened = False  # True when a raise reopens action
        
    def get_button_position(self) -> int:
        """Get the current button position."""
        return self.button_position
    
    def get_small_blind_position(self) -> int:
        """Get the small blind position."""
        if self.num_players == 2:
            # Heads-up: button is also small blind
            return self.button_position
        else:
            # Multi-way: SB is one position after button
            return (self.button_position + 1) % self.num_players
    
    def get_big_blind_position(self) -> int:
        """Get the big blind position."""
        if self.num_players == 2:
            # Heads-up: big blind is opposite of button
            return (self.button_position + 1) % self.num_players
        else:
            # Multi-way: BB is two positions after button
            return (self.button_position + 2) % self.num_players
    
    def get_speaking_order_preflop(self, active_players: List[bool]) -> List[int]:
        """Get speaking order for preflop.
        
        Args:
            active_players: List indicating which players are still in hand
            
        Returns:
            List of player positions in speaking order
        """
        order = []
        
        if self.num_players == 2:
            # Heads-up preflop: SB (button) acts first, then BB
            start_pos = self.button_position
        else:
            # Multi-way preflop: first to act is UTG (after BB)
            start_pos = (self.button_position + 3) % self.num_players
        
        # Build order from start position
        for i in range(self.num_players):
            pos = (start_pos + i) % self.num_players
            if active_players[pos]:
                order.append(pos)
        
        return order
    
    def get_speaking_order_postflop(self, active_players: List[bool]) -> List[int]:
        """Get speaking order for postflop streets.
        
        Args:
            active_players: List indicating which players are still in hand
            
        Returns:
            List of player positions in speaking order
        """
        order = []
        
        # Postflop: first active player after button speaks first
        start_pos = (self.button_position + 1) % self.num_players
        
        for i in range(self.num_players):
            pos = (start_pos + i) % self.num_players
            if active_players[pos]:
                order.append(pos)
        
        return order
    
    def get_speaking_order(self, street: Street, active_players: List[bool]) -> List[int]:
        """Get speaking order for the given street.
        
        Args:
            street: Current street
            active_players: List indicating which players are still in hand
            
        Returns:
            List of player positions in speaking order
        """
        if street == Street.PREFLOP:
            return self.get_speaking_order_preflop(active_players)
        else:
            return self.get_speaking_order_postflop(active_players)
    
    def validate_action(
        self,
        player_pos: int,
        action: ActionType,
        amount: float,
        player_stack: float,
        player_bet_this_round: float,
        current_bet: float
    ) -> ActionValidation:
        """Validate if an action is legal.
        
        Args:
            player_pos: Player position
            action: Action type to validate
            amount: Action amount (for bet/raise/call)
            player_stack: Player's current stack
            player_bet_this_round: Player's bet so far this round
            current_bet: Highest bet this round
            
        Returns:
            ActionValidation with legality and details
        """
        errors = []
        to_call = current_bet - player_bet_this_round
        
        # Validate FOLD
        if action == ActionType.FOLD:
            # Fold is always legal
            return ActionValidation(is_legal=True)
        
        # Validate CHECK
        if action == ActionType.CHECK:
            if to_call > 0.01:  # Small epsilon for floating point
                errors.append(f"Cannot check when facing a bet of {to_call:.2f}")
                return ActionValidation(
                    is_legal=False,
                    errors=errors,
                    suggested_action=ActionType.CALL
                )
            return ActionValidation(is_legal=True)
        
        # Validate CALL
        if action == ActionType.CALL:
            if to_call < 0.01:
                errors.append("Cannot call when there's no bet to call")
                return ActionValidation(
                    is_legal=False,
                    errors=errors,
                    suggested_action=ActionType.CHECK
                )
            if amount < to_call - 0.01 and amount < player_stack - 0.01:
                errors.append(f"Call amount {amount:.2f} is less than required {to_call:.2f}")
                return ActionValidation(is_legal=False, errors=errors)
            return ActionValidation(is_legal=True)
        
        # Validate BET
        if action == ActionType.BET:
            if current_bet > 0.01:
                errors.append(f"Cannot bet when there's already a bet of {current_bet:.2f}")
                return ActionValidation(
                    is_legal=False,
                    errors=errors,
                    suggested_action=ActionType.RAISE
                )
            
            # Check minimum bet (usually BB)
            min_bet = self.big_blind
            if amount < min_bet - 0.01 and amount < player_stack - 0.01:
                errors.append(f"Bet {amount:.2f} is below minimum {min_bet:.2f}")
                return ActionValidation(is_legal=False, errors=errors, min_raise=min_bet)
            
            if amount > player_stack + 0.01:
                errors.append(f"Bet {amount:.2f} exceeds stack {player_stack:.2f}")
                return ActionValidation(is_legal=False, errors=errors)
            
            return ActionValidation(is_legal=True)
        
        # Validate RAISE
        if action == ActionType.RAISE:
            if current_bet < 0.01:
                errors.append("Cannot raise when there's no bet to raise")
                return ActionValidation(
                    is_legal=False,
                    errors=errors,
                    suggested_action=ActionType.BET
                )
            
            # Calculate minimum raise
            # Min raise = current bet + (current bet - previous bet)
            # If no previous raise, min raise = current bet + big blind
            if self.last_raise_amount > 0.01:
                min_raise_amount = current_bet + self.last_raise_amount
            else:
                min_raise_amount = current_bet + self.big_blind
            
            total_to_put_in = amount
            
            # Check if it's actually an all-in below min raise (allowed)
            if total_to_put_in < min_raise_amount - 0.01:
                if total_to_put_in >= player_stack - 0.01:
                    # All-in below min raise is allowed
                    return ActionValidation(is_legal=True)
                else:
                    errors.append(
                        f"Raise to {total_to_put_in:.2f} is below minimum {min_raise_amount:.2f}"
                    )
                    return ActionValidation(
                        is_legal=False,
                        errors=errors,
                        min_raise=min_raise_amount,
                        max_raise=player_stack
                    )
            
            if total_to_put_in > player_stack + 0.01:
                errors.append(f"Raise to {total_to_put_in:.2f} exceeds stack {player_stack:.2f}")
                return ActionValidation(is_legal=False, errors=errors)
            
            return ActionValidation(is_legal=True, min_raise=min_raise_amount)
        
        # Validate ALL-IN
        if action == ActionType.ALLIN:
            if player_stack < 0.01:
                errors.append("Cannot go all-in with no stack")
                return ActionValidation(is_legal=False, errors=errors)
            # All-in is always legal if you have chips
            return ActionValidation(is_legal=True)
        
        # Unknown action
        errors.append(f"Unknown action type: {action}")
        return ActionValidation(is_legal=False, errors=errors)
    
    def process_action(
        self,
        player_pos: int,
        action: ActionType,
        amount: float,
        state: TableState
    ) -> Tuple[bool, List[str]]:
        """Process a player action and update internal state.
        
        Uses centralized rules validation with graceful handling:
        - Illegal actions generate WARNINGs
        - Invalid amounts are clamped/corrected when possible
        - Folded players cannot act (enforced)
        
        Args:
            player_pos: Player position
            action: Action type
            amount: Action amount
            state: Current table state
            
        Returns:
            Tuple of (success, list of messages)
        """
        messages = []
        
        if player_pos >= len(state.players):
            return False, [f"Invalid player position {player_pos}"]
        
        player = state.players[player_pos]
        
        # Create context for rules validation
        context = holdem_rules.ActionContext(
            player_pos=player_pos,
            player_stack=player.stack,
            player_bet_this_round=player.bet_this_round,
            player_folded=player.folded,
            player_all_in=player.all_in,
            current_bet=state.current_bet,
            big_blind=self.big_blind,
            last_raise_amount=self.last_raise_amount
        )
        
        # Check action legality using centralized rules
        is_legal, errors = holdem_rules.is_action_legal(action, context)
        
        if not is_legal:
            # Log warning and try to suggest correction
            logger.warning(f"Illegal action attempted: {action} by player {player_pos} ({player.name})")
            for error in errors:
                logger.warning(f"  - {error}")
            
            # Try to suggest a corrected action
            suggested = holdem_rules.suggest_corrected_action(action, context)
            if suggested:
                logger.warning(f"  Suggested correction: {suggested}")
                messages.append(
                    f"WARNING: {action} is illegal - suggested action: {suggested}. Errors: {'; '.join(errors)}"
                )
            else:
                messages.append(f"WARNING: {action} is illegal. Errors: {'; '.join(errors)}")
            
            return False, messages
        
        # Validate and potentially correct bet amount
        bet_validation = holdem_rules.validate_bet_amount(action, amount, context)
        
        if not bet_validation.is_valid:
            logger.warning(
                f"Invalid bet amount {amount:.2f} for action {action} by player {player_pos} ({player.name})"
            )
            for error in bet_validation.errors:
                logger.warning(f"  - {error}")
            messages.append(f"WARNING: Invalid bet amount. Errors: {'; '.join(bet_validation.errors)}")
            return False, messages
        
        # Apply corrections if any
        corrected_amount = amount
        if bet_validation.corrected_amount is not None:
            corrected_amount = bet_validation.corrected_amount
            logger.warning(
                f"Bet amount corrected from {amount:.2f} to {corrected_amount:.2f} for player {player_pos} ({player.name})"
            )
            for warning in bet_validation.warnings:
                logger.warning(f"  - {warning}")
            messages.append(f"Amount corrected: {amount:.2f} -> {corrected_amount:.2f}")
        
        # Log any warnings from bet validation
        for warning in bet_validation.warnings:
            if bet_validation.corrected_amount is None:
                logger.warning(f"Bet validation warning: {warning}")
        
        # Mark player as having acted
        self.players_acted[player_pos] = True
        
        # Process the action with corrected amount
        if action == ActionType.FOLD:
            messages.append(f"Player {player_pos} ({player.name}) folds")
            
        elif action == ActionType.CHECK:
            messages.append(f"Player {player_pos} ({player.name}) checks")
            
        elif action == ActionType.CALL:
            messages.append(
                f"Player {player_pos} ({player.name}) calls {corrected_amount:.2f}"
            )
            
        elif action == ActionType.BET:
            # Update current bet and last raise
            self.current_bet = corrected_amount
            self.last_raise_amount = corrected_amount
            self.action_reopened = True
            # Reset players_acted for players after this one
            self._reopen_action(player_pos)
            messages.append(f"Player {player_pos} ({player.name}) bets {corrected_amount:.2f}")
            
        elif action == ActionType.RAISE:
            # Update last raise amount
            raise_by = corrected_amount - state.current_bet
            self.last_raise_amount = raise_by
            self.current_bet = corrected_amount
            self.action_reopened = True
            # Reset players_acted for players after this one
            self._reopen_action(player_pos)
            messages.append(
                f"Player {player_pos} ({player.name}) raises to {corrected_amount:.2f}"
            )
            
        elif action == ActionType.ALLIN:
            # Determine if this reopens action
            if corrected_amount > state.current_bet:
                raise_by = corrected_amount - state.current_bet
                # If this is the first bet/raise on the street, require minimum bet (big blind)
                if self.last_raise_amount == 0:
                    min_raise = self.big_blind
                    if raise_by >= min_raise:
                        self.action_reopened = True
                        self.last_raise_amount = raise_by
                        self._reopen_action(player_pos)
                else:
                    if raise_by >= self.last_raise_amount:
                        self.action_reopened = True
                        self.last_raise_amount = raise_by
                        self._reopen_action(player_pos)
            self.current_bet = max(self.current_bet, corrected_amount)
            messages.append(
                f"Player {player_pos} ({player.name}) goes all-in for {corrected_amount:.2f}"
            )
        
        return True, messages
    
    def _reopen_action(self, raiser_pos: int):
        """Reopen action for players who already acted before a raise.
        
        Args:
            raiser_pos: Position of player who raised
        """
        # All players except raiser need to act again
        for i in range(self.num_players):
            if i != raiser_pos:
                self.players_acted[i] = False
    
    def is_betting_round_complete(
        self,
        state: TableState
    ) -> bool:
        """Check if the current betting round is complete using centralized rules.
        
        A betting round is complete when:
        - All active players have acted
        - All bets are equalized (or players are all-in)
        - Or only one player remains
        
        Args:
            state: Current table state
            
        Returns:
            True if betting round is complete
        """
        can_advance, reason = holdem_rules.can_advance_to_next_street(
            state.players, self.players_acted, state.current_bet
        )
        
        if not can_advance:
            logger.debug(f"Betting round incomplete: {reason}")
        else:
            logger.debug(f"Betting round complete: {reason}")
        
        return can_advance
    
    def can_advance_street(self, state: TableState) -> bool:
        """Check if we can advance to the next street.
        
        Args:
            state: Current table state
            
        Returns:
            True if ready to advance street
        """
        return self.is_betting_round_complete(state)
    
    def advance_street(self, state: TableState) -> Optional[Street]:
        """Advance to the next street using centralized rules.
        
        Args:
            state: Current table state
            
        Returns:
            Next street, or None if hand is over
        """
        if not self.can_advance_street(state):
            logger.warning("Cannot advance street - betting round not complete")
            return None
        
        # Reset betting round state
        self.current_bet = 0.0
        self.last_raise_amount = 0.0
        self.players_acted = [False] * self.num_players
        self.action_reopened = False
        
        # Use centralized rule for next street
        next_street = holdem_rules.get_next_street(state.street)
        if next_street:
            self.current_street = next_street
            logger.info(f"Advanced from {state.street} to {next_street}")
        else:
            logger.info(f"Hand complete after {state.street}")
        
        return next_street
    
    def validate_state(self, state: TableState) -> GameStateValidation:
        """Validate table state for consistency using centralized rules.
        
        Checks:
        - Pot is non-negative
        - All stacks are non-negative
        - No illegal bet amounts
        - Pot roughly equals sum of contributions
        - Folded players are properly inactive
        
        Args:
            state: Table state to validate
            
        Returns:
            GameStateValidation with results
        """
        errors = []
        warnings = []
        
        # Use centralized pot consistency check
        pot_ok, pot_warnings = holdem_rules.check_pot_consistency(state.pot, state.players)
        if not pot_ok:
            # Negative pot is an error, not just a warning
            if state.pot < 0:
                errors.extend([w for w in pot_warnings if "negative" in w.lower()])
                warnings.extend([w for w in pot_warnings if "negative" not in w.lower()])
            else:
                warnings.extend(pot_warnings)
        
        # Use centralized stack consistency check
        stacks_ok, stack_errors = holdem_rules.check_stack_consistency(state.players)
        if not stacks_ok:
            errors.extend(stack_errors)
        
        # Check folded players are properly marked
        folded_ok, folded_warnings = holdem_rules.check_folded_players_inactive(
            state.players, self.players_acted
        )
        if not folded_ok:
            warnings.extend(folded_warnings)
        
        is_valid = len(errors) == 0
        
        if errors:
            logger.error(f"State validation failed: {errors}")
        if warnings:
            logger.warning(f"State validation warnings: {warnings}")
        
        return GameStateValidation(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )
    
    def post_blinds(self, state: TableState) -> List[str]:
        """Post blinds at the start of a hand.
        
        Args:
            state: Current table state
            
        Returns:
            List of messages about blind posting
        """
        messages = []
        
        sb_pos = self.get_small_blind_position()
        bb_pos = self.get_big_blind_position()
        
        if sb_pos < len(state.players):
            sb_player = state.players[sb_pos]
            sb_amount = min(self.small_blind, sb_player.stack)
            messages.append(
                f"Player {sb_pos} ({sb_player.name}) posts small blind {sb_amount:.2f}"
            )
            self.current_bet = sb_amount
        
        if bb_pos < len(state.players):
            bb_player = state.players[bb_pos]
            bb_amount = min(self.big_blind, bb_player.stack)
            messages.append(
                f"Player {bb_pos} ({bb_player.name}) posts big blind {bb_amount:.2f}"
            )
            self.current_bet = bb_amount
            self.last_raise_amount = bb_amount - self.small_blind
        
        return messages
