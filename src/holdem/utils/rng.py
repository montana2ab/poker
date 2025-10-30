"""Random number generation utilities."""

import numpy as np
from typing import Optional


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
