# Checkpoint Migrations

This directory contains utilities for migrating checkpoints between different versions of the poker MCCFR system.

## Overview

As the system evolves, checkpoint formats may change due to:
- Infoset format updates (e.g., versioning, action encoding)
- Storage format changes (e.g., float64 → int32 compact)
- Metadata schema updates

The migration tools ensure backward compatibility and allow you to upgrade old checkpoints to work with newer versions of the code.

## Supported Migrations

### v1 → v2 (Infoset Versioning)

Converts legacy infoset format to versioned format:
- **Before (v1)**: `"FLOP:12:check_call.bet_0.75p.check_call"`
- **After (v2)**: `"v2:FLOP:12:C-B75-C"`

Changes:
- Adds version prefix (`v2:`)
- Converts action history to abbreviated format
- Updates metadata with version information

## Usage

### Migrate a Single Checkpoint

```python
from pathlib import Path
from migrations.checkpoint_migration import CheckpointMigrator

migrator = CheckpointMigrator()

# Migrate checkpoint
original_path = Path("logdir/checkpoints/checkpoint_iter1000.pkl")
migrated_path = migrator.migrate_checkpoint(original_path)

# Validate migration
if migrator.validate_migrated_checkpoint(original_path, migrated_path):
    print("✓ Migration successful!")
```

### Migrate All Checkpoints in a Directory

```python
from pathlib import Path
from migrations.checkpoint_migration import migrate_checkpoint_directory

# Migrate all checkpoints in directory
checkpoint_dir = Path("logdir/checkpoints")
count = migrate_checkpoint_directory(checkpoint_dir)
print(f"Migrated {count} checkpoint(s)")
```

### Command Line Usage

```bash
# Migrate a single checkpoint
python -c "
from pathlib import Path
from migrations.checkpoint_migration import CheckpointMigrator

migrator = CheckpointMigrator()
migrator.migrate_checkpoint(Path('logdir/checkpoints/checkpoint_iter1000.pkl'))
"

# Migrate all checkpoints
python -c "
from pathlib import Path
from migrations.checkpoint_migration import migrate_checkpoint_directory

migrate_checkpoint_directory(Path('logdir/checkpoints'))
"
```

## Migration Safety

The migration tools include several safety features:

1. **Non-destructive**: Original checkpoints are never modified. Migrated checkpoints are saved with a `_migrated` suffix.

2. **Validation**: After migration, the tool validates that:
   - Infoset counts match
   - Data structure is preserved
   - Sample values are consistent

3. **Version detection**: Automatically detects checkpoint version from metadata.

4. **Idempotent**: Running migration on an already-migrated checkpoint is safe (no-op).

## File Structure

After migration, you'll have:

```
logdir/checkpoints/
├── checkpoint_iter1000.pkl              # Original
├── checkpoint_iter1000_metadata.json     # Original metadata
├── checkpoint_iter1000_regrets.pkl      # Original regrets
├── checkpoint_iter1000_migrated.pkl     # Migrated checkpoint
└── checkpoint_iter1000_migrated_metadata.json  # Migrated metadata
```

## Testing Migrations

The migration tools are tested in `tests/test_checkpoint_migration.py`:

```bash
python tests/test_checkpoint_migration.py
```

## Extending Migrations

To add a new migration (e.g., v2 → v3):

1. Add a migration method to `CheckpointMigrator`:
```python
def _migrate_v2_to_v3(self, checkpoint_data: Dict, metadata: Dict) -> Tuple[Dict, Dict]:
    # Implement migration logic
    pass
```

2. Register it in `__init__`:
```python
self.version_migrations = {
    "v1": self._migrate_v1_to_v2,
    "v2": self._migrate_v2_to_v3,  # New migration
}
```

3. Update `SUPPORTED_VERSIONS` and `CURRENT_CHECKPOINT_VERSION`.

4. Add tests for the new migration.

## Related Documentation

- [CHECKPOINT_FORMAT.md](../CHECKPOINT_FORMAT.md) - Checkpoint file structure
- [CHECKPOINTING.md](../CHECKPOINTING.md) - Checkpoint management guide
- [IMPLEMENTATION_SUMMARY_INFOSET_VERSIONING.md](../IMPLEMENTATION_SUMMARY_INFOSET_VERSIONING.md) - Infoset versioning details
