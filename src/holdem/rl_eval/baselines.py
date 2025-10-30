"""Baseline agents for evaluation."""

import random
from typing import List
from holdem.abstraction.actions import AbstractAction
from holdem.types import TableState


class RandomAgent:
    """Agent that plays randomly."""
    
    def __init__(self):
        self.name = "Random"
    
    def get_action(
        self,
        state: TableState,
        available_actions: List[AbstractAction]
    ) -> AbstractAction:
        """Get random action."""
        return random.choice(available_actions)


class AlwaysFoldAgent:
    """Agent that always folds."""
    
    def __init__(self):
        self.name = "AlwaysFold"
    
    def get_action(
        self,
        state: TableState,
        available_actions: List[AbstractAction]
    ) -> AbstractAction:
        """Always fold if possible, otherwise check/call."""
        if AbstractAction.FOLD in available_actions:
            return AbstractAction.FOLD
        return AbstractAction.CHECK_CALL


class AlwaysCallAgent:
    """Agent that always calls."""
    
    def __init__(self):
        self.name = "AlwaysCall"
    
    def get_action(
        self,
        state: TableState,
        available_actions: List[AbstractAction]
    ) -> AbstractAction:
        """Always check/call."""
        return AbstractAction.CHECK_CALL


class TightAgent:
    """Agent that plays tight (only strong hands)."""
    
    def __init__(self):
        self.name = "Tight"
    
    def get_action(
        self,
        state: TableState,
        available_actions: List[AbstractAction]
    ) -> AbstractAction:
        """Play tight strategy."""
        # Simplified: fold most of the time
        if random.random() < 0.7:
            if AbstractAction.FOLD in available_actions:
                return AbstractAction.FOLD
        return AbstractAction.CHECK_CALL


class AggressiveAgent:
    """Agent that plays aggressively."""
    
    def __init__(self):
        self.name = "Aggressive"
    
    def get_action(
        self,
        state: TableState,
        available_actions: List[AbstractAction]
    ) -> AbstractAction:
        """Play aggressive strategy."""
        # Prefer betting/raising
        bet_actions = [
            AbstractAction.BET_POT,
            AbstractAction.BET_HALF_POT,
            AbstractAction.BET_DOUBLE_POT
        ]
        
        for action in bet_actions:
            if action in available_actions and random.random() < 0.6:
                return action
        
        return AbstractAction.CHECK_CALL
