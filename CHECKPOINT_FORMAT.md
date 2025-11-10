# MCCFR Checkpoint Format

## Overview

MCCFR training creates "full state" checkpoints that contain all necessary information to resume training exactly where it left off. Each complete checkpoint consists of three files that must be present together.

## Complete Checkpoint Files

A complete checkpoint named `checkpoint_iter{N}_t{T}s` consists of:

### 1. Main Checkpoint File: `checkpoint_iter{N}_t{T}s.pkl`

Contains the policy and strategy data:
- `regrets`: Dictionary of regret values per information set and action
- `strategy_sum`: Cumulative strategy sum for computing average strategy

### 2. Metadata File: `checkpoint_iter{N}_t{T}s_metadata.json`

Contains training state and configuration:
```json
{
  "iteration": 1000,
  "elapsed_seconds": 3600.5,
  "metrics": {
    "avg_regret_preflop": 0.123,
    "avg_regret_flop": 0.234,
    "avg_regret_turn": 0.345,
    "avg_regret_river": 0.456,
    "iterations_per_second": 2.5,
    "total_iterations": 1000,
    "num_infosets": 50000
  },
  "rng_state": {
    "seed": 42,
    "numpy_state": [...],
    "python_random_state": [...]
  },
  "epsilon": 0.6,
  "regret_discount_alpha": 1.0,
  "strategy_discount_beta": 1.0,
  "bucket_metadata": {
    "bucket_file_sha": "abc123...",
    "k_preflop": 169,
    "k_flop": 1000,
    "k_turn": 1000,
    "k_river": 1000,
    "num_samples": 10000,
    "seed": 42
  }
}
```

### 3. Regrets File: `checkpoint_iter{N}_t{T}s_regrets.pkl`

Contains the full regret tracker state for warm-start:
- Complete regret tables
- Complete strategy sum tables
- Internal state needed for exact continuation

## Validation

The system validates checkpoint completeness before loading:

```python
from pathlib import Path
from holdem.mccfr.solver import MCCFRSolver

checkpoint_path = Path("checkpoints/checkpoint_iter1000_t3600s.pkl")

# Check if checkpoint is complete
if MCCFRSolver.is_checkpoint_complete(checkpoint_path):
    print("✓ Complete checkpoint found")
else:
    print("✗ Incomplete checkpoint (missing metadata or regrets file)")
```

## Loading Checkpoints

```python
from holdem.mccfr.solver import MCCFRSolver

solver = MCCFRSolver(config, bucketing)

try:
    iteration = solver.load_checkpoint(
        checkpoint_path,
        validate_buckets=True,  # Verify bucket config matches
        warm_start=True         # Load full regret state
    )
    print(f"✓ Resumed from iteration {iteration}")
except ValueError as e:
    print(f"✗ Cannot load checkpoint: {e}")
```

## Multi-Instance Resume

When resuming multi-instance training, the coordinator:

1. Scans each instance's checkpoint directory
2. Filters out incomplete checkpoints (missing metadata or regrets)
3. Selects the latest complete checkpoint for each instance
4. Logs clearly which checkpoints were found/ignored

Example log output:
```
Instance 0: Skipping incomplete checkpoint checkpoint_iter500.pkl (metadata=False, regrets=True)
Instance 0: Resuming from complete checkpoint 'checkpoint_iter1000_t3600s.pkl' (2 complete checkpoint(s) available, 1 incomplete ignored)
```

## Backward Compatibility

**Legacy checkpoints** (created before this change) that only have `.pkl` files without metadata/regrets files:
- Will be detected as incomplete
- Will be skipped during multi-instance resume
- Can still be loaded manually if needed (with warnings)

## Best Practices

1. **Always keep all three files together** - Do not move or delete individual files
2. **Use `.gitignore`** to exclude checkpoints from version control (they're large)
3. **Archive complete checkpoints** - Keep checkpoint sets intact when backing up
4. **Monitor logs** during resume to ensure correct checkpoint was loaded
5. **Validate buckets** when resuming to prevent training with incompatible configurations

## Troubleshooting

### "Incomplete checkpoint" error

**Symptom**: Training fails to resume with error about incomplete checkpoint

**Solution**: 
- Ensure all three files exist (`.pkl`, `_metadata.json`, `_regrets.pkl`)
- Check that files weren't partially copied or corrupted
- If files are incomplete, start training from scratch

### "Bucket configuration mismatch" error

**Symptom**: Cannot load checkpoint due to bucket hash mismatch

**Solution**:
- Use the same bucket file that was used for the checkpoint
- If bucket file was regenerated, you must restart training from scratch
- Always keep bucket files with their corresponding checkpoints

### Old incomplete checkpoints being ignored

**Symptom**: Multi-instance resume says "no complete checkpoints found"

**Solution**:
- This is expected behavior - old incomplete checkpoints are now ignored
- Check if complete checkpoints exist with all three files
- If none exist, training will start from scratch (which is correct)
