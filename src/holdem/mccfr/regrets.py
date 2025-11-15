"""Regret tracking for CFR."""

import numpy as np
from typing import Dict, List, Optional
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.compact_storage import StorageBackend, DenseStorage, CompactStorage


class RegretTracker:
    """Tracks cumulative regrets for CFR.
    
    Supports pluggable storage backends:
    - DenseStorage: Python dicts with float64 (default, current behavior)
    - CompactStorage: Numpy arrays with int32/float32 for memory savings
    """
    
    def __init__(self, storage_mode: str = "dense"):
        """Initialize RegretTracker with specified storage backend.
        
        Args:
            storage_mode: "dense" for dict-based storage (default), 
                         "compact" for numpy-based compact storage
        """
        # Select storage backend
        if storage_mode == "compact":
            self._storage: StorageBackend = CompactStorage()
        elif storage_mode == "dense":
            self._storage: StorageBackend = DenseStorage()
        else:
            raise ValueError(f"Unknown storage mode: {storage_mode}. Use 'dense' or 'compact'")
        
        self._storage_mode = storage_mode
        
        # Lazy discount tracking to avoid iterating over all infosets
        # Track cumulative discount factors that haven't been applied yet
        self._cumulative_regret_discount: float = 1.0
        self._cumulative_strategy_discount: float = 1.0
        
        # Track which infosets have had discounts applied
        # When an infoset is accessed, we apply pending discounts
        self._regret_discount_applied: Dict[str, float] = {}
        self._strategy_discount_applied: Dict[str, float] = {}
    
    # Backward compatibility: expose storage as dict-like attributes
    @property
    def regrets(self) -> Dict[str, Dict[AbstractAction, float]]:
        """Get regrets as dict (for backward compatibility)."""
        result = {}
        for infoset in self._storage.get_all_infosets_regrets():
            result[infoset] = self._storage.get_all_regrets(infoset)
        return result
    
    @property
    def strategy_sum(self) -> Dict[str, Dict[AbstractAction, float]]:
        """Get strategy_sum as dict (for backward compatibility)."""
        result = {}
        for infoset in self._storage.get_all_infosets_strategy():
            result[infoset] = self._storage.get_all_strategy_sums(infoset)
        return result
    
    def _apply_pending_regret_discount(self, infoset: str):
        """Apply any pending discount factors to an infoset's regrets."""
        if not self._storage.has_infoset_regrets(infoset):
            return
        
        # Check if this infoset needs discount applied
        last_applied = self._regret_discount_applied.get(infoset, 1.0)
        if last_applied != self._cumulative_regret_discount:
            # Calculate the discount factor to apply
            discount_to_apply = self._cumulative_regret_discount / last_applied
            
            # Apply discount through storage backend
            self._storage.apply_discount_to_infoset_regrets(infoset, discount_to_apply)
            
            # Mark as up to date
            self._regret_discount_applied[infoset] = self._cumulative_regret_discount
    
    def _apply_pending_strategy_discount(self, infoset: str):
        """Apply any pending discount factors to an infoset's strategy."""
        if not self._storage.has_infoset_strategy(infoset):
            return
        
        # Check if this infoset needs discount applied
        last_applied = self._strategy_discount_applied.get(infoset, 1.0)
        if last_applied != self._cumulative_strategy_discount:
            # Calculate the discount factor to apply
            discount_to_apply = self._cumulative_strategy_discount / last_applied
            
            # Apply discount through storage backend
            self._storage.apply_discount_to_infoset_strategy(infoset, discount_to_apply)
            
            # Mark as up to date
            self._strategy_discount_applied[infoset] = self._cumulative_strategy_discount
    
    def get_regret(self, infoset: str, action: AbstractAction) -> float:
        """Get cumulative regret for action at infoset."""
        # Apply pending discounts before reading
        self._apply_pending_regret_discount(infoset)
        
        return self._storage.get_regret(infoset, action)
    
    def update_regret(self, infoset: str, action: AbstractAction, regret: float, weight: float = 1.0):
        """Update cumulative regret.
        
        Args:
            infoset: Information set identifier
            action: Action to update
            regret: Instantaneous regret value
            weight: Linear weight (typically iteration number for Linear MCCFR)
        """
        # Apply pending discounts before updating
        if self._storage.has_infoset_regrets(infoset):
            self._apply_pending_regret_discount(infoset)
        else:
            # Mark as up to date with current cumulative discount
            self._regret_discount_applied[infoset] = self._cumulative_regret_discount
        
        self._storage.update_regret(infoset, action, regret, weight)
    
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
        if self._storage.has_infoset_strategy(infoset):
            self._apply_pending_strategy_discount(infoset)
        else:
            # Mark as up to date with current cumulative discount
            self._strategy_discount_applied[infoset] = self._cumulative_strategy_discount
        
        for action, prob in strategy.items():
            self._storage.add_strategy(infoset, action, prob, weight)
    
    def get_average_strategy(self, infoset: str, actions: List[AbstractAction]) -> Dict[AbstractAction, float]:
        """Get average strategy over all iterations."""
        if not self._storage.has_infoset_strategy(infoset):
            # Return uniform if never visited
            uniform_prob = 1.0 / len(actions) if actions else 0.0
            return {action: uniform_prob for action in actions}
        
        # Apply pending discounts before reading
        self._apply_pending_strategy_discount(infoset)
        
        strategy_sum_dict = self._storage.get_all_strategy_sums(infoset)
        total = sum(strategy_sum_dict.values())
        
        if total > 0:
            return {action: strategy_sum_dict.get(action, 0.0) / total for action in actions}
        else:
            uniform_prob = 1.0 / len(actions) if actions else 0.0
            return {action: uniform_prob for action in actions}
    
    def reset_regrets(self):
        """Reset cumulative regrets (for CFR+)."""
        # Apply all pending discounts first before resetting negatives
        for infoset in self._storage.get_all_infosets_regrets():
            self._apply_pending_regret_discount(infoset)
            self._storage.reset_negative_regrets(infoset)
    
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
        for infoset in self._storage.get_all_infosets_regrets():
            self._apply_pending_regret_discount(infoset)
        for infoset in self._storage.get_all_infosets_strategy():
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
        if not self._storage.has_infoset_regrets(infoset):
            return False  # No regrets yet, don't prune
        
        # Apply pending discounts before checking
        self._apply_pending_regret_discount(infoset)
        
        regrets_dict = self._storage.get_all_regrets(infoset)
        for action in actions:
            regret = regrets_dict.get(action, 0.0)
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
        for infoset in self._storage.get_all_infosets_regrets():
            self._apply_pending_regret_discount(infoset)
        for infoset in self._storage.get_all_infosets_strategy():
            self._apply_pending_strategy_discount(infoset)
        
        # Get state from storage backend
        state = self._storage.get_state()
        
        # Add lazy discount tracking state
        state['cumulative_regret_discount'] = self._cumulative_regret_discount
        state['cumulative_strategy_discount'] = self._cumulative_strategy_discount
        
        return state
    
    def set_state(self, state: Dict):
        """Restore regret tracker state from checkpoint.
        
        Args:
            state: Dictionary containing regrets and strategy_sum
        """
        # Restore storage backend state
        self._storage.set_state(state)
        
        # Restore lazy discount tracking state (with backward compatibility)
        self._cumulative_regret_discount = state.get('cumulative_regret_discount', 1.0)
        self._cumulative_strategy_discount = state.get('cumulative_strategy_discount', 1.0)
        
        # Reset tracking dictionaries - all infosets are now up-to-date
        self._regret_discount_applied = {
            infoset: self._cumulative_regret_discount 
            for infoset in self._storage.get_all_infosets_regrets()
        }
        self._strategy_discount_applied = {
            infoset: self._cumulative_strategy_discount 
            for infoset in self._storage.get_all_infosets_strategy()
        }
