"""Metrics tracking for poker AI system.

Tracks metrics required by P0 requirements:
- rt/decision_time_ms, rt/iterations, rt/failsafe_fallback_rate, rt/ev_delta_bbs
- translator/illegal_after_roundtrip (must stay 0)
- abstraction/bucket_pop_std, abstraction/collision_rate
- eval/mbb100_mean, eval/mbb100_CI95
- policy/kl_to_blueprint_root, policy/entropy_by_street
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np
from collections import defaultdict
from holdem.utils.logging import get_logger

logger = get_logger("metrics")


@dataclass
class MetricsTracker:
    """Central metrics tracking for poker AI system.
    
    Collects and aggregates metrics from different components:
    - Runtime resolver (rt/*)
    - Action translator (translator/*)
    - Abstraction/bucketing (abstraction/*)
    - Evaluation (eval/*)
    - Policy (policy/*)
    """
    
    # Runtime metrics
    rt_decision_times: List[float] = field(default_factory=list)
    rt_iterations_list: List[int] = field(default_factory=list)
    rt_fallback_count: int = 0
    rt_total_solves: int = 0
    rt_ev_deltas: List[float] = field(default_factory=list)
    
    # Translator metrics
    translator_illegal_count: int = 0
    translator_total_translations: int = 0
    
    # Abstraction metrics
    abstraction_bucket_populations: Dict[str, List[int]] = field(default_factory=lambda: defaultdict(list))
    abstraction_collision_count: int = 0
    abstraction_total_buckets: int = 0
    
    # Evaluation metrics
    eval_bb_per_100: List[float] = field(default_factory=list)
    
    # Policy metrics
    policy_kl_values: List[float] = field(default_factory=list)
    policy_entropy_by_street: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    def record_rt_solve(
        self,
        decision_time_ms: float,
        iterations: int,
        used_fallback: bool,
        ev_delta_bbs: float = 0.0
    ):
        """Record a runtime solve.
        
        Args:
            decision_time_ms: Time taken for decision (milliseconds)
            iterations: Number of CFR iterations completed
            used_fallback: Whether fallback to blueprint was used
            ev_delta_bbs: EV difference from blueprint (in big blinds)
        """
        self.rt_decision_times.append(decision_time_ms)
        self.rt_iterations_list.append(iterations)
        self.rt_total_solves += 1
        self.rt_ev_deltas.append(ev_delta_bbs)
        
        if used_fallback:
            self.rt_fallback_count += 1
    
    def record_translation(self, is_legal: bool):
        """Record an action translation.
        
        Args:
            is_legal: Whether the translated action is legal after round-trip
        """
        self.translator_total_translations += 1
        if not is_legal:
            self.translator_illegal_count += 1
    
    def record_bucket_assignment(self, street: str, bucket_populations: List[int]):
        """Record bucket population distribution for a street.
        
        Args:
            street: Street name (preflop/flop/turn/river)
            bucket_populations: List of number of hands per bucket
        """
        self.abstraction_bucket_populations[street] = bucket_populations
    
    def record_bucket_collision(self, collided: bool):
        """Record a bucket collision (same bucket for different hand strengths).
        
        Args:
            collided: Whether a collision occurred
        """
        self.abstraction_total_buckets += 1
        if collided:
            self.abstraction_collision_count += 1
    
    def record_eval_result(self, bb_per_100: float):
        """Record an evaluation result.
        
        Args:
            bb_per_100: Big blinds won per 100 hands
        """
        self.eval_bb_per_100.append(bb_per_100)
    
    def record_policy_kl(self, kl_divergence: float):
        """Record KL divergence to blueprint.
        
        Args:
            kl_divergence: KL(policy || blueprint)
        """
        self.policy_kl_values.append(kl_divergence)
    
    def record_policy_entropy(self, street: str, entropy: float):
        """Record policy entropy for a street.
        
        Args:
            street: Street name
            entropy: Shannon entropy of policy
        """
        self.policy_entropy_by_street[street].append(entropy)
    
    def get_metrics(self) -> Dict[str, float]:
        """Get all metrics as a dictionary.
        
        Returns:
            Dictionary of metric_name -> value
        """
        metrics = {}
        
        # Runtime metrics
        if self.rt_decision_times:
            metrics['rt/decision_time_ms'] = float(np.mean(self.rt_decision_times))
            metrics['rt/decision_time_p50'] = float(np.percentile(self.rt_decision_times, 50))
            metrics['rt/decision_time_p90'] = float(np.percentile(self.rt_decision_times, 90))
            metrics['rt/decision_time_p99'] = float(np.percentile(self.rt_decision_times, 99))
        
        if self.rt_iterations_list:
            metrics['rt/iterations'] = float(np.mean(self.rt_iterations_list))
        
        if self.rt_total_solves > 0:
            metrics['rt/failsafe_fallback_rate'] = self.rt_fallback_count / self.rt_total_solves
        
        if self.rt_ev_deltas:
            metrics['rt/ev_delta_bbs'] = float(np.mean(self.rt_ev_deltas))
            metrics['rt/ev_delta_std'] = float(np.std(self.rt_ev_deltas))
        
        # Translator metrics (MUST be 0)
        if self.translator_total_translations > 0:
            metrics['translator/illegal_after_roundtrip'] = \
                self.translator_illegal_count / self.translator_total_translations
        else:
            metrics['translator/illegal_after_roundtrip'] = 0.0
        
        # Abstraction metrics
        for street, populations in self.abstraction_bucket_populations.items():
            if populations:
                std = float(np.std(populations))
                metrics[f'abstraction/bucket_pop_std_{street}'] = std
        
        if self.abstraction_total_buckets > 0:
            metrics['abstraction/collision_rate'] = \
                self.abstraction_collision_count / self.abstraction_total_buckets
        
        # Evaluation metrics
        if self.eval_bb_per_100:
            metrics['eval/mbb100_mean'] = float(np.mean(self.eval_bb_per_100)) * 1000  # Convert to milli-bb
            
            # Compute 95% confidence interval
            if len(self.eval_bb_per_100) > 1:
                std_err = np.std(self.eval_bb_per_100) / np.sqrt(len(self.eval_bb_per_100))
                ci95 = 1.96 * std_err
                metrics['eval/mbb100_CI95'] = float(ci95) * 1000
        
        # Policy metrics
        if self.policy_kl_values:
            metrics['policy/kl_to_blueprint_root'] = float(np.mean(self.policy_kl_values))
            metrics['policy/kl_p90'] = float(np.percentile(self.policy_kl_values, 90))
        
        for street, entropies in self.policy_entropy_by_street.items():
            if entropies:
                metrics[f'policy/entropy_{street}'] = float(np.mean(entropies))
        
        return metrics
    
    def log_summary(self):
        """Log a summary of all metrics."""
        metrics = self.get_metrics()
        
        logger.info("=" * 60)
        logger.info("METRICS SUMMARY")
        logger.info("=" * 60)
        
        # Group by category
        categories = {
            'rt/': 'Runtime Resolver',
            'translator/': 'Action Translator',
            'abstraction/': 'Bucketing/Abstraction',
            'eval/': 'Evaluation',
            'policy/': 'Policy'
        }
        
        for prefix, name in categories.items():
            category_metrics = {k: v for k, v in metrics.items() if k.startswith(prefix)}
            if category_metrics:
                logger.info(f"\n{name}:")
                for key, value in sorted(category_metrics.items()):
                    if isinstance(value, float):
                        logger.info(f"  {key}: {value:.4f}")
                    else:
                        logger.info(f"  {key}: {value}")
        
        logger.info("=" * 60)
        
        # Check critical constraints
        illegal_rate = metrics.get('translator/illegal_after_roundtrip', 0.0)
        if illegal_rate > 0:
            logger.error(f"CONSTRAINT VIOLATION: translator/illegal_after_roundtrip = {illegal_rate} (MUST be 0)")
    
    def reset(self):
        """Reset all metrics."""
        self.rt_decision_times.clear()
        self.rt_iterations_list.clear()
        self.rt_fallback_count = 0
        self.rt_total_solves = 0
        self.rt_ev_deltas.clear()
        
        self.translator_illegal_count = 0
        self.translator_total_translations = 0
        
        self.abstraction_bucket_populations.clear()
        self.abstraction_collision_count = 0
        self.abstraction_total_buckets = 0
        
        self.eval_bb_per_100.clear()
        
        self.policy_kl_values.clear()
        self.policy_entropy_by_street.clear()


# Global metrics tracker instance
_global_tracker: Optional[MetricsTracker] = None


def get_metrics_tracker() -> MetricsTracker:
    """Get the global metrics tracker instance.
    
    Returns:
        Global MetricsTracker instance
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = MetricsTracker()
    return _global_tracker


def reset_metrics():
    """Reset the global metrics tracker."""
    global _global_tracker
    if _global_tracker is not None:
        _global_tracker.reset()
