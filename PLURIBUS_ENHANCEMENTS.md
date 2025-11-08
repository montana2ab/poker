# Pluribus-Style Enhancements Implementation

This document describes the implementation of Pluribus-inspired enhancements to the poker AI system.

## Overview

Four major features have been added:

1. **Real-time depth-limited resolver (rt_resolver/)** - Bounded subgame resolution for real-time play
2. **Action abstraction + translation** - Proper action discretization and client translation
3. **Practical card abstraction** - Robust bucket builders for flop/turn/river
4. **Hardened multi-player MCCFR** - External sampling with negative regret pruning

## 1. Real-time Depth-Limited Resolver

### Location
- `src/holdem/rt_resolver/`

### Components

#### SubgameBuilder (`subgame_builder.py`)
Constructs bounded subgames from current game state:
- Freezes action history up to current state
- Restricts action set based on mode (tight/balanced/loose)
- Limits depth to `max_depth` streets ahead

```python
from holdem.rt_resolver.subgame_builder import SubgameBuilder, SubgameState
from holdem.abstraction.action_translator import ActionSetMode

builder = SubgameBuilder(
    max_depth=1,  # Look ahead 1 street
    action_set_mode=ActionSetMode.BALANCED
)

root = builder.build_from_state(table_state, history=[])
actions = builder.get_actions(root, stack=200.0, in_position=True)
```

#### LeafEvaluator (`leaf_evaluator.py`)
Evaluates terminal nodes (leaves) using:
- Blueprint counterfactual values (CFV) when available
- Rollouts using blueprint strategy (configurable samples)
- Reduced action set for speed

```python
from holdem.rt_resolver.leaf_evaluator import LeafEvaluator

evaluator = LeafEvaluator(
    blueprint=blueprint_policy,
    num_rollout_samples=10,
    use_cfv=True  # Try CFV first, fallback to rollout
)

value = evaluator.evaluate(state, hero_hand, villain_range, hero_position)
```

#### DepthLimitedCFR (`depth_limited_cfr.py`)
CFR solver with small iteration budget and time constraints:
- Iteration budget: 400-1200 (configurable)
- Time limit: 80ms default (configurable)
- KL regularization toward blueprint
- Warm-start from blueprint strategy

```python
from holdem.rt_resolver.depth_limited_cfr import DepthLimitedCFR

solver = DepthLimitedCFR(
    blueprint=blueprint_policy,
    subgame_builder=builder,
    leaf_evaluator=evaluator,
    min_iterations=400,
    max_iterations=1200,
    time_limit_ms=80,
    kl_weight=0.5
)

strategy = solver.solve(root_state, hero_hand, villain_range, hero_position)
metrics = solver.get_metrics()
```

### Configuration

Add to your config file:

```yaml
rt:
  max_depth: 1
  time_ms: 80
  min_iterations: 400
  max_iterations: 1200
  samples_per_leaf: 10
  action_set_mode: "balanced"  # tight, balanced, or loose
  use_cfv: true
  kl_weight: 0.5
  track_metrics: true
```

Or in Python:

```python
from holdem.types import RTResolverConfig

config = RTResolverConfig(
    max_depth=1,
    time_ms=80,
    min_iterations=400,
    max_iterations=1200,
    samples_per_leaf=10,
    action_set_mode="balanced",
    kl_weight=0.5
)
```

### Metrics

The solver tracks:
- `solve_time_ms`: Time taken to solve (milliseconds)
- `iterations`: Number of CFR iterations performed
- `ev_delta_bbs`: EV difference vs blueprint (big blinds)
- `time_per_iteration_ms`: Average time per iteration

## 2. Action Abstraction + Translation

### Location
- `src/holdem/abstraction/action_translator.py`

### Features

#### ActionTranslator
Converts between discrete action IDs and legal poker actions:
- `to_discrete()`: Convert legal moves to discrete action ID
- `to_client()`: Convert action ID to client-specific action
- Handles min-raise constraints, all-in capping, chip rounding
- PokerStars compliance

