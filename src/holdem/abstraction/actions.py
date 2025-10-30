"""Action abstraction."""

from enum import Enum
from dataclasses import dataclass
from typing import List
from holdem.types import Action, ActionType


class AbstractAction(Enum):
    """Abstract action buckets."""
    FOLD = "fold"
    CHECK_CALL = "check_call"
    BET_QUARTER_POT = "bet_0.25p"
    BET_HALF_POT = "bet_0.5p"
    BET_POT = "bet_1.0p"
    BET_DOUBLE_POT = "bet_2.0p"
    ALL_IN = "all_in"


@dataclass
class ActionAbstraction:
    """Maps abstract actions to concrete actions."""
    
    @staticmethod
    def get_available_actions(
        pot: float,
        stack: float,
        current_bet: float,
        player_bet: float,
        can_check: bool
    ) -> List[AbstractAction]:
        """Get available abstract actions."""
        actions = []
        
        # Always can fold (unless can check for free)
        if current_bet > player_bet:
            actions.append(AbstractAction.FOLD)
        
        # Check/Call
        actions.append(AbstractAction.CHECK_CALL)
        
        # Betting actions
        to_call = current_bet - player_bet
        remaining_stack = stack - to_call
        
        if remaining_stack > 0:
            # Quarter pot
            if remaining_stack >= pot * 0.25:
                actions.append(AbstractAction.BET_QUARTER_POT)
            
            # Half pot
            if remaining_stack >= pot * 0.5:
                actions.append(AbstractAction.BET_HALF_POT)
            
            # Pot
            if remaining_stack >= pot:
                actions.append(AbstractAction.BET_POT)
            
            # Double pot
            if remaining_stack >= pot * 2:
                actions.append(AbstractAction.BET_DOUBLE_POT)
            
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
        """Convert abstract action to concrete action."""
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
                AbstractAction.BET_HALF_POT: 0.5,
                AbstractAction.BET_POT: 1.0,
                AbstractAction.BET_DOUBLE_POT: 2.0
            }
            
            fraction = pot_fraction_map.get(abstract_action, 1.0)
            bet_amount = pot * fraction
            
            # Cap at stack
            bet_amount = min(bet_amount, stack - to_call)
            
            if current_bet == 0:
                return Action(ActionType.BET, amount=bet_amount + to_call)
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
            
            if ratio < 0.375:  # Between 0.25 and 0.5
                return AbstractAction.BET_QUARTER_POT
            elif ratio < 0.75:  # Between 0.5 and 1.0
                return AbstractAction.BET_HALF_POT
            elif ratio < 1.5:  # Between 1.0 and 2.0
                return AbstractAction.BET_POT
            else:
                return AbstractAction.BET_DOUBLE_POT
        
        return AbstractAction.CHECK_CALL
