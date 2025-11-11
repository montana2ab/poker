"""
Checkpoint version migration utilities.

This module provides tools for migrating checkpoints between different versions,
handling changes in:
- Infoset format/versioning
- Regret/strategy storage formats
- Metadata schema changes

Phase 2.2-2.3: Support for infoset versioning and compact storage migrations.
"""

from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import json
import pickle
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# Version constants
CURRENT_CHECKPOINT_VERSION = "v2"
SUPPORTED_VERSIONS = ["v1", "v2"]


class CheckpointMigrator:
    """
    Migrates checkpoints between different versions.
    
    Handles:
    - Legacy (v1) to versioned (v2) infoset format
    - float64 to int32 compact storage conversion
    - Metadata schema updates
    """
    
    def __init__(self):
        self.version_migrations = {
            "v1": self._migrate_v1_to_v2,
        }
    
    def detect_checkpoint_version(self, metadata: Dict[str, Any]) -> str:
        """
        Detect checkpoint version from metadata.
        
        Args:
            metadata: Checkpoint metadata dictionary
            
        Returns:
            Version string (e.g., "v1", "v2")
        """
        # Check for explicit version field
        if 'checkpoint_version' in metadata:
            return metadata['checkpoint_version']
        
        # Check for infoset version in metadata (v2+)
        if 'infoset_version' in metadata:
            return "v2"
        
        # Legacy checkpoints (pre-versioning)
        return "v1"
    
    def _migrate_v1_to_v2(
        self,
        checkpoint_data: Dict,
        metadata: Dict[str, Any]
    ) -> Tuple[Dict, Dict[str, Any]]:
        """
        Migrate v1 checkpoint (legacy format) to v2 (versioned format).
        
        Changes:
        - Convert infoset keys from "STREET:bucket:history" to "v2:STREET:bucket:history"
        - Convert action history from "action1.action2" to "C-B75-C" format
        - Add infoset_version to metadata
        
        Args:
            checkpoint_data: Original checkpoint data
            metadata: Original metadata
            
        Returns:
            Tuple of (migrated_checkpoint_data, migrated_metadata)
        """
        print(f"Migrating checkpoint from v1 to v2...")
        
        migrated_data = {}
        
        # Migrate regrets
        if 'regrets' in checkpoint_data:
            migrated_data['regrets'] = self._migrate_infoset_keys_v1_to_v2(
                checkpoint_data['regrets']
            )
        
        # Migrate strategy_sum
        if 'strategy_sum' in checkpoint_data:
            migrated_data['strategy_sum'] = self._migrate_infoset_keys_v1_to_v2(
                checkpoint_data['strategy_sum']
            )
        
        # Preserve other fields
        for key in checkpoint_data:
            if key not in ['regrets', 'strategy_sum']:
                migrated_data[key] = checkpoint_data[key]
        
        # Update metadata
        migrated_metadata = metadata.copy()
        migrated_metadata['checkpoint_version'] = "v2"
        migrated_metadata['infoset_version'] = "v2"
        
        print(f"✓ Migrated {len(migrated_data.get('regrets', {}))} regret infosets")
        print(f"✓ Migrated {len(migrated_data.get('strategy_sum', {}))} strategy infosets")
        
        return migrated_data, migrated_metadata
    
    def _migrate_infoset_keys_v1_to_v2(self, infoset_table: Dict) -> Dict:
        """
        Migrate infoset keys from v1 to v2 format.
        
        v1 format: "STREET:bucket:history"
        v2 format: "v2:STREET:bucket:history"
        
        Also converts action history format if needed.
        """
        migrated_table = {}
        
        for infoset_key, action_dict in infoset_table.items():
            # Check if already v2 format
            if infoset_key.startswith("v2:"):
                migrated_table[infoset_key] = action_dict
                continue
            
            # Parse v1 format
            parts = infoset_key.split(":", 2)
            if len(parts) != 3:
                # Unknown format, keep as-is
                migrated_table[infoset_key] = action_dict
                continue
            
            street, bucket, history = parts
            
            # Convert history format if needed
            # v1 uses "action1.action2" format
            # v2 uses "C-B75-C" format
            if "." in history:
                history = self._convert_history_format(history)
            
            # Create v2 format key
            new_key = f"v2:{street}:{bucket}:{history}"
            migrated_table[new_key] = action_dict
        
        return migrated_table
    
    def _convert_history_format(self, old_history: str) -> str:
        """
        Convert action history from v1 to v2 format.
        
        v1: "check_call.bet_0.75p.check_call"
        v2: "C-B75-C"
        """
        if not old_history:
            return ""
        
        actions = old_history.split(".")
        converted = []
        
        for action in actions:
            if action == "fold":
                converted.append("F")
            elif action in ["check_call", "check", "call"]:
                converted.append("C")
            elif action == "all_in":
                converted.append("A")
            elif action.startswith("bet_") or action.startswith("raise_"):
                # Extract percentage
                try:
                    # Remove prefix and "p" suffix
                    action_cleaned = action.replace("bet_", "").replace("raise_", "").replace("p", "")
                    fraction = float(action_cleaned)
                    percentage = int(fraction * 100)
                    converted.append(f"B{percentage}")
                except (ValueError, IndexError):
                    converted.append("B100")
            else:
                converted.append("B100")
        
        return "-".join(converted)
    
    def migrate_checkpoint(
        self,
        checkpoint_path: Path,
        output_path: Optional[Path] = None,
        target_version: str = CURRENT_CHECKPOINT_VERSION
    ) -> Path:
        """
        Migrate a checkpoint to target version.
        
        Args:
            checkpoint_path: Path to checkpoint to migrate
            output_path: Optional output path (default: append "_migrated" to filename)
            target_version: Target version (default: current version)
            
        Returns:
            Path to migrated checkpoint
        """
        if target_version not in SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported target version: {target_version}")
        
        # Load checkpoint
        print(f"Loading checkpoint from {checkpoint_path}...")
        with open(checkpoint_path, 'rb') as f:
            checkpoint_data = pickle.load(f)
        
        # Load metadata
        metadata_path = checkpoint_path.parent / f"{checkpoint_path.stem}_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {}
        
        # Detect current version
        current_version = self.detect_checkpoint_version(metadata)
        print(f"Detected checkpoint version: {current_version}")
        
        if current_version == target_version:
            print(f"Checkpoint already at target version {target_version}")
            return checkpoint_path
        
        # Perform migrations
        migrated_data = checkpoint_data
        migrated_metadata = metadata
        
        # Chain migrations if needed
        version_order = ["v1", "v2"]
        start_idx = version_order.index(current_version)
        end_idx = version_order.index(target_version)
        
        for idx in range(start_idx, end_idx):
            version = version_order[idx]
            if version in self.version_migrations:
                migrated_data, migrated_metadata = self.version_migrations[version](
                    migrated_data, migrated_metadata
                )
        
        # Determine output path
        if output_path is None:
            output_path = checkpoint_path.parent / f"{checkpoint_path.stem}_migrated.pkl"
        
        # Save migrated checkpoint
        print(f"Saving migrated checkpoint to {output_path}...")
        with open(output_path, 'wb') as f:
            pickle.dump(migrated_data, f)
        
        # Save migrated metadata
        metadata_output = output_path.parent / f"{output_path.stem}_metadata.json"
        with open(metadata_output, 'w') as f:
            json.dump(migrated_metadata, f, indent=2)
        
        print(f"✓ Migration complete: {current_version} → {target_version}")
        
        return output_path
    
    def validate_migrated_checkpoint(
        self,
        original_path: Path,
        migrated_path: Path
    ) -> bool:
        """
        Validate that migration preserved data correctly.
        
        Args:
            original_path: Path to original checkpoint
            migrated_path: Path to migrated checkpoint
            
        Returns:
            True if validation passes
        """
        print("Validating migrated checkpoint...")
        
        # Load both checkpoints
        with open(original_path, 'rb') as f:
            original_data = pickle.load(f)
        
        with open(migrated_path, 'rb') as f:
            migrated_data = pickle.load(f)
        
        # Check that number of infosets matches
        original_regrets = original_data.get('regrets', {})
        migrated_regrets = migrated_data.get('regrets', {})
        
        if len(original_regrets) != len(migrated_regrets):
            print(f"✗ Regret infoset count mismatch: {len(original_regrets)} vs {len(migrated_regrets)}")
            return False
        
        original_strategies = original_data.get('strategy_sum', {})
        migrated_strategies = migrated_data.get('strategy_sum', {})
        
        if len(original_strategies) != len(migrated_strategies):
            print(f"✗ Strategy infoset count mismatch: {len(original_strategies)} vs {len(migrated_strategies)}")
            return False
        
        # Sample validation: check a few values
        sample_size = min(10, len(original_regrets))
        sampled_keys = list(original_regrets.keys())[:sample_size]
        
        for old_key in sampled_keys:
            # Find corresponding new key (may have different format)
            # For v1→v2 migration, extract bucket and compare action counts
            parts = old_key.split(":", 2)
            if len(parts) == 3:
                street, bucket, _ = parts
                
                # Find matching infoset in migrated data
                found = False
                for new_key in migrated_regrets:
                    if f":{street}:{bucket}:" in new_key:
                        # Check action counts match
                        if len(original_regrets[old_key]) == len(migrated_regrets[new_key]):
                            found = True
                            break
                
                if not found:
                    print(f"✗ Could not find matching infoset for {old_key}")
                    return False
        
        print("✓ Validation passed")
        return True


