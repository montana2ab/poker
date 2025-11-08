# Adaptive Epsilon Schedule

## Overview

The adaptive epsilon schedule feature automatically adjusts exploration rates during MCCFR training based on real-time performance metrics. Unlike fixed schedules, it adapts to the actual machine performance and game tree coverage, ensuring optimal exploration regardless of hardware capabilities.

## Key Features

### Performance-Based Adaptation
- **IPS Monitoring**: Tracks iterations per second averaged over a configurable window
- **Coverage Tracking**: Monitors infoset discovery rate (new infosets per 1000 iterations)
- **Adaptive Transitions**: Adjusts epsilon decrease timing based on criteria

### Transition Modes

1. **Standard Transition**: Occurs at scheduled iteration when criteria are met
2. **Early Transition**: Moves to next epsilon level up to 10% earlier when performance exceeds targets
3. **Delayed Transition**: Waits up to 15% longer when performance is below targets
4. **Forced Transition**: Guarantees progression after 30% extension to prevent blocking

## Configuration

### Basic Example

```yaml
# In your MCCFR config YAML
mccfr:
  num_iterations: 2500000
  
  # Standard epsilon schedule (base schedule)
  epsilon_schedule:
    - [0, 0.60]
    - [110000, 0.50]
    - [240000, 0.40]
    - [480000, 0.30]
    - [720000, 0.20]
    - [960000, 0.12]
    - [1020000, 0.08]
  
  # Enable adaptive scheduling
  adaptive_epsilon_enabled: true
  adaptive_target_ips: 35.0                # Expected iterations/second for your machine
  adaptive_window_merges: 10               # Average over last 10 logging intervals
  adaptive_min_infoset_growth: 10.0        # Minimum new infosets per 1000 iterations
  adaptive_early_shift_ratio: 0.1          # Allow up to 10% early transition
  adaptive_extension_ratio: 0.15           # Allow up to 15% delay
  adaptive_force_after_ratio: 0.30         # Force after 30% extension
```

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `adaptive_epsilon_enabled` | `false` | Enable adaptive epsilon scheduling |
| `adaptive_target_ips` | `35.0` | Target iterations per second for your machine |
| `adaptive_window_merges` | `10` | Number of recent merges to average for metrics |
| `adaptive_min_infoset_growth` | `10.0` | Minimum new infosets per 1000 iterations required |
| `adaptive_early_shift_ratio` | `0.1` | Allow epsilon decrease up to 10% earlier |
| `adaptive_extension_ratio` | `0.15` | Allow epsilon decrease delay up to 15% |
| `adaptive_force_after_ratio` | `0.30` | Force epsilon decrease after 30% extension |

## How It Works

### Decision Logic

For each epsilon transition in the base schedule, the scheduler:

1. **Calculates earliest possible transition**: `target_iteration * (1.0 - early_shift_ratio)`
2. **Calculates latest allowed transition**: `target_iteration * (1.0 + extension_ratio)`
3. **Calculates force threshold**: `target_iteration * (1.0 + force_after_ratio)`

At each iteration, it checks:

```python
# Check criteria
ips_ok = average_ips >= 0.9 * target_ips
growth_ok = infoset_growth_rate >= min_infoset_growth
criteria_met = ips_ok and growth_ok

# Decision
if iteration < earliest:
    wait  # Too early
elif iteration < target and super_performance:
    transition_early  # Excellent performance
elif iteration >= target and criteria_met:
    transition  # On time, criteria met
elif iteration >= force_threshold:
    transition  # Force to prevent blocking
elif iteration < latest:
    wait  # Within extension period
else:
    transition  # Extension period expired
```

### Example Scenario

Base schedule has transition at 110,000 iterations from ε=0.6 to ε=0.5.

**Fast Machine (45 iter/s, 20 infosets/k)**:
- Earliest: 99,000 (90% of 110k)
- Criteria met: IPS 45 > 31.5 (0.9 * 35) ✓, growth 20 > 10 ✓
- **Result**: Early transition at ~99,000

**Target Machine (35 iter/s, 12 infosets/k)**:
- At 110,000: IPS 35 > 31.5 ✓, growth 12 > 10 ✓
- **Result**: Standard transition at 110,000

**Slow Machine (20 iter/s, 8 infosets/k)**:
- At 110,000: IPS 20 < 31.5 ✗, growth 8 < 10 ✗
- Latest: 126,500 (115% of 110k)
- Force: 143,000 (130% of 110k)
- **Result**: Delayed transition at 126,500 (or 143,000 if still not meeting criteria)

