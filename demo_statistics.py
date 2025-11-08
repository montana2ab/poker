#!/usr/bin/env python3
"""Demonstration of confidence interval and sample size calculator features.

This script demonstrates the new statistical features for poker AI evaluation:
1. Automatic confidence interval calculation
2. Sample size recommendation
3. Margin adequacy checking
4. AIVAT variance reduction integration
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
from holdem.rl_eval.statistics import (
    compute_confidence_interval,
    required_sample_size,
    check_margin_adequacy,
    format_ci_result,
    estimate_variance_reduction
)
from holdem.rl_eval.eval_loop import Evaluator
from holdem.mccfr.policy_store import PolicyStore


def demo_confidence_intervals():
    """Demonstrate confidence interval calculation."""
    print("\n" + "="*70)
    print("DEMO 1: CONFIDENCE INTERVAL CALCULATION")
    print("="*70)
    
    # Simulate some evaluation results
    np.random.seed(42)
    winrate_mean = 5.0  # bb/100
    winrate_std = 10.0
    n_hands = 1000
    
    results = np.random.normal(winrate_mean, winrate_std, n_hands)
    
    # Compute CI using bootstrap method
    ci_bootstrap = compute_confidence_interval(
        results,
        confidence=0.95,
        method="bootstrap",
        n_bootstrap=10000
    )
    
    print(f"\nEvaluation results from {n_hands} hands:")
    print(f"  Method: Bootstrap (non-parametric)")
    print(f"  {format_ci_result(ci_bootstrap['mean'], ci_bootstrap, decimals=2, unit='bb/100')}")
    
    # Compute CI using analytical method
    ci_analytical = compute_confidence_interval(
        results,
        confidence=0.95,
        method="analytical"
    )
    
    print(f"\n  Method: Analytical (t-distribution)")
    print(f"  {format_ci_result(ci_analytical['mean'], ci_analytical, decimals=2, unit='bb/100')}")
    
    print(f"\n  Standard error: {ci_bootstrap['stderr']:.3f}")
    print(f"  Variance: {ci_bootstrap['std']**2:.2f}")


def demo_sample_size_calculation():
    """Demonstrate sample size calculation."""
    print("\n" + "="*70)
    print("DEMO 2: SAMPLE SIZE CALCULATION")
    print("="*70)
    
    # Example scenarios
    scenarios = [
        {"variance": 100.0, "margin": 1.0, "desc": "Standard scenario (σ²=100, target ±1 bb/100)"},
        {"variance": 100.0, "margin": 2.0, "desc": "Relaxed margin (σ²=100, target ±2 bb/100)"},
        {"variance": 25.0, "margin": 1.0, "desc": "Low variance (σ²=25, target ±1 bb/100)"},
        {"variance": 400.0, "margin": 1.0, "desc": "High variance (σ²=400, target ±1 bb/100)"},
    ]
    
    print("\nRequired sample sizes for different scenarios:")
    print(f"{'Scenario':<50} {'Sample Size':>15}")
    print("-" * 70)
    
    for scenario in scenarios:
        n = required_sample_size(
            target_margin=scenario["margin"],
            estimated_variance=scenario["variance"],
            confidence=0.95
        )
        print(f"{scenario['desc']:<50} {n:>15,} hands")


def demo_margin_adequacy():
    """Demonstrate margin adequacy checking."""
    print("\n" + "="*70)
    print("DEMO 3: MARGIN ADEQUACY CHECKING")
    print("="*70)
    
    # Simulate evaluation with different sample sizes
    np.random.seed(42)
    true_mean = 5.0
    variance = 100.0
    target_margin = 1.0
    
    sample_sizes = [100, 500, 1000, 2000]
    
    print(f"\nTarget margin: ±{target_margin} bb/100")
    print(f"Estimated variance: {variance}")
    print(f"\n{'Sample Size':>12} {'Current Margin':>15} {'Status':>12} {'Recommendation'}")
    print("-" * 100)
    
    for n in sample_sizes:
        results = np.random.normal(true_mean, np.sqrt(variance), n)
        ci = compute_confidence_interval(results, confidence=0.95, method="analytical")
        
        adequacy = check_margin_adequacy(
            current_margin=ci['margin'],
            target_margin=target_margin,
            current_n=n,
            estimated_variance=variance
        )
        
        status = "✓ Adequate" if adequacy['is_adequate'] else "✗ Inadequate"
        print(f"{n:>12,} {ci['margin']:>15.3f} {status:>12}", end="")
        
        if not adequacy['is_adequate']:
            # Calculate additional needed
            required_n = required_sample_size(target_margin, variance)
            additional = max(0, required_n - n)
            print(f"  Need {additional:,} more samples")
        else:
            print()


def demo_variance_reduction():
    """Demonstrate AIVAT variance reduction benefits."""
    print("\n" + "="*70)
    print("DEMO 4: AIVAT VARIANCE REDUCTION")
    print("="*70)
    
    # Example from EVAL_PROTOCOL.md
    vanilla_var = 100.0
    aivat_var = 22.0  # 78% reduction
    
    reduction = estimate_variance_reduction(vanilla_var, aivat_var)
    
    print(f"\nVariance reduction analysis:")
    print(f"  Vanilla variance: {reduction['vanilla_variance']:.2f}")
    print(f"  AIVAT variance: {reduction['aivat_variance']:.2f}")
    print(f"  Reduction: {reduction['reduction_pct']:.1f}%")
    print(f"  Efficiency gain: {reduction['efficiency_gain']:.2f}x")
    
    # Calculate sample size savings
    target_margin = 1.0
    
    n_vanilla = required_sample_size(target_margin, vanilla_var)
    n_aivat = required_sample_size(target_margin, aivat_var)
    
    savings = n_vanilla - n_aivat
    savings_pct = (savings / n_vanilla) * 100
    
    print(f"\nSample size for ±{target_margin} bb/100 margin:")
    print(f"  Without AIVAT: {n_vanilla:,} hands")
    print(f"  With AIVAT: {n_aivat:,} hands")
    print(f"  Savings: {savings:,} hands ({savings_pct:.1f}%)")


def demo_full_evaluation():
    """Demonstrate full evaluation with CI and AIVAT."""
    print("\n" + "="*70)
    print("DEMO 5: FULL EVALUATION WITH CONFIDENCE INTERVALS")
    print("="*70)
    
    print("\nRunning evaluation with AIVAT and automatic CI calculation...")
    print("(This uses a simplified simulation for demonstration)")
    
    # Create evaluator with CI calculation
    policy = PolicyStore()
    evaluator = Evaluator(
        policy,
        use_aivat=True,
        confidence_level=0.95,
        target_margin=2.0  # Target ±2 bb/100 for demo (more lenient)
    )
    
    # Run small evaluation for demo
    results = evaluator.evaluate(num_episodes=200, warmup_episodes=100)
    
    print("\n" + "-"*70)
    print("EVALUATION RESULTS")
    print("-"*70)
    
    for baseline_name, metrics in results.items():
        if baseline_name == 'aivat_stats':
            continue
        
        ci = metrics['confidence_interval']
        print(f"\n{baseline_name}:")
        print(f"  Winrate: {format_ci_result(ci['mean'], ci, decimals=2, unit='bb/100')}")
        print(f"  Variance: {metrics['variance']:.2f}")
        
        if 'aivat' in metrics:
            aivat_metrics = metrics['aivat']
            print(f"  AIVAT variance reduction: {aivat_metrics['variance_reduction_pct']:.1f}%")
            print(f"    Vanilla variance: {aivat_metrics['vanilla_variance']:.2f}")
            print(f"    AIVAT variance: {aivat_metrics['aivat_variance']:.2f}")
        
        if 'margin_adequacy' in metrics:
            adequacy = metrics['margin_adequacy']
            if adequacy['is_adequate']:
                print(f"  ✓ Margin is adequate (≤ {adequacy['target_margin']:.2f})")
            else:
                print(f"  ⚠ {adequacy['recommendation']}")


def main():
    """Run all demonstrations."""
    print("\n" + "#"*70)
    print("# CONFIDENCE INTERVALS AND SAMPLE SIZE CALCULATOR DEMO")
    print("#"*70)
    print("\nThis demonstration shows the new statistical features for")
    print("statistically valid poker AI evaluation.")
    
    demo_confidence_intervals()
    demo_sample_size_calculation()
    demo_margin_adequacy()
    demo_variance_reduction()
    demo_full_evaluation()
    
    print("\n" + "#"*70)
    print("# DEMO COMPLETE")
    print("#"*70)
    print("\nFor more information, see EVAL_PROTOCOL.md")
    print()


if __name__ == '__main__':
    main()
