#!/usr/bin/env python3
"""Example usage of enhanced RT vs Blueprint evaluation.

This script demonstrates how to use the enhanced evaluation tool with
various configurations.
"""

import json
import tempfile


def example_minimal():
    """Minimal example with a dummy policy."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Minimal Evaluation")
    print("="*70)
    
    print("\nCommand to run:")
    print("python tools/eval_rt_vs_blueprint_enhanced.py \\")
    print("    --policy runs/blueprint/avg_policy.json \\")
    print("    --hands 1000 \\")
    print("    --paired \\")
    print("    --output results/minimal_eval.json")
    print("\nThis will:")
    print("  - Evaluate 1000 hands")
    print("  - Use paired bootstrap for variance reduction")
    print("  - Output results to JSON file")


def example_multi_seed():
    """Example with multiple seeds."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Multi-Seed Evaluation")
    print("="*70)
    
    print("\nCommand to run:")
    print("python tools/eval_rt_vs_blueprint_enhanced.py \\")
    print("    --policy runs/blueprint/avg_policy.json \\")
    print("    --seeds 42,1337,2025 \\")
    print("    --hands-per-seed 5000 \\")
    print("    --paired \\")
    print("    --output results/multi_seed_eval.json")
    print("\nThis will:")
    print("  - Run 3 evaluations with different seeds")
    print("  - 5,000 hands per seed (15,000 total)")
    print("  - Aggregate results across all seeds")
    print("  - Validate stability of conclusions")


def example_production():
    """Example with production configuration."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Production Configuration")
    print("="*70)
    
    print("\nCommand to run:")
    print("python tools/eval_rt_vs_blueprint_enhanced.py \\")
    print("    --policy runs/blueprint/avg_policy.json \\")
    print("    --seeds 42,1337,2025 \\")
    print("    --hands-per-seed 5000 \\")
    print("    --paired \\")
    print("    --street-samples flop=16,turn=32,river=64 \\")
    print("    --time-budget-ms 110 \\")
    print("    --strict-budget \\")
    print("    --aivat \\")
    print("    --bootstrap-reps 2000 \\")
    print("    --output results/production_eval.json \\")
    print("    --export-csv results/production_eval.csv")
    print("\nThis will:")
    print("  - Comprehensive evaluation with all features")
    print("  - 15,000 total hands across 3 seeds")
    print("  - Stratified by position and street")
    print("  - Per-street adaptive sampling (16/32/64)")
    print("  - Strict time budget (p95 ≤ 110ms)")
    print("  - AIVAT for variance reduction")
    print("  - 2,000 bootstrap replicates")
    print("  - Output to both JSON and CSV")
    print("  - Automated DoD validation")


def example_interpreting_results():
    """Show how to interpret results."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Interpreting Results")
    print("="*70)
    
    # Example output
    example_result = {
        "commit_hash": "abcd1234",
        "seeds": [42, 1337, 2025],
        "total_hands": 15000,
        "bootstrap_reps": 2000,
        "ev_delta_bb100": 3.45,
        "ci_lower": 1.23,
        "ci_upper": 5.67,
        "is_significant": True,
        "p_value": 0.0012,
        "latency": {
            "mean": 85.2,
            "p50": 78.5,
            "p95": 105.3,
            "fallback_rate": 0.023
        },
        "kl_stats": {
            "p50": 0.125,
            "p95": 0.245
        }
    }
    
    print("\nExample output:")
    print(json.dumps(example_result, indent=2))
    
    print("\n\nInterpretation:")
    print(f"  EVΔ: {example_result['ev_delta_bb100']:+.2f} bb/100")
    print(f"  → RT search wins {example_result['ev_delta_bb100']:.2f} big blinds per 100 hands")
    
    print(f"\n  95% CI: [{example_result['ci_lower']:+.2f}, {example_result['ci_upper']:+.2f}]")
    print(f"  → We're 95% confident the true EVΔ is in this range")
    
    print(f"\n  Significant: {example_result['is_significant']}")
    print(f"  → {'✅ RT is statistically better than blueprint' if example_result['is_significant'] else '❌ No significant difference'}")
    
    print(f"\n  Latency p95: {example_result['latency']['p95']:.1f}ms")
    print(f"  → {'✅ Meets 110ms requirement' if example_result['latency']['p95'] <= 110 else '❌ Exceeds 110ms requirement'}")
    
    print(f"\n  Fallback rate: {example_result['latency']['fallback_rate']*100:.1f}%")
    print(f"  → {'✅ Under 5% fallback' if example_result['latency']['fallback_rate'] <= 0.05 else '❌ Exceeds 5% fallback'}")
    
    print(f"\n  KL p50: {example_result['kl_stats']['p50']:.3f}")
    print(f"  → {'✅ In acceptable range [0.05, 0.25]' if 0.05 <= example_result['kl_stats']['p50'] <= 0.25 else '⚠️  Outside acceptable range'}")


def example_quick_reference():
    """Quick reference for common tasks."""
    print("\n" + "="*70)
    print("QUICK REFERENCE")
    print("="*70)
    
    print("\n1. QUICK TEST (1000 hands):")
    print("   python tools/eval_rt_vs_blueprint_enhanced.py \\")
    print("       --policy <policy> --hands 1000 --paired")
    
    print("\n2. STANDARD EVAL (10k hands):")
    print("   python tools/eval_rt_vs_blueprint_enhanced.py \\")
    print("       --policy <policy> --hands 10000 --paired \\")
    print("       --output results/eval.json")
    
    print("\n3. MULTI-SEED (3×5k hands):")
    print("   python tools/eval_rt_vs_blueprint_enhanced.py \\")
    print("       --policy <policy> --seeds 42,1337,2025 \\")
    print("       --hands-per-seed 5000 --paired")
    
    print("\n4. WITH AIVAT (variance reduction):")
    print("   python tools/eval_rt_vs_blueprint_enhanced.py \\")
    print("       --policy <policy> --hands 10000 --paired --aivat")
    
    print("\n5. LATENCY FOCUSED (strict budget):")
    print("   python tools/eval_rt_vs_blueprint_enhanced.py \\")
    print("       --policy <policy> --hands 10000 --paired \\")
    print("       --time-budget-ms 110 --strict-budget")
    
    print("\n6. PRODUCTION (all features):")
    print("   python tools/eval_rt_vs_blueprint_enhanced.py \\")
    print("       --policy <policy> --seeds 42,1337,2025 \\")
    print("       --hands-per-seed 5000 --paired \\")
    print("       --street-samples flop=16,turn=32,river=64 \\")
    print("       --time-budget-ms 110 --strict-budget --aivat \\")
    print("       --bootstrap-reps 2000 \\")
    print("       --output results/eval.json \\")
    print("       --export-csv results/eval.csv")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("ENHANCED RT VS BLUEPRINT EVALUATION - EXAMPLES")
    print("="*70)
    
    example_minimal()
    example_multi_seed()
    example_production()
    example_interpreting_results()
    example_quick_reference()
    
    print("\n" + "="*70)
    print("For complete documentation, see:")
    print("  docs/ENHANCED_RT_EVAL_GUIDE.md")
    print("="*70 + "\n")
