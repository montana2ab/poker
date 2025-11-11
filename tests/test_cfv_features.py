"""Tests for CFV feature construction."""

import pytest
import numpy as np
from holdem.value_net.features import (
    CFVFeatureBuilder,
    FeatureStats,
    get_feature_dimension,
    create_bucket_embeddings
)
from holdem.types import Street, Position


def test_feature_dimension():
    """Test that feature dimension calculation is correct."""
    embed_dim = 64
    expected_dim = 4 + 1 + 6 + 1 + 6 + 1 + 1 + 1 + 1 + embed_dim + (6 * embed_dim)
    
    actual_dim = get_feature_dimension(embed_dim)
    
    assert actual_dim == expected_dim, f"Expected {expected_dim}, got {actual_dim}"


def test_bucket_embeddings_creation():
    """Test bucket embedding creation."""
    num_buckets = 100
    embed_dim = 64
    seed = 42
    
    embeddings = create_bucket_embeddings(num_buckets, embed_dim, seed)
    
    assert embeddings.shape == (num_buckets, embed_dim)
    assert embeddings.dtype == np.float32
    
    # Check that embeddings are not all zeros
    assert np.abs(embeddings).sum() > 0
    
    # Check reproducibility
    embeddings2 = create_bucket_embeddings(num_buckets, embed_dim, seed)
    np.testing.assert_array_equal(embeddings, embeddings2)


def test_feature_builder_basic():
    """Test basic feature building."""
    num_buckets = 100
    embed_dim = 64
    bucket_embeddings = create_bucket_embeddings(num_buckets, embed_dim, seed=42)
    
    builder = CFVFeatureBuilder(
        bucket_embeddings=bucket_embeddings,
        topk_range=16,
        embed_dim=embed_dim
    )
    
    # Build features
    ranges = {
        Position.BTN: [(10, 0.8), (20, 0.2)],
        Position.BB: [(15, 0.5), (25, 0.5)]
    }
    
    features = builder.build_features(
        street=Street.FLOP,
        num_players=2,
        hero_position=Position.BTN,
        spr=5.0,
        pot_size=10.0,
        to_call=2.0,
        last_bet=2.0,
        action_set="balanced",
        public_bucket=50,
        ranges=ranges
    )
    
    # Check feature vector
    feature_vector = features.to_vector()
    expected_dim = get_feature_dimension(embed_dim)
    
    assert feature_vector.shape == (expected_dim,)
    assert feature_vector.dtype == np.float32
    
    # Check street one-hot
    assert features.street_onehot[Street.FLOP.value] == 1.0
    assert features.street_onehot.sum() == 1.0
    
    # Check position one-hot
    assert features.hero_position_onehot[Position.BTN.value] == 1.0
    assert features.hero_position_onehot.sum() == 1.0
    
    # Check SPR bins
    assert features.spr_bins.sum() == 1.0


def test_spr_binning():
    """Test SPR binning into 6 categories."""
    num_buckets = 100
    embed_dim = 64
    bucket_embeddings = create_bucket_embeddings(num_buckets, embed_dim, seed=42)
    
    builder = CFVFeatureBuilder(
        bucket_embeddings=bucket_embeddings,
        topk_range=16,
        embed_dim=embed_dim
    )
    
    # Test different SPR values
    test_cases = [
        (1.0, 0),   # [0-2)
        (3.0, 1),   # [2-5)
        (7.0, 2),   # [5-10)
        (15.0, 3),  # [10-20)
        (30.0, 4),  # [20-50)
        (60.0, 5),  # [50+)
    ]
    
    for spr, expected_bin in test_cases:
        spr_bins = builder._bin_spr(spr)
        assert spr_bins[expected_bin] == 1.0, f"SPR {spr} should be in bin {expected_bin}"
        assert spr_bins.sum() == 1.0


