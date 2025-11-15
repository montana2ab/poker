# Abstraction Hash Security

## Overview

The abstraction hash is a SHA256 hash of the bucket configuration used to train a poker strategy. This hash ensures that strategies are only used with the bucket configuration they were trained with, preventing subtle but catastrophic bugs from mixing incompatible abstractions.

## Why is this important?

When training a poker AI using MCCFR (Monte Carlo Counterfactual Regret Minimization), the game tree is abstracted using "buckets" - groups of similar hand situations. The bucket configuration includes:

- Number of buckets per street (preflop, flop, turn, river)
- Clustering algorithm parameters
- Random seed for bucket generation
- Number of players

**If you load a strategy trained with one bucket configuration but try to use it with a different configuration, the following problems occur:**

1. **Infoset Mismatch**: The strategy's infosets won't correspond to the correct game states
2. **Wrong Actions**: The AI will apply strategies to the wrong situations
3. **Degraded Play**: Play quality will be severely compromised
4. **Training Corruption**: Resuming training will corrupt the strategy irreparably

## How the Hash Works

The abstraction hash is calculated in `solver.py` using `_calculate_bucket_hash()`:

```python
def _calculate_bucket_hash(self) -> str:
    """Calculate SHA256 hash of bucket configuration."""
    import hashlib
    import json
    
    bucket_data = {
        'k_preflop': self.bucketing.config.k_preflop,
        'k_flop': self.bucketing.config.k_flop,
        'k_turn': self.bucketing.config.k_turn,
        'k_river': self.bucketing.config.k_river,
        'num_samples': self.bucketing.config.num_samples,
        'seed': self.bucketing.config.seed,
        'num_players': self.bucketing.config.num_players,
        # Plus cluster centers if available
    }
    
    data_str = json.dumps(bucket_data, sort_keys=True)
    return hashlib.sha256(data_str.encode('utf-8')).hexdigest()
```

The hash includes:
- Bucket counts for each street
- Number of samples used for clustering
- Random seed
- Number of players
- Actual cluster centers (when fitted)

## When is the Hash Validated?

### 1. Checkpoint Loading (solver.py)

When you resume training from a checkpoint, the hash is **automatically validated**:

```python
solver.load_checkpoint(checkpoint_path, validate_buckets=True)
```

If the hash doesn't match, you'll get a clear error:

```
ValueError: Bucket configuration mismatch!
Current SHA: abc123...
Checkpoint SHA: def456...
Cannot safely resume training with different bucket configuration.
```

### 2. Policy Loading (policy_store.py)

When you load a saved policy for evaluation or play, you can validate the hash:

```python
# Load with validation
policy = PolicyStore.load(
    "path/to/policy.pkl",
    expected_bucket_hash=current_hash,
    validate_buckets=True
)
```

**Important**: The validation only happens if you provide `expected_bucket_hash`. To get the current hash:

```python
solver = MCCFRSolver(config, bucketing, num_players)
current_hash = solver._calculate_bucket_hash()
```

## Error Messages

### Hash Mismatch Error

If validation fails, you'll see a detailed error message:

```
================================================================================
🚨 ABSTRACTION HASH MISMATCH DETECTED 🚨
================================================================================
Policy file: avg_policy.pkl
Expected SHA256: abc123def456...
Stored SHA256:   789xyz012...

This policy was trained with DIFFERENT bucket configuration!

Consequences of using incompatible abstraction:
  • Infosets will not match correctly
  • Strategy will be applied to wrong game states
  • Play quality will be severely degraded
  • Training progress will be corrupted if resuming

Action required:
  1. Verify you are using the correct bucket file
  2. If buckets changed, retrain the policy from scratch
  3. Use '--no-validate-buckets' flag ONLY for debugging (NOT RECOMMENDED)
================================================================================

Stored bucket configuration:
  k_preflop: 169
  k_flop:    1000
  k_turn:    1000
  k_river:   1000
  seed:      42
  num_players: 2
```

### Missing Hash Warning

If you load a legacy policy without metadata:

```
⚠️  Policy avg_policy.pkl has NO bucket metadata
   This is a legacy policy or was saved without bucket configuration
   Cannot verify abstraction compatibility - USE AT YOUR OWN RISK
   Recommendation: Retrain policy with current code version
```

## Best Practices

### 1. Always Save Policies with Metadata

The current code **automatically** includes bucket metadata when you save policies:

```python
# This automatically includes bucket metadata
solver.save_policy(logdir)
```

### 2. Validate When Loading for Production

When loading policies for real play or evaluation, always validate:

```python
# Get current bucket hash
current_hash = solver._calculate_bucket_hash()

# Load with validation
policy = PolicyStore.load(
    policy_path,
    expected_bucket_hash=current_hash,
    validate_buckets=True
)
```

### 3. Document Bucket Configuration

When sharing policies or checkpoints, always document:
- Bucket configuration (k_preflop, k_flop, k_turn, k_river)
- Random seed
- Number of players
- Abstraction hash (first 8-16 characters)

Example:
```
Strategy: BlueprintV1
Buckets: 169/1000/1000/1000 (preflop/flop/turn/river)
Seed: 42
Players: 2
Hash: abc123de...
```

### 4. Never Mix Strategies Across Abstractions

**DON'T:**
- Resume training with different bucket configuration
- Use a policy trained with 2-player buckets for 3-player games
- Change clustering seed and continue training

