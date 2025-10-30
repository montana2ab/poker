"""Action definitions and mapping."""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class ClickAction:
    """Physical click action."""
    x: int
    y: int
    button: str = "left"
    
    def __str__(self) -> str:
        return f"Click({self.x}, {self.y})"


@dataclass
class KeyAction:
    """Keyboard action."""
    key: str
    
    def __str__(self) -> str:
        return f"Key({self.key})"


@dataclass
class WaitAction:
    """Wait/delay action."""
    duration_ms: int
    
    def __str__(self) -> str:
        return f"Wait({self.duration_ms}ms)"
