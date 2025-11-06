# Linear MCCFR Implementation Summary

This document describes the implementation of Linear MCCFR (LCFR) with discounting and dynamic pruning, as used in the Pluribus poker AI.

## Overview

The implementation adds two key optimizations to the Monte Carlo CFR algorithm:

1. **Linear MCCFR (LCFR)**: Uses linear weighting (∝ t) for regret and strategy updates to accelerate convergence (~3x speedup as reported in Pluribus paper)
2. **Dynamic Pruning**: Skips 95% of iterations when all actions have very negative regrets, except at river and terminal nodes

## 1. Linear MCCFR with Discounting

### Configuration Parameters

Added to `MCCFRConfig` in `src/holdem/types.py`:

```python
# Linear MCCFR parameters
use_linear_weighting: bool = True  # Use Linear MCCFR (weighting ∝ t)
discount_interval: int = 1000  # Apply discounting every N iterations
regret_discount_alpha: float = 1.0  # Regret discount factor (α)
strategy_discount_beta: float = 1.0  # Strategy discount factor (β)
```

### Implementation Details

#### Regret Updates (src/holdem/mccfr/regrets.py)

The `update_regret` method now accepts a `weight` parameter for linear weighting:

```python
def update_regret(self, infoset: str, action: AbstractAction, regret: float, weight: float = 1.0):
    """Update cumulative regret with linear weighting.
    
    Formula: R[I,a] = R[I,a] + weight * regret
    
    For Linear MCCFR: weight = t (iteration number)
    For standard CFR: weight = 1.0
    """
    current = self.regrets[infoset].get(action, 0.0)
    self.regrets[infoset][action] = current + weight * regret
```

#### Strategy Accumulation (src/holdem/mccfr/regrets.py)

The `add_strategy` method uses linear weighting for strategy sum:

```python
def add_strategy(self, infoset: str, strategy: Dict[AbstractAction, float], weight: float = 1.0):
    """Add to cumulative strategy with linear weighting.
    
    Formula: S[I,a] = S[I,a] + weight * π_reach(I) * σ[I,a]
    
    For Linear MCCFR: weight = t * reach_prob
    For standard CFR: weight = reach_prob
    """
    for action, prob in strategy.items():
        current = self.strategy_sum[infoset].get(action, 0.0)
        self.strategy_sum[infoset][action] = current + prob * weight
```

#### Discounting (src/holdem/mccfr/regrets.py)

Separate discount factors for regrets (α) and strategy (β):

```python
def discount(self, regret_factor: float = 1.0, strategy_factor: float = 1.0):
    """Apply discounting at regular intervals.
    
    Formula:
        R[I,a] = α * R[I,a]
        S[I,a] = β * S[I,a]
    """
    for infoset in self.regrets:
        for action in self.regrets[infoset]:
            self.regrets[infoset][action] *= regret_factor
    
    for infoset in self.strategy_sum:
        for action in self.strategy_sum[infoset]:
            self.strategy_sum[infoset][action] *= strategy_factor
```

#### Usage in MCCFR (src/holdem/mccfr/mccfr_os.py)

Linear weighting is applied during CFR recursion:

```python
# Get iteration weight for Linear MCCFR
weight = float(iteration) if self.use_linear_weighting else 1.0

# Update regrets with linear weighting
for action in actions:
    regret = action_utilities.get(action, 0.0) - expected_utility
    self.regret_tracker.update_regret(infoset, action, regret, weight)

# Add to strategy sum with linear weighting (weighted by reach probability)
strategy_weight = weight * reach_prob
self.regret_tracker.add_strategy(infoset, strategy, strategy_weight)
```

#### Solver Integration (src/holdem/mccfr/solver.py)

Discounting is applied at regular intervals during training:

```python
# Apply discounting at regular intervals
if (self.iteration % self.config.discount_interval == 0 and 
    (self.config.regret_discount_alpha < 1.0 or self.config.strategy_discount_beta < 1.0)):
    self.sampler.regret_tracker.discount(
        regret_factor=self.config.regret_discount_alpha,
        strategy_factor=self.config.strategy_discount_beta
    )
```

## 2. Dynamic Pruning

### Configuration Parameters

Added to `MCCFRConfig`:

