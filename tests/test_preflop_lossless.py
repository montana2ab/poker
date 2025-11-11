"""Tests for lossless 169 preflop abstraction."""

import pytest
from holdem.abstraction.preflop_lossless import (
    get_hand_type,
    hand_type_to_bucket,
    get_bucket_169,
    bucket_to_hand_type,
    get_hand_name,
    ALL_HAND_NAMES
)
from holdem.types import Card


class TestPreflopLossless:
    """Test cases for lossless 169 preflop abstraction."""
    
    def test_pairs(self):
        """Test that all pairs map to buckets 0-12."""
        # AA should be bucket 0
        assert get_bucket_169([Card('A', 's'), Card('A', 'h')]) == 0
        
        # KK should be bucket 1
        assert get_bucket_169([Card('K', 's'), Card('K', 'h')]) == 1
        
        # 22 should be bucket 12
        assert get_bucket_169([Card('2', 's'), Card('2', 'h')]) == 12
    
    def test_suited_hands(self):
        """Test that suited hands map to buckets 13-90."""
        # AKs should be bucket 13
        assert get_bucket_169([Card('A', 's'), Card('K', 's')]) == 13
        
        # AQs should be bucket 14
        assert get_bucket_169([Card('A', 'h'), Card('Q', 'h')]) == 14
        
        # 32s should be bucket 90 (last suited hand)
        assert get_bucket_169([Card('3', 'd'), Card('2', 'd')]) == 90
    
    def test_offsuit_hands(self):
        """Test that offsuit hands map to buckets 91-168."""
        # AKo should be bucket 91
        assert get_bucket_169([Card('A', 's'), Card('K', 'h')]) == 91
        
        # AQo should be bucket 92
        assert get_bucket_169([Card('A', 'h'), Card('Q', 'd')]) == 92
        
        # 32o should be bucket 168 (last offsuit hand)
        assert get_bucket_169([Card('3', 's'), Card('2', 'h')]) == 168
    
    def test_hand_type_ordering(self):
        """Test that cards are ordered correctly regardless of input order."""
        # AK should be same whether A comes first or second
        assert get_bucket_169([Card('A', 's'), Card('K', 's')]) == \
               get_bucket_169([Card('K', 's'), Card('A', 's')])
        
        # Same for offsuit
        assert get_bucket_169([Card('A', 's'), Card('K', 'h')]) == \
               get_bucket_169([Card('K', 'h'), Card('A', 's')])
    
    def test_suited_vs_offsuit_distinct(self):
        """Test that suited and offsuit versions map to different buckets."""
        # AKs vs AKo
        aks = get_bucket_169([Card('A', 's'), Card('K', 's')])
        ako = get_bucket_169([Card('A', 's'), Card('K', 'h')])
        assert aks != ako
        assert aks == 13  # suited
        assert ako == 91  # offsuit
    
    def test_all_169_buckets_used(self):
        """Test that we use exactly 169 buckets (0-168)."""
        # Generate all possible hand types
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        
        buckets_seen = set()
        
        # Pairs
        for rank in ranks:
            bucket = get_bucket_169([Card(rank, 's'), Card(rank, 'h')])
            buckets_seen.add(bucket)
        
        # Suited hands
        for i, high in enumerate(ranks):
            for low in ranks[i+1:]:
                bucket = get_bucket_169([Card(high, 's'), Card(low, 's')])
                buckets_seen.add(bucket)
        
        # Offsuit hands
        for i, high in enumerate(ranks):
            for low in ranks[i+1:]:
                bucket = get_bucket_169([Card(high, 's'), Card(low, 'h')])
                buckets_seen.add(bucket)
        
        # Should have exactly 169 unique buckets
        assert len(buckets_seen) == 169
        assert buckets_seen == set(range(169))
    
    def test_bucket_to_hand_type_roundtrip(self):
        """Test that we can convert bucket back to hand type."""
        # Test a few examples
        test_cases = [
            (0, ('A', 'A', False)),   # AA
            (12, ('2', '2', False)),  # 22
            (13, ('A', 'K', True)),   # AKs
            (91, ('A', 'K', False)),  # AKo
            (168, ('3', '2', False)), # 32o
        ]
        
        for bucket, expected_hand_type in test_cases:
            hand_type = bucket_to_hand_type(bucket)
            assert hand_type == expected_hand_type
    
    def test_hand_names(self):
        """Test human-readable hand names."""
        assert get_hand_name(0) == "AA"
        assert get_hand_name(1) == "KK"
        assert get_hand_name(12) == "22"
        assert get_hand_name(13) == "AKs"
        assert get_hand_name(14) == "AQs"
        assert get_hand_name(91) == "AKo"
        assert get_hand_name(92) == "AQo"
        assert get_hand_name(168) == "32o"
    
    def test_all_hand_names_list(self):
        """Test that ALL_HAND_NAMES contains all 169 hand names."""
        assert len(ALL_HAND_NAMES) == 169
        assert ALL_HAND_NAMES[0] == "AA"
        assert ALL_HAND_NAMES[13] == "AKs"
        assert ALL_HAND_NAMES[91] == "AKo"
        assert ALL_HAND_NAMES[168] == "32o"
    
    def test_get_hand_type(self):
        """Test get_hand_type function."""
        # Pair
        high, low, suited = get_hand_type([Card('A', 's'), Card('A', 'h')])
        assert high == 'A' and low == 'A' and suited == False
        
        # Suited
        high, low, suited = get_hand_type([Card('A', 's'), Card('K', 's')])
        assert high == 'A' and low == 'K' and suited == True
        
        # Offsuit
        high, low, suited = get_hand_type([Card('A', 's'), Card('K', 'h')])
        assert high == 'A' and low == 'K' and suited == False
        
        # Order should be normalized
        high, low, suited = get_hand_type([Card('K', 's'), Card('A', 'h')])
        assert high == 'A' and low == 'K' and suited == False
    
    def test_hand_type_to_bucket_all_hands(self):
        """Test that hand_type_to_bucket works for all 169 hand types."""
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        
        buckets = set()
        
        # Pairs
        for rank in ranks:
            bucket = hand_type_to_bucket(rank, rank, False)
            assert 0 <= bucket <= 12
            buckets.add(bucket)
        
        # Suited
        for i, high in enumerate(ranks):
            for low in ranks[i+1:]:
                bucket = hand_type_to_bucket(high, low, True)
                assert 13 <= bucket <= 90
                buckets.add(bucket)
        
        # Offsuit
        for i, high in enumerate(ranks):
            for low in ranks[i+1:]:
                bucket = hand_type_to_bucket(high, low, False)
                assert 91 <= bucket <= 168
                buckets.add(bucket)
        
        # Should have all 169 buckets
        assert len(buckets) == 169
    
    def test_consistency_with_real_cards(self):
        """Test that abstraction is consistent across different suits."""
        # All AK suited combinations should map to same bucket
        aks_buckets = [
            get_bucket_169([Card('A', 's'), Card('K', 's')]),
            get_bucket_169([Card('A', 'h'), Card('K', 'h')]),
            get_bucket_169([Card('A', 'd'), Card('K', 'd')]),
            get_bucket_169([Card('A', 'c'), Card('K', 'c')]),
        ]
        assert len(set(aks_buckets)) == 1  # All same
        assert aks_buckets[0] == 13
        
        # All AK offsuit combinations should map to same bucket
        ako_buckets = [
            get_bucket_169([Card('A', 's'), Card('K', 'h')]),
            get_bucket_169([Card('A', 'h'), Card('K', 'd')]),
            get_bucket_169([Card('A', 'd'), Card('K', 'c')]),
            get_bucket_169([Card('A', 'c'), Card('K', 's')]),
        ]
        assert len(set(ako_buckets)) == 1  # All same
        assert ako_buckets[0] == 91
    
    def test_invalid_inputs(self):
        """Test error handling for invalid inputs."""
        # Empty list
        with pytest.raises(ValueError):
            get_bucket_169([])
        
        # Only one card
        with pytest.raises(ValueError):
            get_bucket_169([Card('A', 's')])
        
        # More than two cards
        with pytest.raises(ValueError):
            get_bucket_169([Card('A', 's'), Card('K', 's'), Card('Q', 's')])
        
        # Invalid bucket index
        with pytest.raises(ValueError):
            bucket_to_hand_type(-1)
        
        with pytest.raises(ValueError):
            bucket_to_hand_type(169)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
