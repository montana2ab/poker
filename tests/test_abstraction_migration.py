"""Tests for abstraction migration and hash validation.

This module tests that strategies trained with different bucket configurations
are properly rejected to prevent mixing incompatible abstractions.
"""

import pytest
import tempfile
from pathlib import Path
from holdem.types import MCCFRConfig, BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.mccfr.policy_store import PolicyStore


def create_bucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2, seed=42, num_players=2):
    """Helper to create and build a bucketing instance."""
    config_bucket = BucketConfig(
        k_preflop=k_preflop, 
        k_flop=k_flop, 
        k_turn=k_turn, 
        k_river=k_river, 
        seed=seed,
        num_players=num_players,
        num_samples=100  # Small number for faster tests
    )
    bucketing = HandBucketing(config=config_bucket)
    bucketing.build()  # Build the buckets
    return bucketing


def test_policy_save_includes_bucket_metadata():
    """Test that saved policies include bucket metadata."""
    bucketing = create_bucketing()
    config = MCCFRConfig(num_iterations=10)
    solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    # Run a few iterations
    for i in range(10):
        solver.sampler.sample_iteration(i + 1)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Save policy
        solver.save_policy(logdir)
        
        # Load and verify pickle format
        policy_pkl = PolicyStore.load(logdir / "avg_policy.pkl", validate_buckets=False)
        assert policy_pkl.bucket_metadata is not None
        assert 'bucket_file_sha' in policy_pkl.bucket_metadata
        assert policy_pkl.bucket_metadata['k_preflop'] == 2
        assert policy_pkl.bucket_metadata['seed'] == 42
        
        # Load and verify JSON format
        policy_json = PolicyStore.load_json(logdir / "avg_policy.json", validate_buckets=False)
        assert policy_json.bucket_metadata is not None
        assert 'bucket_file_sha' in policy_json.bucket_metadata
        assert policy_json.bucket_metadata['k_preflop'] == 2


def test_policy_load_accepts_matching_hash():
    """Test that policy loading succeeds when hash matches."""
    bucketing = create_bucketing()
    
    config = MCCFRConfig(num_iterations=10)
    solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    # Run a few iterations and save
    for i in range(10):
        solver.sampler.sample_iteration(i + 1)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        solver.save_policy(logdir)
        
        # Calculate expected hash
        expected_hash = solver._calculate_bucket_hash()
        
        # Load with validation - should succeed
        policy = PolicyStore.load(
            logdir / "avg_policy.pkl", 
            expected_bucket_hash=expected_hash,
            validate_buckets=True
        )
        assert policy is not None
        assert policy.bucket_metadata['bucket_file_sha'] == expected_hash


def test_policy_load_rejects_mismatched_hash():
    """Test that policy loading fails when hash doesn't match."""
    bucketing = create_bucketing()
    
    config = MCCFRConfig(num_iterations=10)
    solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    # Run a few iterations and save
    for i in range(10):
        solver.sampler.sample_iteration(i + 1)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        solver.save_policy(logdir)
        
        # Try to load with wrong expected hash
        wrong_hash = "0" * 64  # Fake hash
        
        with pytest.raises(ValueError, match="Abstraction hash mismatch"):
            PolicyStore.load(
                logdir / "avg_policy.pkl",
                expected_bucket_hash=wrong_hash,
                validate_buckets=True
            )


def test_policy_load_json_rejects_mismatched_hash():
    """Test that JSON policy loading also validates hash."""
    bucketing = create_bucketing()
    
    config = MCCFRConfig(num_iterations=10)
    solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    # Run a few iterations and save
    for i in range(10):
        solver.sampler.sample_iteration(i + 1)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        solver.save_policy(logdir)
        
        # Try to load JSON with wrong expected hash
        wrong_hash = "0" * 64
        
        with pytest.raises(ValueError, match="Abstraction hash mismatch"):
            PolicyStore.load_json(
                logdir / "avg_policy.json",
                expected_bucket_hash=wrong_hash,
                validate_buckets=True
            )


def test_different_bucket_configs_produce_different_hashes():
    """Test that different bucket configurations produce different hashes."""
    bucketing1 = create_bucketing(k_preflop=2, seed=42)
    bucketing2 = create_bucketing(k_preflop=3, seed=42)
    
    
    
    config = MCCFRConfig(num_iterations=10)
    solver1 = MCCFRSolver(config=config, bucketing=bucketing1, num_players=2)
    solver2 = MCCFRSolver(config=config, bucketing=bucketing2, num_players=2)
    
    hash1 = solver1._calculate_bucket_hash()
    hash2 = solver2._calculate_bucket_hash()
    
    assert hash1 != hash2, "Different bucket configurations must produce different hashes"


def test_policy_from_different_buckets_rejected():
    """Test migration scenario: policy trained with one bucket config rejected by another.
    
    This simulates the real-world scenario where:
    1. User trains a policy with bucket config A
    2. User changes bucket configuration to B
    3. User tries to load the old policy - should be rejected
    """
    # Create first bucket configuration and train policy
    bucketing1 = create_bucketing(k_preflop=2, seed=42)
    
    config = MCCFRConfig(num_iterations=10)
    solver1 = MCCFRSolver(config=config, bucketing=bucketing1, num_players=2)
    
    for i in range(10):
        solver1.sampler.sample_iteration(i + 1)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        solver1.save_policy(logdir)
        
        # Create second solver with DIFFERENT bucket configuration
        bucketing2 = create_bucketing(k_preflop=3, seed=42)
        
        solver2 = MCCFRSolver(config=config, bucketing=bucketing2, num_players=2)
        expected_hash2 = solver2._calculate_bucket_hash()
        
        # Try to load policy trained with bucketing1 using bucketing2's hash
        # This should FAIL with clear error message
        with pytest.raises(ValueError, match="Abstraction hash mismatch"):
            PolicyStore.load(
                logdir / "avg_policy.pkl",
                expected_bucket_hash=expected_hash2,
                validate_buckets=True
            )


