"""Compact storage backend for MCCFR regrets and strategies.

This module provides memory-efficient storage alternatives to the standard
dictionary-based storage used in RegretTracker. The compact storage uses:
- numpy arrays with float32 instead of float64
- Indexed action mapping instead of string keys
- Contiguous memory layout for better cache performance

Memory savings: ~40-50% compared to standard dict-based storage.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from holdem.abstraction.actions import AbstractAction


class ActionIndexer:
    """Maps AbstractAction enums to integer indices for compact storage."""
    
    def __init__(self):
        # Create bidirectional mapping
        self._action_to_idx: Dict[AbstractAction, int] = {}
        self._idx_to_action: Dict[int, AbstractAction] = {}
        self._next_idx = 0
        
    def get_or_create_index(self, action: AbstractAction) -> int:
        """Get index for action, creating new index if needed."""
        if action not in self._action_to_idx:
            self._action_to_idx[action] = self._next_idx
            self._idx_to_action[self._next_idx] = action
            self._next_idx += 1
        return self._action_to_idx[action]
    
    def get_action(self, idx: int) -> AbstractAction:
        """Get action from index."""
        return self._idx_to_action[idx]
    
    def get_index(self, action: AbstractAction) -> Optional[int]:
        """Get index for action, or None if not found."""
        return self._action_to_idx.get(action)
    
    def num_actions(self) -> int:
        """Get total number of mapped actions."""
        return self._next_idx


class CompactRegretStorage:
    """Memory-efficient regret storage using numpy arrays.
    
    Uses float32 arrays and integer action indices instead of dict[str, float].
    Provides significant memory savings for large game trees.
    """
    
    def __init__(self, max_actions: int = 20):
        """Initialize compact regret storage.
        
        Args:
            max_actions: Maximum number of actions per infoset (default: 20)
        """
        self.max_actions = max_actions
        self.action_indexer = ActionIndexer()
        
        # Storage: infoset -> (action_indices, regret_values)
        # action_indices: int32 array of action indices
        # regret_values: float32 array of regret values
        self.regrets: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
        self.strategy_sum: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
        
        # Lazy discount tracking (same as RegretTracker)
        self._cumulative_regret_discount: float = 1.0
        self._cumulative_strategy_discount: float = 1.0
        self._regret_discount_applied: Dict[str, float] = {}
        self._strategy_discount_applied: Dict[str, float] = {}
    
    def _apply_pending_regret_discount(self, infoset: str):
        """Apply pending discount factors to an infoset's regrets."""
        if infoset not in self.regrets:
            return
        
        last_applied = self._regret_discount_applied.get(infoset, 1.0)
        if last_applied != self._cumulative_regret_discount:
            discount_to_apply = self._cumulative_regret_discount / last_applied
            
            # Apply discount to regret values (in-place)
            _, regret_values = self.regrets[infoset]
            regret_values *= discount_to_apply
            
            self._regret_discount_applied[infoset] = self._cumulative_regret_discount
    
    def _apply_pending_strategy_discount(self, infoset: str):
        """Apply pending discount factors to an infoset's strategy."""
        if infoset not in self.strategy_sum:
            return
        
        last_applied = self._strategy_discount_applied.get(infoset, 1.0)
        if last_applied != self._cumulative_strategy_discount:
            discount_to_apply = self._cumulative_strategy_discount / last_applied
            
            # Apply discount to strategy values (in-place)
            _, strategy_values = self.strategy_sum[infoset]
            strategy_values *= discount_to_apply
            
            self._strategy_discount_applied[infoset] = self._cumulative_strategy_discount
    
    def get_regret(self, infoset: str, action: AbstractAction) -> float:
        """Get cumulative regret for action at infoset."""
        if infoset not in self.regrets:
            return 0.0
        
        self._apply_pending_regret_discount(infoset)
        
        action_idx = self.action_indexer.get_index(action)
        if action_idx is None:
            return 0.0
        
        action_indices, regret_values = self.regrets[infoset]
        # Find action in indices array
        mask = (action_indices == action_idx)
        if not np.any(mask):
            return 0.0
        
        return float(regret_values[mask][0])
    
    def update_regret(self, infoset: str, action: AbstractAction, regret: float, weight: float = 1.0):
        """Update cumulative regret."""
        action_idx = self.action_indexer.get_or_create_index(action)
        
        if infoset in self.regrets:
            self._apply_pending_regret_discount(infoset)
            
            action_indices, regret_values = self.regrets[infoset]
            # Find action in indices array
            mask = (action_indices == action_idx)
            
            if np.any(mask):
                # Update existing regret
                regret_values[mask] += weight * regret
            else:
                # Add new action
                new_indices = np.append(action_indices, action_idx)
                new_values = np.append(regret_values, weight * regret)
                self.regrets[infoset] = (new_indices, new_values)
        else:
            # Create new infoset entry
            action_indices = np.array([action_idx], dtype=np.int32)
            regret_values = np.array([weight * regret], dtype=np.float32)
            self.regrets[infoset] = (action_indices, regret_values)
            self._regret_discount_applied[infoset] = self._cumulative_regret_discount
    
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
        if infoset in self.strategy_sum:
            self._apply_pending_strategy_discount(infoset)
            
            action_indices, strategy_values = self.strategy_sum[infoset]
            
            for action, prob in strategy.items():
                action_idx = self.action_indexer.get_or_create_index(action)
                mask = (action_indices == action_idx)
                
                if np.any(mask):
                    strategy_values[mask] += prob * weight
                else:
                    # Add new action
                    new_indices = np.append(action_indices, action_idx)
                    new_values = np.append(strategy_values, prob * weight)
                    self.strategy_sum[infoset] = (new_indices, new_values)
        else:
            # Create new infoset entry
            action_indices = []
            strategy_values = []
            
            for action, prob in strategy.items():
                action_idx = self.action_indexer.get_or_create_index(action)
                action_indices.append(action_idx)
                strategy_values.append(prob * weight)
            
            self.strategy_sum[infoset] = (
                np.array(action_indices, dtype=np.int32),
                np.array(strategy_values, dtype=np.float32)
            )
            self._strategy_discount_applied[infoset] = self._cumulative_strategy_discount
    
    def get_average_strategy(self, infoset: str, actions: List[AbstractAction]) -> Dict[AbstractAction, float]:
        """Get average strategy over all iterations."""
        if infoset not in self.strategy_sum:
            uniform_prob = 1.0 / len(actions) if actions else 0.0
            return {action: uniform_prob for action in actions}
        
        self._apply_pending_strategy_discount(infoset)
        
        action_indices, strategy_values = self.strategy_sum[infoset]
        total = np.sum(strategy_values)
        
        if total > 0:
            result = {}
            for action in actions:
                action_idx = self.action_indexer.get_index(action)
                if action_idx is not None:
                    mask = (action_indices == action_idx)
                    if np.any(mask):
                        result[action] = float(strategy_values[mask][0] / total)
                    else:
                        result[action] = 0.0
                else:
                    result[action] = 0.0
            return result
        else:
            uniform_prob = 1.0 / len(actions) if actions else 0.0
            return {action: uniform_prob for action in actions}
    
    def reset_regrets(self):
        """Reset cumulative regrets (for CFR+)."""
        for infoset in list(self.regrets.keys()):
            self._apply_pending_regret_discount(infoset)
            _, regret_values = self.regrets[infoset]
            # Zero out negative regrets
            regret_values[regret_values < 0] = 0.0
    
    def discount(self, regret_factor: float = 1.0, strategy_factor: float = 1.0):
        """Discount regrets and strategy (lazy evaluation)."""
        self._cumulative_regret_discount *= regret_factor
        self._cumulative_strategy_discount *= strategy_factor
    
    def apply_pending_discounts(self):
        """Force application of all pending discount factors."""
        for infoset in list(self.regrets.keys()):
            self._apply_pending_regret_discount(infoset)
        for infoset in list(self.strategy_sum.keys()):
            self._apply_pending_strategy_discount(infoset)
    
    def should_prune(self, infoset: str, actions: List[AbstractAction], threshold: float) -> bool:
        """Check if all actions at infoset have regret below threshold."""
        if infoset not in self.regrets:
            return False
        
        self._apply_pending_regret_discount(infoset)
        
        _, regret_values = self.regrets[infoset]
        return bool(np.all(regret_values < threshold))
    
    def get_state(self) -> Dict:
        """Get complete storage state for checkpointing."""
        # Apply all pending discounts
        self.apply_pending_discounts()
        
        # Convert to serializable format
        regrets_serializable = {}
        for infoset, (action_indices, regret_values) in self.regrets.items():
            action_dict = {}
            for idx, value in zip(action_indices, regret_values):
                action = self.action_indexer.get_action(int(idx))
                action_dict[action.value] = float(value)
            regrets_serializable[infoset] = action_dict
        
        strategy_sum_serializable = {}
        for infoset, (action_indices, strategy_values) in self.strategy_sum.items():
            action_dict = {}
            for idx, value in zip(action_indices, strategy_values):
                action = self.action_indexer.get_action(int(idx))
                action_dict[action.value] = float(value)
            strategy_sum_serializable[infoset] = action_dict
        
        return {
            'regrets': regrets_serializable,
            'strategy_sum': strategy_sum_serializable,
            'cumulative_regret_discount': self._cumulative_regret_discount,
            'cumulative_strategy_discount': self._cumulative_strategy_discount,
            'storage_mode': 'compact'
        }
    
    def set_state(self, state: Dict):
        """Restore storage state from checkpoint."""
        # Rebuild action indexer
        self.action_indexer = ActionIndexer()
        
        # Restore regrets
        self.regrets = {}
        for infoset, action_dict in state['regrets'].items():
            action_indices = []
            regret_values = []
            
            for action_str, regret in action_dict.items():
                action = AbstractAction(action_str)
                action_idx = self.action_indexer.get_or_create_index(action)
                action_indices.append(action_idx)
                regret_values.append(regret)
            
            self.regrets[infoset] = (
                np.array(action_indices, dtype=np.int32),
                np.array(regret_values, dtype=np.float32)
            )
        
        # Restore strategy_sum
        self.strategy_sum = {}
        for infoset, action_dict in state['strategy_sum'].items():
            action_indices = []
            strategy_values = []
            
            for action_str, prob in action_dict.items():
                action = AbstractAction(action_str)
                action_idx = self.action_indexer.get_or_create_index(action)
                action_indices.append(action_idx)
                strategy_values.append(prob)
            
            self.strategy_sum[infoset] = (
                np.array(action_indices, dtype=np.int32),
                np.array(strategy_values, dtype=np.float32)
            )
        
        # Restore discount tracking
        self._cumulative_regret_discount = state.get('cumulative_regret_discount', 1.0)
        self._cumulative_strategy_discount = state.get('cumulative_strategy_discount', 1.0)
        
        self._regret_discount_applied = {
            infoset: self._cumulative_regret_discount for infoset in self.regrets
        }
        self._strategy_discount_applied = {
            infoset: self._cumulative_strategy_discount for infoset in self.strategy_sum
        }
    
    def get_memory_usage(self) -> Dict[str, int]:
        """Estimate memory usage in bytes."""
        import sys
        
        regrets_size = 0
        for action_indices, regret_values in self.regrets.values():
            regrets_size += action_indices.nbytes + regret_values.nbytes
        
        strategy_size = 0
        for action_indices, strategy_values in self.strategy_sum.values():
            strategy_size += action_indices.nbytes + strategy_values.nbytes
        
        overhead_size = sys.getsizeof(self.regrets) + sys.getsizeof(self.strategy_sum)
        
        return {
            'regrets_bytes': regrets_size,
            'strategy_bytes': strategy_size,
            'overhead_bytes': overhead_size,
            'total_bytes': regrets_size + strategy_size + overhead_size,
            'num_infosets_regrets': len(self.regrets),
            'num_infosets_strategy': len(self.strategy_sum)
        }