def migrate_checkpoint_directory(
    checkpoint_dir: Path,
    target_version: str = CURRENT_CHECKPOINT_VERSION
) -> int:
    """
    Migrate all checkpoints in a directory.
    
    Args:
        checkpoint_dir: Directory containing checkpoints
        target_version: Target version
        
    Returns:
        Number of checkpoints migrated
    """
    migrator = CheckpointMigrator()
    count = 0
    
    # Find all checkpoint files
    checkpoint_files = list(checkpoint_dir.glob("checkpoint_*.pkl"))
    
    print(f"Found {len(checkpoint_files)} checkpoint(s) in {checkpoint_dir}")
    
    for checkpoint_path in checkpoint_files:
        # Skip already migrated files
        if "_migrated" in checkpoint_path.stem:
            continue
        
        try:
            migrated_path = migrator.migrate_checkpoint(
                checkpoint_path,
                target_version=target_version
            )
            
            # Validate
            if migrator.validate_migrated_checkpoint(checkpoint_path, migrated_path):
                count += 1
            else:
                print(f"⚠ Validation failed for {checkpoint_path}")
        
        except Exception as e:
            print(f"✗ Failed to migrate {checkpoint_path}: {e}")
            continue
    
    print(f"\n✓ Successfully migrated {count}/{len(checkpoint_files)} checkpoint(s)")
    
    return count
