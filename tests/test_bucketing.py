"""Test bucketing functionality."""

import pytest
import numpy as np
from pathlib import Path
from holdem.types import BucketConfig, Street, Card
from holdem.abstraction.bucketing import HandBucketing, generate_random_hands


def test_bucketing_stable_with_seed():
    """Test that bucketing produces stable results with same seed."""
    config = BucketConfig(
        k_preflop=8,
        k_flop=20,
        k_turn=15,
        k_river=10,
        num_samples=1000,
        seed=42
    )
    
    # Build buckets twice with same seed
    bucketing1 = HandBucketing(config)
    bucketing1.build(num_samples=1000)
    
    bucketing2 = HandBucketing(config)
    bucketing2.build(num_samples=1000)
    
    # Test same bucket assignments
    test_hands = generate_random_hands(100, Street.FLOP, seed=123)
    
    for hole_cards, board in test_hands:
        bucket1 = bucketing1.get_bucket(hole_cards, board, Street.FLOP)
        bucket2 = bucketing2.get_bucket(hole_cards, board, Street.FLOP)
        assert bucket1 == bucket2, "Buckets should be stable with same seed"


def test_bucketing_produces_files(tmp_path):
    """Test that bucketing produces output files."""
    config = BucketConfig(
        k_preflop=8,
        k_flop=20,
        k_turn=15,
        k_river=10,
        num_samples=500,
        seed=42
    )
    
    bucketing = HandBucketing(config)
    bucketing.build(num_samples=500)
    
    # Save
    out_path = tmp_path / "test_buckets.pkl"
    bucketing.save(out_path)
    
    assert out_path.exists(), "Bucket file should exist"
    
    # Load and verify
    loaded = HandBucketing.load(out_path)
    assert loaded.fitted, "Loaded buckets should be fitted"
    
    # Test that loaded buckets work
    test_hands = generate_random_hands(10, Street.PREFLOP, seed=456)
    for hole_cards, board in test_hands:
        bucket = loaded.get_bucket(hole_cards, board, Street.PREFLOP)
        assert 0 <= bucket < config.k_preflop, "Bucket should be in valid range"


def test_bucket_range():
    """Test that bucket assignments are in valid range."""
    config = BucketConfig(
        k_preflop=12,
        k_flop=60,
        k_turn=40,
        k_river=24,
        num_samples=500,
        seed=42
    )
    
    bucketing = HandBucketing(config)
    bucketing.build(num_samples=500)
    
    # Test each street
    streets_and_k = [
        (Street.PREFLOP, config.k_preflop),
        (Street.FLOP, config.k_flop),
        (Street.TURN, config.k_turn),
        (Street.RIVER, config.k_river)
    ]
    
    for street, k in streets_and_k:
        test_hands = generate_random_hands(50, street, seed=street.value * 100)
        for hole_cards, board in test_hands:
            bucket = bucketing.get_bucket(hole_cards, board, street)
            assert 0 <= bucket < k, f"Bucket {bucket} out of range [0, {k}) for {street.name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
