#!/usr/bin/env python3
"""
Manual integration test for checkpoint resume fix.
Simulates the exact scenario from the problem statement.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Mock dependencies
sys.modules['numpy'] = MagicMock()
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()
sys.modules['eval7'] = MagicMock()
sys.modules['torch'] = MagicMock()
sys.modules['torch.utils'] = MagicMock()
sys.modules['torch.utils.tensorboard'] = MagicMock()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
from holdem.types import MCCFRConfig
from unittest.mock import Mock


def simulate_problem_scenario():
    """
    Simulate the exact scenario from the problem statement:
    - 6 instances
    - Each has checkpoints like: checkpoint_iter22158_t3600s_regrets.pkl
    - Each should also have: checkpoint_iter22158_t3600s.pkl
    - And metadata: checkpoint_iter22158_t3600s_metadata.json
    """
    print("\n" + "="*70)
    print("Simulating Problem Scenario from Issue")
    print("="*70)
    
    mock_bucketing = Mock()
    
    # Create config matching the problem
    config = MCCFRConfig(
        time_budget_seconds=28800,  # 8 hours
        snapshot_interval_seconds=3600,  # 1 hour snapshots
        num_workers=1
    )
    
    coordinator = MultiInstanceCoordinator(
        num_instances=6,  # As in the problem
        config=config,
        bucketing=mock_bucketing,
        num_players=2
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Simulate the checkpoint structure from the problem
        checkpoint_data = [
            (0, 22158, 3600),
            (1, 22001, 3608),
            (2, 22001, 3607),
            (3, 22375, 3600),
            (4, 22217, 3600),
            (5, 22361, 3600),
        ]
        
        print("\nCreating checkpoint files as they would be saved...")
        for instance_id, iter_num, elapsed_time in checkpoint_data:
            instance_dir = tmpdir / f"instance_{instance_id}" / "checkpoints"
            instance_dir.mkdir(parents=True, exist_ok=True)
            
            # Create the files in the same order as save_checkpoint would
            checkpoint_name = f"checkpoint_iter{iter_num}_t{elapsed_time}s"
            
            # 1. Main policy checkpoint
            main_file = instance_dir / f"{checkpoint_name}.pkl"
            main_file.touch()
            print(f"  Instance {instance_id}: Created {main_file.name}")
            
            # 2. Metadata file
            import time
            time.sleep(0.01)  # Small delay
            metadata_file = instance_dir / f"{checkpoint_name}_metadata.json"
            metadata_file.write_text('{"iteration": ' + str(iter_num) + '}')
            print(f"  Instance {instance_id}: Created {metadata_file.name}")
            
            # 3. Regrets file (created last, so has latest mtime)
            time.sleep(0.01)  # Small delay
            regrets_file = instance_dir / f"{checkpoint_name}_regrets.pkl"
            regrets_file.touch()
            print(f"  Instance {instance_id}: Created {regrets_file.name}")
        
        print("\n" + "-"*70)
        print("Finding checkpoints for resume...")
        print("-"*70)
        
        # Now find checkpoints - this is where the bug would occur
        checkpoints = coordinator._find_resume_checkpoints(tmpdir)
        
        print(f"\nFound {len(checkpoints)} checkpoint(s)\n")
        
        all_correct = True
        for i, cp in enumerate(checkpoints):
            if cp is None:
                print(f"❌ Instance {i}: No checkpoint found!")
                all_correct = False
                continue
            
            # Check if it's the correct file (not _regrets.pkl)
            is_regrets = cp.stem.endswith("_regrets")
            status = "❌" if is_regrets else "✅"
            
            print(f"{status} Instance {i}: {cp.name}")
            
            if is_regrets:
                print(f"   ERROR: Selected _regrets.pkl file!")
                all_correct = False
            else:
                # Verify metadata file exists with matching name
                metadata_path = cp.parent / f"{cp.stem}_metadata.json"
                if metadata_path.exists():
                    print(f"   ✓ Metadata file exists: {metadata_path.name}")
                else:
                    print(f"   ❌ Metadata file NOT found: {metadata_path.name}")
                    all_correct = False
        
        print("\n" + "="*70)
        if all_correct:
            print("✅ SUCCESS: All checkpoints correctly selected (no _regrets.pkl)")
            print("✅ All metadata files can be found")
            print("\nThe issue is FIXED! Resume will work correctly now.")
        else:
            print("❌ FAILED: Some checkpoints incorrectly selected")
            print("❌ Resume would fail with metadata not found errors")
        print("="*70)
        
        return all_correct


if __name__ == "__main__":
    success = simulate_problem_scenario()
    sys.exit(0 if success else 1)
