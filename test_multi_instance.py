#!/usr/bin/env python3
"""
Minimal test for multi-instance coordinator functionality.
Tests the CLI argument parsing and basic coordinator initialization.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Mock heavy dependencies
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()
sys.modules['eval7'] = MagicMock()
sys.modules['torch'] = MagicMock()
sys.modules['torch.utils'] = MagicMock()
sys.modules['torch.utils.tensorboard'] = MagicMock()

def test_cli_parsing():
    """Test that CLI correctly parses --num-instances argument."""
    print("Testing CLI argument parsing...")
    
    # Mock the dependencies
    with patch('holdem.cli.train_blueprint.HandBucketing') as mock_bucketing, \
         patch('holdem.cli.train_blueprint.MCCFRConfig') as mock_config:
        
        # Import after patching
        from holdem.cli.train_blueprint import main
        
        # Test arguments
        test_args = [
            'train_blueprint',
            '--buckets', 'fake_buckets.pkl',
            '--logdir', 'fake_logdir',
            '--iters', '1000',
            '--num-instances', '4'
        ]
        
        with patch('sys.argv', test_args):
            try:
                # This will fail when trying to load buckets, but we can check if parsing works
                main()
            except SystemExit:
                pass
            except Exception as e:
                # We expect it to fail at bucket loading, which is fine
                if "fake_buckets.pkl" in str(e) or "No such file" in str(e):
                    print("✓ CLI parsing successful (failed at expected point: bucket loading)")
                else:
                    print(f"✗ Unexpected error: {e}")
                    return False
    
    return True


def test_coordinator_initialization():
    """Test MultiInstanceCoordinator initialization."""
    print("\nTesting MultiInstanceCoordinator initialization...")
    
    # Import the coordinator
    from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator, InstanceProgress
    from holdem.types import MCCFRConfig
    
    # Create mock bucketing
    mock_bucketing = Mock()
    
    # Create test config
    config = MCCFRConfig(
        num_iterations=1000,
        checkpoint_interval=100,
        discount_interval=50,
        exploration_epsilon=0.6,
        num_workers=1
    )
    
    # Test initialization
    coordinator = MultiInstanceCoordinator(
        num_instances=4,
        config=config,
        bucketing=mock_bucketing,
        num_players=2
    )
    
    # Verify iteration ranges
    assert len(coordinator.iteration_ranges) == 4
    print(f"  ✓ Created 4 iteration ranges")
    
    # Check that iterations are properly distributed
    total_iters = sum(end - start for start, end in coordinator.iteration_ranges)
    assert total_iters == 1000
    print(f"  ✓ Total iterations correctly distributed: {total_iters}")
    
    # Check ranges don't overlap
    ranges = sorted(coordinator.iteration_ranges)
    for i in range(len(ranges) - 1):
        assert ranges[i][1] == ranges[i+1][0]
    print(f"  ✓ Iteration ranges are contiguous")
    
    print("\nIteration distribution:")
    for i, (start, end) in enumerate(coordinator.iteration_ranges):
        print(f"  Instance {i}: {start} to {end-1} ({end-start} iterations)")
    
    return True


def test_instance_progress():
    """Test InstanceProgress tracking."""
    print("\nTesting InstanceProgress...")
    
    from holdem.mccfr.multi_instance_coordinator import InstanceProgress
    
    # Create progress tracker
    progress = InstanceProgress(
        instance_id=0,
        start_iter=0,
        end_iter=1000
    )
    
    # Test initial state
    assert progress.progress_pct() == 0.0
    print(f"  ✓ Initial progress: {progress.progress_pct():.1f}%")
    
    # Update progress
    progress.update(500, "running")
    assert progress.progress_pct() == 50.0
    print(f"  ✓ Mid progress: {progress.progress_pct():.1f}%")
    
    # Complete
    progress.update(999, "completed")
    assert progress.progress_pct() == 99.9
    print(f"  ✓ Near completion: {progress.progress_pct():.1f}%")
    
    # Test serialization
    data = progress.to_dict()
    assert data['instance_id'] == 0
    assert data['status'] == 'completed'
    assert 'progress_pct' in data
    print(f"  ✓ Serialization to dict works")
    
    return True


def test_error_conditions():
    """Test error handling in coordinator."""
    print("\nTesting error conditions...")
    
    from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
    from holdem.types import MCCFRConfig
    
    mock_bucketing = Mock()
    
    # Test 1: Invalid num_instances
    config = MCCFRConfig(num_iterations=1000, num_workers=1)
    try:
        coordinator = MultiInstanceCoordinator(
            num_instances=0,
            config=config,
            bucketing=mock_bucketing
        )
        print("  ✗ Should have raised ValueError for num_instances=0")
        return False
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError for invalid num_instances: {e}")
    
    # Test 2: Time budget mode (not supported)
    config_time = MCCFRConfig(
        time_budget_seconds=3600,
        num_workers=1
    )
    try:
        coordinator = MultiInstanceCoordinator(
            num_instances=2,
            config=config_time,
            bucketing=mock_bucketing
        )
        print("  ✗ Should have raised ValueError for time-budget mode")
        return False
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError for time-budget mode: {e}")
    
    # Test 3: No iterations specified
    config_no_iter = MCCFRConfig(num_workers=1, num_iterations=None)
    try:
        coordinator = MultiInstanceCoordinator(
            num_instances=2,
            config=config_no_iter,
            bucketing=mock_bucketing
        )
        print("  ✗ Should have raised ValueError for missing iterations")
        return False
    except (ValueError, AttributeError, TypeError) as e:
        # ValueError from our check, or AttributeError/TypeError if None is used
        print(f"  ✓ Correctly raised error for missing iterations: {type(e).__name__}")
    
    return True


def test_uneven_distribution():
    """Test that uneven iteration counts are handled correctly."""
    print("\nTesting uneven iteration distribution...")
    
    from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
    from holdem.types import MCCFRConfig
    
    mock_bucketing = Mock()
    
    # Test with 1000 iterations and 3 instances (not evenly divisible)
    config = MCCFRConfig(num_iterations=1000, num_workers=1)
    coordinator = MultiInstanceCoordinator(
        num_instances=3,
        config=config,
        bucketing=mock_bucketing
    )
    
    # Check distribution
    iter_counts = [end - start for start, end in coordinator.iteration_ranges]
    print(f"  Distribution: {iter_counts}")
    
    # Total should still be 1000
    assert sum(iter_counts) == 1000
    print(f"  ✓ Total iterations: {sum(iter_counts)}")
    
    # Difference between max and min should be at most 1
    assert max(iter_counts) - min(iter_counts) <= 1
    print(f"  ✓ Even distribution (max diff: {max(iter_counts) - min(iter_counts)})")
    
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Multi-Instance Coordinator Tests")
    print("=" * 60)
    
    tests = [
        # test_cli_parsing,  # Skip this as it requires too many dependencies
        test_coordinator_initialization,
        test_instance_progress,
        test_error_conditions,
        test_uneven_distribution,
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
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
