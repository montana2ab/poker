"""Serialization utilities."""

import json
import pickle
from pathlib import Path
from typing import Any


def save_json(data: Any, path: Path):
    """Save data as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def load_json(path: Path) -> Any:
    """Load data from JSON."""
    with open(path, 'r') as f:
        return json.load(f)


def save_pickle(data: Any, path: Path):
    """Save data using pickle."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)


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
