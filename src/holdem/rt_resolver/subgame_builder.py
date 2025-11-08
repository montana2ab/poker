"""Subgame builder for depth-limited resolving.

Constructs bounded subgames from the current game state by:
- Freezing the action history
- Restricting the action set based on mode
- Limiting depth to current street + max_depth
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from holdem.types import Card, Street, TableState
from holdem.abstraction.actions import AbstractAction, ActionAbstraction
from holdem.abstraction.action_translator import ActionSetMode
from holdem.utils.logging import get_logger

logger = get_logger("rt_resolver.subgame_builder")


@dataclass
class SubgameState:
    """Represents a state in the subgame."""
    street: Street
    board: List[Card]
    pot: float
    history: List[str]
    active_players: int
    depth: int  # Depth from root (0 = current state)
    

class SubgameBuilder:
    """Builds bounded subgames for depth-limited resolving.
    
    Features:
    - Freeze action history up to current state
    - Restrict action set based on mode (tight/balanced/loose)
    - Limit lookahead depth to max_depth streets
    """
    
    def __init__(
        self,
        max_depth: int = 1,
        action_set_mode: ActionSetMode = ActionSetMode.BALANCED
    ):
        """Initialize subgame builder.
        
        Args:
            max_depth: Maximum number of streets to look ahead (1 = current street only)
            action_set_mode: Action set restriction (tight/balanced/loose)
        """
        self.max_depth = max_depth
        self.action_set_mode = action_set_mode
        logger.info(f"SubgameBuilder initialized: max_depth={max_depth}, mode={action_set_mode.name}")
    
    def build_from_state(
        self,
        table_state: TableState,
        history: List[str]
    ) -> SubgameState:
        """Build subgame root from current table state.
        
        Args:
            table_state: Current table state
            history: Action history up to this point
            
        Returns:
            Root state of the subgame
        """
        root = SubgameState(
            street=table_state.street,
            board=table_state.board.copy(),
            pot=table_state.pot,
            history=history.copy(),
            active_players=table_state.num_players,
            depth=0
        )
        
        logger.debug(
            f"Built subgame root: street={root.street.name}, "
            f"pot={root.pot:.1f}, depth={root.depth}"
        )
        
        return root
    
    def get_actions(
        self,
        state: SubgameState,
        stack: float,
        current_bet: float = 0.0,
        player_bet: float = 0.0,
        in_position: bool = True
    ) -> List[AbstractAction]:
        """Get available actions at a subgame state.
        
        Respects action set restrictions based on mode and depth.
        
        Args:
            state: Current subgame state
            stack: Player's remaining stack
            current_bet: Current bet to match
            player_bet: Player's current bet this round
            in_position: Whether player is in position
            
        Returns:
            List of available abstract actions
        """
        # Check depth limit
        if state.depth >= self.max_depth:
            # At depth limit, only allow passive actions
            actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL]
            logger.debug(f"At depth limit {state.depth}, returning passive actions only")
            return actions
        
        # Get full action set
        can_check = (current_bet == player_bet)
        actions = ActionAbstraction.get_available_actions(
            pot=state.pot,
            stack=stack,
            current_bet=current_bet,
            player_bet=player_bet,
            can_check=can_check,
            street=state.street,
            in_position=in_position
        )
        
        # Apply action set restriction based on mode
        if self.action_set_mode == ActionSetMode.TIGHT:
            # Keep only: fold, call, and 2-3 bet sizes
            restricted = [a for a in actions if a in [
                AbstractAction.FOLD,
                AbstractAction.CHECK_CALL,
                AbstractAction.BET_POT,
                AbstractAction.BET_THREE_QUARTERS_POT,
                AbstractAction.ALL_IN
            ]]
            if restricted:
                actions = restricted
        elif self.action_set_mode == ActionSetMode.BALANCED:
            # Keep: fold, call, and 3-4 bet sizes
            restricted = [a for a in actions if a in [
                AbstractAction.FOLD,
                AbstractAction.CHECK_CALL,
                AbstractAction.BET_TWO_THIRDS_POT,
                AbstractAction.BET_POT,
                AbstractAction.BET_OVERBET_150,
                AbstractAction.ALL_IN
            ]]
            if restricted:
                actions = restricted
        # LOOSE mode: keep all actions
        
        return actions
    
    def is_terminal(self, state: SubgameState) -> bool:
        """Check if state is terminal (leaf node).
        
        Args:
            state: Subgame state to check
            
        Returns:
            True if state is terminal
        """
        # Terminal if:
        # 1. Depth limit reached
        if state.depth >= self.max_depth:
            return True
        
        # 2. History indicates fold or showdown
        if state.history:
            last_action = state.history[-1]
            if last_action == "fold":
                return True
            # Showdown detection (simplified)
            if state.street == Street.RIVER and last_action in ["check_call", "call"]:
                return True
        
        # 3. Only one active player (others folded)
        if state.active_players <= 1:
            return True
        
        return False
    
    def advance_state(
        self,
        state: SubgameState,
        action: AbstractAction,
        next_street: Optional[Street] = None,
        next_board: Optional[List[Card]] = None,
        pot_increment: float = 0.0
    ) -> SubgameState:
        """Advance to next state after action.
        
        Args:
            state: Current state
            action: Action taken
            next_street: Next street (if advancing)
            next_board: Next board cards (if advancing)
            pot_increment: Amount added to pot
            
        Returns:
            Next subgame state
        """
        next_state = SubgameState(
            street=next_street if next_street else state.street,
            board=next_board if next_board else state.board.copy(),
            pot=state.pot + pot_increment,
            history=state.history + [action.value],
            active_players=state.active_players,
            depth=state.depth + 1
        )
        
        # Update active players if fold
        if action == AbstractAction.FOLD:
            next_state.active_players -= 1
        
        return next_state