def test_policy_without_metadata_warns_but_loads():
    """Test that legacy policies without metadata generate warnings but still load."""
    # Create a policy without metadata (simulating legacy policy)
    policy_store = PolicyStore()
    policy_store.policy = {
        'test_infoset': {'fold': 0.5, 'call': 0.5}
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        policy_path = Path(tmpdir) / "legacy_policy.pkl"
        
        # Save without metadata (using old-style format)
        from holdem.utils.serialization import save_pickle
        save_pickle({'policy': policy_store.policy}, policy_path)
        
        # Load with validation - should warn but not fail
        loaded = PolicyStore.load(policy_path, validate_buckets=True)
        assert loaded.bucket_metadata is None
        assert len(loaded.policy) == 1


def test_policy_validation_can_be_disabled():
    """Test that validation can be bypassed when explicitly disabled."""
    bucketing = create_bucketing()
    
    config = MCCFRConfig(num_iterations=10)
    solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    for i in range(10):
        solver.sampler.sample_iteration(i + 1)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        solver.save_policy(logdir)
        
        # Load with wrong hash but validation disabled - should succeed
        wrong_hash = "0" * 64
        policy = PolicyStore.load(
            logdir / "avg_policy.pkl",
            expected_bucket_hash=wrong_hash,
            validate_buckets=False  # Explicitly disable validation
        )
        assert policy is not None


def test_same_bucket_config_produces_same_hash():
    """Test that the same bucketing instance produces identical hashes."""
    bucketing = create_bucketing(k_preflop=2, seed=42)
    
    config = MCCFRConfig(num_iterations=10)
    solver1 = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    solver2 = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    # Same bucketing instance should produce same hash
    hash1 = solver1._calculate_bucket_hash()
    hash2 = solver2._calculate_bucket_hash()
    
    assert hash1 == hash2, "Same bucketing instance must produce identical hashes"


def test_bucket_config_hash_includes_cluster_centers():
    """Test that cluster centers affect the hash (not just configuration parameters).
    
    Even with identical configuration parameters, if cluster centers differ
    (which happens when building buckets independently due to random sampling),
    the hash should be different. This prevents accidentally using buckets
    from different builds.
    """
    # Build two separate bucketing instances with same config
    bucketing1 = create_bucketing(k_preflop=2, seed=42)
    bucketing2 = create_bucketing(k_preflop=2, seed=42)
    
    config = MCCFRConfig(num_iterations=10)
    solver1 = MCCFRSolver(config=config, bucketing=bucketing1, num_players=2)
    solver2 = MCCFRSolver(config=config, bucketing=bucketing2, num_players=2)
    
    hash1 = solver1._calculate_bucket_hash()
    hash2 = solver2._calculate_bucket_hash()
    
    # Hashes will be different because cluster centers differ (random sampling)
    # This is CORRECT behavior - we don't want to mix buckets from different builds
    assert hash1 != hash2, ("Hash must include cluster centers, not just config params. "
                           "Different bucket builds should have different hashes.")


def test_policy_load_without_expected_hash_only_informs():
    """Test that loading without expected hash provides info but doesn't validate."""
    bucketing = create_bucketing()
    
    config = MCCFRConfig(num_iterations=10)
    solver = MCCFRSolver(config=config, bucketing=bucketing, num_players=2)
    
    for i in range(10):
        solver.sampler.sample_iteration(i + 1)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        solver.save_policy(logdir)
        
        # Load without expected hash - should load successfully
        policy = PolicyStore.load(
            logdir / "avg_policy.pkl",
            expected_bucket_hash=None,
            validate_buckets=True
        )
        assert policy is not None
        assert policy.bucket_metadata is not None


def test_num_players_in_hash():
    """Test that different num_players values produce different hashes."""
    bucketing1 = create_bucketing(k_preflop=2, seed=42, num_players=2)
    bucketing2 = create_bucketing(k_preflop=2, seed=42, num_players=3)
    
    
    
    config = MCCFRConfig(num_iterations=10)
    solver1 = MCCFRSolver(config=config, bucketing=bucketing1, num_players=2)
    solver2 = MCCFRSolver(config=config, bucketing=bucketing2, num_players=3)
    
    hash1 = solver1._calculate_bucket_hash()
    hash2 = solver2._calculate_bucket_hash()
    
    assert hash1 != hash2, "Different num_players must produce different hashes"


def test_legacy_json_format_compatibility():
    """Test that old JSON format (raw policy dict) still loads."""
    # Create old-style JSON policy (just the policy dict, no metadata wrapper)
    legacy_policy = {
        'test_infoset': {'fold': 0.5, 'call': 0.5}
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        from holdem.utils.serialization import save_json
        policy_path = Path(tmpdir) / "legacy_policy.json"
        save_json(legacy_policy, policy_path)
        
        # Load legacy format - should work
        loaded = PolicyStore.load_json(policy_path, validate_buckets=False)
        assert loaded.bucket_metadata is None
        assert len(loaded.policy) == 1
        assert 'test_infoset' in loaded.policy
