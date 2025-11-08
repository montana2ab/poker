#!/usr/bin/env python3
"""Example demonstrating AIVAT usage for variance reduction in evaluation.

This example shows how to:
1. Create an evaluator with AIVAT enabled
2. Run evaluation with warmup phase
3. Compare variance reduction results
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from holdem.rl_eval.eval_loop import Evaluator
from holdem.rl_eval.aivat import AIVATEvaluator
from holdem.mccfr.policy_store import PolicyStore


def example_basic_aivat():
    """Basic AIVAT usage example."""
    print("=" * 60)
    print("EXAMPLE 1: Basic AIVAT Usage")
    print("=" * 60)
    
    # Create a policy to evaluate (in this example, it's a placeholder)
    policy = PolicyStore()
    
    # Create evaluator with AIVAT enabled
    print("\nCreating evaluator with AIVAT enabled...")
    evaluator = Evaluator(
        policy=policy,
        use_aivat=True,  # Enable AIVAT
        num_players=9    # Number of players in game
    )
    
    # Run evaluation
    print("\nRunning evaluation:")
    print("  - Warmup episodes: 100 (for baseline training)")
    print("  - Evaluation episodes: 500")
    
    results = evaluator.evaluate(
        num_episodes=500,
        warmup_episodes=100
    )
    
    # Display results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    for baseline_name, metrics in results.items():
        if baseline_name == 'aivat_stats':
            continue
            
        print(f"\nVs {baseline_name}:")
        print(f"  Mean winnings: {metrics['mean']:.2f}")
        print(f"  Std dev: {metrics['std']:.2f}")
        
        if 'aivat' in metrics:
            aivat = metrics['aivat']
            print(f"\n  Variance Reduction with AIVAT:")
            print(f"    Vanilla variance: {aivat['vanilla_variance']:.2f}")
            print(f"    AIVAT variance: {aivat['aivat_variance']:.2f}")
            print(f"    Reduction: {aivat['variance_reduction_pct']:.1f}%")
            
            # Calculate sample efficiency gain
            if aivat['variance_reduction_ratio'] < 1.0:
                efficiency_gain = 1.0 / aivat['variance_reduction_ratio']
                print(f"    Sample efficiency: {efficiency_gain:.1f}x improvement")


def example_comparison():
    """Compare evaluation with and without AIVAT."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 2: Comparing Vanilla vs AIVAT")
    print("=" * 60)
    
    policy = PolicyStore()
    
    # Vanilla evaluation
    print("\nRunning VANILLA evaluation...")
    evaluator_vanilla = Evaluator(policy, use_aivat=False)
    results_vanilla = evaluator_vanilla.evaluate(num_episodes=200)
    
    # AIVAT evaluation
    print("\nRunning AIVAT evaluation...")
    evaluator_aivat = Evaluator(policy, use_aivat=True, num_players=9)
    results_aivat = evaluator_aivat.evaluate(
        num_episodes=200,
        warmup_episodes=100
    )
    
    # Compare results
    print("\n" + "=" * 60)
    print("COMPARISON: VANILLA vs AIVAT")
    print("=" * 60)
    
    for baseline_name in ['Random', 'AlwaysCall', 'Tight', 'Aggressive']:
        vanilla_var = results_vanilla[baseline_name]['variance']
        
        if 'aivat' in results_aivat[baseline_name]:
            aivat_var = results_aivat[baseline_name]['aivat']['aivat_variance']
            reduction = (vanilla_var - aivat_var) / vanilla_var * 100 if vanilla_var > 0 else 0
            
            print(f"\nVs {baseline_name}:")
            print(f"  Vanilla variance: {vanilla_var:.2f}")
            print(f"  AIVAT variance: {aivat_var:.2f}")
            print(f"  Reduction: {reduction:.1f}%")


def example_standalone_aivat():
    """Example of using AIVATEvaluator standalone (without Evaluator)."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 3: Standalone AIVAT Usage")
    print("=" * 60)
    
    import random
    random.seed(42)
    
    # Create AIVAT evaluator
    aivat = AIVATEvaluator(num_players=2, min_samples=50)
    
    # Simulate training phase - collect samples
    print("\nPhase 1: Collecting training samples...")
    for player_id in [0, 1]:
        for _ in range(50):
            # Simulate different game states
            state_key = f"state_{random.randint(0, 9)}"
            payoff = random.gauss(0, 10)
            
            aivat.add_sample(
                player_id=player_id,
                state_key=state_key,
                payoff=payoff
            )
    
    print(f"  Collected {sum(len(s) for s in aivat.samples.values())} samples")
    
    # Train value functions
    print("\nPhase 2: Training value functions...")
    aivat.train_value_functions()
    print(f"  Trained: {aivat.trained}")
    
    # Evaluation phase
    print("\nPhase 3: Evaluation with variance reduction...")
    vanilla_results = []
    aivat_results = []
    
    for _ in range(200):
        state_key = f"state_{random.randint(0, 9)}"
        payoff = random.gauss(0, 10)
        
        vanilla_results.append(payoff)
        
        advantage = aivat.compute_advantage(
            player_id=0,
            state_key=state_key,
            actual_payoff=payoff
        )
        aivat_results.append(advantage)
    
    # Calculate variance reduction
    stats = aivat.compute_variance_reduction(vanilla_results, aivat_results)
    
    print("\nResults:")
    print(f"  Vanilla variance: {stats['vanilla_variance']:.2f}")
    print(f"  AIVAT variance: {stats['aivat_variance']:.2f}")
    print(f"  Reduction: {stats['variance_reduction_pct']:.1f}%")
    print(f"  Samples: {stats['num_samples']}")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("AIVAT VARIANCE REDUCTION EXAMPLES")
    print("=" * 60)
    
    # Run examples
    example_basic_aivat()
    example_comparison()
    example_standalone_aivat()
    
    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
    print("\nKey takeaways:")
    print("  1. AIVAT reduces evaluation variance significantly (30-95%)")
    print("  2. Enables faster evaluation with smaller sample sizes")
    print("  3. Maintains unbiased estimation")
    print("  4. Easy to integrate - just set use_aivat=True")
    print("=" * 60 + "\n")
