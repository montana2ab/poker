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
        
        # Lazy discount tracking to avoid iterating over all infosets
        # Track cumulative discount factors that haven't been applied yet
        self._cumulative_regret_discount: float = 1.0
        self._cumulative_strategy_discount: float = 1.0
        
        # Track which infosets have had discounts applied
        # When an infoset is accessed, we apply pending discounts
        self._regret_discount_applied: Dict[str, float] = {}
        self._strategy_discount_applied: Dict[str, float] = {}
    
    def _apply_pending_regret_discount(self, infoset: str):
        """Apply any pending discount factors to an infoset's regrets."""
        if infoset not in self.regrets:
            return
        
        # Check if this infoset needs discount applied
        last_applied = self._regret_discount_applied.get(infoset, 1.0)
        if last_applied != self._cumulative_regret_discount:
            # Calculate the discount factor to apply
            discount_to_apply = self._cumulative_regret_discount / last_applied
            
            # Apply discount to all actions in this infoset
            for action in self.regrets[infoset]:
                self.regrets[infoset][action] *= discount_to_apply
            
            # Mark as up to date
            self._regret_discount_applied[infoset] = self._cumulative_regret_discount
    
    def _apply_pending_strategy_discount(self, infoset: str):
        """Apply any pending discount factors to an infoset's strategy."""
        if infoset not in self.strategy_sum:
            return
        
        # Check if this infoset needs discount applied
        last_applied = self._strategy_discount_applied.get(infoset, 1.0)
        if last_applied != self._cumulative_strategy_discount:
            # Calculate the discount factor to apply
            discount_to_apply = self._cumulative_strategy_discount / last_applied
            
            # Apply discount to all actions in this infoset
            for action in self.strategy_sum[infoset]:
                self.strategy_sum[infoset][action] *= discount_to_apply
            
            # Mark as up to date
            self._strategy_discount_applied[infoset] = self._cumulative_strategy_discount
    
    def get_regret(self, infoset: str, action: AbstractAction) -> float:
        """Get cumulative regret for action at infoset."""
        if infoset not in self.regrets:
            return 0.0
        
        # Apply pending discounts before reading
        self._apply_pending_regret_discount(infoset)
        
        return self.regrets[infoset].get(action, 0.0)
    
    def update_regret(self, infoset: str, action: AbstractAction, regret: float, weight: float = 1.0):
        """Update cumulative regret.
        
        Args:
            infoset: Information set identifier
            action: Action to update
            regret: Instantaneous regret value
            weight: Linear weight (typically iteration number for Linear MCCFR)
        """
        # Apply pending discounts before updating
        if infoset in self.regrets:
            self._apply_pending_regret_discount(infoset)
        else:
            self.regrets[infoset] = {}
            # Mark as up to date with current cumulative discount
            self._regret_discount_applied[infoset] = self._cumulative_regret_discount
        
        current = self.regrets[infoset].get(action, 0.0)
        self.regrets[infoset][action] = current + weight * regret
    
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
        """Add to cumulative strategy.
        
        Args:
            infoset: Information set identifier
            strategy: Current strategy (probability distribution over actions)
            weight: Linear weight (typically iteration number for Linear MCCFR, 
                   weighted by reach probability)
        """
        # Apply pending discounts before updating
        if infoset in self.strategy_sum:
            self._apply_pending_strategy_discount(infoset)
        else:
            self.strategy_sum[infoset] = {}
            # Mark as up to date with current cumulative discount
            self._strategy_discount_applied[infoset] = self._cumulative_strategy_discount
        
        for action, prob in strategy.items():
            current = self.strategy_sum[infoset].get(action, 0.0)
            self.strategy_sum[infoset][action] = current + prob * weight
    
    def get_average_strategy(self, infoset: str, actions: List[AbstractAction]) -> Dict[AbstractAction, float]:
        """Get average strategy over all iterations."""
        if infoset not in self.strategy_sum:
            # Return uniform if never visited
            uniform_prob = 1.0 / len(actions) if actions else 0.0
            return {action: uniform_prob for action in actions}
        
        # Apply pending discounts before reading
        self._apply_pending_strategy_discount(infoset)
        
        strategy_sum = self.strategy_sum[infoset]
        total = sum(strategy_sum.values())
        
        if total > 0:
            return {action: strategy_sum.get(action, 0.0) / total for action in actions}
        else:
            uniform_prob = 1.0 / len(actions) if actions else 0.0
            return {action: uniform_prob for action in actions}
    
    def reset_regrets(self):
        """Reset cumulative regrets (for CFR+)."""
        # Apply all pending discounts first before resetting negatives
        for infoset in list(self.regrets.keys()):
            self._apply_pending_regret_discount(infoset)
            for action in self.regrets[infoset]:
                if self.regrets[infoset][action] < 0:
                    self.regrets[infoset][action] = 0.0
    
    def discount(self, regret_factor: float = 1.0, strategy_factor: float = 1.0):
        """Discount regrets and strategy (for CFR+ and Linear MCCFR).
        
        Uses lazy evaluation: instead of iterating over all infosets immediately,
        we track cumulative discount factors and apply them only when infosets are accessed.
        This prevents O(n) operations where n = number of discovered infosets.
        
        Args:
            regret_factor: Discount factor α for regrets
            strategy_factor: Discount factor β for average strategy
        """
        # Update cumulative discount factors
        # These will be applied lazily when infosets are accessed/updated
        self._cumulative_regret_discount *= regret_factor
        self._cumulative_strategy_discount *= strategy_factor
    
    def apply_pending_discounts(self):
        """Force application of all pending discount factors.
        
        This method is provided for backward compatibility and testing.
        In normal operation, discounts are applied lazily for performance.
        """
        # Apply pending discounts to all infosets
        for infoset in list(self.regrets.keys()):
            self._apply_pending_regret_discount(infoset)
        for infoset in list(self.strategy_sum.keys()):
            self._apply_pending_strategy_discount(infoset)
    
    def should_prune(self, infoset: str, actions: List[AbstractAction], threshold: float) -> bool:
        """Check if all actions at infoset have regret below threshold.
        
        Args:
            infoset: Information set to check
            actions: List of available actions
            threshold: Regret threshold (typically -300,000,000)
        
        Returns:
            True if all actions have regret below threshold
        """
        if infoset not in self.regrets:
            return False  # No regrets yet, don't prune
        
        # Apply pending discounts before checking
        self._apply_pending_regret_discount(infoset)
        
        for action in actions:
            regret = self.regrets[infoset].get(action, 0.0)
            if regret >= threshold:
                return False  # At least one action above threshold
        
        return True  # All actions below threshold
    
    def get_state(self) -> Dict:
        """Get complete regret tracker state for checkpointing.
        
        Before returning state, applies all pending discounts to ensure
        the saved state is fully up-to-date.
        
        Returns:
            Dictionary containing regrets and strategy_sum with serializable keys
        """
        # Apply all pending discounts before saving
        for infoset in list(self.regrets.keys()):
            self._apply_pending_regret_discount(infoset)
        for infoset in list(self.strategy_sum.keys()):
            self._apply_pending_strategy_discount(infoset)
        
        # Convert AbstractAction keys to string values for serialization
        regrets_serializable = {}
        for infoset, action_dict in self.regrets.items():
            regrets_serializable[infoset] = {
                action.value: regret for action, regret in action_dict.items()
            }
        
        strategy_sum_serializable = {}
        for infoset, action_dict in self.strategy_sum.items():
            strategy_sum_serializable[infoset] = {
                action.value: prob for action, prob in action_dict.items()
            }
        
        return {
            'regrets': regrets_serializable,
            'strategy_sum': strategy_sum_serializable,
            'cumulative_regret_discount': self._cumulative_regret_discount,
            'cumulative_strategy_discount': self._cumulative_strategy_discount
        }
    
    def set_state(self, state: Dict):
        """Restore regret tracker state from checkpoint.
        
        Args:
            state: Dictionary containing regrets and strategy_sum
        """
        # Convert string keys back to AbstractAction
        self.regrets = {}
        for infoset, action_dict in state['regrets'].items():
            self.regrets[infoset] = {
                AbstractAction(action_str): regret 
                for action_str, regret in action_dict.items()
            }
        
        self.strategy_sum = {}
        for infoset, action_dict in state['strategy_sum'].items():
            self.strategy_sum[infoset] = {
                AbstractAction(action_str): prob 
                for action_str, prob in action_dict.items()
            }
        
        # Restore lazy discount tracking state (with backward compatibility)
        self._cumulative_regret_discount = state.get('cumulative_regret_discount', 1.0)
        self._cumulative_strategy_discount = state.get('cumulative_strategy_discount', 1.0)
        
        # Reset tracking dictionaries - all infosets are now up-to-date
        self._regret_discount_applied = {infoset: self._cumulative_regret_discount for infoset in self.regrets}
        self._strategy_discount_applied = {infoset: self._cumulative_strategy_discount for infoset in self.strategy_sum}
