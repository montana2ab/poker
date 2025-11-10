#!/usr/bin/env python3
"""
Test for checkpoint resume fix - ensuring _regrets.pkl files are not selected as checkpoints.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Mock heavy dependencies before any imports
sys.modules['numpy'] = MagicMock()
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()
sys.modules['eval7'] = MagicMock()
sys.modules['torch'] = MagicMock()
sys.modules['torch.utils'] = MagicMock()
sys.modules['torch.utils.tensorboard'] = MagicMock()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def test_checkpoint_selection_excludes_regrets():
    """Test that _find_resume_checkpoints excludes _regrets.pkl files."""
    print("\nTesting checkpoint selection excludes _regrets.pkl files...")
    
    from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
    from holdem.types import MCCFRConfig
    
    mock_bucketing = Mock()
    
    # Create test config
    config = MCCFRConfig(
        num_iterations=1000,
        checkpoint_interval=100,
        discount_interval=50,
        exploration_epsilon=0.6,
        num_workers=1
    )
    
    coordinator = MultiInstanceCoordinator(
        num_instances=2,
        config=config,
        bucketing=mock_bucketing,
        num_players=2
    )
    
    # Create a temporary directory structure mimicking a checkpoint with regrets files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create instance directories with checkpoints
        for i in range(2):
            instance_dir = tmpdir / f"instance_{i}" / "checkpoints"
            instance_dir.mkdir(parents=True, exist_ok=True)
            
            # Create checkpoint files as they would be created by save_checkpoint
            # The main checkpoint file
            main_checkpoint = instance_dir / f"checkpoint_iter22158_t3600s.pkl"
            main_checkpoint.touch()
            
            # The regrets file (created after main checkpoint, so has later mtime)
            import time
            time.sleep(0.01)  # Ensure different mtime
            regrets_checkpoint = instance_dir / f"checkpoint_iter22158_t3600s_regrets.pkl"
            regrets_checkpoint.touch()
            
            # The metadata file (matching main checkpoint name)
            metadata_file = instance_dir / f"checkpoint_iter22158_t3600s_metadata.json"
            metadata_file.touch()
        
        # Find checkpoints
        checkpoints = coordinator._find_resume_checkpoints(tmpdir)
        
        # Verify we found checkpoints for both instances
        assert len(checkpoints) == 2
        assert all(cp is not None for cp in checkpoints), "Should find checkpoints for all instances"
        print(f"  ✓ Found checkpoints for all instances")
        
        # Verify they point to the main checkpoint files, not _regrets.pkl
        for i, cp in enumerate(checkpoints):
            assert cp.exists(), f"Checkpoint {i} should exist"
            assert cp.suffix == '.pkl', f"Checkpoint {i} should be a .pkl file"
            assert 'checkpoint_' in cp.name, f"Checkpoint {i} should have 'checkpoint_' in name"
            assert not cp.stem.endswith('_regrets'), f"Checkpoint {i} should NOT be a _regrets.pkl file"
            print(f"  ✓ Instance {i} checkpoint: {cp.name} (correctly excludes _regrets.pkl)")
            
            # Verify the corresponding metadata file would exist
            metadata_path = cp.parent / f"{cp.stem}_metadata.json"
            assert metadata_path.exists(), f"Metadata file should exist at {metadata_path}"
            print(f"  ✓ Instance {i} metadata file exists: {metadata_path.name}")
    
    return True


def test_checkpoint_selection_with_multiple_checkpoints():
    """Test that the latest main checkpoint is selected when multiple exist."""
    print("\nTesting selection of latest main checkpoint...")
    
    from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
    from holdem.types import MCCFRConfig
    
    mock_bucketing = Mock()
    
    config = MCCFRConfig(
        num_iterations=1000,
        checkpoint_interval=100,
        discount_interval=50,
        exploration_epsilon=0.6,
        num_workers=1
    )
    
    coordinator = MultiInstanceCoordinator(
        num_instances=1,
        config=config,
        bucketing=mock_bucketing,
        num_players=2
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        instance_dir = tmpdir / "instance_0" / "checkpoints"
        instance_dir.mkdir(parents=True, exist_ok=True)
        
        # Create multiple checkpoints with different times
        import time
        checkpoints_created = []
        
        for iter_num in [100, 200, 300]:
            # Main checkpoint
            cp = instance_dir / f"checkpoint_iter{iter_num}_t1800s.pkl"
            cp.touch()
            checkpoints_created.append(cp)
            time.sleep(0.01)
            
            # Regrets file (should be ignored)
            regrets = instance_dir / f"checkpoint_iter{iter_num}_t1800s_regrets.pkl"
            regrets.touch()
            time.sleep(0.01)
        
        # Find checkpoints
        checkpoints = coordinator._find_resume_checkpoints(tmpdir)
        
        # Should return the latest checkpoint (iter300)
        assert len(checkpoints) == 1
        assert checkpoints[0] is not None
        assert "iter300" in checkpoints[0].name, f"Should select latest checkpoint, got {checkpoints[0].name}"
        assert not checkpoints[0].stem.endswith('_regrets'), "Should not select _regrets.pkl file"
        print(f"  ✓ Selected latest checkpoint: {checkpoints[0].name}")
    
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("Checkpoint Resume Fix Tests")
    print("=" * 70)
    
    tests = [
        test_checkpoint_selection_excludes_regrets,
        test_checkpoint_selection_with_multiple_checkpoints,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"✗ {test.__name__} FAILED")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
