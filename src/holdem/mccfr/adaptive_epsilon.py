"""Adaptive epsilon scheduler based on performance and coverage metrics."""

import time
from collections import deque
from typing import List, Tuple, Optional, Dict
from holdem.types import MCCFRConfig
from holdem.utils.logging import get_logger

logger = get_logger("mccfr.adaptive_epsilon")


class AdaptiveEpsilonScheduler:
    """Adaptive epsilon scheduler that adjusts exploration based on performance metrics.
    
    The scheduler monitors:
    - Iterations per second (IPS) - training speed
    - Infoset growth rate - coverage of game tree
    
    It adapts epsilon transitions based on whether the machine is keeping up with
    target performance and discovering new infosets at expected rates.
    """
    
    def __init__(self, config: MCCFRConfig, base_schedule: Optional[List[Tuple[int, float]]] = None):
        """Initialize adaptive epsilon scheduler.
        
        Args:
            config: MCCFR configuration with adaptive parameters
            base_schedule: Base epsilon schedule [(iteration, epsilon), ...]
                          If None, uses config.epsilon_schedule
        """
        self.config = config
        
        # Use provided schedule or fall back to config
        if base_schedule is not None:
            self.base_schedule = sorted(base_schedule, key=lambda x: x[0])
        elif config.epsilon_schedule is not None:
            self.base_schedule = sorted(config.epsilon_schedule, key=lambda x: x[0])
        else:
            # No schedule provided - adaptive scheduling won't be used
            self.base_schedule = []
        
        # Adaptive parameters
        self.target_ips = config.adaptive_target_ips
        self.window_size = config.adaptive_window_merges
        self.min_infoset_growth = config.adaptive_min_infoset_growth
        self.early_shift_ratio = config.adaptive_early_shift_ratio
        self.extension_ratio = config.adaptive_extension_ratio
        self.force_after_ratio = config.adaptive_force_after_ratio
        
        # Performance tracking
        self._ips_window = deque(maxlen=self.window_size)  # Recent IPS measurements
        self._merge_times = deque(maxlen=self.window_size)  # (iteration, timestamp, num_infosets)
        
        # Schedule state tracking
        self._current_schedule_index = 0  # Index in base_schedule we're transitioning to
        self._current_epsilon = None  # Current epsilon value
        self._transition_state = "none"  # none, waiting, early, delayed, forced
        self._waiting_since_iteration = None  # When we started waiting for criteria
        
        # Initialize current epsilon from base schedule
        if self.base_schedule:
            self._current_epsilon = self.base_schedule[0][1]
        
        logger.info(f"Adaptive epsilon scheduler initialized")
        logger.info(f"  Target IPS: {self.target_ips:.1f}")
        logger.info(f"  Min infoset growth: {self.min_infoset_growth:.1f} per 1000 iterations")
        logger.info(f"  Early shift ratio: {self.early_shift_ratio:.1%}")
        logger.info(f"  Extension ratio: {self.extension_ratio:.1%}")
        logger.info(f"  Force after ratio: {self.force_after_ratio:.1%}")
    
    def record_merge(self, iteration: int, num_infosets: int, elapsed_seconds: float, 
                     iterations_in_batch: int):
        """Record a merge event for performance tracking.
        
        Args:
            iteration: Current iteration number
            num_infosets: Total number of infosets discovered
            elapsed_seconds: Time elapsed for this batch/merge
            iterations_in_batch: Number of iterations in this batch
        """
        current_time = time.time()
        
        # Calculate IPS for this batch
        if elapsed_seconds > 0:
            ips = iterations_in_batch / elapsed_seconds
            self._ips_window.append(ips)
        
        # Record merge data for infoset growth calculation
        self._merge_times.append((iteration, current_time, num_infosets))
    
    def get_average_ips(self) -> Optional[float]:
        """Get average IPS over the recent window.
        
        Returns:
            Average IPS, or None if not enough data
        """
        if not self._ips_window:
            return None
        return sum(self._ips_window) / len(self._ips_window)
    
    def get_infoset_growth_rate(self) -> Optional[float]:
        """Get infoset growth rate (new infosets per 1000 iterations).
        
        Returns:
            Growth rate, or None if not enough data
        """
        if len(self._merge_times) < 2:
            return None
        
        # Calculate growth over the entire window
        oldest = self._merge_times[0]
        newest = self._merge_times[-1]
        
        iteration_delta = newest[0] - oldest[0]
        infoset_delta = newest[2] - oldest[2]
        
        if iteration_delta <= 0:
            return None
        
        # Return as "per 1000 iterations"
        return (infoset_delta / iteration_delta) * 1000.0
    
    def should_transition(self, iteration: int) -> bool:
        """Check if we should transition to the next epsilon level.
        
        Args:
            iteration: Current iteration number
            
        Returns:
            True if epsilon should be updated
        """
        if not self.base_schedule:
            return False
        
        # Check if we've exhausted the schedule
        if self._current_schedule_index >= len(self.base_schedule):
            return False
        
        target_iteration, target_epsilon = self.base_schedule[self._current_schedule_index]
        
        # If we haven't reached the earliest possible transition, wait
        earliest_iteration = int(target_iteration * (1.0 - self.early_shift_ratio))
        if iteration < earliest_iteration:
            return False
        
        # Calculate threshold iterations
        latest_iteration = int(target_iteration * (1.0 + self.extension_ratio))
        force_iteration = int(target_iteration * (1.0 + self.force_after_ratio))
        
        # Force transition if we've exceeded the force threshold
        if iteration >= force_iteration:
            logger.info(f"Forcing epsilon transition to {target_epsilon:.3f} at iteration {iteration} "
                       f"(force threshold: {force_iteration})")
            self._transition_state = "forced"
            return True
        
        # Check if criteria are met for transition
        avg_ips = self.get_average_ips()
        growth_rate = self.get_infoset_growth_rate()
        
        # Need sufficient data to make adaptive decision
        if avg_ips is None or growth_rate is None:
            # Not enough data yet, but allow transition if we're past target iteration
            if iteration >= target_iteration:
                logger.info(f"Transitioning epsilon to {target_epsilon:.3f} at iteration {iteration} "
                           f"(insufficient data for adaptive decision)")
                self._transition_state = "none"
                return True
            return False
        
        # Check criteria
        ips_threshold = 0.9 * self.target_ips
        ips_criteria_met = avg_ips >= ips_threshold
        growth_criteria_met = growth_rate >= self.min_infoset_growth
        criteria_met = ips_criteria_met and growth_criteria_met
        
        # Early transition if criteria exceeded before target iteration
        if iteration < target_iteration and criteria_met:
            # Allow early transition with strong performance
            if avg_ips >= self.target_ips and growth_rate >= self.min_infoset_growth * 1.2:
                logger.info(f"Early epsilon transition to {target_epsilon:.3f} at iteration {iteration} "
                           f"(IPS: {avg_ips:.1f}/{self.target_ips:.1f}, "
                           f"growth: {growth_rate:.1f}/{self.min_infoset_growth:.1f})")
                self._transition_state = "early"
                return True
            return False
        
        # At or past target iteration
        if iteration >= target_iteration:
            if criteria_met:
                logger.info(f"Epsilon transition to {target_epsilon:.3f} at iteration {iteration} "
                           f"(IPS: {avg_ips:.1f}/{self.target_ips:.1f}, "
                           f"growth: {growth_rate:.1f}/{self.min_infoset_growth:.1f})")
                self._transition_state = "none"
                return True
            elif iteration >= latest_iteration:
                # Extension period expired, transition anyway
                logger.info(f"Delayed epsilon transition to {target_epsilon:.3f} at iteration {iteration} "
                           f"(extension period expired, IPS: {avg_ips:.1f}/{self.target_ips:.1f}, "
                           f"growth: {growth_rate:.1f}/{self.min_infoset_growth:.1f})")
                self._transition_state = "delayed"
                return True
            else:
                # Within extension period, keep waiting
                if self._waiting_since_iteration is None:
                    self._waiting_since_iteration = iteration
                    logger.info(f"Delaying epsilon transition (waiting for criteria, "
                               f"IPS: {avg_ips:.1f}/{self.target_ips:.1f}, "
                               f"growth: {growth_rate:.1f}/{self.min_infoset_growth:.1f})")
                self._transition_state = "waiting"
                return False
        
        return False
    
    def get_epsilon(self, iteration: int) -> float:
        """Get the current epsilon value for the given iteration.
        
        Args:
            iteration: Current iteration number
            
        Returns:
            Current epsilon value
        """
        if not self.base_schedule:
            return self.config.exploration_epsilon
        
        # Check if we should transition
        if self.should_transition(iteration):
            self._current_epsilon = self.base_schedule[self._current_schedule_index][1]
            self._current_schedule_index += 1
            self._waiting_since_iteration = None
        
        return self._current_epsilon if self._current_epsilon is not None else self.config.exploration_epsilon
    
    def get_metrics(self) -> Dict[str, float]:
        """Get current adaptive metrics for logging.
        
        Returns:
            Dictionary of metric names to values
        """
        avg_ips = self.get_average_ips()
        growth_rate = self.get_infoset_growth_rate()
        
        metrics = {}
        if avg_ips is not None:
            metrics['adaptive/ips'] = avg_ips
            metrics['adaptive/ips_ratio'] = avg_ips / self.target_ips if self.target_ips > 0 else 0.0
        if growth_rate is not None:
            metrics['adaptive/infoset_growth'] = growth_rate
            metrics['adaptive/growth_ratio'] = growth_rate / self.min_infoset_growth if self.min_infoset_growth > 0 else 0.0
        
        return metrics
