# Checkpoint Management Guide

This guide explains the checkpoint system, including abstraction hash validation for safe training resumption.

## Overview

The MCCFR solver provides robust checkpointing with:
- Full training state preservation (RNG, regrets, strategies, epsilon)
- Abstraction hash validation for compatibility
- Snapshot system for exporting policies
- Multi-platform deterministic training

## Checkpoint Structure

### Files Created

When saving a checkpoint at iteration `N`, three files are created:

```
logdir/checkpoints/
├── checkpoint_iterN.pkl          # Main checkpoint (regrets, strategy_sum)
├── checkpoint_iterN_metadata.json # Metadata (iteration, RNG state, config)
└── checkpoint_iterN_regrets.pkl   # Full regret tracker state
```

### Snapshot Structure

Snapshots export trained policies for deployment:

```
logdir/snapshots/snapshot_iterN_tXXs/
├── metadata.json                 # Training metadata + abstraction hash
├── avg_policy_preflop.json.gz   # Preflop average policy
├── avg_policy_flop.json.gz      # Flop average policy
├── avg_policy_turn.json.gz      # Turn average policy
└── avg_policy_river.json.gz     # River average policy
```

## Abstraction Hash Validation

### What is the Abstraction Hash?

The abstraction hash is a SHA256 fingerprint of your bucket configuration that ensures checkpoint compatibility. It includes:

- Bucket counts per street (k_preflop, k_flop, k_turn, k_river)
- Training parameters (num_samples, seed, num_players)
- Cluster centers (for deterministic cross-platform compatibility)

### Why Hash Validation?

Loading a checkpoint trained with different buckets would produce **incorrect strategies**. The hash validation prevents this by checking compatibility before resuming training.

**Example scenario:**
```python
# Training run 1: 24/80/80/64 buckets
bucketing1 = HandBucketing(BucketConfig(
    k_preflop=24, k_flop=80, k_turn=80, k_river=64,
    num_samples=10000, seed=42, num_players=6
))

# Training run 2: 24/80/80/128 buckets (DIFFERENT!)
bucketing2 = HandBucketing(BucketConfig(
    k_preflop=24, k_flop=80, k_turn=80, k_river=128,  # ❌ Changed river buckets
    num_samples=10000, seed=42, num_players=6
))

# Trying to load checkpoint from run 1 with bucketing2 will fail:
# ValueError: Bucket configuration mismatch!
```

### How Hash Validation Works

#### 1. Saving Checkpoint

When saving, the hash is automatically calculated and stored:

```python
def save_checkpoint(self, logdir: Path, iteration: int):
    # Calculate hash
    bucket_sha = self._calculate_bucket_hash()
    
    # Save in metadata
    metadata = {
        'iteration': iteration,
        'bucket_metadata': {
            'bucket_file_sha': bucket_sha,
            'k_preflop': self.bucketing.config.k_preflop,
            'k_flop': self.bucketing.config.k_flop,
            # ... other config
        }
    }
```

#### 2. Loading Checkpoint

When loading, hashes are compared:

```python
def load_checkpoint(self, checkpoint_path: Path, validate_buckets: bool = True):
    if validate_buckets:
        current_sha = self._calculate_bucket_hash()
        checkpoint_sha = metadata['bucket_metadata']['bucket_file_sha']
        
        if current_sha != checkpoint_sha:
            raise ValueError(
                f"Bucket configuration mismatch!\n"
                f"Current SHA: {current_sha}\n"
                f"Checkpoint SHA: {checkpoint_sha}\n"
                f"Cannot safely resume training."
            )
```

## Usage Examples

### Basic Training with Checkpoints

```python
from holdem.types import MCCFRConfig, BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver

# 1. Create bucketing
bucketing = HandBucketing(BucketConfig(
    k_preflop=24,
    k_flop=80,
    k_turn=80,
    k_river=64,
    num_samples=10000,
    seed=42,
    num_players=6
))
bucketing.build()

# 2. Create solver with checkpointing
config = MCCFRConfig(
    num_iterations=10_000_000,
    checkpoint_interval=100_000,  # Save every 100k iterations
    snapshot_interval_seconds=3600,  # Snapshot every hour
)

solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=6)

# 3. Train with automatic checkpointing
solver.train(logdir=Path("runs/my_training"))
# Checkpoints saved automatically every 100k iterations
```

### Resuming from Checkpoint

