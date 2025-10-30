"""Safety checks and guardrails."""

import time
from typing import Optional
from holdem.types import TableState
from holdem.utils.logging import get_logger

logger = get_logger("control.safety")


class SafetyChecker:
    """Validates actions before execution."""
    
    def __init__(self):
        self.last_action_time: Optional[float] = None
        self.action_count = 0
        self.session_start = time.time()
    
    def check_action(
        self,
        action: str,
        state: TableState,
        min_delay_ms: int = 500
    ) -> tuple[bool, str]:
        """Check if action is safe to execute."""
        # Rate limiting
        if self.last_action_time:
            elapsed = (time.time() - self.last_action_time) * 1000
            if elapsed < min_delay_ms:
                return False, f"Action too fast (need {min_delay_ms}ms delay)"
        
        # Sanity checks
        if not state:
            return False, "Invalid state"
        
        # Stack check
        if state.players:
            our_player = state.players[0]  # Assume first player is us
            if our_player.stack <= 0:
                return False, "No chips remaining"
        
        # Session limits
        session_duration = time.time() - self.session_start
        if session_duration > 14400:  # 4 hours
            return False, "Session limit reached (4 hours)"
        
        if self.action_count > 5000:
            return False, "Action limit reached (5000 actions)"
        
        self.last_action_time = time.time()
        self.action_count += 1
        
        return True, "OK"
    
    def reset(self):
        """Reset safety checker."""
        self.last_action_time = None
        self.action_count = 0
        self.session_start = time.time()
