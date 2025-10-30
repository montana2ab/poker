"""Timing utilities."""

import time
from typing import Optional, Dict
from contextlib import contextmanager


class Timer:
    """Simple timer for measuring execution time."""
    
    def __init__(self, name: str = ""):
        self.name = name
        self.start_time: Optional[float] = None
        self.elapsed: float = 0.0
    
    def start(self):
        """Start the timer."""
        self.start_time = time.perf_counter()
    
    def stop(self) -> float:
        """Stop the timer and return elapsed time."""
        if self.start_time is None:
            return 0.0
        self.elapsed = time.perf_counter() - self.start_time
        self.start_time = None
        return self.elapsed
    
    def reset(self):
        """Reset the timer."""
        self.start_time = None
        self.elapsed = 0.0
    
    @contextmanager
    def measure(self):
        """Context manager for timing a block of code."""
        self.start()
        try:
            yield self
        finally:
            self.stop()


class TimerRegistry:
    """Registry for multiple named timers."""
    
    def __init__(self):
        self.timers: Dict[str, Timer] = {}
    
    def get_timer(self, name: str) -> Timer:
        """Get or create a timer by name."""
        if name not in self.timers:
            self.timers[name] = Timer(name)
        return self.timers[name]
    
    def start(self, name: str):
        """Start a timer."""
        self.get_timer(name).start()
    
    def stop(self, name: str) -> float:
        """Stop a timer and return elapsed time."""
        return self.get_timer(name).stop()
    
    @contextmanager
    def measure(self, name: str):
        """Context manager for timing with named timer."""
        timer = self.get_timer(name)
        timer.start()
        try:
            yield timer
        finally:
            timer.stop()
    
    def get_stats(self) -> Dict[str, float]:
        """Get elapsed time for all timers."""
        return {name: timer.elapsed for name, timer in self.timers.items()}
    
    def reset_all(self):
        """Reset all timers."""
        for timer in self.timers.values():
            timer.reset()


# Global timer registry
_timer_registry = TimerRegistry()


def get_timer_registry() -> TimerRegistry:
    """Get global timer registry."""
    return _timer_registry
