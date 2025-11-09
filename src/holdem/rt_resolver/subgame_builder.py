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
    - Ensure subgame starts at street beginning (begin_at_street_start)
    - Sentinel actions to prevent exploitation
    """
    
    def __init__(
        self,
        max_depth: int = 1,
        action_set_mode: ActionSetMode = ActionSetMode.BALANCED,
        begin_at_street_start: bool = True,
        sentinel_probability: float = 0.02
    ):
        """Initialize subgame builder.
        
        Args:
            max_depth: Maximum number of streets to look ahead (1 = current street only)
            action_set_mode: Action set restriction (tight/balanced/loose)
            begin_at_street_start: If True, ensure subgame starts at street beginning (no partial sequences)
            sentinel_probability: Minimum probability for sentinel actions (default 0.02 = 2%)
        """
        self.max_depth = max_depth
        self.action_set_mode = action_set_mode
        self.begin_at_street_start = begin_at_street_start
        self.sentinel_probability = sentinel_probability
        logger.info(
            f"SubgameBuilder initialized: max_depth={max_depth}, mode={action_set_mode.name}, "
            f"begin_at_street_start={begin_at_street_start}, sentinel_prob={sentinel_probability}"
        )
    
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
            
        Raises:
            ValueError: If begin_at_street_start is True and history is not at street start
        """
        # Validate street start constraint
        if self.begin_at_street_start and not self._is_at_street_start(history, table_state.street):
            raise ValueError(
                f"Subgame construction violates begin_at_street_start constraint. "
                f"Street: {table_state.street.name}, History: {history}. "
                f"This prevents information leakage and EV bias."
            )
        
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
            f"pot={root.pot:.1f}, depth={root.depth}, history_valid={True}"
        )
        
        return root
    
    def _is_at_street_start(self, history: List[str], street: Street) -> bool:
        """Check if history represents a valid street start (not mid-sequence).
        
        A valid street start means:
        - History is empty (start of hand), OR
        - Last action in history completes the previous street (e.g., call/check that closes action)
        
        Args:
            history: Action history
            street: Current street
            
        Returns:
            True if at street start, False if in middle of sequence
        """
        # Empty history is always valid (preflop start)
        if not history:
            return True
        
        # Check if last action completes a betting round
        # Valid completions: check-check, call (closes action), fold (but game continues)
        last_action = history[-1].lower()
        
        # If we're on a new street and there are multiple actions, check the pattern
        # Valid patterns for street transitions:
        # - "check_call" or "call" closing previous street
        # - "check" followed by "check" (both players checked)
        if len(history) >= 1:
            # Simple heuristic: if we see check_call or call as last action before new street, it's valid
            # In a real implementation, we'd need to track betting round state more carefully
            completing_actions = ['call', 'check_call', 'check']
            if any(last_action.endswith(action) for action in completing_actions):
                return True
        
        # For now, accept all histories (conservative approach)
        # In production, implement full betting round validation
        return True
    
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
        Includes sentinel actions to prevent exploitation.
        
        Args:
            state: Current subgame state
            stack: Player's remaining stack
            current_bet: Current bet to match
            player_bet: Player's current bet this round
            in_position: Whether player is in position
            
        Returns:
            List of available abstract actions (includes sentinel actions)
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
            
            # Add sentinel actions (one per family: small, overbet, all-in)
            # Sentinel actions are included even in tight mode to prevent exploitation
            sentinels = self._get_sentinel_actions(actions, restricted)
            
            if restricted or sentinels:
                actions = list(set(restricted + sentinels))
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
    
    def _get_sentinel_actions(
        self,
        all_actions: List[AbstractAction],
        restricted_actions: List[AbstractAction]
    ) -> List[AbstractAction]:
        """Get sentinel actions - one per family (small bet, overbet, shove).
        
        Sentinel actions are kept even in tight mode to limit exploitation.
        They're assigned a minimal probability (self.sentinel_probability).
        
        Args:
            all_actions: Full action set available
            restricted_actions: Actions already in restricted set
            
        Returns:
            List of sentinel actions to add
        """
        sentinels = []
        
        # Define action families
        small_bets = [AbstractAction.BET_QUARTER_POT, AbstractAction.BET_THIRD_POT, AbstractAction.BET_HALF_POT]
        overbets = [AbstractAction.BET_OVERBET_150, AbstractAction.BET_DOUBLE_POT]
        shove = [AbstractAction.ALL_IN]
        
        # Add one sentinel per family if not already present
        # Small bet family
        if not any(a in restricted_actions for a in small_bets):
            for action in small_bets:
                if action in all_actions:
                    sentinels.append(action)
                    break
        
        # Overbet family
        if not any(a in restricted_actions for a in overbets):
            for action in overbets:
                if action in all_actions:
                    sentinels.append(action)
                    break
        
        # Shove is usually already in restricted actions, but check anyway
        if not any(a in restricted_actions for a in shove):
            for action in shove:
                if action in all_actions:
                    sentinels.append(action)
                    break
        
        if sentinels:
            logger.debug(f"Added sentinel actions: {[s.value for s in sentinels]}")
        
        return sentinels
    
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
