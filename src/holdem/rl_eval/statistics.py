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