## TensorBoard Metrics

When adaptive scheduling is enabled, additional metrics are logged:

- `adaptive/ips`: Current iterations per second
- `adaptive/ips_ratio`: Ratio of current IPS to target (1.0 = meeting target)
- `adaptive/infoset_growth`: New infosets per 1000 iterations
- `adaptive/growth_ratio`: Ratio of current growth to minimum (1.0 = meeting minimum)

View these metrics:
```bash
tensorboard --logdir ./logs/tensorboard
```

## Determining Your Target IPS

Run a short training session to measure your machine's performance:

```python
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver

config = MCCFRConfig(num_iterations=50000)
bucketing = HandBucketing.load("assets/abstraction/buckets.pkl")
solver = MCCFRSolver(config, bucketing)

import time
start = time.time()
solver.train()
elapsed = time.time() - start
ips = 50000 / elapsed

print(f"Your machine: {ips:.1f} iterations/second")
print(f"Set adaptive_target_ips: {ips:.1f}")
```

## Best Practices

### 1. Calibrate Target IPS
- Run test training to measure your machine's actual performance
- Set `adaptive_target_ips` to ~90% of observed peak to allow margin

### 2. Monitor Metrics
- Watch `adaptive/ips_ratio` in TensorBoard
- Value consistently < 0.9 indicates target may be too high
- Value consistently > 1.2 indicates target may be too low

### 3. Adjust Growth Threshold
- Higher `adaptive_min_infoset_growth` for complex games
- Lower for simpler abstractions or later training phases
- Monitor `adaptive/growth_ratio` for guidance

### 4. Use with Time-Based Training
Adaptive scheduling works well with time-budget training:

```yaml
mccfr:
  time_budget_seconds: 691200  # 8 days
  adaptive_epsilon_enabled: true
  epsilon_schedule:
    - [0, 0.60]
    - [110000, 0.50]
    # ... rest of schedule
```

## Comparison with Fixed Schedule

| Fixed Schedule | Adaptive Schedule |
|----------------|-------------------|
| Same timing on all machines | Adjusts to machine capability |
| May be too fast for slow hardware | Delays when needed |
| May be too slow for fast hardware | Accelerates when possible |
| No coverage awareness | Monitors infoset discovery |
| Predictable but inflexible | Flexible and robust |

## Example Output

With adaptive scheduling enabled:

```
INFO     Adaptive epsilon scheduler initialized
INFO       Target IPS: 35.0
INFO       Min infoset growth: 10.0 per 1000 iterations
INFO       Early shift ratio: 10.0%
INFO       Extension ratio: 15.0%
INFO       Force after ratio: 30.0%

...

INFO     Early epsilon transition to 0.500 at iteration 99000 
         (IPS: 42.3/35.0, growth: 18.5/10.0)

...

INFO     Delaying epsilon transition (waiting for criteria, 
         IPS: 28.1/35.0, growth: 8.2/10.0)

...

INFO     Epsilon transition to 0.400 at iteration 248000 
         (IPS: 32.7/35.0, growth: 11.3/10.0)
```

## Troubleshooting

### Issue: Epsilon never decreases
**Cause**: Criteria never met, extension period expires repeatedly
**Solution**: 
- Lower `adaptive_target_ips`
- Lower `adaptive_min_infoset_growth`
- Check machine resources (CPU, RAM)

### Issue: Transitions happen too quickly
**Cause**: Machine exceeds targets significantly
**Solution**:
- Increase `adaptive_target_ips`
- Reduce `adaptive_early_shift_ratio`

### Issue: Training gets stuck
**Cause**: Force transition threshold not being reached
**Solution**: 
- This shouldn't happen - force threshold guarantees progress
- Check logs for transition messages
- Verify `adaptive_force_after_ratio` is set (default: 0.30)

## Testing

Run the test suite:
```bash
pytest tests/test_adaptive_epsilon.py -v
pytest tests/test_adaptive_epsilon_integration.py -v
```

## Implementation Details

The adaptive scheduler is implemented in `src/holdem/mccfr/adaptive_epsilon.py` and integrated into both `MCCFRSolver` and `ParallelMCCFRSolver`. It uses a sliding window to track recent performance and makes decisions at each logging interval (typically every 10,000 iterations).

For more details, see the source code documentation.
