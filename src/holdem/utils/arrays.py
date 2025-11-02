"""Array utilities for consistent dtype and memory layout."""

import numpy as np
from typing import Union, List


def ensure_float64(arr: Union[np.ndarray, List]) -> np.ndarray:
    """
    Ensure array is float64 dtype (what scikit-learn expects).
    
    Args:
        arr: Input array or list
        
    Returns:
        numpy array with dtype float64
    """
    if isinstance(arr, list):
        arr = np.array(arr)
    
    if arr.dtype != np.float64:
        arr = arr.astype(np.float64)
    
    return arr


def ensure_contiguous(arr: np.ndarray) -> np.ndarray:
    """
    Ensure array is C-contiguous in memory.
    
    Args:
        arr: Input array
        
    Returns:
        C-contiguous array
    """
    if not arr.flags['C_CONTIGUOUS']:
        arr = np.ascontiguousarray(arr)
    
    return arr


def prepare_for_sklearn(arr: Union[np.ndarray, List]) -> np.ndarray:
    """
    Prepare array for use with scikit-learn models.
    Ensures float64 dtype and C-contiguous memory layout.
    
    Args:
        arr: Input array or list
        
    Returns:
        Array ready for sklearn (float64, C-contiguous)
    """
    arr = ensure_float64(arr)
    arr = ensure_contiguous(arr)
    return arr


def safe_reshape(arr: np.ndarray, shape: tuple, order='C') -> np.ndarray:
    """
    Safely reshape array, ensuring proper memory layout.
    
    Args:
        arr: Input array
        shape: Target shape
        order: Memory order ('C' for row-major, 'F' for column-major)
        
    Returns:
        Reshaped array
    """
    reshaped = np.reshape(arr, shape, order=order)
    
    # Ensure contiguous after reshape
    if not reshaped.flags['C_CONTIGUOUS']:
        reshaped = np.ascontiguousarray(reshaped)
    
    return reshaped
