"""
Example Usage: KL Regularization Enhancement

This example demonstrates the new KL regularization features.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from holdem.types import SearchConfig, Street
from holdem.realtime.resolver import SubgameResolver
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.abstraction.actions import AbstractAction


def create_example_blueprint():
    """Create a simple blueprint strategy."""
    tracker = RegretTracker()
    
    # Add some example strategies
    for i in range(3):
        infoset = f"EXAMPLE:{i}:state"
        tracker.add_strategy(infoset, {
            AbstractAction.FOLD: 0.1,
            AbstractAction.CHECK_CALL: 0.4,
            AbstractAction.BET_HALF_POT: 0.3,
            AbstractAction.BET_POT: 0.2
        }, 10.0)
    
    return PolicyStore(tracker)


class ExampleSubgame:
    """Simple example subgame."""
    def __init__(self, street):
        self.state = type('obj', (object,), {'street': street})()
    
    def get_actions(self, infoset):
        return [
            AbstractAction.FOLD,
            AbstractAction.CHECK_CALL,
            AbstractAction.BET_HALF_POT,
            AbstractAction.BET_POT
        ]


def example_default_configuration():
    """Example 1: Default configuration (conservative play)."""
    print("\n" + "="*60)
    print("Example 1: Default Configuration (Conservative Play)")
    print("="*60)
    
    config = SearchConfig(
        min_iterations=10,
        time_budget_ms=100
    )
    
    print(f"\nKL Weights by Street:")
    print(f"  Flop:   {config.kl_weight_flop}")
    print(f"  Turn:   {config.kl_weight_turn}")
    print(f"  River:  {config.kl_weight_river}")
    print(f"  OOP Bonus: +{config.kl_weight_oop_bonus}")
    
    blueprint = create_example_blueprint()
    resolver = SubgameResolver(config, blueprint)
    
    # Solve for different scenarios
    print(f"\nSolving subgames...")
    for street in [Street.FLOP, Street.TURN, Street.RIVER]:
        for is_oop in [False, True]:
            position = "OOP" if is_oop else "IP"
            subgame = ExampleSubgame(street)
            
            # Get the KL weight that will be used
            kl_weight = config.get_kl_weight(street, is_oop)
            print(f"\n{street.name} {position}: kl_weight = {kl_weight:.2f}")
            
            # Solve
            strategy = resolver.solve(
                subgame,
                f"EXAMPLE:0:state",
                street=street,
                is_oop=is_oop
            )
    
    # Get statistics
    print("\n" + "-"*60)
    print("KL Divergence Statistics:")
    print("-"*60)
    stats = resolver.get_kl_statistics()
    
    for street_name, positions in stats.items():
        for position, stat_dict in positions.items():
            print(f"\n{street_name.upper()} {position}:")
            print(f"  Average:  {stat_dict['avg']:.4f}")
            print(f"  Median:   {stat_dict['p50']:.4f}")
            print(f"  P90:      {stat_dict['p90']:.4f}")
            print(f"  P99:      {stat_dict['p99']:.4f}")
            print(f"  High%:    {stat_dict['pct_high']:.1f}%")
            print(f"  Samples:  {stat_dict['count']}")


def example_exploit_mode():
    """Example 2: Exploit caller mode (aggressive play)."""
    print("\n" + "="*60)
    print("Example 2: Exploit Caller Mode (Aggressive Play)")
    print("="*60)
    
    config = SearchConfig(
        min_iterations=10,
        time_budget_ms=100,
        # Lower weights for more deviation from blueprint
        kl_weight_flop=0.15,
        kl_weight_turn=0.30,
        kl_weight_river=0.40
    )
    
    print(f"\nKL Weights by Street (Exploit Mode):")
    print(f"  Flop:   {config.kl_weight_flop} (vs default 0.30)")
    print(f"  Turn:   {config.kl_weight_turn} (vs default 0.50)")
    print(f"  River:  {config.kl_weight_river} (vs default 0.70)")
    
    blueprint = create_example_blueprint()
    resolver = SubgameResolver(config, blueprint)
    
    # Solve a river spot OOP
    subgame = ExampleSubgame(Street.RIVER)
    kl_weight = config.get_kl_weight(Street.RIVER, is_oop=True)
    
    print(f"\nRiver OOP: kl_weight = {kl_weight:.2f} (vs default 0.80)")
    print("Lower weight allows more exploitation!")
    
    strategy = resolver.solve(
        subgame,
        "EXAMPLE:0:state",
        street=Street.RIVER,
        is_oop=True
    )
    
    print(f"\nStrategy computed with more freedom to deviate from blueprint")


def example_custom_configuration():
    """Example 3: Custom configuration."""
    print("\n" + "="*60)
    print("Example 3: Custom Configuration")
    print("="*60)
    
    config = SearchConfig(
        min_iterations=15,
        time_budget_ms=150,
        # Custom weights
        kl_weight_flop=0.25,
        kl_weight_turn=0.45,
        kl_weight_river=0.65,
        kl_weight_oop_bonus=0.15,  # Stronger OOP bonus
        # Statistics configuration
        track_kl_stats=True,
        kl_high_threshold=0.25,  # Lower threshold
        # Blueprint clipping
        blueprint_clip_min=1e-5  # Different clipping
    )
    
    print(f"\nCustom Configuration:")
    print(f"  Street weights: {config.kl_weight_flop}/{config.kl_weight_turn}/{config.kl_weight_river}")
    print(f"  OOP bonus: +{config.kl_weight_oop_bonus}")
    print(f"  High KL threshold: {config.kl_high_threshold}")
    print(f"  Blueprint clip min: {config.blueprint_clip_min}")
    
    blueprint = create_example_blueprint()
    resolver = SubgameResolver(config, blueprint)
    
    # Solve a flop spot
    subgame = ExampleSubgame(Street.FLOP)
    strategy = resolver.solve(
        subgame,
        "EXAMPLE:0:state",
        street=Street.FLOP,
        is_oop=True
    )
    
    print(f"\nStrategy computed with custom parameters")


def example_kl_weight_comparison():
    """Example 4: Compare KL weights across scenarios."""
    print("\n" + "="*60)
    print("Example 4: KL Weight Comparison Table")
    print("="*60)
    
    config = SearchConfig()
    
    print("\n{:<15} {:<10} {:<10}".format("Scenario", "IP Weight", "OOP Weight"))
    print("-" * 40)
    
    for street in [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]:
        ip_weight = config.get_kl_weight(street, is_oop=False)
        oop_weight = config.get_kl_weight(street, is_oop=True)
        print("{:<15} {:<10.2f} {:<10.2f}".format(street.name, ip_weight, oop_weight))
    
    print("\n" + "="*60)
    print("Key Insights:")
    print("="*60)
    print("1. Weights increase from flop to river")
    print("   → More regularization later in hand")
    print("2. OOP weights are higher than IP")
    print("   → More conservative when out of position")
    print("3. Preflop uses default kl_weight (1.0)")
    print("   → Can be customized separately if needed")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("KL REGULARIZATION ENHANCEMENT - EXAMPLES")
    print("="*60)
    
    try:
        example_default_configuration()
        example_exploit_mode()
        example_custom_configuration()
        example_kl_weight_comparison()
        
        print("\n" + "="*60)
        print("✓ All examples completed successfully!")
        print("="*60)
        print("\nFor more details, see: KL_REGULARIZATION_ENHANCEMENT.md")
        
    except Exception as e:
        print(f"\n✗ Example failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