```python
# 1. Load same bucketing configuration
bucketing = HandBucketing(BucketConfig(
    k_preflop=24, k_flop=80, k_turn=80, k_river=64,
    num_samples=10000, seed=42, num_players=6
))
bucketing.build()

# 2. Create solver
solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=6)

# 3. Resume from checkpoint
checkpoint_path = Path("runs/my_training/checkpoints/checkpoint_iter500000.pkl")
resumed_iteration = solver.load_checkpoint(
    checkpoint_path,
    validate_buckets=True  # Enable hash validation (default)
)

print(f"Resumed training from iteration {resumed_iteration}")

# 4. Continue training
solver.train(logdir=Path("runs/my_training"))
# Will continue from iteration 500001
```

### Handling Hash Mismatches

If you get a hash mismatch error:

```
ValueError: Bucket configuration mismatch!
Current SHA: a1b2c3d4...
Checkpoint SHA: e5f6g7h8...
Cannot safely resume training.
```

**Possible causes:**

1. **Different bucket counts**: Changed k_preflop/k_flop/k_turn/k_river
2. **Different training parameters**: Changed num_samples or seed
3. **Different num_players**: Changed player count
4. **Rebuilt buckets**: Even with same config, rebuilding generates new cluster centers

**Solutions:**

**Option 1: Use correct bucketing (RECOMMENDED)**
```python
# Load the original bucketing from disk
bucketing = HandBucketing.load(Path("runs/my_training/buckets.pkl"))
# This ensures exact match with checkpoint
```

**Option 2: Retrain from scratch**
```python
# Start new training with new bucketing
solver.train(logdir=Path("runs/new_training"))
```

**Option 3: Disable validation (NOT RECOMMENDED)**
```python
# Only use if you know what you're doing!
resumed_iteration = solver.load_checkpoint(
    checkpoint_path,
    validate_buckets=False  # ⚠️ UNSAFE - strategies may be incorrect
)
```

### Loading Pre-Built Buckets

To ensure compatibility, always save and load buckets:

```python
# During initial training
bucketing.build()
bucketing.save(Path("runs/my_training/buckets.pkl"))

# When resuming
bucketing = HandBucketing.load(Path("runs/my_training/buckets.pkl"))
# This guarantees exact cluster centers match
```

## Checkpoint Metadata

The metadata JSON contains:

```json
{
  "iteration": 500000,
  "elapsed_seconds": 28800.5,
  "num_players": 6,
  "infoset_version": "v1.0",
  "rng_state": [...],
  "bucket_metadata": {
    "bucket_file_sha": "a1b2c3d4e5f6...",  // SHA256 hash
    "k_preflop": 24,
    "k_flop": 80,
    "k_turn": 80,
    "k_river": 64,
    "num_samples": 10000,
    "seed": 42,
    "num_players": 6
  },
  "metrics": {
    "states_per_sec": 173.2,
    "avg_regret_preflop": 0.045,
    // ...
  }
}
```

## Best Practices

### 1. Always Save Buckets with Checkpoints

```python
# When starting training
bucketing.build()
bucketing.save(logdir / "buckets.pkl")

# When resuming
bucketing = HandBucketing.load(logdir / "buckets.pkl")
```

### 2. Use Consistent Configuration

Keep your bucket configuration in a config file:

```yaml
# config/buckets_6max.yaml
k_preflop: 24
k_flop: 80
k_turn: 80
k_river: 64
num_samples: 10000
seed: 42
num_players: 6
```

Load it consistently:

```python
import yaml
with open("config/buckets_6max.yaml") as f:
    bucket_config = yaml.safe_load(f)

bucketing = HandBucketing(BucketConfig(**bucket_config))
```

### 3. Checkpoint Frequently

```python
MCCFRConfig(
    checkpoint_interval=50_000,  # More frequent saves
    snapshot_interval_seconds=1800  # Every 30 minutes
)
```

### 4. Clean Old Checkpoints

Keep only recent checkpoints to save disk space:

```bash
# Keep last 5 checkpoints
cd runs/my_training/checkpoints
ls -t checkpoint_iter*.pkl | tail -n +6 | xargs rm -f
```

Or use a rotation script:

