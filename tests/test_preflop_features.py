"""Test preflop feature extraction."""

import pytest
import numpy as np
from holdem.types import Card
from holdem.abstraction.preflop_features import extract_preflop_features


def test_extract_preflop_features_dimensions():
    """Test that preflop features have correct dimensions."""
    hole = [Card('A', 'h'), Card('K', 'h')]
    
    features = extract_preflop_features(hole, equity_samples=50)
    
    # Should have 10 dimensions
    assert len(features) == 10
    assert features.dtype == np.float64


def test_extract_preflop_features_values():
    """Test that preflop features have valid values."""
    hole = [Card('A', 'h'), Card('K', 'h')]
    
    features = extract_preflop_features(hole, equity_samples=50)
    
    # All features should be in [0, 1]
    assert np.all(features >= 0.0)
    assert np.all(features <= 1.0)


def test_preflop_pocket_aces():
    """Test pocket aces features."""
    hole = [Card('A', 'h'), Card('A', 'd')]
    
    features = extract_preflop_features(hole, equity_samples=50)
    
    # High card = 1.0 (normalized 14/14)
    assert features[0] == pytest.approx(1.0)
    
    # Low card = 1.0 (normalized 14/14)
    assert features[1] == pytest.approx(1.0)
    
    # Is pair = 1.0
    assert features[2] == 1.0
    
    # Premium pair (AA) = 1.0
    assert features[7] == 1.0


def test_preflop_suited_connectors():
    """Test suited connectors features."""
    hole = [Card('T', 'h'), Card('9', 'h')]
    
    features = extract_preflop_features(hole, equity_samples=50)
    
    # Is suited = 1.0
    assert features[3] == 1.0
    
    # Gap should be small (normalized)
    assert features[4] <= 1.0 / 12.0  # Gap of 1
    
    # Is suited connectors = 1.0
    assert features[6] == 1.0


def test_preflop_offsuit_trash():
    """Test offsuit trash hand."""
    hole = [Card('7', 'h'), Card('2', 'd')]
    
    features = extract_preflop_features(hole, equity_samples=50)
    
    # Is pair = 0.0
    assert features[2] == 0.0
    
    # Is suited = 0.0
    assert features[3] == 0.0
    
    # Is broadway = 0.0
    assert features[5] == 0.0
    
    # Is suited connectors = 0.0
    assert features[6] == 0.0
    
    # Premium pair = 0.0
    assert features[7] == 0.0
    
    # Equity and strength should be relatively low (or default 0.5 if calc fails)
    assert features[8] <= 0.5  # Equity
    assert features[9] < 0.4  # Strength score


def test_preflop_broadway():
    """Test broadway cards."""
    hole = [Card('A', 'h'), Card('Q', 'd')]
    
    features = extract_preflop_features(hole, equity_samples=50)
    
    # Is broadway = 1.0
    assert features[5] == 1.0


def test_preflop_premium_pairs():
    """Test premium pairs (QQ, KK, AA)."""
    for rank in ['Q', 'K', 'A']:
        hole = [Card(rank, 'h'), Card(rank, 'd')]
        features = extract_preflop_features(hole, equity_samples=50)
        
        # Is pair = 1.0
        assert features[2] == 1.0
        
        # Premium pair = 1.0
        assert features[7] == 1.0


def test_preflop_non_premium_pairs():
    """Test non-premium pairs."""
    hole = [Card('J', 'h'), Card('J', 'd')]
    
    features = extract_preflop_features(hole, equity_samples=50)
    
    # Is pair = 1.0
    assert features[2] == 1.0
    
    # Premium pair = 0.0 (only QQ+ are premium)
    assert features[7] == 0.0


def test_preflop_gap_calculation():
    """Test gap calculation."""
    # Small gap
    hole1 = [Card('9', 'h'), Card('8', 'd')]
    features1 = extract_preflop_features(hole1, equity_samples=50)
    gap1 = features1[4]
    
    # Large gap
    hole2 = [Card('A', 'h'), Card('2', 'd')]
    features2 = extract_preflop_features(hole2, equity_samples=50)
    gap2 = features2[4]
    
    # Gap for connectors should be smaller
    assert gap1 < gap2


def test_preflop_empty_input():
    """Test empty input handling."""
    features = extract_preflop_features([], equity_samples=50)
    
    # Should return zeros
    assert len(features) == 10
    assert np.all(features == 0.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
