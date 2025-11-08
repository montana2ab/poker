# KL Regularization Enhancement

This document describes the enhanced KL regularization features implemented for the real-time subgame solver.

## Overview

The KL regularization system has been enhanced to provide more fine-grained control over how the solver balances exploration and exploitation based on:
- **Game street** (flop, turn, river)
- **Position** (In Position vs Out Of Position)
- **Blueprint policy clipping** for numerical stability
- **Comprehensive statistics tracking**

## Features

### 1. Street-Based KL Weights

KL weights now vary by street to reflect the increasing importance of staying close to the blueprint strategy as the game progresses:

- **Flop**: `kl_weight = 0.30` (more exploration early)
- **Turn**: `kl_weight = 0.50` (balanced)
- **River**: `kl_weight = 0.70` (more exploitation, stay closer to blueprint)

These values are configurable via `SearchConfig`:

```python
config = SearchConfig(
    kl_weight_flop=0.30,
    kl_weight_turn=0.50,
    kl_weight_river=0.70
)
```

### 2. Position-Based Adjustment

An additional weight bonus is applied when the player is Out Of Position (OOP), reflecting the increased importance of sticking to proven strategies when at a positional disadvantage:

- **OOP Bonus**: `+0.10` added to the street-based weight

Example weights:
- Flop IP: 0.30, Flop OOP: 0.40
- Turn IP: 0.50, Turn OOP: 0.60
- River IP: 0.70, River OOP: 0.80

Configure the OOP bonus:

```python
config = SearchConfig(
    kl_weight_oop_bonus=0.10  # Default value
)
```

### 3. Blueprint Policy Clipping

Blueprint policy probabilities are now clipped to a minimum value before KL divergence calculation to prevent numerical instability:

- **Default clip minimum**: `1e-6`
- Prevents infinity or NaN values in KL calculations
- Ensures well-defined divergence even with very small probabilities

Configure the clipping:

```python
config = SearchConfig(
    blueprint_clip_min=1e-6  # Default value
)
```

### 4. Comprehensive KL Statistics Tracking

The resolver now tracks detailed KL divergence statistics broken down by street and position:

**Statistics collected:**
- **avg**: Mean KL divergence
- **p50**: Median (50th percentile)
- **p90**: 90th percentile
- **p99**: 99th percentile
- **pct_high**: Percentage of iterations with KL > threshold (default 0.3)
- **count**: Number of samples

**Logging example:**
```
INFO: Resolved subgame in 20 iterations (1.0ms) | Street: flop | Position: IP | 
      KL weight: 0.30 | KL stats - avg: 0.4816, p50: 0.4903, p90: 0.5410, 
      p99: 0.5705 | KL>0.3: 100.0%
```

Retrieve statistics programmatically:

```python
resolver = SubgameResolver(config, blueprint)
# ... solve some subgames ...
stats = resolver.get_kl_statistics()

# Access stats by street and position
flop_ip_stats = stats['flop']['IP']
print(f"Avg KL: {flop_ip_stats['avg']:.4f}")
print(f"P90 KL: {flop_ip_stats['p90']:.4f}")
```

### 5. Adaptive KL Weight (Optional Feature)

Configuration options are available for future implementation of adaptive KL weight adjustment:

```python
config = SearchConfig(
    adaptive_kl_weight=False,  # Enable adaptive adjustment
    target_kl_flop=0.12,       # Target KL for flop
    target_kl_turn=0.18,       # Target KL for turn
    target_kl_river=0.25       # Target KL for river
)
```

When `adaptive_kl_weight=True`, the system could automatically adjust weights to achieve target KL values. This feature is prepared but not yet fully implemented.

### 6. Exploit Caller Mode

For a more exploitative strategy against calling-heavy opponents, use lower KL weights:

```python
config = SearchConfig(
    kl_weight_flop=0.15,   # vs default 0.30
    kl_weight_turn=0.30,   # vs default 0.50
    kl_weight_river=0.40   # vs default 0.70
)
```

Lower weights allow more deviation from the blueprint, enabling more aggressive exploitation.

## Usage

### Basic Usage