```python
def cleanup_old_checkpoints(logdir: Path, keep_last: int = 5):
    """Keep only the last N checkpoints."""
    checkpoint_dir = logdir / "checkpoints"
    checkpoints = sorted(
        checkpoint_dir.glob("checkpoint_iter*.pkl"),
        key=lambda p: int(p.stem.split("_")[-1].replace("iter", ""))
    )
    
    for ckpt in checkpoints[:-keep_last]:
        ckpt.unlink()
        # Also remove associated files
        (ckpt.parent / f"{ckpt.stem}_metadata.json").unlink(missing_ok=True)
        (ckpt.parent / f"{ckpt.stem}_regrets.pkl").unlink(missing_ok=True)
```

### 5. Verify Checkpoint Integrity

```python
# Check if checkpoint is complete
is_complete = MCCFRSolver.is_checkpoint_complete(checkpoint_path)
if not is_complete:
    print("⚠️ Checkpoint incomplete, missing metadata or regrets file")
```

## Troubleshooting

### Problem: "Bucket configuration mismatch"

**Cause:** Trying to load checkpoint with different bucket configuration

**Solution:** Load the original buckets:
```python
bucketing = HandBucketing.load(Path("runs/my_training/buckets.pkl"))
```

### Problem: "Checkpoint incomplete"

**Cause:** Training was interrupted mid-save, or files were deleted

**Solution:** Load a previous checkpoint:
```python
# List available checkpoints
checkpoints = sorted(logdir.glob("checkpoints/checkpoint_iter*.pkl"))
# Try loading second-to-last
solver.load_checkpoint(checkpoints[-2])
```

### Problem: Different cluster centers after rebuild

**Cause:** K-means clustering is stochastic (even with fixed seed, sklearn versions differ)

**Solution:** Always use saved buckets, never rebuild:
```python
# ❌ WRONG - rebuilding creates new centers
bucketing = HandBucketing(BucketConfig(...))
bucketing.build()  # New cluster centers!

# ✅ CORRECT - load original centers
bucketing = HandBucketing.load(Path("runs/my_training/buckets.pkl"))
```

### Problem: Cross-platform resume fails

**Cause:** Different sklearn versions produce different cluster centers

**Solution:** Use the same sklearn version across platforms, or retrain:
```bash
# Check sklearn version in metadata
cat runs/my_training/checkpoints/checkpoint_iter*_metadata.json | grep sklearn

# Install matching version
pip install scikit-learn==1.3.0
```

## Testing

Verify hash validation works:

```bash
# Run validation tests
pytest tests/test_bucket_validation.py -v

# Expected tests:
# ✓ test_bucket_hash_calculation
# ✓ test_different_buckets_different_hash
# ✓ test_checkpoint_saves_bucket_metadata
# ✓ test_checkpoint_validation_accepts_matching_buckets
# ✓ test_checkpoint_validation_rejects_mismatched_buckets
# ✓ test_snapshot_saves_bucket_metadata
```

## Advanced: Multi-Instance Training

When training multiple instances simultaneously:

```python
# Instance 1: Preflop specialist
bucketing1 = HandBucketing(BucketConfig(k_preflop=48, ...))
solver1.train(logdir=Path("runs/preflop_specialist"))

# Instance 2: Postflop specialist  
bucketing2 = HandBucketing(BucketConfig(k_preflop=24, k_flop=160, ...))
solver2.train(logdir=Path("runs/postflop_specialist"))

# Each has independent hash validation
```

## Summary

**Key Points:**

1. ✅ **Abstraction hash ensures checkpoint compatibility**
2. ✅ **Always save and load buckets.pkl with checkpoints**
3. ✅ **Hash validation is automatic and enabled by default**
4. ✅ **Mismatch errors prevent incorrect strategy loading**
5. ✅ **Complete test coverage validates the system**

**Remember:**
- Hash = SHA256(bucket config + cluster centers)
- Validation prevents training with wrong buckets
- Always use `bucketing.save()` and `bucketing.load()`
- Keep sklearn version consistent across platforms

---

**Related Documentation:**
- [PLURIBUS_GAP_PLAN.txt](PLURIBUS_GAP_PLAN.txt) - Section 1.3.1
- [CHECKPOINT_FORMAT.md](CHECKPOINT_FORMAT.md) - Detailed format spec
- [GETTING_STARTED.md](GETTING_STARTED.md) - Quickstart guide

**Implementation:**
- `src/holdem/mccfr/solver.py:497-527` - `_calculate_bucket_hash()`
- `src/holdem/mccfr/solver.py:640-663` - Validation in `load_checkpoint()`
- `tests/test_bucket_validation.py` - Test suite (6 tests)
