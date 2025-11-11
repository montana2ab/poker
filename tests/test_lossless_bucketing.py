"""Tests for lossless 169 preflop abstraction integration with bucketing."""

import pytest
from pathlib import Path
import tempfile
from holdem.abstraction.bucketing import HandBucketing
from holdem.types import BucketConfig, Street, Card


class TestLosslessPreflopBucketing:
    """Test cases for lossless 169 preflop abstraction in bucketing system."""
    
    def test_lossless_preflop_initialization(self):
        """Test that lossless preflop can be enabled."""
        config = BucketConfig(
            k_preflop=169,  # Will be ignored when using lossless
            k_flop=50,
            k_turn=50,
            k_river=50,
            num_samples=100,
            seed=42,
            num_players=2
        )
        
        bucketing = HandBucketing(config, use_lossless_preflop=True)
        assert bucketing.use_lossless_preflop is True
    
    def test_lossless_preflop_build_skips_kmeans(self):
        """Test that k-means is skipped for preflop when using lossless."""
        config = BucketConfig(
            k_preflop=169,
            k_flop=50,
            k_turn=50,
            k_river=50,
            num_samples=100,
            seed=42,
            num_players=2
        )
        
        bucketing = HandBucketing(config, use_lossless_preflop=True)
        bucketing.build(num_samples=100)
        
        # Preflop should not have a model
        assert Street.PREFLOP not in bucketing.models
        
        # Other streets should have models
        assert Street.FLOP in bucketing.models
        assert Street.TURN in bucketing.models
        assert Street.RIVER in bucketing.models
        
        assert bucketing.fitted is True
    
    def test_lossless_preflop_get_bucket(self):
        """Test that get_bucket uses lossless abstraction for preflop."""
        config = BucketConfig(
            k_preflop=169,
            k_flop=50,
            k_turn=50,
            k_river=50,
            num_samples=100,
            seed=42,
            num_players=2
        )
        
        bucketing = HandBucketing(config, use_lossless_preflop=True)
        bucketing.build(num_samples=100)
        
        # Test AA (should be bucket 0)
        bucket = bucketing.get_bucket([Card('A', 's'), Card('A', 'h')], [], Street.PREFLOP)
        assert bucket == 0
        
        # Test AKs (should be bucket 13)
        bucket = bucketing.get_bucket([Card('A', 's'), Card('K', 's')], [], Street.PREFLOP)
        assert bucket == 13
        
        # Test AKo (should be bucket 91)
        bucket = bucketing.get_bucket([Card('A', 's'), Card('K', 'h')], [], Street.PREFLOP)
        assert bucket == 91
        
        # Test 32o (should be bucket 168)
        bucket = bucketing.get_bucket([Card('3', 's'), Card('2', 'h')], [], Street.PREFLOP)
        assert bucket == 168
    
    def test_lossless_preflop_consistent_bucketing(self):
        """Test that same hand types map to same bucket."""
        config = BucketConfig(
            k_preflop=169,
            k_flop=50,
            k_turn=50,
            k_river=50,
            num_samples=100,
            seed=42,
            num_players=2
        )
        
        bucketing = HandBucketing(config, use_lossless_preflop=True)
        bucketing.build(num_samples=100)
        
        # All AKs hands should map to same bucket
        aks_buckets = [
            bucketing.get_bucket([Card('A', 's'), Card('K', 's')], [], Street.PREFLOP),
            bucketing.get_bucket([Card('A', 'h'), Card('K', 'h')], [], Street.PREFLOP),
            bucketing.get_bucket([Card('A', 'd'), Card('K', 'd')], [], Street.PREFLOP),
            bucketing.get_bucket([Card('A', 'c'), Card('K', 'c')], [], Street.PREFLOP),
        ]
        assert len(set(aks_buckets)) == 1  # All same
        assert aks_buckets[0] == 13
    
    def test_lossless_preflop_save_and_load(self):
        """Test that lossless preflop flag is saved and loaded."""
        config = BucketConfig(
            k_preflop=169,
            k_flop=50,
            k_turn=50,
            k_river=50,
            num_samples=100,
            seed=42,
            num_players=2
        )
        
        bucketing = HandBucketing(config, use_lossless_preflop=True)
        bucketing.build(num_samples=100)
        
        # Save to temporary file
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "buckets.pkl"
            bucketing.save(save_path)
            
            # Load from file
            loaded_bucketing = HandBucketing.load(save_path)
            
            # Check that lossless preflop is preserved
            assert loaded_bucketing.use_lossless_preflop is True
            
            # Check that bucketing still works
            bucket = loaded_bucketing.get_bucket([Card('A', 's'), Card('A', 'h')], [], Street.PREFLOP)
            assert bucket == 0
    
    def test_kmeans_preflop_still_works(self):
        """Test that k-means preflop still works when lossless is disabled."""
        config = BucketConfig(
            k_preflop=24,
            k_flop=50,
            k_turn=50,
            k_river=50,
            num_samples=100,
            seed=42,
            num_players=2
        )
        
        bucketing = HandBucketing(config, use_lossless_preflop=False)
        bucketing.build(num_samples=100)
        
        # Preflop should have a k-means model
        assert Street.PREFLOP in bucketing.models
        
        # Get bucket should work
        bucket = bucketing.get_bucket([Card('A', 's'), Card('A', 'h')], [], Street.PREFLOP)
        assert 0 <= bucket < 24
    
    def test_postflop_bucketing_unaffected(self):
        """Test that postflop bucketing is not affected by lossless preflop."""
        config = BucketConfig(
            k_preflop=169,
            k_flop=50,
            k_turn=50,
            k_river=50,
            num_samples=100,
            seed=42,
            num_players=2
        )
        
        bucketing = HandBucketing(config, use_lossless_preflop=True)
        bucketing.build(num_samples=100)
        
        # Test flop bucketing
        flop_bucket = bucketing.get_bucket(
            [Card('A', 's'), Card('K', 's')],
            [Card('Q', 'h'), Card('J', 'h'), Card('T', 'h')],
            Street.FLOP
        )
        assert 0 <= flop_bucket < 50
        
        # Test turn bucketing
        turn_bucket = bucketing.get_bucket(
            [Card('A', 's'), Card('K', 's')],
            [Card('Q', 'h'), Card('J', 'h'), Card('T', 'h'), Card('9', 'h')],
            Street.TURN
        )
        assert 0 <= turn_bucket < 50
        
        # Test river bucketing
        river_bucket = bucketing.get_bucket(
            [Card('A', 's'), Card('K', 's')],
            [Card('Q', 'h'), Card('J', 'h'), Card('T', 'h'), Card('9', 'h'), Card('8', 'h')],
            Street.RIVER
        )
        assert 0 <= river_bucket < 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
