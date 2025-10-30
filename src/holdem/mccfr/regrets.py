"""Regret tracking for CFR."""

import numpy as np
from typing import Dict, List
from holdem.abstraction.actions import AbstractAction


class RegretTracker:
    """Tracks cumulative regrets for CFR."""
    
    def __init__(self):
        # infoset -> action -> cumulative regret
        self.regrets: Dict[str, Dict[AbstractAction, float]] = {}
        
        # infoset -> action -> cumulative strategy
        self.strategy_sum: Dict[str, Dict[AbstractAction, float]] = {}
    
    def get_regret(self, infoset: str, action: AbstractAction) -> float:
        """Get cumulative regret for action at infoset."""
        if infoset not in self.regrets:
            return 0.0
        return self.regrets[infoset].get(action, 0.0)
    
    def update_regret(self, infoset: str, action: AbstractAction, regret: float):
        """Update cumulative regret."""
        if infoset not in self.regrets:
            self.regrets[infoset] = {}
        
        current = self.regrets[infoset].get(action, 0.0)
        self.regrets[infoset][action] = current + regret
    
    def get_strategy(self, infoset: str, actions: List[AbstractAction]) -> Dict[AbstractAction, float]:
        """Get current strategy using regret matching."""
        if not actions:
            return {}
        
        # Get positive regrets
        regret_sum = 0.0
        strategy = {}
        
        for action in actions:
            regret = max(0.0, self.get_regret(infoset, action))
            strategy[action] = regret
            regret_sum += regret
        
        # Normalize to get strategy
        if regret_sum > 0:
            for action in actions:
                strategy[action] /= regret_sum
        else:
            # Uniform strategy if all regrets are non-positive
            uniform_prob = 1.0 / len(actions)
            for action in actions:
                strategy[action] = uniform_prob
        
        return strategy
    
    def add_strategy(self, infoset: str, strategy: Dict[AbstractAction, float], weight: float = 1.0):
        """Add to cumulative strategy."""
        if infoset not in self.strategy_sum:
            self.strategy_sum[infoset] = {}
        
        for action, prob in strategy.items():
            current = self.strategy_sum[infoset].get(action, 0.0)
            self.strategy_sum[infoset][action] = current + prob * weight
    
    def get_average_strategy(self, infoset: str, actions: List[AbstractAction]) -> Dict[AbstractAction, float]:
        """Get average strategy over all iterations."""
        if infoset not in self.strategy_sum:
            # Return uniform if never visited
            uniform_prob = 1.0 / len(actions) if actions else 0.0
            return {action: uniform_prob for action in actions}
        
        strategy_sum = self.strategy_sum[infoset]
        total = sum(strategy_sum.values())
        
        if total > 0:
            return {action: strategy_sum.get(action, 0.0) / total for action in actions}
        else:
            uniform_prob = 1.0 / len(actions) if actions else 0.0
            return {action: uniform_prob for action in actions}
    
    def reset_regrets(self):
        """Reset cumulative regrets (for CFR+)."""
        for infoset in self.regrets:
            for action in self.regrets[infoset]:
                if self.regrets[infoset][action] < 0:
                    self.regrets[infoset][action] = 0.0
    
    def discount(self, factor: float):
        """Discount regrets and strategy (for CFR+)."""
        for infoset in self.regrets:
            for action in self.regrets[infoset]:
                self.regrets[infoset][action] *= factor
        
        for infoset in self.strategy_sum:
            for action in self.strategy_sum[infoset]:
                self.strategy_sum[infoset][action] *= factor
