"""Subgame construction for real-time search."""

from typing import List, Optional
from holdem.types import Card, Street, TableState
from holdem.abstraction.actions import AbstractAction
from holdem.utils.logging import get_logger

logger = get_logger("realtime.subgame")


class SubgameBuilder:
    """Constructs limited subgames for real-time solving."""
    
    def __init__(self, depth_limit: int = 1):
        self.depth_limit = depth_limit
    
    def build_subgame(
        self,
        state: TableState,
        our_cards: List[Card],
        history: List[str]
    ):
        """Build subgame starting from current state."""
        # Determine streets to include
        current_street = state.street
        streets_to_solve = [current_street]
        
        if self.depth_limit >= 1 and current_street != Street.RIVER:
            # Include next street
            next_street = Street(current_street.value + 1)
            streets_to_solve.append(next_street)
        
        logger.debug(f"Building subgame for streets: {[s.name for s in streets_to_solve]}")
        
        # In full implementation, would construct game tree for these streets
        # with action abstraction and belief states
        
        return SubgameTree(streets_to_solve, state, our_cards)


class SubgameTree:
    """Represents a limited subgame tree."""
    
    def __init__(self, streets: List[Street], state: TableState, our_cards: List[Card]):
        self.streets = streets
        self.state = state
        self.our_cards = our_cards
        self.nodes = {}
    
    def get_actions(self, infoset: str) -> List[AbstractAction]:
        """Get available actions at infoset."""
        # Simplified
        return [
            AbstractAction.FOLD,
            AbstractAction.CHECK_CALL,
            AbstractAction.BET_HALF_POT,
            AbstractAction.BET_POT
        ]
