"""Test that features are returned in the correct dtype for scikit-learn."""

import numpy as np

try:
    from holdem.types import Card, Street
    from holdem.abstraction.features import extract_features, extract_simple_features
except ImportError:
    import sys
    import os
    # Add src to path if running from tests directory
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from holdem.types import Card, Street
    from holdem.abstraction.features import extract_features, extract_simple_features


def test_extract_features_returns_float64():
    """Test that extract_features returns float64 arrays."""
    # Create sample cards
    hole_cards = [Card('A', 'h'), Card('K', 's')]
    board = [Card('Q', 'd'), Card('J', 'c'), Card('T', 'h')]
    
    # Extract features
    features = extract_features(
        hole_cards=hole_cards,
        board=board,
        street=Street.FLOP,
        position=3,
        pot=100.0,
        stack=1000.0,
        num_opponents=1
    )
    
    # Verify dtype is float64 (what scikit-learn expects)
    assert features.dtype == np.float64, f"Expected float64 but got {features.dtype}"
    assert features.shape[0] > 0, "Features should not be empty"


def test_extract_simple_features_returns_float64():
    """Test that extract_simple_features returns float64 arrays."""
    # Create sample cards
    hole_cards = [Card('A', 'h'), Card('K', 's')]
    board = [Card('Q', 'd'), Card('J', 'c'), Card('T', 'h')]
    
    # Extract simple features
    features = extract_simple_features(hole_cards, board)
    
    # Verify dtype is float64 (what scikit-learn expects)
    assert features.dtype == np.float64, f"Expected float64 but got {features.dtype}"
    assert features.shape[0] == 5, "Simple features should have 5 elements"


def test_extract_simple_features_empty_cards_returns_float64():
    """Test that extract_simple_features with empty cards returns float64 zeros."""
    # Empty cards should return zeros with float64 dtype
    features = extract_simple_features([], [])
    
    assert features.dtype == np.float64, f"Expected float64 but got {features.dtype}"
    assert features.shape[0] == 5, "Should return 5 zeros"
    assert np.all(features == 0), "All values should be zero"


def test_sklearn_kmeans_compatibility():
    """Test that features work with sklearn KMeans without dtype warnings."""
    from sklearn.cluster import KMeans
    
    # Create multiple sample hands with features
    hole_cards_list = [
        [Card('A', 'h'), Card('K', 's')],
        [Card('Q', 'd'), Card('J', 'c')],
        [Card('9', 'h'), Card('8', 'd')],
        [Card('7', 's'), Card('6', 'c')],
        [Card('5', 'h'), Card('4', 'd')],
    ]
    
    board = []
    
    # Extract features for all hands
    features_list = [extract_simple_features(hc, board) for hc in hole_cards_list]
    X = np.array(features_list)
    
    # Verify the array is float64
    assert X.dtype == np.float64, f"Feature matrix should be float64 but got {X.dtype}"
    
    # This should work without warnings about dtype mismatch
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    kmeans.fit(X)
    
    # Verify predictions also work
    predictions = kmeans.predict(X)
    assert len(predictions) == len(hole_cards_list), "Should get one prediction per hand"
    assert all(0 <= p < 2 for p in predictions), "All predictions should be valid cluster IDs"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