def test_range_embeddings_zero_padding():
    """Test that missing positions are zero-padded in range embeddings."""
    num_buckets = 100
    embed_dim = 64
    bucket_embeddings = create_bucket_embeddings(num_buckets, embed_dim, seed=42)
    
    builder = CFVFeatureBuilder(
        bucket_embeddings=bucket_embeddings,
        topk_range=16,
        embed_dim=embed_dim
    )
    
    # Only provide BTN range (heads-up)
    ranges = {
        Position.BTN: [(10, 1.0)]
    }
    
    range_embeddings = builder._build_range_embeddings(ranges, num_players=2)
    
    # Should be [6, embed_dim] with most rows zero
    assert range_embeddings.shape == (6, embed_dim)
    
    # BTN row should be non-zero
    assert np.abs(range_embeddings[Position.BTN.value]).sum() > 0
    
    # Other rows should be zero (except BB which might have data)
    # At least some rows should be zero
    zero_rows = (np.abs(range_embeddings).sum(axis=1) == 0).sum()
    assert zero_rows >= 4, "Expected at least 4 zero-padded rows for 2-player game"


def test_topk_range_stability():
    """Test that top-K range selection is stable."""
    num_buckets = 100
    embed_dim = 64
    bucket_embeddings = create_bucket_embeddings(num_buckets, embed_dim, seed=42)
    
    builder = CFVFeatureBuilder(
        bucket_embeddings=bucket_embeddings,
        topk_range=16,
        embed_dim=embed_dim
    )
    
    # Create range with >16 buckets
    ranges = {
        Position.BTN: [(i, 1.0 / (i + 1)) for i in range(20)]
    }
    
    range_embeddings1 = builder._build_range_embeddings(ranges, num_players=2)
    range_embeddings2 = builder._build_range_embeddings(ranges, num_players=2)
    
    # Should be identical
    np.testing.assert_array_equal(range_embeddings1, range_embeddings2)
    
    # Should only use top-16
    # (Can't directly verify, but embeddings should be deterministic)


def test_feature_normalization():
    """Test feature normalization with FeatureStats."""
    # Create dummy stats
    features = np.array([1.0, 2.0, 3.0, 4.0])
    mean = np.array([1.5, 2.5, 3.5, 4.5])
    std = np.array([0.5, 0.5, 0.5, 0.5])
    
    stats = FeatureStats(mean=mean, std=std)
    
    # Normalize
    normalized = stats.normalize(features)
    
    # Check z-score
    expected = (features - mean) / std
    np.testing.assert_array_almost_equal(normalized, expected)


def test_feature_stats_serialization():
    """Test FeatureStats to_dict and from_dict."""
    mean = np.array([1.0, 2.0, 3.0])
    std = np.array([0.1, 0.2, 0.3])
    
    stats = FeatureStats(mean=mean, std=std)
    
    # Serialize
    stats_dict = stats.to_dict()
    
    # Deserialize
    stats_loaded = FeatureStats.from_dict(stats_dict)
    
    # Check equality
    np.testing.assert_array_equal(stats_loaded.mean, mean)
    np.testing.assert_array_equal(stats_loaded.std, std)


def test_out_of_range_bucket():
    """Test handling of out-of-range bucket IDs."""
    num_buckets = 100
    embed_dim = 64
    bucket_embeddings = create_bucket_embeddings(num_buckets, embed_dim, seed=42)
    
    builder = CFVFeatureBuilder(
        bucket_embeddings=bucket_embeddings,
        topk_range=16,
        embed_dim=embed_dim
    )
    
    # Test with out-of-range public bucket
    ranges = {
        Position.BTN: [(10, 1.0)]
    }
    
    features = builder.build_features(
        street=Street.FLOP,
        num_players=2,
        hero_position=Position.BTN,
        spr=5.0,
        pot_size=10.0,
        to_call=2.0,
        last_bet=2.0,
        action_set="balanced",
        public_bucket=9999,  # Out of range
        ranges=ranges
    )
    
    # Should return zero embedding for out-of-range bucket
    assert features.public_bucket_embedding.sum() == 0.0