```python
# Dynamic pruning parameters
enable_pruning: bool = True  # Enable dynamic pruning
pruning_threshold: float = -300_000_000.0  # Regret threshold for pruning
pruning_probability: float = 0.95  # Probability to skip iteration when below threshold
```

### Implementation Details

#### Pruning Logic (src/holdem/mccfr/regrets.py)

Added method to check if all actions have regrets below threshold:

```python
def should_prune(self, infoset: str, actions: List[AbstractAction], threshold: float) -> bool:
    """Check if all actions at infoset have regret below threshold.
    
    Returns True if all actions have regret < threshold, indicating
    that this branch can be pruned in the current iteration.
    """
    if infoset not in self.regrets:
        return False  # No regrets yet, don't prune
    
    for action in actions:
        regret = self.regrets[infoset].get(action, 0.0)
        if regret >= threshold:
            return False  # At least one action above threshold
    
    return True  # All actions below threshold
```

#### CFR Recursion with Pruning (src/holdem/mccfr/mccfr_os.py)

Pruning is applied before processing each information set:

```python
# Dynamic pruning: skip iteration if conditions are met
# Don't prune at river or terminal nodes
is_river = (street == Street.RIVER)
if (self.enable_pruning and 
    not is_river and 
    current_player == sample_player and
    self.regret_tracker.should_prune(infoset, actions, self.pruning_threshold)):
    # Sample q ∈ [0,1) and skip with pruning_probability
    if self.rng.random() < self.pruning_probability:
        # Skip this iteration - return neutral utility
        return 0.0
```

Key aspects:
- Pruning is **disabled at river** (preserves terminal node accuracy)
- Pruning only applies to the **sample player** (not opponent nodes)
- Pruning probability is configurable (default 0.95 = skip 95% of iterations)
- Decision is made **per-iteration** (not per-action) with single RNG call

## Benefits

### Linear MCCFR
- **Faster convergence**: ~3x speedup as reported in Pluribus paper
- **Better late-game focus**: Later iterations have more influence on final strategy
- **Configurable**: Can disable by setting `use_linear_weighting=False`

### Dynamic Pruning
- **Reduced computation**: Skips 95% of iterations for unpromising branches
- **Preserved accuracy**: Never prunes at river or terminal nodes
- **Efficient sampling**: Single RNG call per iteration decision

## Usage Example

```python
from holdem.types import MCCFRConfig, BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver

# Configure Linear MCCFR with discounting and pruning
mccfr_config = MCCFRConfig(
    num_iterations=2_500_000,
    use_linear_weighting=True,  # Enable Linear MCCFR
    discount_interval=1000,      # Discount every 1000 iterations
    regret_discount_alpha=0.95,  # Regret discount factor
    strategy_discount_beta=0.98, # Strategy discount factor
    enable_pruning=True,         # Enable dynamic pruning
    pruning_threshold=-300_000_000.0,  # Pluribus threshold
    pruning_probability=0.95     # Skip 95% when pruning
)

# Create and train solver
bucketing = HandBucketing(BucketConfig())
bucketing.build()

solver = MCCFRSolver(mccfr_config, bucketing)
solver.train()
```

## Testing

Comprehensive test suite in `tests/test_linear_mccfr.py`:

1. **test_linear_weighting_regret_update**: Verifies linear weighting in regret updates
2. **test_linear_weighting_strategy_accumulation**: Verifies linear weighting in strategy sum
3. **test_separate_discount_factors**: Tests independent α and β discount factors
4. **test_should_prune_logic**: Tests pruning threshold logic
5. **test_default_config_values**: Verifies default configuration
6. **test_backward_compatibility**: Ensures old API still works
7. **test_linear_weighting_impact**: Verifies linear weighting gives more weight to later iterations
8. **test_discount_preserves_ratios**: Verifies discounting preserves relative regret ratios

All tests pass successfully (8/8).

## References

- Pluribus paper: "Superhuman AI for multiplayer poker" (Brown & Sandholm, 2019)
- Linear MCCFR provides ~3x convergence speedup
- Dynamic pruning skips 95% of iterations for very negative regrets (< -300,000,000)
- Both optimizations are key to Pluribus's efficiency
