"""Test array utility functions for dtype and memory layout handling."""

import numpy as np
import pytest
from holdem.utils.arrays import (
    ensure_float64,
    ensure_contiguous,
    prepare_for_sklearn,
    safe_reshape
)


def test_ensure_float64_from_list():
    """Test converting list to float64 array."""
    data = [1.0, 2.0, 3.0]
    result = ensure_float64(data)
    
    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float64
    assert np.array_equal(result, np.array([1.0, 2.0, 3.0], dtype=np.float64))


def test_ensure_float64_from_float32():
    """Test converting float32 array to float64."""
    data = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    result = ensure_float64(data)
    
    assert result.dtype == np.float64
    assert np.array_equal(result, np.array([1.0, 2.0, 3.0], dtype=np.float64))


def test_ensure_float64_already_float64():
    """Test that float64 arrays pass through unchanged."""
    data = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    result = ensure_float64(data)
    
    assert result.dtype == np.float64
    assert np.array_equal(result, data)


def test_ensure_contiguous_non_contiguous():
    """Test making non-contiguous array contiguous."""
    # Create non-contiguous array by slicing
    data = np.array([[1, 2, 3, 4], [5, 6, 7, 8]], dtype=np.float64)
    non_contiguous = data[:, ::2]  # Every other column
    
    assert not non_contiguous.flags['C_CONTIGUOUS']
    
    result = ensure_contiguous(non_contiguous)
    
    assert result.flags['C_CONTIGUOUS']
    assert np.array_equal(result, non_contiguous)


def test_ensure_contiguous_already_contiguous():
    """Test that contiguous arrays pass through unchanged."""
    data = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    
    assert data.flags['C_CONTIGUOUS']
    
    result = ensure_contiguous(data)
    
    assert result.flags['C_CONTIGUOUS']
    assert np.array_equal(result, data)


def test_prepare_for_sklearn_list():
    """Test preparing list for sklearn."""
    data = [[1.0, 2.0], [3.0, 4.0]]
    result = prepare_for_sklearn(data)
    
    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float64
    assert result.flags['C_CONTIGUOUS']
    assert result.shape == (2, 2)


def test_prepare_for_sklearn_float32():
    """Test preparing float32 array for sklearn."""
    data = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    result = prepare_for_sklearn(data)
    
    assert result.dtype == np.float64
    assert result.flags['C_CONTIGUOUS']


def test_prepare_for_sklearn_non_contiguous():
    """Test preparing non-contiguous array for sklearn."""
    data = np.array([[1, 2, 3, 4], [5, 6, 7, 8]], dtype=np.float64)
    non_contiguous = data[:, ::2]  # Every other column
    
    result = prepare_for_sklearn(non_contiguous)
    
    assert result.dtype == np.float64
    assert result.flags['C_CONTIGUOUS']
    assert np.array_equal(result, non_contiguous)


def test_safe_reshape():
    """Test safe reshaping."""
    data = np.array([1, 2, 3, 4, 5, 6], dtype=np.float64)
    result = safe_reshape(data, (2, 3))
    
    assert result.shape == (2, 3)
    assert result.flags['C_CONTIGUOUS']
    assert np.array_equal(result, [[1, 2, 3], [4, 5, 6]])


def test_safe_reshape_maintains_contiguity():
    """Test that reshape maintains contiguity."""
    data = np.array([1, 2, 3, 4], dtype=np.float64)
    result = safe_reshape(data, (2, 2))
    
    assert result.flags['C_CONTIGUOUS']


def test_sklearn_compatibility():
    """Test that prepared arrays work with sklearn."""
    from sklearn.cluster import KMeans
    
    # Create test data with potential issues
    data_list = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]]
    
    # Prepare for sklearn
    X = prepare_for_sklearn(data_list)
    
    # This should work without warnings
    kmeans = KMeans(n_clusters=2, random_state=42)
    kmeans.fit(X)
    
    # Test prediction
    predictions = kmeans.predict(X)
    assert len(predictions) == 4
    assert all(0 <= p < 2 for p in predictions)


def test_prepare_for_sklearn_1d():
    """Test preparing 1D array for sklearn."""
    data = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    result = prepare_for_sklearn(data)
    
    assert result.dtype == np.float64
    assert result.flags['C_CONTIGUOUS']
    assert result.shape == (3,)


def test_prepare_for_sklearn_3d():
    """Test preparing 3D array for sklearn."""
    data = np.array([[[1, 2], [3, 4]], [[5, 6], [7, 8]]], dtype=np.float32)
    result = prepare_for_sklearn(data)
    
    assert result.dtype == np.float64
    assert result.flags['C_CONTIGUOUS']
    assert result.shape == (2, 2, 2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
