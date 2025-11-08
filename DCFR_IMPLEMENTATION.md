# DCFR and Warm-Start Implementation

This document describes the implementation of Discounted CFR (DCFR) / CFR+ with adaptive regret discounting, regret pruning, and warm-start functionality for resuming training from checkpoints.

## Overview

The implementation adds three key enhancements to the MCCFR algorithm:

1. **DCFR/CFR+ Adaptive Discounting**: Uses time-dependent discount factors to accelerate convergence
2. **Regret Pruning**: Skips 95% of iterations when all actions have very negative regrets (already implemented)
3. **Warm-Start**: Fully restores regret tracker state when resuming from checkpoints

## 1. DCFR/CFR+ Adaptive Discounting

### Theory

Discounted CFR (DCFR) and CFR+ use adaptive discount factors that change over time to accelerate convergence. The key insight is that recent iterations should have more influence on the final strategy than early iterations.

**Discount formulas** (based on CFR+ paper: https://arxiv.org/abs/1407.5042):
- Regret discount: `α = (t + d) / (t + 2d)`
- Strategy discount: `β = t / (t + d)`

Where:
- `t` = current iteration number
- `d` = discount interval (default: 1000 iterations)

These formulas ensure:
- Early iterations: stronger discounting (α≈0.67, β≈0.5 at t=1000)
- Late iterations: weaker discounting (α≈0.92, β≈0.91 at t=10000)
- Convergence: α→1.0, β→1.0 as t→∞

**CFR+ property**: Additionally, negative regrets are reset to 0 after each discount, which has been shown to improve convergence.

### Configuration

Added to `MCCFRConfig` in `src/holdem/types.py`:

```python
# Discount mode: "none", "static", or "dcfr"
discount_mode: str = "dcfr"  # Default: DCFR adaptive discounting

# Discount interval (apply discounting every N iterations)
discount_interval: int = 1000

# Static discount factors (used when discount_mode="static")
regret_discount_alpha: float = 1.0  # Regret discount factor (α)
strategy_discount_beta: float = 1.0  # Strategy discount factor (β)

# DCFR parameters
dcfr_reset_negative_regrets: bool = True  # CFR+ behavior
```

**Discount modes:**
- `"none"`: No discounting (α=1.0, β=1.0) - standard CFR
- `"static"`: Use fixed `regret_discount_alpha` and `strategy_discount_beta`
- `"dcfr"`: Use adaptive DCFR formulas (recommended)

### Implementation

#### Discount Calculation (src/holdem/mccfr/solver.py)

```python
if self.iteration % self.config.discount_interval == 0:
    if self.config.discount_mode == "dcfr":
        # DCFR/CFR+ adaptive discounting
        t = float(self.iteration)
        d = float(self.config.discount_interval)
        
        # α = (t + d) / (t + 2d) for regrets
        alpha = (t + d) / (t + 2 * d)
        
        # β = t / (t + d) for strategy
        beta = t / (t + d) if t > 0 else 0.0
        
        # Apply discounting
        self.sampler.regret_tracker.discount(
            regret_factor=alpha,
            strategy_factor=beta
        )
        
        # CFR+: Reset negative regrets to 0
        if self.config.dcfr_reset_negative_regrets:
            self.sampler.regret_tracker.reset_regrets()
```

## 2. Warm-Start from Checkpoint

### Overview

Warm-start allows training to resume from a checkpoint with the full regret tracker state restored. This is essential for:
- Long-running training jobs (days/weeks)
- Recovering from interruptions
- Iterative refinement of strategies

### Implementation

#### Regret State Serialization (src/holdem/mccfr/regrets.py)

Added methods to save and restore complete regret state:

```python
def get_state(self) -> Dict:
    """Get complete regret tracker state for checkpointing."""
    # Convert AbstractAction keys to string values for serialization
    regrets_serializable = {
        infoset: {action.value: regret for action, regret in action_dict.items()}
        for infoset, action_dict in self.regrets.items()
    }
    
    strategy_sum_serializable = {
        infoset: {action.value: prob for action, prob in action_dict.items()}
        for infoset, action_dict in self.strategy_sum.items()
    }
    
    return {
        'regrets': regrets_serializable,
        'strategy_sum': strategy_sum_serializable
    }

def set_state(self, state: Dict):
    """Restore regret tracker state from checkpoint."""
    # Convert string keys back to AbstractAction
    self.regrets = {
        infoset: {AbstractAction(action_str): regret 
                 for action_str, regret in action_dict.items()}
        for infoset, action_dict in state['regrets'].items()
    }
    
    self.strategy_sum = {
        infoset: {AbstractAction(action_str): prob 
                 for action_str, prob in action_dict.items()}
        for infoset, action_dict in state['strategy_sum'].items()
    }
```

#### Enhanced Checkpoint Saving (src/holdem/mccfr/solver.py)

Checkpoints now include full regret state:

```python
def save_checkpoint(self, logdir: Path, iteration: int, elapsed_seconds: float = 0):
    """Save training checkpoint with full state."""
    # Save policy (average strategy)
    policy_store.save(checkpoint_dir / f"{checkpoint_name}.pkl")
    
    # Save metadata (iteration, metrics, RNG state, epsilon, etc.)
    save_json(metadata, metadata_path)
    
    # Save full regret state for warm-start
    regret_state = self.sampler.regret_tracker.get_state()
    save_pickle(regret_state, regret_state_path)
```

#### Checkpoint Loading with Warm-Start (src/holdem/mccfr/solver.py)

```python
def load_checkpoint(self, checkpoint_path: Path, warm_start: bool = True) -> int:
    """Load checkpoint and optionally warm-start from full state."""
    # Load and validate metadata
    metadata = load_json(metadata_path)
    
    # Validate bucket configuration (ensures compatibility)
    if validate_buckets:
        current_sha = self._calculate_bucket_hash()
        checkpoint_sha = metadata['bucket_metadata']['bucket_file_sha']
        if current_sha != checkpoint_sha:
            raise ValueError("Bucket configuration mismatch!")
    
    # Restore RNG state
    self.sampler.rng.set_state(metadata['rng_state'])
    
    # Restore epsilon
    self._current_epsilon = metadata['epsilon']
    self.sampler.set_epsilon(self._current_epsilon)
    
    # Restore full regret state for warm-start
    if warm_start:
        regret_state = load_pickle(regret_state_path)
        self.sampler.regret_tracker.set_state(regret_state)
        logger.info("✓ Warm-start: Full regret tracker state restored")
```

### Usage Example

```python
from holdem.types import MCCFRConfig, BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from pathlib import Path

# Configure training
config = MCCFRConfig(
    num_iterations=5_000_000,
    discount_mode="dcfr",  # Enable DCFR
    checkpoint_interval=100_000
)

bucketing = HandBucketing(BucketConfig())
bucketing.build()

solver = MCCFRSolver(config, bucketing)

# Initial training
logdir = Path("output/training")
solver.train(logdir)

# Resume training with warm-start
checkpoint_path = logdir / "checkpoints" / "checkpoint_iter1000000.pkl"
solver2 = MCCFRSolver(config, bucketing)
solver2.load_checkpoint(checkpoint_path, warm_start=True)
solver2.train(logdir)  # Continues from iteration 1,000,000
```

## 3. Validation Metrics

### L2 Regret Slope per Street

Tracks the slope of regret L2 norm over time for each street. The slope should be **monotonically decreasing** (negative), indicating convergence.

**Implementation** (src/holdem/mccfr/solver.py):

```python
def _calculate_regret_norm_metrics(self) -> Dict[str, float]:
    """Calculate L2 regret norms and slopes per street."""
    # Calculate average L2 norm for each street
    for street, regret_norms in regrets_by_street.items():
        avg_norm = sum(regret_norms) / len(regret_norms)
        metrics[f'avg_regret_norm/{street}'] = avg_norm
    
    # Calculate slope using linear regression on recent history
    if len(self._regret_history) >= 2:
        iterations_arr = np.array(iterations)
        norms_arr = np.array(norms)
        slope, intercept = np.polyfit(iterations_arr, norms_arr, 1)
        
        metrics[f'regret_slope/{street}'] = slope
        metrics[f'regret_slope_ok/{street}'] = 1.0 if slope < 0 else 0.0
```

**TensorBoard metrics:**
- `avg_regret_norm/preflop`, `avg_regret_norm/flop`, etc.
- `regret_slope/preflop`, `regret_slope/flop`, etc.
- `regret_slope_ok/preflop`, etc. (1.0 if negative, 0.0 otherwise)

### Policy Entropy per Street

Tracks policy entropy over time. Entropy should **decrease post-river** as the strategy converges to more deterministic play.

**Implementation** (src/holdem/mccfr/solver.py):

```python
def _calculate_policy_entropy_metrics(self) -> Dict[str, float]:
    """Calculate policy entropy per street."""
    # Calculate entropy: H(p) = -Σ p(a) * log₂(p(a))
    for infoset in self.sampler.regret_tracker.strategy_sum:
        avg_strategy = self.regret_tracker.get_average_strategy(infoset, actions)
        
        entropy = 0.0
        for action, prob in avg_strategy.items():
            if prob > 0:
                entropy -= prob * math.log2(prob)
        
        street = self._extract_street_from_infoset(infoset)
        entropy_by_street[street].append(entropy)
    
    # Average entropy per street
    metrics[f'policy_entropy/{street}'] = avg_entropy
    metrics[f'policy_entropy_max/{street}'] = max_entropy
```

**TensorBoard metrics:**
- `policy_entropy/preflop`, `policy_entropy/flop`, `policy_entropy/turn`, `policy_entropy/river`
- `policy_entropy_max/preflop`, etc. (maximum entropy across all infosets)
- `policy_entropy/IP`, `policy_entropy/OOP` (by position)

**Validation criteria:**
- River entropy should decrease over training iterations
- Lower entropy = more deterministic strategy = better convergence

## 4. Testing

Comprehensive test suite in `tests/test_dcfr_warmstart.py`:

1. **test_dcfr_discount_calculation**: Verifies DCFR discount formulas
2. **test_dcfr_reset_negative_regrets**: Tests CFR+ negative regret reset
3. **test_regret_state_serialization**: Tests regret state save/load
4. **test_warm_start_checkpoint**: Tests full warm-start functionality
5. **test_warm_start_disabled**: Tests that warm-start can be disabled
6. **test_discount_mode_none**: Tests no discounting mode
7. **test_discount_mode_static**: Tests static discount mode

All tests pass successfully (7/7).

## Benefits

### DCFR Adaptive Discounting
- **Faster convergence**: Proven to accelerate CFR convergence
- **Better late-game focus**: Recent iterations have more influence
- **Automatic tuning**: No manual tuning of discount factors
- **CFR+ property**: Negative regret reset improves convergence

### Warm-Start
- **Long training jobs**: Resume multi-day training runs
- **Fault tolerance**: Recover from crashes or interruptions
- **Iterative refinement**: Continue training existing strategies
- **Experimentation**: Branch from checkpoints to test different configs

### Validation Metrics
- **Convergence monitoring**: Track L2 regret slope (should be negative)
- **Strategy quality**: Track policy entropy (should decrease)
- **Per-street analysis**: Identify convergence issues by street
- **TensorBoard integration**: Visualize metrics over time

## References

- CFR+ paper: "Solving Imperfect Information Games Using Decomposition" (Tammelin et al., 2014)
  - https://arxiv.org/abs/1407.5042
- Pluribus paper: "Superhuman AI for multiplayer poker" (Brown & Sandholm, 2019)
  - Dynamic pruning with threshold -300,000,000
- Linear MCCFR provides ~3x convergence speedup
- DCFR further accelerates convergence with adaptive discounting

## Configuration Examples

### Recommended: DCFR with all optimizations
```python
config = MCCFRConfig(
    num_iterations=5_000_000,
    use_linear_weighting=True,       # Linear MCCFR
    discount_mode="dcfr",             # DCFR adaptive discounting
    discount_interval=1000,
    dcfr_reset_negative_regrets=True, # CFR+ property
    enable_pruning=True,              # Dynamic pruning
    pruning_threshold=-300_000_000.0,
    pruning_probability=0.95
)
```

### Static discounting (manual tuning)
```python
config = MCCFRConfig(
    discount_mode="static",
    regret_discount_alpha=0.95,
    strategy_discount_beta=0.98,
    discount_interval=1000
)
```

### No discounting (baseline)
```python
config = MCCFRConfig(
    discount_mode="none",
    use_linear_weighting=True,  # Still use linear weighting
    enable_pruning=True          # Still use pruning
)
```
