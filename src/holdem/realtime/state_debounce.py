"""State change detection and debouncing for vision→runtime integration (P1).

Prevents unnecessary re-solving by:
1. Detecting actual state changes (pot, to_call, street, SPR, action mask)
2. Applying sliding median filter to OCR amounts to reduce noise
3. Only triggering re-solve when meaningful changes occur
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from collections import deque
import numpy as np
from holdem.types import TableState, Street
from holdem.utils.logging import get_logger

logger = get_logger("realtime.state_debounce")


@dataclass
class StateSnapshot:
    """Snapshot of table state for change detection."""
    pot: float
    to_call: float
    street: Street
    spr: float  # Stack-to-pot ratio
    action_mask: Tuple[bool, ...]  # Available actions (fold, call, bet_sizes...)
    current_bet: float
    hero_stack: float
    
    def __eq__(self, other) -> bool:
        """Check if two states are meaningfully different."""
        if not isinstance(other, StateSnapshot):
            return False
        
        # Check exact matches for street and action mask
        if self.street != other.street:
            return False
        if self.action_mask != other.action_mask:
            return False
        
        # Check approximate matches for float values (within 1%)
        def approx_equal(a: float, b: float, threshold: float = 0.01) -> bool:
            if abs(a) < 0.01 and abs(b) < 0.01:
                return True  # Both near zero
            return abs(a - b) / max(abs(a), abs(b)) < threshold
        
        if not approx_equal(self.pot, other.pot):
            return False
        if not approx_equal(self.to_call, other.to_call):
            return False
        if not approx_equal(self.spr, other.spr, threshold=0.05):  # SPR can vary more
            return False
        if not approx_equal(self.current_bet, other.current_bet):
            return False
        if not approx_equal(self.hero_stack, other.hero_stack):
            return False
        
        return True


class StateDebouncer:
    """Debounces state changes to prevent unnecessary re-solving.
    
    Features:
    - Sliding median filter for OCR amounts (pot, to_call, stacks)
    - State change detection
    - Configurable filter window size
    """
    
    def __init__(
        self,
        median_window_size: int = 5,
        min_pot_change: float = 0.5,  # Minimum pot change to trigger (in BBs)
        min_stack_change: float = 1.0  # Minimum stack change to trigger
    ):
        """Initialize state debouncer.
        
        Args:
            median_window_size: Size of sliding median window (3-5 frames)
            min_pot_change: Minimum pot change to consider (in BBs)
            min_stack_change: Minimum stack change to consider
        """
        self.median_window_size = median_window_size
        self.min_pot_change = min_pot_change
        self.min_stack_change = min_stack_change
        
        # Sliding windows for raw OCR values
        self.pot_history: deque = deque(maxlen=median_window_size)
        self.to_call_history: deque = deque(maxlen=median_window_size)
        self.stack_history: deque = deque(maxlen=median_window_size)
        self.current_bet_history: deque = deque(maxlen=median_window_size)
        
        # Last committed state
        self.last_state: Optional[StateSnapshot] = None
        
        # Statistics
        self.total_frames = 0
        self.state_changes_detected = 0
        self.frames_filtered = 0
        
        logger.info(
            f"StateDebouncer initialized: window={median_window_size}, "
            f"min_pot_change={min_pot_change}, min_stack_change={min_stack_change}"
        )
    
    def process_frame(
        self,
        state: TableState,
        force_update: bool = False
    ) -> Tuple[bool, StateSnapshot]:
        """Process a new frame and determine if state has changed.
        
        Args:
            state: Current table state from vision
            force_update: Force state update regardless of changes
            
        Returns:
            (state_changed, smoothed_state)
        """
        self.total_frames += 1
        
        # Add raw OCR values to history
        self.pot_history.append(state.pot)
        self.to_call_history.append(state.to_call)
        self.stack_history.append(state.effective_stack)
        self.current_bet_history.append(state.current_bet)
        
        # Apply sliding median filter
        smoothed_pot = self._median_filter(self.pot_history)
        smoothed_to_call = self._median_filter(self.to_call_history)
        smoothed_stack = self._median_filter(self.stack_history)
        smoothed_current_bet = self._median_filter(self.current_bet_history)
        
        # Compute SPR with smoothed values
        smoothed_spr = smoothed_stack / max(smoothed_pot, 1.0)
        
        # Create action mask (simplified - based on available actions)
        action_mask = self._compute_action_mask(state)
        
        # Create smoothed state snapshot
        smoothed_state = StateSnapshot(
            pot=smoothed_pot,
            to_call=smoothed_to_call,
            street=state.street,
            spr=smoothed_spr,
            action_mask=action_mask,
            current_bet=smoothed_current_bet,
            hero_stack=smoothed_stack
        )
        
        # Check if state has changed
        if force_update or self.last_state is None:
            state_changed = True
        else:
            state_changed = not (smoothed_state == self.last_state)
        
        if state_changed:
            self.state_changes_detected += 1
            self.last_state = smoothed_state
            logger.debug(
                f"State change detected: pot={smoothed_pot:.1f}, "
                f"to_call={smoothed_to_call:.1f}, street={state.street.name}, "
                f"spr={smoothed_spr:.1f}"
            )
        else:
            self.frames_filtered += 1
        
        return state_changed, smoothed_state
    
    def _median_filter(self, values: deque) -> float:
        """Apply median filter to a sequence of values.
        
        Args:
            values: Deque of values
            
        Returns:
            Median value
        """
        if not values:
            return 0.0
        return float(np.median(list(values)))
    
    def _compute_action_mask(self, state: TableState) -> Tuple[bool, ...]:
        """Compute action mask for state comparison.
        
        Args:
            state: Table state
            
        Returns:
            Tuple of booleans indicating available actions
        """
        # Simplified action mask:
        # (can_fold, can_call, can_bet_small, can_bet_medium, can_bet_large, can_all_in)
        
        can_fold = state.to_call > 0
        can_call = True
        can_bet_small = state.effective_stack > 0.3 * state.pot
        can_bet_medium = state.effective_stack > state.pot
        can_bet_large = state.effective_stack > 1.5 * state.pot
        can_all_in = state.effective_stack > 0
        
        return (can_fold, can_call, can_bet_small, can_bet_medium, can_bet_large, can_all_in)
    
    def should_resolve(
        self,
        state: TableState,
        force: bool = False
    ) -> bool:
        """Determine if we should trigger a re-solve.
        
        Args:
            state: Current table state
            force: Force re-solve regardless of changes
            
        Returns:
            True if should re-solve, False otherwise
        """
        state_changed, smoothed_state = self.process_frame(state, force_update=force)
        return state_changed
    
    def get_smoothed_state(self, state: TableState) -> StateSnapshot:
        """Get smoothed state without checking for changes.
        
        Args:
            state: Current table state
            
        Returns:
            Smoothed state snapshot
        """
        _, smoothed_state = self.process_frame(state, force_update=False)
        return smoothed_state
    
    def reset(self):
        """Reset debouncer state."""
        self.pot_history.clear()
        self.to_call_history.clear()
        self.stack_history.clear()
        self.current_bet_history.clear()
        self.last_state = None
        self.total_frames = 0
        self.state_changes_detected = 0
        self.frames_filtered = 0
        logger.info("StateDebouncer reset")
    
    def get_statistics(self) -> dict:
        """Get debouncer statistics.
        
        Returns:
            Dictionary with statistics
        """
        filter_rate = self.frames_filtered / max(self.total_frames, 1)
        
        return {
            'total_frames': self.total_frames,
            'state_changes_detected': self.state_changes_detected,
            'frames_filtered': self.frames_filtered,
            'filter_rate': filter_rate,
            'avg_frames_per_change': self.total_frames / max(self.state_changes_detected, 1)
        }
