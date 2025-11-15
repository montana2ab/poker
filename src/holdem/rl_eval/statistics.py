"""Statistical functions for confidence intervals and sample size calculation.

This module provides tools for computing confidence intervals and determining
required sample sizes for statistically valid poker AI evaluation.

Key Features:
- Bootstrap confidence intervals (non-parametric)
- Analytical confidence intervals (parametric, assuming normality)
- Sample size calculation for target margin of error
- Variance estimation and reporting

Reference:
    Efron & Tibshirani (1994). "An Introduction to the Bootstrap"
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import json
import hashlib
from datetime import datetime
from pathlib import Path
from holdem.utils.logging import get_logger

logger = get_logger("rl_eval.statistics")


def compute_confidence_interval(
    results: List[float],
    confidence: float = 0.95,
    method: str = "bootstrap",
    n_bootstrap: int = 10000
) -> Dict[str, Any]:
    """Compute confidence interval for evaluation results.
    
    Args:
        results: List of evaluation results (e.g., payoffs, winrates)
        confidence: Confidence level (default: 0.95 for 95% CI)
        method: Method for CI calculation - "bootstrap" or "analytical"
        n_bootstrap: Number of bootstrap samples (for bootstrap method)
        
    Returns:
        Dictionary containing:
            - mean: Sample mean
            - ci_lower: Lower bound of confidence interval
            - ci_upper: Upper bound of confidence interval
            - margin: Margin of error (half-width of CI)
            - confidence: Confidence level used
            - std: Standard deviation
            - stderr: Standard error
            - method: Method used for computation
            
    Example:
        >>> results = [1.5, 2.3, -0.5, 1.8, 0.2]
        >>> ci = compute_confidence_interval(results, confidence=0.95)
        >>> print(f"Mean: {ci['mean']:.2f} ± {ci['margin']:.2f}")
    """
    if len(results) == 0:
        raise ValueError("Cannot compute confidence interval for empty results")
    
    results_array = np.array(results)
    mean = np.mean(results_array)
    std = np.std(results_array, ddof=1)  # Sample std with Bessel's correction
    n = len(results_array)
    stderr = std / np.sqrt(n)
    
    if method == "bootstrap":
        ci_lower, ci_upper = _compute_ci_bootstrap(
            results_array, confidence, n_bootstrap
        )
    elif method == "analytical":
        ci_lower, ci_upper = _compute_ci_analytical(
            results_array, confidence
        )
    else:
        raise ValueError(f"Unknown method: {method}. Use 'bootstrap' or 'analytical'")
    
    margin = (ci_upper - ci_lower) / 2.0
    
    logger.debug(
        f"CI computed: mean={mean:.4f}, "
        f"CI=[{ci_lower:.4f}, {ci_upper:.4f}], "
        f"margin={margin:.4f} ({method})"
    )
    
    return {
        'mean': float(mean),
        'ci_lower': float(ci_lower),
        'ci_upper': float(ci_upper),
        'margin': float(margin),
        'confidence': confidence,
        'std': float(std),
        'stderr': float(stderr),
        'method': method,
        'n': n
    }


def _compute_ci_bootstrap(
    results: np.ndarray,
    confidence: float,
    n_bootstrap: int
) -> Tuple[float, float]:
    """Compute bootstrap confidence interval (non-parametric).
    
    Uses percentile bootstrap method which doesn't assume any particular
    distribution for the data.
    
    Args:
        results: Array of results
        confidence: Confidence level
        n_bootstrap: Number of bootstrap samples
        
    Returns:
        Tuple of (ci_lower, ci_upper)
    """
    n = len(results)
    bootstrap_means = np.zeros(n_bootstrap)
    
    # Generate bootstrap samples
    for i in range(n_bootstrap):
        # Resample with replacement
        sample = np.random.choice(results, size=n, replace=True)
        bootstrap_means[i] = np.mean(sample)
    
    # Calculate percentiles for CI
    alpha = 1 - confidence
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100
    
    ci_lower = np.percentile(bootstrap_means, lower_percentile)
    ci_upper = np.percentile(bootstrap_means, upper_percentile)
    
    return ci_lower, ci_upper


def _compute_ci_analytical(
    results: np.ndarray,
    confidence: float
) -> Tuple[float, float]:
    """Compute analytical confidence interval assuming normality.
    
    Uses t-distribution for small samples and normal approximation for large.
    
    Args:
        results: Array of results
        confidence: Confidence level
        
    Returns:
        Tuple of (ci_lower, ci_upper)
    """
    try:
        from scipy import stats
    except ImportError:
        logger.warning("scipy not available, using approximate normal CI")
        return _compute_ci_normal_approx(results, confidence)
    
    n = len(results)
    mean = np.mean(results)
    stderr = stats.sem(results)
    
    # Use t-distribution for more accurate small-sample inference
    alpha = 1 - confidence
    t_critical = stats.t.ppf(1 - alpha/2, n - 1)
    
    margin = t_critical * stderr
    ci_lower = mean - margin
    ci_upper = mean + margin
    
    return ci_lower, ci_upper


def _compute_ci_normal_approx(
    results: np.ndarray,
    confidence: float
) -> Tuple[float, float]:
    """Compute CI using normal approximation (fallback when scipy unavailable).
    
    Args:
        results: Array of results
        confidence: Confidence level
        
    Returns:
        Tuple of (ci_lower, ci_upper)
    """
    n = len(results)
    mean = np.mean(results)
    std = np.std(results, ddof=1)
    stderr = std / np.sqrt(n)
    
    # Z-score for confidence level (normal approximation)
    # 0.95 -> 1.96, 0.99 -> 2.576
    z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576, 0.999: 3.291}
    z_critical = z_scores.get(confidence, 1.96)  # Default to 95%
    
    margin = z_critical * stderr
    ci_lower = mean - margin
    ci_upper = mean + margin
    
    return ci_lower, ci_upper


def required_sample_size(
    target_margin: float,
    estimated_variance: float,
    confidence: float = 0.95
) -> int:
    """Calculate required sample size for target margin of error.
    
    Uses the formula: n = (Z * σ / E)²
    where:
        - Z is the critical value for the confidence level
        - σ is the estimated standard deviation
        - E is the desired margin of error
    
    Args:
        target_margin: Desired margin of error (e.g., ±1 bb/100)
        estimated_variance: Estimated variance from pilot study or previous data
        confidence: Confidence level (default: 0.95)
        
    Returns:
        Required sample size (rounded up)
        
    Example:
        >>> # Want ±1 bb/100 margin with σ²=100
        >>> n = required_sample_size(target_margin=1.0, estimated_variance=100.0)
        >>> print(f"Required sample size: {n} hands")
    """
    if target_margin <= 0:
        raise ValueError("target_margin must be positive")
    if estimated_variance < 0:
        raise ValueError("estimated_variance must be non-negative")
    
    estimated_std = np.sqrt(estimated_variance)
    
    try:
        from scipy import stats
        alpha = 1 - confidence
        z_critical = stats.norm.ppf(1 - alpha/2)
    except ImportError:
        # Fallback z-scores
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576, 0.999: 3.291}
        z_critical = z_scores.get(confidence, 1.96)
    
    # Formula: n = (Z * σ / E)²
    n = (z_critical * estimated_std / target_margin) ** 2
    
    # Round up to ensure we meet the target margin
    required_n = int(np.ceil(n))
    
    logger.info(
        f"Sample size calculation: target_margin={target_margin:.4f}, "
        f"σ={estimated_std:.4f}, confidence={confidence:.2f} -> n={required_n}"
    )
    
    return required_n


def estimate_variance_reduction(
    vanilla_variance: float,
    aivat_variance: float
) -> Dict[str, float]:
    """Calculate variance reduction percentage from AIVAT.
    
    Args:
        vanilla_variance: Variance without variance reduction
        aivat_variance: Variance with AIVAT
        
    Returns:
        Dictionary with reduction metrics
    """
    if vanilla_variance <= 0:
        raise ValueError("vanilla_variance must be positive")
    
    reduction_pct = (1 - aivat_variance / vanilla_variance) * 100
    
    return {
        'vanilla_variance': vanilla_variance,
        'aivat_variance': aivat_variance,
        'reduction_pct': reduction_pct,
        'efficiency_gain': vanilla_variance / max(aivat_variance, 1e-10)
    }


def check_margin_adequacy(
    current_margin: float,
    target_margin: float,
    current_n: int,
    estimated_variance: float,
    confidence: float = 0.95
) -> Dict[str, Any]:
    """Check if current margin of error is adequate and recommend action.
    
    Args:
        current_margin: Current margin of error from evaluation
        target_margin: Desired margin of error
        current_n: Current sample size
        estimated_variance: Estimated variance from current evaluation
        confidence: Confidence level
        
    Returns:
        Dictionary with adequacy check results and recommendations
    """
    is_adequate = current_margin <= target_margin
    
    if not is_adequate:
        # Calculate how many more samples needed
        required_n = required_sample_size(target_margin, estimated_variance, confidence)
        additional_n = max(0, required_n - current_n)
        
        recommendation = (
            f"Current margin ({current_margin:.4f}) exceeds target ({target_margin:.4f}). "
            f"Recommend {additional_n} additional samples (total: {required_n})"
        )
    else:
        recommendation = f"Margin adequate: {current_margin:.4f} ≤ {target_margin:.4f}"
    
    return {
        'is_adequate': is_adequate,
        'current_margin': current_margin,
        'target_margin': target_margin,
        'current_n': current_n,
        'recommendation': recommendation
    }


def format_ci_result(
    value: float,
    ci_info: Dict[str, Any],
    decimals: int = 2,
    unit: str = ""
) -> str:
    """Format a value with confidence interval for display.
    
    Args:
        value: The value to format (typically the mean)
        ci_info: CI info dict from compute_confidence_interval
        decimals: Number of decimal places
        unit: Optional unit string (e.g., "bb/100")
        
    Returns:
        Formatted string like "5.23 ± 0.45 bb/100 (95% CI: [4.78, 5.68])"
    """
    margin = ci_info['margin']
    ci_lower = ci_info['ci_lower']
    ci_upper = ci_info['ci_upper']
    confidence_pct = int(ci_info['confidence'] * 100)
    
    unit_str = f" {unit}" if unit else ""
    
    formatted = (
        f"{value:.{decimals}f} ± {margin:.{decimals}f}{unit_str} "
        f"({confidence_pct}% CI: [{ci_lower:.{decimals}f}, {ci_upper:.{decimals}f}])"
    )
    
    return formatted


class EvaluationStats:
    """Accumulate and compute evaluation statistics for poker players.
    
    This class collects results from multiple hands across multiple players
    and computes key metrics including winrates in bb/100, standard deviations,
    and 95% confidence intervals.
    
    Attributes:
        big_blind: Size of the big blind (for bb/100 calculation)
        confidence_level: Confidence level for intervals (default: 0.95)
        player_results: Dict mapping player_id to list of payoffs
        
    Example:
        >>> stats = EvaluationStats(big_blind=2.0)
        >>> stats.add_result(player_id=0, payoff=10.0)
        >>> stats.add_result(player_id=1, payoff=-10.0)
        >>> metrics = stats.compute_metrics()
        >>> print(metrics[0]['bb_per_100'])
    """
    
    def __init__(
        self,
        big_blind: float = 2.0,
        confidence_level: float = 0.95
    ):
        """Initialize evaluation statistics collector.
        
        Args:
            big_blind: Size of the big blind for bb/100 calculation
            confidence_level: Confidence level for CI (default: 0.95)
        """
        self.big_blind = big_blind
        self.confidence_level = confidence_level
        self.player_results: Dict[int, List[float]] = {}
        
        logger.debug(
            f"EvaluationStats initialized: bb={big_blind}, "
            f"confidence={confidence_level}"
        )
    
    def add_result(self, player_id: int, payoff: float) -> None:
        """Add a single hand result for a player.
        
        Args:
            player_id: Player identifier (seat number or player index)
            payoff: Payoff for this hand (in chips)
        """
        if player_id not in self.player_results:
            self.player_results[player_id] = []
        self.player_results[player_id].append(payoff)
    
    def add_results_batch(
        self,
        player_id: int,
        payoffs: List[float]
    ) -> None:
        """Add multiple hand results for a player at once.
        
        Args:
            player_id: Player identifier
            payoffs: List of payoffs (in chips)
        """
        if player_id not in self.player_results:
            self.player_results[player_id] = []
        self.player_results[player_id].extend(payoffs)
    
    def compute_metrics(
        self,
        player_id: Optional[int] = None,
        method: str = "analytical"
    ) -> Dict[int, Dict[str, Any]]:
        """Compute evaluation metrics for players.
        
        Args:
            player_id: Specific player to compute for (None = all players)
            method: CI method - "analytical" (t-distribution) or "bootstrap"
            
        Returns:
            Dict mapping player_id to metrics dict containing:
                - n_hands: Number of hands played
                - mean_payoff: Mean payoff per hand (in chips)
                - bb_per_100: Winrate in big blinds per 100 hands
                - std: Standard deviation of payoffs
                - ci_lower: Lower bound of 95% CI for mean payoff
                - ci_upper: Upper bound of 95% CI for mean payoff
                - ci_lower_bb100: Lower bound of 95% CI in bb/100
                - ci_upper_bb100: Upper bound of 95% CI in bb/100
                - margin: Margin of error (±)
                - margin_bb100: Margin of error in bb/100
                
        Example:
            >>> stats.add_result(0, 5.0)
            >>> stats.add_result(0, -3.0)
            >>> metrics = stats.compute_metrics(player_id=0)
            >>> print(f"BB/100: {metrics[0]['bb_per_100']:.2f}")
        """
        if player_id is not None:
            players_to_compute = [player_id]
        else:
            players_to_compute = list(self.player_results.keys())
        
        results = {}
        
        for pid in players_to_compute:
            if pid not in self.player_results:
                logger.warning(f"No results for player {pid}")
                continue
            
            payoffs = self.player_results[pid]
            n_hands = len(payoffs)
            
            if n_hands == 0:
                logger.warning(f"Player {pid} has no hands")
                continue
            
            # Compute basic statistics
            mean_payoff = float(np.mean(payoffs))
            std_payoff = float(np.std(payoffs, ddof=1))
            
            # Convert to bb/100
            bb_per_100 = (mean_payoff / self.big_blind) * 100
            
            # Compute confidence interval
            if n_hands > 1:
                ci_info = compute_confidence_interval(
                    payoffs,
                    confidence=self.confidence_level,
                    method=method
                )
                
                ci_lower = ci_info['ci_lower']
                ci_upper = ci_info['ci_upper']
                margin = ci_info['margin']
                stderr = ci_info['stderr']
                
                # Convert CI to bb/100
                ci_lower_bb100 = (ci_lower / self.big_blind) * 100
                ci_upper_bb100 = (ci_upper / self.big_blind) * 100
                margin_bb100 = (margin / self.big_blind) * 100
            else:
                # Single hand - no meaningful CI
                ci_lower = mean_payoff
                ci_upper = mean_payoff
                margin = 0.0
                stderr = 0.0
                ci_lower_bb100 = bb_per_100
                ci_upper_bb100 = bb_per_100
                margin_bb100 = 0.0
            
            results[pid] = {
                'n_hands': n_hands,
                'mean_payoff': mean_payoff,
                'bb_per_100': bb_per_100,
                'std': std_payoff,
                'stderr': stderr,
                'ci_lower': ci_lower,
                'ci_upper': ci_upper,
                'ci_lower_bb100': ci_lower_bb100,
                'ci_upper_bb100': ci_upper_bb100,
                'margin': margin,
                'margin_bb100': margin_bb100,
                'confidence_level': self.confidence_level
            }
            
            logger.debug(
                f"Player {pid}: {n_hands} hands, "
                f"bb/100={bb_per_100:.2f} ± {margin_bb100:.2f}"
            )
        
        return results
    
    def to_dict(
        self,
        include_raw_results: bool = False,
        method: str = "analytical"
    ) -> Dict[str, Any]:
        """Serialize evaluation statistics to dictionary.
        
        Args:
            include_raw_results: Whether to include raw payoff lists
            method: CI computation method
            
        Returns:
            Dictionary with all statistics, JSON-serializable
        """
        metrics = self.compute_metrics(method=method)
        
        result = {
            'big_blind': self.big_blind,
            'confidence_level': self.confidence_level,
            'players': metrics
        }
        
        if include_raw_results:
            result['raw_results'] = {
                str(pid): payoffs
                for pid, payoffs in self.player_results.items()
            }
        
        return result
    
    def format_summary(self, player_id: Optional[int] = None) -> str:
        """Format a human-readable summary of statistics.
        
        Args:
            player_id: Specific player to summarize (None = all players)
            
        Returns:
            Formatted string with statistics
        """
        metrics = self.compute_metrics(player_id=player_id)
        
        lines = []
        lines.append("=" * 70)
        lines.append("EVALUATION STATISTICS SUMMARY")
        lines.append("=" * 70)
        
        for pid in sorted(metrics.keys()):
            m = metrics[pid]
            lines.append(f"\nPlayer {pid}:")
            lines.append(f"  Hands played: {m['n_hands']}")
            lines.append(
                f"  Mean payoff: {m['mean_payoff']:.2f} ± {m['margin']:.2f} chips"
            )
            lines.append(
                f"  Winrate: {m['bb_per_100']:.2f} ± {m['margin_bb100']:.2f} bb/100"
            )
            lines.append(
                f"  {int(self.confidence_level*100)}% CI: "
                f"[{m['ci_lower_bb100']:.2f}, {m['ci_upper_bb100']:.2f}] bb/100"
            )
            lines.append(f"  Std deviation: {m['std']:.2f} chips")
        
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def get_player_ids(self) -> List[int]:
        """Get list of all player IDs with results.
        
        Returns:
            List of player IDs
        """
        return list(self.player_results.keys())
    
    def clear(self) -> None:
        """Clear all accumulated results."""
        self.player_results.clear()
        logger.debug("EvaluationStats cleared")


def export_evaluation_results(
    stats: EvaluationStats,
    output_dir: str = "eval_runs",
    config: Optional[Dict[str, Any]] = None,
    prefix: str = "EVAL_RESULTS",
    include_raw: bool = False
) -> str:
    """Export evaluation results to JSON file.
    
    Creates a timestamped JSON file with evaluation statistics and configuration.
    The file is saved in the specified output directory with a name like:
    EVAL_RESULTS_2024-01-15_14-30-45_config_hash.json
    
    Args:
        stats: EvaluationStats object with results
        output_dir: Directory to save results (created if doesn't exist)
        config: Optional dict with evaluation configuration (num_hands, seed, etc.)
        prefix: Prefix for output filename
        include_raw: Whether to include raw payoff data
        
    Returns:
        Path to the created JSON file
        
    Example:
        >>> stats = EvaluationStats(big_blind=2.0)
        >>> # ... accumulate results ...
        >>> config = {'num_hands': 10000, 'seed': 42, 'method': 'blueprint'}
        >>> path = export_evaluation_results(stats, config=config)
        >>> print(f"Results saved to {path}")
    """
    # Create output directory if needed
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Compute config hash for traceability
    config_hash = "default"
    if config:
        config_str = json.dumps(config, sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]
    
    # Build filename
    filename = f"{prefix}_{timestamp}_{config_hash}.json"
    filepath = output_path / filename
    
    # Prepare output data
    output_data = {
        'metadata': {
            'timestamp': timestamp,
            'config_hash': config_hash,
            'version': '1.0'
        },
        'config': config or {},
        'statistics': stats.to_dict(
            include_raw_results=include_raw,
            method="analytical"
        )
    }
    
    # Write to file
    with open(filepath, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Evaluation results exported to {filepath}")
    
    return str(filepath)
