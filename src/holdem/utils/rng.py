"""Random number generation utilities."""

import numpy as np
import random
from typing import Optional, Dict, Any


class RNG:
    """Centralized random number generator."""
    
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
    
    def randint(self, low: int, high: int) -> int:
        """Generate random integer in [low, high)."""
        return self.rng.integers(low, high)
    
    def random(self) -> float:
        """Generate random float in [0.0, 1.0)."""
        return self.rng.random()
    
    def choice(self, arr, size=None, replace=True, p=None):
        """Randomly choose elements from array."""
        return self.rng.choice(arr, size=size, replace=replace, p=p)
    
    def shuffle(self, arr):
        """Shuffle array in-place."""
        self.rng.shuffle(arr)
        return arr
    
    def normal(self, loc=0.0, scale=1.0, size=None):
        """Generate samples from normal distribution."""
        return self.rng.normal(loc, scale, size)
    
    def uniform(self, low=0.0, high=1.0, size=None):
        """Generate samples from uniform distribution."""
        return self.rng.uniform(low, high, size)
    
    def get_state(self) -> Dict[str, Any]:
        """Get the current RNG state for serialization.
        
        Returns:
            Dictionary containing RNG state information
        """
        python_state = random.getstate()
        # Convert tuple to list for JSON serialization
        # Format: (version, tuple_of_ints, gauss_next)
        python_state_serializable = (
            python_state[0],
            list(python_state[1]),  # Convert inner tuple to list
            python_state[2] if len(python_state) > 2 else None
        )
        
        return {
            'seed': self.seed,
            'numpy_state': self.rng.__getstate__(),
            'python_random_state': python_state_serializable
        }
    
    def set_state(self, state: Dict[str, Any]):
        """Restore RNG state from serialized data.
        
        Args:
            state: Dictionary containing RNG state information
        """
        self.seed = state['seed']
        self.rng.__setstate__(state['numpy_state'])
        
        # Restore python random state
        python_state = state['python_random_state']
        # Convert list back to tuple for setstate
        # Format: (version, tuple_of_ints, gauss_next)
        python_state_tuple = (
            python_state[0],
            tuple(python_state[1]),  # Convert inner list back to tuple
            python_state[2] if len(python_state) > 2 else None
        )
        random.setstate(python_state_tuple)


# Global RNG instance
_global_rng: Optional[RNG] = None


def get_rng(seed: Optional[int] = None) -> RNG:
    """Get global RNG instance."""
    global _global_rng
    if _global_rng is None or seed is not None:
        _global_rng = RNG(seed)
    return _global_rng


def set_seed(seed: int):
    """Set global random seed."""
    global _global_rng
    _global_rng = RNG(seed)
    np.random.seed(seed)