```python
from holdem.abstraction.action_translator import ActionTranslator, ActionSetMode, LegalConstraints

translator = ActionTranslator(mode=ActionSetMode.BALANCED)

# Discrete action sets per street
flop_actions = translator.get_action_set(Street.FLOP)
# Returns: [0.33, 0.66, 1.0, 1.5] (pot fractions)

# Convert to client action
constraints = LegalConstraints(
    min_raise=2.0,
    max_bet=200.0,
    min_chip=0.01
)

action = translator.to_client(
    action_id=3,  # Pot-sized bet
    pot=100.0,
    stack=200.0,
    constraints=constraints,
    street=Street.FLOP
)

# Test idempotence
is_close, ev_distance = translator.round_trip_test(
    action, pot=100.0, stack=200.0, constraints=constraints, epsilon=0.05
)
```

#### Action Set Modes

- **TIGHT**: 3-4 actions per street (minimal set)
- **BALANCED**: 4-6 actions per street (recommended)
- **LOOSE**: 6+ actions per street (full set)

#### Action Sets by Street

```python
ACTION_SETS = {
    Street.FLOP: {
        TIGHT: [0.33, 0.75, 1.0],
        BALANCED: [0.33, 0.66, 1.0, 1.5],
        LOOSE: [0.25, 0.33, 0.5, 0.66, 0.75, 1.0, 1.5]
    },
    Street.TURN: {
        TIGHT: [0.66, 1.0, 1.5],
        BALANCED: [0.5, 1.0, 1.5],
        LOOSE: [0.33, 0.5, 0.66, 1.0, 1.5, 2.0]
    },
    Street.RIVER: {
        TIGHT: [0.75, 1.0, 1.5],
        BALANCED: [0.75, 1.25, 'all-in'],
        LOOSE: [0.5, 0.75, 1.0, 1.25, 1.5, 'all-in']
    }
}
```

## 3. Practical Card Abstraction

### Location
- `abstraction/build_flop.py`
- `abstraction/build_turn.py`
- `abstraction/build_river.py`

### Features

#### Flop Abstraction (5k-10k buckets)
```bash
python abstraction/build_flop.py --buckets 8000 --samples 50000 --seed 42 --output data/abstractions/flop
```

Features:
- E[HS] (expected hand strength)
- E[HS²] (variance)
- Texture bins (paired/monotone/connected)
- Draw potential

#### Turn Abstraction (1k-3k buckets)
```bash
python abstraction/build_turn.py --buckets 2000 --samples 30000 --seed 42 --output data/abstractions/turn
```

Features:
- E[HS] with draw resolution
- Board texture evolution
- Pot odds considerations

#### River Abstraction (200-500 buckets)
```bash
python abstraction/build_river.py --buckets 400 --samples 20000 --seed 42 --output data/abstractions/river
```

Features:
- Exact equity calculation
- Hand ranking with kickers
- Simplified (no draws needed)

### Output Files

Each abstraction generates:
- `{street}_medoids_{n}.npy`: Cluster centers (float32)
- `{street}_normalization_{n}.npz`: Feature normalization parameters
- `{street}_checksum_{n}.txt`: SHA-256 checksum + metadata

### Reproducibility

All scripts use:
- Fixed seed (default: 42)
- K-medoids clustering (or KMeans fallback)
- SHA-256 checksums for verification

## 4. Hardened Multi-player MCCFR

### Location
- `src/holdem/mccfr/external_sampling.py`

### Features

#### External Sampling
More stable than outcome sampling for multi-player games:
- Sample opponent actions from strategies
- Traverse ALL actions for updating player
- Alternates player updates (avoid simultaneous updates)

```python
from holdem.mccfr.external_sampling import ExternalSampler

sampler = ExternalSampler(
    bucketing=bucketing,
    num_players=2,
    use_linear_weighting=True,
    enable_nrp=True,
    nrp_coefficient=1.0,
    strategy_freezing=False
)

# Run with player alternation
for iteration in range(num_iterations):
    updating_player = iteration % num_players
    utility = sampler.sample_iteration(iteration, updating_player)
```

#### Negative Regret Pruning (NRP)
Scheduled threshold: τ(t) = c / √t

```python
# Test different coefficients c ∈ [0.5, 2.0]
sampler = ExternalSampler(
    bucketing=bucketing,
    num_players=2,
    nrp_coefficient=1.5  # Try 0.5, 1.0, 1.5, 2.0
)

threshold = sampler.get_nrp_threshold(iteration=1000)
# Returns: -1.5 / sqrt(1000) ≈ -0.047
```

