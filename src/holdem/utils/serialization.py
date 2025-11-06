"""Serialization utilities."""

import os
import json
import pickle
import gzip
from pathlib import Path
from typing import Any


def save_json(data: Any, path: Path, use_gzip: bool = False):
    """Save data as JSON.
    
    Args:
        data: Data to save
        path: Target file path
        use_gzip: If True, save as gzipped JSON (.json.gz)
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use temporary file for atomic write
    tmp_path = path.parent / f"{path.name}.tmp"
    
    try:
        if use_gzip or str(path).endswith('.gz'):
            with gzip.open(tmp_path, 'wt', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        else:
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2)
        
        # Atomic rename
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on error
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def load_json(path: Path) -> Any:
    """Load data from JSON.
    
    Args:
        path: Source file path
        
    Returns:
        Loaded data
    """
    if str(path).endswith('.gz'):
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            return json.load(f)
    else:
        with open(path, 'r') as f:
            return json.load(f)


def save_pickle(data: Any, path: Path):
    """Save data using pickle with atomic write.
    
    Args:
        data: Data to save
        path: Target file path
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use temporary file for atomic write
    tmp_path = path.parent / f"{path.name}.tmp"
    
    try:
        with open(tmp_path, 'wb') as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        # Atomic rename
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on error
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def load_pickle(path: Path) -> Any:
    """Load data from pickle."""
    with open(path, 'rb') as f:
        return pickle.load(f)


def save_text(text: str, path: Path):
    """Save text to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)


def load_text(path: Path) -> str:
    """Load text from file."""
    with open(path, 'r') as f:
        return f.read()
