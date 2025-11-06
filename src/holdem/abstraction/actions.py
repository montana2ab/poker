"""Action abstraction."""

from enum import Enum
from dataclasses import dataclass
from typing import List
from holdem.types import Action, ActionType, Street


class AbstractAction(Enum):
    """Abstract action buckets.
    
    Canonical order: [FOLD, CHECK_CALL, BET_33, BET_66, BET_75, BET_100, BET_150, ALL_IN]
    This order should be maintained everywhere to ensure strategy/regret alignment.
    """
    FOLD = "fold"
    CHECK_CALL = "check_call"
    BET_QUARTER_POT = "bet_0.25p"
    BET_THIRD_POT = "bet_0.33p"
    BET_HALF_POT = "bet_0.5p"
    BET_TWO_THIRDS_POT = "bet_0.66p"
    BET_THREE_QUARTERS_POT = "bet_0.75p"
    BET_POT = "bet_1.0p"
    BET_OVERBET_150 = "bet_1.5p"  # Renamed from BET_ONE_HALF_POT (1.5× pot, not 0.5×)
    BET_DOUBLE_POT = "bet_2.0p"
    ALL_IN = "all_in"


@dataclass
class ActionAbstraction:
    """Maps abstract actions to concrete actions."""
    
    # All-in threshold: if bet >= this fraction of stack, treat as all-in
    ALL_IN_THRESHOLD = 0.97
    
    @staticmethod
    def get_available_actions(
        pot: float,
        stack: float,
        current_bet: float,
        player_bet: float,
        can_check: bool,
        street: Street = Street.PREFLOP,
        in_position: bool = True
    ) -> List[AbstractAction]:
        """Get available abstract actions based on street and position.
        
        Action menu (Exploit-Station vs caller):
        - Flop: IP {33, 75, 100, 150} | OOP {33, 75, 100}
        - Turn: {66, 100, 150}
        - River: {75, 100, 150, all-in}
        (Cuts small bluffs, maximizes thick value.)
        
        Args:
            pot: Current pot size
            stack: Player's remaining stack
            current_bet: Current bet to match
            player_bet: Player's bet this round
            can_check: Whether player can check
            street: Current game street
            in_position: Whether player is in position (IP) or out of position (OOP)
        """
        actions = []
        
        # Always can fold (unless can check for free)
        if current_bet > player_bet:
            actions.append(AbstractAction.FOLD)
        
        # Check/Call
        actions.append(AbstractAction.CHECK_CALL)
        
        # Betting actions based on street and position
        to_call = current_bet - player_bet
        remaining_stack = stack - to_call
        
        if remaining_stack > 0:
            # Define available bet sizes per street and position
            if street == Street.PREFLOP:
                # Preflop: use original abstraction
                bet_sizes = [0.25, 0.5, 1.0, 2.0]
            elif street == Street.FLOP:
                if in_position:
                    # Flop IP: {33, 75, 100, 150}
                    bet_sizes = [0.33, 0.75, 1.0, 1.5]
                else:
                    # Flop OOP: {33, 75, 100}
                    bet_sizes = [0.33, 0.75, 1.0]
            elif street == Street.TURN:
                # Turn: {66, 100, 150}
                bet_sizes = [0.66, 1.0, 1.5]
            elif street == Street.RIVER:
                # River: {75, 100, 150, all-in}
                bet_sizes = [0.75, 1.0, 1.5]
            else:
                # Fallback
                bet_sizes = [0.5, 1.0, 2.0]
            
            # Map bet sizes to actions
            size_to_action = {
                0.25: AbstractAction.BET_QUARTER_POT,
                0.33: AbstractAction.BET_THIRD_POT,
                0.5: AbstractAction.BET_HALF_POT,
                0.66: AbstractAction.BET_TWO_THIRDS_POT,
                0.75: AbstractAction.BET_THREE_QUARTERS_POT,
                1.0: AbstractAction.BET_POT,
                1.5: AbstractAction.BET_OVERBET_150,
                2.0: AbstractAction.BET_DOUBLE_POT
            }
            
            for size in bet_sizes:
                if remaining_stack >= pot * size:
                    action = size_to_action.get(size)
                    if action:
                        actions.append(action)
            
            # All-in (always available if we have chips)
            actions.append(AbstractAction.ALL_IN)
        
        return actions
    
    @staticmethod
    def abstract_to_concrete(
        abstract_action: AbstractAction,
        pot: float,
        stack: float,
        current_bet: float,
        player_bet: float,
        can_check: bool
    ) -> Action:
        """Convert abstract action to concrete action.
        
        Betting semantics:
        - Facing check (current_bet == 0): size = round(f * pot)
        - Facing bet: raise_to = round(f * (pot + call_amount)) (to-size convention)
        - Clamp to stack size; if size >= 97% of stack -> ALL-IN
        """
        to_call = current_bet - player_bet
        
        if abstract_action == AbstractAction.FOLD:
            return Action(ActionType.FOLD)
        
        elif abstract_action == AbstractAction.CHECK_CALL:
            if can_check and to_call == 0:
                return Action(ActionType.CHECK)
            else:
                return Action(ActionType.CALL, amount=to_call)
        
        elif abstract_action == AbstractAction.ALL_IN:
            return Action(ActionType.ALLIN, amount=stack)
        
        else:
            # Betting actions
            pot_fraction_map = {
                AbstractAction.BET_QUARTER_POT: 0.25,
                AbstractAction.BET_THIRD_POT: 0.33,
                AbstractAction.BET_HALF_POT: 0.5,
                AbstractAction.BET_TWO_THIRDS_POT: 0.66,
                AbstractAction.BET_THREE_QUARTERS_POT: 0.75,
                AbstractAction.BET_POT: 1.0,
                AbstractAction.BET_OVERBET_150: 1.5,
                AbstractAction.BET_DOUBLE_POT: 2.0
            }
            
            fraction = pot_fraction_map.get(abstract_action, 1.0)
            
            # Betting semantics: facing check vs facing bet
            # When facing check (or we've already matched the bet), size relative to pot
            # When facing bet, size relative to pot + what we need to call (to-size)
            facing_check = (current_bet == 0 or current_bet == player_bet)
            
            if facing_check:
                # Facing check: bet = fraction * pot
                bet_amount = round(fraction * pot)
            else:
                # Facing bet: raise to = fraction * (pot + call_amount)
                bet_amount = round(fraction * (pot + to_call))
            
            # Cap at stack
            remaining_stack = stack - to_call
            bet_amount = min(bet_amount, remaining_stack)
            
            # If bet >= threshold of stack, treat as all-in
            if bet_amount >= ActionAbstraction.ALL_IN_THRESHOLD * remaining_stack:
                return Action(ActionType.ALLIN, amount=stack)
            
            if facing_check:
                return Action(ActionType.BET, amount=bet_amount)
            else:
                return Action(ActionType.RAISE, amount=bet_amount + to_call)
    
    @staticmethod
    def concrete_to_abstract(
        action: Action,
        pot: float,
        stack: float
    ) -> AbstractAction:
        """Convert concrete action to nearest abstract action."""
        if action.action_type == ActionType.FOLD:
            return AbstractAction.FOLD
        
        elif action.action_type in [ActionType.CHECK, ActionType.CALL]:
            return AbstractAction.CHECK_CALL
        
        elif action.action_type == ActionType.ALLIN or action.amount >= stack * 0.9:
            return AbstractAction.ALL_IN
        
        elif action.action_type in [ActionType.BET, ActionType.RAISE]:
            # Map to nearest pot-sized bet
            ratio = action.amount / max(pot, 1.0)
            
            if ratio < 0.29:  # Closest to 0.25
                return AbstractAction.BET_QUARTER_POT
            elif ratio < 0.415:  # Between 0.33 and 0.5
                return AbstractAction.BET_THIRD_POT
            elif ratio < 0.58:  # Closest to 0.5
                return AbstractAction.BET_HALF_POT
            elif ratio < 0.705:  # Closest to 0.66
                return AbstractAction.BET_TWO_THIRDS_POT
            elif ratio < 0.875:  # Closest to 0.75
                return AbstractAction.BET_THREE_QUARTERS_POT
            elif ratio < 1.25:  # Closest to 1.0
                return AbstractAction.BET_POT
            elif ratio < 1.75:  # Closest to 1.5
                return AbstractAction.BET_OVERBET_150
            else:
                return AbstractAction.BET_DOUBLE_POT
        
        return AbstractAction.CHECK_CALL
