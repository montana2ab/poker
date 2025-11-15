"""Compact storage backend for MCCFR regrets and strategies.

This module provides memory-efficient storage using numpy arrays with int32/float32
types instead of Python dicts with float64 values. Useful for large-scale training
where memory is constrained.

Key features:
- Uses numpy arrays for dense storage
- Action indexing instead of dict keys
- Supports int32 for regrets (with floor), float32 for strategies
- Compatible with existing RegretTracker API
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from holdem.abstraction.actions import AbstractAction


# Pluribus-style regret floor for stability
REGRET_FLOOR = -310_000_000


class StorageBackend(ABC):
    """Abstract base class for regret/strategy storage backends."""
    
    @abstractmethod
    def get_regret(self, infoset: str, action: AbstractAction) -> float:
        """Get cumulative regret for action at infoset."""
        pass
    
    @abstractmethod
    def update_regret(self, infoset: str, action: AbstractAction, regret: float, weight: float = 1.0):
        """Update cumulative regret."""
        pass
    
    @abstractmethod
    def get_strategy_sum(self, infoset: str, action: AbstractAction) -> float:
        """Get cumulative strategy sum for action at infoset."""
        pass
    
    @abstractmethod
    def add_strategy(self, infoset: str, action: AbstractAction, prob: float, weight: float = 1.0):
        """Add to cumulative strategy."""
        pass
    
    @abstractmethod
    def get_all_regrets(self, infoset: str) -> Dict[AbstractAction, float]:
        """Get all regrets for an infoset."""
        pass
    
    @abstractmethod
    def get_all_strategy_sums(self, infoset: str) -> Dict[AbstractAction, float]:
        """Get all strategy sums for an infoset."""
        pass
    
    @abstractmethod
    def has_infoset_regrets(self, infoset: str) -> bool:
        """Check if infoset has regret data."""
        pass
    
    @abstractmethod
    def has_infoset_strategy(self, infoset: str) -> bool:
        """Check if infoset has strategy data."""
        pass
    
    @abstractmethod
    def apply_discount_to_infoset_regrets(self, infoset: str, factor: float):
        """Apply discount factor to all regrets at infoset."""
        pass
    
    @abstractmethod
    def apply_discount_to_infoset_strategy(self, infoset: str, factor: float):
        """Apply discount factor to all strategy sums at infoset."""
        pass
    
    @abstractmethod
    def get_all_infosets_regrets(self) -> List[str]:
        """Get list of all infosets with regret data."""
        pass
    
    @abstractmethod
    def get_all_infosets_strategy(self) -> List[str]:
        """Get list of all infosets with strategy data."""
        pass
    
    @abstractmethod
    def reset_negative_regrets(self, infoset: str):
        """Reset negative regrets to 0 for CFR+."""
        pass
    
    @abstractmethod
    def get_state(self) -> Dict:
        """Get serializable state for checkpointing."""
        pass
    
    @abstractmethod
    def set_state(self, state: Dict):
        """Restore from checkpoint state."""
        pass


class DenseStorage(StorageBackend):
    """Dense storage using Python dicts (current implementation).
    
    This is the default storage mode, using:
    - Dict[str, Dict[AbstractAction, float]] for regrets
    - Dict[str, Dict[AbstractAction, float]] for strategy_sum
    - Full float64 precision
    """
    
    def __init__(self):
        self.regrets: Dict[str, Dict[AbstractAction, float]] = {}
        self.strategy_sum: Dict[str, Dict[AbstractAction, float]] = {}
    
    def get_regret(self, infoset: str, action: AbstractAction) -> float:
        if infoset not in self.regrets:
            return 0.0
        return self.regrets[infoset].get(action, 0.0)
    
    def update_regret(self, infoset: str, action: AbstractAction, regret: float, weight: float = 1.0):
        if infoset not in self.regrets:
            self.regrets[infoset] = {}
        current = self.regrets[infoset].get(action, 0.0)
        self.regrets[infoset][action] = current + weight * regret
    
    def get_strategy_sum(self, infoset: str, action: AbstractAction) -> float:
        if infoset not in self.strategy_sum:
            return 0.0
        return self.strategy_sum[infoset].get(action, 0.0)
    
    def add_strategy(self, infoset: str, action: AbstractAction, prob: float, weight: float = 1.0):
        if infoset not in self.strategy_sum:
            self.strategy_sum[infoset] = {}
        current = self.strategy_sum[infoset].get(action, 0.0)
        self.strategy_sum[infoset][action] = current + prob * weight
    
    def get_all_regrets(self, infoset: str) -> Dict[AbstractAction, float]:
        return self.regrets.get(infoset, {}).copy()
    
    def get_all_strategy_sums(self, infoset: str) -> Dict[AbstractAction, float]:
        return self.strategy_sum.get(infoset, {}).copy()
    
    def has_infoset_regrets(self, infoset: str) -> bool:
        return infoset in self.regrets
    
    def has_infoset_strategy(self, infoset: str) -> bool:
        return infoset in self.strategy_sum
    
    def apply_discount_to_infoset_regrets(self, infoset: str, factor: float):
        if infoset in self.regrets:
            for action in self.regrets[infoset]:
                self.regrets[infoset][action] *= factor
    
    def apply_discount_to_infoset_strategy(self, infoset: str, factor: float):
        if infoset in self.strategy_sum:
            for action in self.strategy_sum[infoset]:
                self.strategy_sum[infoset][action] *= factor
    
    def get_all_infosets_regrets(self) -> List[str]:
        return list(self.regrets.keys())
    
    def get_all_infosets_strategy(self) -> List[str]:
        return list(self.strategy_sum.keys())
    
    def reset_negative_regrets(self, infoset: str):
        if infoset in self.regrets:
            for action in self.regrets[infoset]:
                if self.regrets[infoset][action] < 0:
                    self.regrets[infoset][action] = 0.0
    
    def get_state(self) -> Dict:
        """Get state for serialization."""
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
            'storage_mode': 'dense',
            'regrets': regrets_serializable,
            'strategy_sum': strategy_sum_serializable
        }
    
    def set_state(self, state: Dict):
        """Restore from checkpoint."""
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


class CompactStorage(StorageBackend):
    """Compact storage using numpy arrays with int32/float32.
    
    Memory savings:
    - Uses int32 for regrets (4 bytes vs 8 bytes for float64) = 50% savings
    - Uses float32 for strategies (4 bytes vs 8 bytes) = 50% savings
    - Action indexing instead of dict keys reduces overhead
    - Overall: 40-50% memory reduction for large tables
    
    Limitations:
    - Regrets floored at -310M (Pluribus-style)
    - Slightly reduced precision (int32 for regrets, float32 for strategies)
    - Integer rounding for regret values
    
    Trade-offs:
    - Memory: ~50% reduction
    - Precision: Sufficient for CFR convergence (tested in Pluribus)
    - Speed: Comparable or slightly faster due to better cache locality
    """
    
    def __init__(self):
        # Map infoset -> (action_to_idx, regret_array, strategy_array)
        self._infosets: Dict[str, Tuple[Dict[AbstractAction, int], np.ndarray, np.ndarray]] = {}
        self.regret_floor = REGRET_FLOOR
    
    def _ensure_infoset_regrets(self, infoset: str, action: AbstractAction):
        """Ensure infoset exists in storage, create if needed."""
        if infoset not in self._infosets:
            # Initialize with single action
            action_to_idx = {action: 0}
            regret_array = np.zeros(1, dtype=np.int32)
            strategy_array = np.zeros(1, dtype=np.float32)
            self._infosets[infoset] = (action_to_idx, regret_array, strategy_array)
        else:
            action_to_idx, regret_array, strategy_array = self._infosets[infoset]
            if action not in action_to_idx:
                # Add new action
                idx = len(action_to_idx)
                action_to_idx[action] = idx
                # Expand arrays
                new_regret = np.zeros(len(action_to_idx), dtype=np.int32)
                new_strategy = np.zeros(len(action_to_idx), dtype=np.float32)
                new_regret[:len(regret_array)] = regret_array
                new_strategy[:len(strategy_array)] = strategy_array
                self._infosets[infoset] = (action_to_idx, new_regret, new_strategy)
    
    def get_regret(self, infoset: str, action: AbstractAction) -> float:
        if infoset not in self._infosets:
            return 0.0
        action_to_idx, regret_array, _ = self._infosets[infoset]
        if action not in action_to_idx:
            return 0.0
        idx = action_to_idx[action]
        return float(regret_array[idx])
    
    def update_regret(self, infoset: str, action: AbstractAction, regret: float, weight: float = 1.0):
        self._ensure_infoset_regrets(infoset, action)
        action_to_idx, regret_array, strategy_array = self._infosets[infoset]
        idx = action_to_idx[action]
        
        # Update with weighted regret
        current = float(regret_array[idx])
        new_value = current + weight * regret
        
        # Apply floor and convert to int32
        new_value = max(new_value, self.regret_floor)
        new_value = np.clip(new_value, self.regret_floor, np.iinfo(np.int32).max)
        regret_array[idx] = int(new_value)
    
    def get_strategy_sum(self, infoset: str, action: AbstractAction) -> float:
        if infoset not in self._infosets:
            return 0.0
        action_to_idx, _, strategy_array = self._infosets[infoset]
        if action not in action_to_idx:
            return 0.0
        idx = action_to_idx[action]
        return float(strategy_array[idx])
    
    def add_strategy(self, infoset: str, action: AbstractAction, prob: float, weight: float = 1.0):
        self._ensure_infoset_regrets(infoset, action)
        action_to_idx, regret_array, strategy_array = self._infosets[infoset]
        idx = action_to_idx[action]
        
        # Update with weighted probability
        current = float(strategy_array[idx])
        new_value = current + prob * weight
        strategy_array[idx] = np.float32(new_value)
    
    def get_all_regrets(self, infoset: str) -> Dict[AbstractAction, float]:
        if infoset not in self._infosets:
            return {}
        action_to_idx, regret_array, _ = self._infosets[infoset]
        return {action: float(regret_array[idx]) for action, idx in action_to_idx.items()}
    
    def get_all_strategy_sums(self, infoset: str) -> Dict[AbstractAction, float]:
        if infoset not in self._infosets:
            return {}
        action_to_idx, _, strategy_array = self._infosets[infoset]
        return {action: float(strategy_array[idx]) for action, idx in action_to_idx.items()}
    
    def has_infoset_regrets(self, infoset: str) -> bool:
        return infoset in self._infosets
    
    def has_infoset_strategy(self, infoset: str) -> bool:
        return infoset in self._infosets
    
    def apply_discount_to_infoset_regrets(self, infoset: str, factor: float):
        if infoset in self._infosets:
            action_to_idx, regret_array, strategy_array = self._infosets[infoset]
            # Apply discount, respecting floor and int32 range
            for i in range(len(regret_array)):
                current = float(regret_array[i])
                new_value = current * factor
                new_value = max(new_value, self.regret_floor)
                new_value = np.clip(new_value, self.regret_floor, np.iinfo(np.int32).max)
                regret_array[i] = int(new_value)
    
    def apply_discount_to_infoset_strategy(self, infoset: str, factor: float):
        if infoset in self._infosets:
            action_to_idx, regret_array, strategy_array = self._infosets[infoset]
            strategy_array *= np.float32(factor)
    
    def get_all_infosets_regrets(self) -> List[str]:
        return list(self._infosets.keys())
    
    def get_all_infosets_strategy(self) -> List[str]:
        return list(self._infosets.keys())
    
    def reset_negative_regrets(self, infoset: str):
        if infoset in self._infosets:
            action_to_idx, regret_array, strategy_array = self._infosets[infoset]
            # Set all negative regrets to 0
            regret_array[regret_array < 0] = 0
    
    def get_state(self) -> Dict:
        """Get state for serialization."""
        regrets_serializable = {}
        strategy_sum_serializable = {}
        
        for infoset, (action_to_idx, regret_array, strategy_array) in self._infosets.items():
            regrets_serializable[infoset] = {
                action.value: float(regret_array[idx])
                for action, idx in action_to_idx.items()
            }
            strategy_sum_serializable[infoset] = {
                action.value: float(strategy_array[idx])
                for action, idx in action_to_idx.items()
            }
        
        return {
            'storage_mode': 'compact',
            'regret_floor': self.regret_floor,
            'regrets': regrets_serializable,
            'strategy_sum': strategy_sum_serializable
        }
    
    def set_state(self, state: Dict):
        """Restore from checkpoint."""
        self._infosets = {}
        
        # Restore regrets and strategies
        regrets = state['regrets']
        strategy_sum = state['strategy_sum']
        
        # Build compact storage from serialized data
        for infoset in regrets.keys():
            action_dict = regrets[infoset]
            strategy_dict = strategy_sum.get(infoset, {})
            
            # Create action mapping
            actions = [AbstractAction(action_str) for action_str in action_dict.keys()]
            action_to_idx = {action: i for i, action in enumerate(actions)}
            
            # Create arrays
            regret_array = np.zeros(len(actions), dtype=np.int32)
            strategy_array = np.zeros(len(actions), dtype=np.float32)
            
            # Fill arrays
            for action, idx in action_to_idx.items():
                regret_val = action_dict[action.value]
                regret_val = max(regret_val, self.regret_floor)
                regret_val = np.clip(regret_val, self.regret_floor, np.iinfo(np.int32).max)
                regret_array[idx] = int(regret_val)
                
                if action.value in strategy_dict:
                    strategy_array[idx] = np.float32(strategy_dict[action.value])
            
            self._infosets[infoset] = (action_to_idx, regret_array, strategy_array)
    
    def get_memory_stats(self) -> Dict:
        """Get memory usage statistics."""
        num_infosets = len(self._infosets)
        total_actions = sum(len(action_to_idx) for action_to_idx, _, _ in self._infosets.values())
        
        # Calculate memory usage
        # Compact: int32 (4 bytes) + float32 (4 bytes) per action
        compact_bytes = total_actions * (4 + 4)
        
        # Dense would use: float64 (8 bytes) + float64 (8 bytes) per action
        # Plus dict overhead (approx 200 bytes per infoset + 70 bytes per action entry)
        dense_bytes = total_actions * (8 + 8) + num_infosets * 200 + total_actions * 70
        
        saved_bytes = dense_bytes - compact_bytes
        percent_saved = (saved_bytes / dense_bytes * 100) if dense_bytes > 0 else 0
        
        return {
            'num_infosets': num_infosets,
            'total_actions': total_actions,
            'compact_mb': compact_bytes / (1024 * 1024),
            'dense_mb': dense_bytes / (1024 * 1024),
            'saved_mb': saved_bytes / (1024 * 1024),
            'percent_saved': percent_saved
        }