#### Linear CFR (LCFR)
Weight = iteration number t:

```python
sampler = ExternalSampler(
    bucketing=bucketing,
    num_players=2,
    use_linear_weighting=True  # w_t = t
)
```

#### Strategy Freezing
For blueprint generation (only update regrets, not strategy):

```python
sampler = ExternalSampler(
    bucketing=bucketing,
    num_players=2,
    strategy_freezing=True  # Freeze strategy updates
)
```

## Testing

### Basic Integration Test (no dependencies)
```bash
python tests/test_basic_integration.py
```

### Full Tests (requires dependencies)
```bash
pip install -e .
python tests/test_action_translator.py
python tests/test_external_sampling.py
python tests/test_rt_resolver.py
```

### Test Coverage

#### ActionTranslator
- Basic translation (fold/check/call/bet)
- Min-raise compliance
- All-in capping
- Chip rounding
- Action set modes
- Round-trip idempotence

#### External Sampling
- Initialization
- NRP threshold calculation
- Coefficient range [0.5, 2.0]
- Player alternation
- Strategy freezing
- Linear weighting

#### RT Resolver
- Config management
- SubgameBuilder depth limiting
- Action set restriction by mode
- LeafEvaluator (CFV and rollouts)
- DepthLimitedCFR solving

## Dependencies

Required:
- numpy
- scikit-learn (for KMeans fallback)
- scikit-learn-extra (optional, for K-medoids)

Install:
```bash
pip install numpy scikit-learn
pip install scikit-learn-extra  # Optional, for better k-medoids
```

## Integration Example

```python
from holdem.config import Config
from holdem.mccfr.policy_store import PolicyStore
from holdem.rt_resolver.subgame_builder import SubgameBuilder
from holdem.rt_resolver.leaf_evaluator import LeafEvaluator
from holdem.rt_resolver.depth_limited_cfr import DepthLimitedCFR
from holdem.abstraction.action_translator import ActionTranslator, ActionSetMode

# Load config
config = Config.from_yaml("config.yaml")

# Setup components
blueprint = PolicyStore.load("path/to/blueprint.json")
translator = ActionTranslator(mode=ActionSetMode.BALANCED)

builder = SubgameBuilder(
    max_depth=config.rt.max_depth,
    action_set_mode=ActionSetMode[config.rt.action_set_mode.upper()]
)

evaluator = LeafEvaluator(
    blueprint=blueprint,
    num_rollout_samples=config.rt.samples_per_leaf,
    use_cfv=config.rt.use_cfv
)

solver = DepthLimitedCFR(
    blueprint=blueprint,
    subgame_builder=builder,
    leaf_evaluator=evaluator,
    min_iterations=config.rt.min_iterations,
    max_iterations=config.rt.max_iterations,
    time_limit_ms=config.rt.time_ms,
    kl_weight=config.rt.kl_weight
)

# Solve during game
root_state = builder.build_from_state(table_state, history)
strategy = solver.solve(root_state, hero_hand, villain_range, hero_position)

# Get action
action_id = max(strategy, key=strategy.get)
legal_action = translator.to_client(
    action_id, pot, stack, constraints, street
)
```

## Performance Recommendations

### RT Resolver
- Use `max_depth=1` for speed (current street only)
- Set `time_ms=80` for real-time play
- Use `action_set_mode="tight"` for faster solving
- Enable `use_cfv=True` to leverage blueprint values

### External Sampling
- Start with `nrp_coefficient=1.0`
- Enable `strategy_freezing=True` for final blueprint
- Use `use_linear_weighting=True` (LCFR)

### Card Abstraction
- Flop: 5k-8k buckets (balance quality/memory)
- Turn: 1k-2k buckets (fewer needed with better features)
- River: 200-400 buckets (exact equity dominates)

## References

- Pluribus: Brown & Sandholm (2019) - "Superhuman AI for multiplayer poker"
- CFR+: Tammelin et al. (2015) - "Solving Heads-Up Limit Texas Hold'em"
- LCFR: Brown et al. (2015) - "Regret-based pruning in extensive games"