**DO:**
- Retrain from scratch if bucket configuration changes
- Keep separate policies for each abstraction
- Version your bucket files and policies together

### 5. Handle Legacy Policies Carefully

If you have old policies without metadata:
- They will load with warnings
- Consider retraining with current code
- If you must use them, validate manually that buckets match

## CLI Integration

The validation can be controlled via CLI flags:

```bash
# Enable validation (recommended for production)
holdem-autoplay --policy policy.pkl --buckets buckets.pkl --validate-buckets

# Disable validation (for debugging only)
holdem-autoplay --policy policy.pkl --buckets buckets.pkl --no-validate-buckets
```

## Migration Guide

### Scenario 1: Changing Bucket Configuration

If you need to change your bucket configuration:

1. **Save your current policy** with a descriptive name
2. **Create new bucket configuration**
3. **Train a NEW policy from scratch** with the new buckets
4. **Don't try to resume from old checkpoints**

```bash
# Old configuration
holdem-build-buckets --output buckets_old.pkl --k-preflop 169 ...

# New configuration (different parameters)
holdem-build-buckets --output buckets_new.pkl --k-preflop 200 ...

# Must train from scratch, cannot resume from old checkpoint
holdem-train-blueprint --buckets buckets_new.pkl --output new_policy/
```

### Scenario 2: Legacy Policy Migration

If you have a legacy policy without metadata:

1. **Load the legacy policy** (will generate warnings)
2. **Check if it still works** with current buckets (evaluation)
3. **If performance is poor**, retrain from scratch
4. **If acceptable**, save with new metadata:

```python
# Load legacy policy
policy = PolicyStore.load("legacy_policy.pkl", validate_buckets=False)

# Add current bucket metadata
policy.bucket_metadata = {
    'bucket_file_sha': solver._calculate_bucket_hash(),
    # ... other metadata
}

# Save with metadata
policy.save("migrated_policy.pkl")
```

### Scenario 3: Distributed Training

When training across multiple machines:

1. **Use the same bucket file** on all machines
2. **Verify hash matches** before starting:

```python
# On each machine
hash1 = solver1._calculate_bucket_hash()
hash2 = solver2._calculate_bucket_hash()
assert hash1 == hash2, "Bucket files must be identical!"
```

3. **Validate checkpoints** when merging or resuming

## Testing

The abstraction hash system is thoroughly tested in `tests/test_abstraction_migration.py`:

- Hash calculation consistency
- Validation with matching hashes (accepts)
- Validation with mismatched hashes (rejects with clear error)
- Legacy policy compatibility
- Different bucket configs produce different hashes
- Validation bypass for debugging

Run tests:

```bash
pytest tests/test_abstraction_migration.py -v
```

## Security Implications

The abstraction hash acts as a **safety mechanism**:

1. **Prevents Accidental Mixing**: You can't accidentally use wrong buckets
2. **Audit Trail**: Hash provides provenance for trained strategies
3. **Reproducibility**: Hash helps ensure exact configuration can be reproduced
4. **Debugging**: Clear error messages help diagnose configuration issues quickly

## Technical Details

### Hash Calculation

The hash is deterministic and platform-independent:
- Uses JSON serialization with `sort_keys=True`
- Converts numpy arrays to lists for consistency
- Uses SHA256 for cryptographic strength
- Includes both configuration AND fitted parameters (cluster centers)

### Storage Format

Policies are saved with metadata:

```python
{
    'policy': {
        'infoset1': {'fold': 0.3, 'call': 0.7},
        'infoset2': {...},
        ...
    },
    'bucket_metadata': {
        'bucket_file_sha': 'abc123...',
        'k_preflop': 169,
        'k_flop': 1000,
        'k_turn': 1000,
        'k_river': 1000,
        'num_samples': 10000,
        'seed': 42,
        'num_players': 2
    }
}
```

### Backward Compatibility

The system maintains backward compatibility:
- Legacy policies without metadata still load (with warnings)
- Validation can be disabled explicitly
- Both pickle and JSON formats supported
- Old JSON format (raw dict) still works

## FAQ

**Q: Can I disable validation permanently?**  
A: Not recommended. Validation is crucial for correctness. Only disable for debugging.

**Q: What if I change just one parameter?**  
A: Even changing one parameter (e.g., seed) changes the hash. You must retrain.

**Q: Can I manually fix the hash?**  
A: No. The hash must match the actual bucket configuration. Tampering defeats the purpose.

**Q: How do I check if two bucket files are identical?**  
A: Compare their hashes:
```python
hash1 = solver1._calculate_bucket_hash()
hash2 = solver2._calculate_bucket_hash()
print(f"Match: {hash1 == hash2}")
```

**Q: What about checkpoints vs final policies?**  
A: Both store and validate the hash. Checkpoints also store full metadata.

**Q: Can I use a 2-player policy for 3-player games?**  
A: No. num_players is part of the hash. You must train separate policies.

## Summary

The abstraction hash system provides **automatic protection** against a critical class of bugs:

✅ **Enabled by default** - no action needed for new code  
✅ **Backward compatible** - legacy policies still work  
✅ **Clear error messages** - easy to diagnose issues  
✅ **Comprehensive testing** - thoroughly validated  
✅ **Production ready** - safe for deployment  

**Remember**: If bucket configuration changes, retrain from scratch. There's no shortcut.