```python
from holdem.types import SearchConfig, Street
from holdem.realtime.resolver import SubgameResolver
from holdem.mccfr.policy_store import PolicyStore

# Create config with default settings
config = SearchConfig()

# Create resolver
blueprint = PolicyStore(...)  # Load your blueprint strategy
resolver = SubgameResolver(config, blueprint)

# Solve a subgame
strategy = resolver.solve(
    subgame=subgame,
    infoset="some_infoset",
    street=Street.FLOP,
    is_oop=True
)

# Get statistics
stats = resolver.get_kl_statistics()
```

### Custom Configuration

```python
# Configure for aggressive exploitation
config = SearchConfig(
    # Exploit caller mode
    kl_weight_flop=0.15,
    kl_weight_turn=0.30,
    kl_weight_river=0.40,
    
    # Increase OOP bonus
    kl_weight_oop_bonus=0.15,
    
    # Adjust statistics tracking
    track_kl_stats=True,
    kl_high_threshold=0.25,  # Lower threshold
    
    # Blueprint clipping
    blueprint_clip_min=1e-6
)
```

## Implementation Details

### Modified Files

1. **`src/holdem/types.py`**
   - Added street-specific KL weight parameters to `SearchConfig`
   - Added `get_kl_weight()` method to compute dynamic weights
   - Added blueprint clipping and statistics tracking parameters
   - Added adaptive KL configuration options

2. **`src/holdem/realtime/resolver.py`**
   - Updated `__init__()` to initialize KL history tracking
   - Updated `solve()` to accept street and position parameters
   - Updated `_cfr_iteration()` to use dynamic KL weights
   - Updated `_kl_divergence()` to implement blueprint clipping
   - Added `get_kl_statistics()` method for retrieving aggregated stats
   - Enhanced logging to show detailed KL statistics

### Tests

- **`tests/test_kl_regularization.py`**: Original tests (updated for API changes)
- **`tests/test_kl_enhancements.py`**: Comprehensive tests for new features

Run tests:
```bash
python tests/test_kl_regularization.py
python tests/test_kl_enhancements.py
```

## Configuration Reference

### SearchConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `kl_weight_flop` | float | 0.30 | KL weight for flop street |
| `kl_weight_turn` | float | 0.50 | KL weight for turn street |
| `kl_weight_river` | float | 0.70 | KL weight for river street |
| `kl_weight_oop_bonus` | float | 0.10 | Additional weight when OOP |
| `blueprint_clip_min` | float | 1e-6 | Minimum blueprint probability |
| `track_kl_stats` | bool | True | Enable statistics tracking |
| `kl_high_threshold` | float | 0.3 | Threshold for "high KL" metric |
| `adaptive_kl_weight` | bool | False | Enable adaptive adjustment |
| `target_kl_flop` | float | 0.12 | Target KL for flop (adaptive) |
| `target_kl_turn` | float | 0.18 | Target KL for turn (adaptive) |
| `target_kl_river` | float | 0.25 | Target KL for river (adaptive) |

## Recommendations

### Conservative Play (Default)
- Use default weights (0.30/0.50/0.70)
- Stays closer to blueprint strategy
- More robust against unknown opponents

### Exploitative Play
- Use lower weights (0.15/0.30/0.40)
- Allows more deviation from blueprint
- Better against predictable opponents

### Position-Aware
- Keep OOP bonus at 0.10 or higher
- Crucial for playing profitably OOP
- Reduces risk of over-exploitation

## Future Enhancements

1. **Adaptive KL Weight**: Implement automatic adjustment based on observed KL values
2. **Opponent Modeling**: Integrate opponent statistics to dynamically adjust weights
3. **Per-Opponent Profiles**: Save and load weight configurations per opponent type
4. **Real-time Adjustment**: Adjust weights during play based on running statistics

## References

- Original KL regularization implementation: `src/holdem/realtime/resolver.py`
- Subgame solving: Brown & Sandholm (2017) "Superhuman AI for heads-up no-limit poker: Libratus beats top professionals"
- Real-time search with KL regularization: Brown & Sandholm (2019) "Superhuman AI for multiplayer poker"
