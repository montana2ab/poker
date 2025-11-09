"""Action translation between discrete and client-specific actions.

Translates abstract action IDs to legal poker client actions, handling:
- Min-raise constraints
- All-in capping
- Chip rounding
- PokerStars-specific rules
"""

from enum import IntEnum
from dataclasses import dataclass
from typing import List, Tuple, Optional
from holdem.types import Action, ActionType, Street
from holdem.abstraction.actions import AbstractAction
from holdem.utils.logging import get_logger

logger = get_logger("abstraction.action_translator")


class ActionSetMode(IntEnum):
    """Action set tightness modes."""
    TIGHT = 0    # Minimal action set (3-4 actions per street)
    BALANCED = 1  # Balanced action set (5-6 actions per street)
    LOOSE = 2    # Full action set (7+ actions per street)


@dataclass
class LegalConstraints:
    """Legal constraints for action translation."""
    min_raise: float  # Minimum raise amount
    max_bet: float    # Maximum bet (all-in cap)
    min_chip: float   # Minimum chip increment (e.g., 1 BB or 0.01)
    

class ActionTranslator:
    """Translates between abstract and client-specific actions.
    
    Handles:
    - Discretization of bet sizes per street
    - Translation to legal client actions (rounding, min-raise, all-in)
    - Idempotent round-trip conversion
    - PokerStars compliance
    """
    
    # Define action set per street and mode
    ACTION_SETS = {
        Street.FLOP: {
            ActionSetMode.TIGHT: [0.33, 0.75, 1.0],
            ActionSetMode.BALANCED: [0.33, 0.66, 1.0, 1.5],
            ActionSetMode.LOOSE: [0.25, 0.33, 0.5, 0.66, 0.75, 1.0, 1.5]
        },
        Street.TURN: {
            ActionSetMode.TIGHT: [0.66, 1.0, 1.5],
            ActionSetMode.BALANCED: [0.5, 1.0, 1.5],
            ActionSetMode.LOOSE: [0.33, 0.5, 0.66, 1.0, 1.5, 2.0]
        },
        Street.RIVER: {
            ActionSetMode.TIGHT: [0.75, 1.0, 1.5],
            ActionSetMode.BALANCED: [0.75, 1.25, 'all-in'],
            ActionSetMode.LOOSE: [0.5, 0.75, 1.0, 1.25, 1.5, 'all-in']
        },
        Street.PREFLOP: {
            ActionSetMode.TIGHT: [0.5, 1.0, 2.0],
            ActionSetMode.BALANCED: [0.33, 1.0, 2.5],
            ActionSetMode.LOOSE: [0.25, 0.5, 1.0, 2.0, 3.0]
        }
    }
    
    def __init__(self, mode: ActionSetMode = ActionSetMode.BALANCED):
        """Initialize action translator.
        
        Args:
            mode: Action set mode (tight, balanced, or loose)
        """
        self.mode = mode
        logger.info(f"ActionTranslator initialized with mode: {mode.name}")
    
    def to_discrete(
        self,
        pot: float,
        stack: float,
        legal_moves: List[Action],
        street: Street = Street.FLOP
    ) -> int:
        """Convert legal moves to discrete action ID.
        
        Args:
            pot: Current pot size
            stack: Player's remaining stack
            legal_moves: List of legal actions available
            street: Current game street
            
        Returns:
            Discrete action ID (0-indexed)
        """
        # Get action set for this street
        action_sizes = self.ACTION_SETS.get(street, {}).get(
            self.mode,
            self.ACTION_SETS[Street.FLOP][self.mode]
        )
        
        # Map legal moves to nearest discrete action
        # 0 = FOLD, 1 = CHECK/CALL, 2+ = bet sizes
        action_map = {
            ActionType.FOLD: 0,
            ActionType.CHECK: 1,
            ActionType.CALL: 1,
        }
        
        # Check if we have fold/check/call
        for move in legal_moves:
            if move.action_type in action_map:
                # Return the first passive action found
                return action_map[move.action_type]
        
        # Otherwise, find nearest bet size
        min_distance = float('inf')
        best_id = 2  # Default to first bet size
        
        for i, size in enumerate(action_sizes):
            if isinstance(size, str) and size == 'all-in':
                # Check if we can go all-in
                for move in legal_moves:
                    if move.action_type == ActionType.ALLIN:
                        return i + 2  # Offset by fold/call
            else:
                # Calculate target bet amount
                target = pot * size
                # Find closest legal move
                for move in legal_moves:
                    if move.action_type in [ActionType.BET, ActionType.RAISE]:
                        distance = abs(move.amount - target)
                        if distance < min_distance:
                            min_distance = distance
                            best_id = i + 2
        
        return best_id
    
    def to_client(
        self,
        action_id: int,
        pot: float,
        stack: float,
        constraints: LegalConstraints,
        street: Street = Street.FLOP,
        current_bet: float = 0.0,
        player_bet: float = 0.0
    ) -> Action:
        """Convert discrete action ID to client-specific action.
        
        Ensures compliance with:
        - PokerStars min-raise rules
        - All-in capping
        - Chip rounding
        
        Args:
            action_id: Discrete action ID
            pot: Current pot size
            stack: Player's remaining stack
            constraints: Legal constraints (min_raise, max_bet, min_chip)
            street: Current game street
            current_bet: Current bet to match
            player_bet: Player's current bet this round
            
        Returns:
            Legal Action object
        """
        # Get action set for this street
        action_sizes = self.ACTION_SETS.get(street, {}).get(
            self.mode,
            self.ACTION_SETS[Street.FLOP][self.mode]
        )
        
        # 0 = FOLD
        if action_id == 0:
            return Action(ActionType.FOLD)
        
        # 1 = CHECK/CALL
        if action_id == 1:
            to_call = current_bet - player_bet
            if to_call <= 0:
                return Action(ActionType.CHECK)
            else:
                return Action(ActionType.CALL, amount=to_call)
        
        # 2+ = bet sizes
        bet_index = action_id - 2
        if bet_index >= len(action_sizes):
            # Out of range, return all-in
            return Action(ActionType.ALLIN, amount=stack)
        
        size = action_sizes[bet_index]
        
        # Handle all-in
        if isinstance(size, str) and size == 'all-in':
            return Action(ActionType.ALLIN, amount=stack)
        
        # Calculate bet amount
        to_call = current_bet - player_bet
        remaining_stack = stack - to_call
        
        # Bet sizing relative to pot
        bet_amount = pot * size
        
        # Round to chip increment
        bet_amount = round(bet_amount / constraints.min_chip) * constraints.min_chip
        
        # Apply min-raise constraint
        if to_call > 0:
            # When facing a bet, minimum raise is at least min_raise above the call
            min_total = to_call + constraints.min_raise
            if bet_amount + to_call < min_total:
                bet_amount = constraints.min_raise
        else:
            # When betting into empty pot, ensure at least min_raise
            bet_amount = max(bet_amount, constraints.min_raise)
        
        # Cap at remaining stack
        bet_amount = min(bet_amount, remaining_stack)
        
        # Cap at max_bet
        bet_amount = min(bet_amount, constraints.max_bet)
        
        # If bet is >= 97% of stack, treat as all-in
        if bet_amount >= 0.97 * remaining_stack:
            return Action(ActionType.ALLIN, amount=stack)
        
        # Return appropriate action type
        if to_call <= 0:
            return Action(ActionType.BET, amount=bet_amount)
        else:
            return Action(ActionType.RAISE, amount=bet_amount + to_call)
    
    def round_trip_test(
        self,
        action: Action,
        pot: float,
        stack: float,
        constraints: LegalConstraints,
        street: Street = Street.FLOP,
        epsilon: float = 0.05
    ) -> Tuple[bool, float]:
        """Test idempotence of action translation.
        
        Args:
            action: Original action
            pot: Pot size
            stack: Stack size
            constraints: Legal constraints
            street: Game street
            epsilon: Maximum allowed EV distance (as fraction of pot)
            
        Returns:
            (is_idempotent, ev_distance)
        """
        # Convert to discrete
        legal_moves = [action]
        action_id = self.to_discrete(pot, stack, legal_moves, street)
        
        # Convert back to client
        recovered_action = self.to_client(
            action_id, pot, stack, constraints, street
        )
        
        # Compare actions
        if action.action_type != recovered_action.action_type:
            # Type changed, measure EV distance
            ev_distance = abs(action.amount - recovered_action.amount) / max(pot, 1.0)
            return False, ev_distance
        
        # For bet/raise, check amount difference
        if action.action_type in [ActionType.BET, ActionType.RAISE, ActionType.ALLIN]:
            amount_diff = abs(action.amount - recovered_action.amount)
            ev_distance = amount_diff / max(pot, 1.0)
            is_close = ev_distance <= epsilon
            return is_close, ev_distance
        
        # For fold/check/call, must match exactly
        return True, 0.0
    
    def get_action_set(self, street: Street) -> List[float]:
        """Get action set for a given street.
        
        Args:
            street: Game street
            
        Returns:
            List of pot-sized bet fractions
        """
        return self.ACTION_SETS.get(street, {}).get(
            self.mode,
            self.ACTION_SETS[Street.FLOP][self.mode]
        )
