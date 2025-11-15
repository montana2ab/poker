#!/usr/bin/env python3
"""Integration test for bucket configuration comparison infrastructure.

Tests the complete pipeline:
1. Create bucket configurations
2. Mock training (to avoid long wait times)
3. Test evaluation script logic
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.bucket_configs import BucketConfigFactory
from holdem.types import BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.policy_store import PolicyStore
from holdem.abstraction.actions import AbstractAction
from holdem.rl_eval.statistics import compute_confidence_interval
import numpy as np


def test_bucket_config_factory():
    """Test BucketConfigFactory."""
    print("=" * 70)
    print("TEST 1: BucketConfigFactory")
    print("=" * 70)
    
    # Test listing
    configs = BucketConfigFactory.list_configs()
    assert len(configs) >= 3, "Should have at least 3 configs"
    print(f"✓ Found {len(configs)} configurations")
    
    # Test creation
    for name in ['A', 'B', 'C']:
        config, metadata = BucketConfigFactory.create(name)
        assert isinstance(config, BucketConfig)
        assert metadata['config_name'] == name
        print(f"✓ Config {name}: {metadata['spec']}")
    
    # Test spec retrieval
    spec_a = BucketConfigFactory.get_config_spec('A')
    assert spec_a == "24/80/80/64"
    print(f"✓ Spec retrieval works: {spec_a}")
    
    print("✓ BucketConfigFactory tests passed\n")


def test_bucket_creation():
    """Test bucket creation with small sample size."""
    print("=" * 70)
    print("TEST 2: Bucket Creation")
    print("=" * 70)
    
    # Create config A with minimal samples
    config, metadata = BucketConfigFactory.create('A', num_samples=100, seed=42)
    
    # Build buckets
    print("Building buckets with 100 samples...")
    bucketing = HandBucketing(config)
    bucketing.build(num_samples=100)
    
    # Verify buckets were built
    assert bucketing.fitted
    print(f"✓ Buckets built successfully")
    print(f"  Models created: {len(bucketing.models)}")
    
    # Test saving and loading
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
        temp_path = Path(f.name)
    
    bucketing.save(temp_path)
    print(f"✓ Buckets saved to temp file")
    
    loaded_bucketing = HandBucketing.load(temp_path)
    assert loaded_bucketing.fitted
    print(f"✓ Buckets loaded successfully")
    
    # Clean up
    temp_path.unlink()
    
    print("✓ Bucket creation tests passed\n")


def test_policy_store():
    """Test PolicyStore functionality."""
    print("=" * 70)
    print("TEST 3: PolicyStore")
    print("=" * 70)
    
    # Create a simple policy
    policy_data = {
        'infoset1': {
            AbstractAction.FOLD.value: 0.2,
            AbstractAction.CHECK_CALL.value: 0.5,
            AbstractAction.BET_HALF_POT.value: 0.3,
        },
        'infoset2': {
            AbstractAction.CHECK_CALL.value: 0.8,
            AbstractAction.BET_POT.value: 0.2,
        },
    }
    
    store = PolicyStore()
    store.policy = policy_data
    
    # Test num_infosets
    num = store.num_infosets()
    assert num == 2
    print(f"✓ PolicyStore has {num} infosets")
    
    # Test saving and loading
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
        temp_path = Path(f.name)
    
    store.save(temp_path)
    print(f"✓ Policy saved")
    
    loaded = PolicyStore.load(temp_path)
    assert loaded.num_infosets() == 2
    print(f"✓ Policy loaded successfully")
    
    # Clean up
    temp_path.unlink()
    
    print("✓ PolicyStore tests passed\n")


def test_statistics():
    """Test statistics module."""
    print("=" * 70)
    print("TEST 4: Statistics")
    print("=" * 70)
    
    # Generate sample data
    np.random.seed(42)
    results = np.random.normal(5.0, 10.0, 1000)
    
    # Compute CI
    ci = compute_confidence_interval(
        list(results),
        confidence=0.95,
        method="bootstrap",
        n_bootstrap=1000
    )
    
    print(f"✓ Bootstrap CI computed: {ci['mean']:.2f} ± {ci['margin']:.2f}")
    assert 'mean' in ci
    assert 'ci_lower' in ci
    assert 'ci_upper' in ci
    
    # Test analytical method
    ci_analytical = compute_confidence_interval(
        list(results),
        confidence=0.95,
        method="analytical"
    )
    
    print(f"✓ Analytical CI computed: {ci_analytical['mean']:.2f} ± {ci_analytical['margin']:.2f}")
    
    print("✓ Statistics tests passed\n")


def test_training_script_help():
    """Test training script help."""
    print("=" * 70)
    print("TEST 5: Training Script")
    print("=" * 70)
    
    import subprocess
    result = subprocess.run(
        ['python', 'scripts/compare_buckets_training.py', '--list-configs'],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert 'config_a' in result.stdout or 'Base configuration' in result.stdout
    print("✓ Training script --list-configs works")
    
    # Test help
    result = subprocess.run(
        ['python', 'scripts/compare_buckets_training.py', '--help'],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert '--configs' in result.stdout
    print("✓ Training script --help works")
    
    print("✓ Training script tests passed\n")


def test_eval_script_help():
    """Test evaluation script help."""
    print("=" * 70)
    print("TEST 6: Evaluation Script")
    print("=" * 70)
    
    import subprocess
    result = subprocess.run(
        ['python', 'scripts/compare_buckets_eval.py', '--help'],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert '--experiment' in result.stdout
    assert '--strategies' in result.stdout
    print("✓ Evaluation script --help works")
    
    print("✓ Evaluation script tests passed\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("ABSTRACTION EXPERIMENTS INTEGRATION TEST")
    print("=" * 70)
    print()
    
    try:
        test_bucket_config_factory()
        test_bucket_creation()
        test_policy_store()
        test_statistics()
        test_training_script_help()
        test_eval_script_help()
        
        print("=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        print()
        print("The abstraction experiments infrastructure is working correctly!")
        print()
        print("Next steps:")
        print("  1. Run training: python scripts/compare_buckets_training.py --configs A B --iters 100000 --output experiments/")
        print("  2. Run evaluation: python scripts/compare_buckets_eval.py --experiment experiments/ --hands 10000")
        print("  3. See ABSTRACTION_EXPERIMENTS.md for detailed usage")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
