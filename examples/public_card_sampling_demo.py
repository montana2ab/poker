"""Example usage of public card sampling feature.

This demonstrates how to use the Pluribus public card sampling technique
to reduce variance in subgame solving.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import Card, Street, SearchConfig, TableState
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.resolver import SubgameResolver
from holdem.realtime.subgame import SubgameTree


def example_basic_usage():
    """Basic usage of public card sampling."""
    print("=== Example 1: Basic Public Card Sampling ===\n")
    
    # Configure sampling: solve on 10 sampled boards
    config = SearchConfig(
        time_budget_ms=500,        # Total time budget
        min_iterations=100,        # Minimum CFR iterations per solve
        samples_per_solve=10,      # Number of board samples
        kl_weight_flop=0.30        # KL regularization weight
    )
    
    # Create resolver with blueprint policy
    blueprint = PolicyStore()  # In practice, load trained blueprint
    resolver = SubgameResolver(config, blueprint)
    
    # Current game state (flop)
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[
            Card('A', 'h'),  # Flop
            Card('K', 's'),
            Card('Q', 'd')
        ]
    )
    
    # Hero's hole cards
    our_cards = [Card('J', 'c'), Card('T', 'c')]
    
    # Create subgame
    subgame = SubgameTree([Street.FLOP], state, our_cards)
    
    # Solve with public card sampling
    # This will:
    # 1. Sample 10 possible turn cards
    # 2. Solve subgame on each sampled board
    # 3. Average the resulting strategies
    strategy = resolver.solve_with_sampling(
        subgame=subgame,
        infoset="AhKsQd_JcTc",
        our_cards=our_cards,
        street=Street.FLOP,
        is_oop=False
    )
    
    print("Strategy with 10 board samples:")
    for action, prob in strategy.items():
        print(f"  {action.value}: {prob:.3f}")
    
    print("\n✓ Example complete\n")


def example_comparison():
    """Compare strategies with and without sampling."""
    print("=== Example 2: Comparing With/Without Sampling ===\n")
    
    # Configuration without sampling
    config_no_sampling = SearchConfig(
        time_budget_ms=100,
        min_iterations=100,
        samples_per_solve=1  # No sampling
    )
    
    # Configuration with sampling
    config_with_sampling = SearchConfig(
        time_budget_ms=500,
        min_iterations=100,
        samples_per_solve=10  # Sample 10 boards
    )
    
    blueprint = PolicyStore()
    
    # Same game state for both
    state = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
    )
    our_cards = [Card('J', 'c'), Card('T', 'c')]
    subgame = SubgameTree([Street.FLOP], state, our_cards)
    
    # Solve without sampling
    resolver_no_sampling = SubgameResolver(config_no_sampling, blueprint)
    strategy_no_sampling = resolver_no_sampling.solve(
        subgame, "test_infoset", street=Street.FLOP
    )
    
    print("Strategy WITHOUT sampling:")
    for action, prob in strategy_no_sampling.items():
        print(f"  {action.value}: {prob:.3f}")
    
    # Solve with sampling
    resolver_with_sampling = SubgameResolver(config_with_sampling, blueprint)
    strategy_with_sampling = resolver_with_sampling.solve_with_sampling(
        subgame, "test_infoset", our_cards, street=Street.FLOP
    )
    
    print("\nStrategy WITH sampling (10 boards):")
    for action, prob in strategy_with_sampling.items():
        print(f"  {action.value}: {prob:.3f}")
    
    print("\n✓ Example complete\n")


def example_different_streets():
    """Example of sampling on different streets."""
    print("=== Example 3: Sampling on Different Streets ===\n")
    
    config = SearchConfig(
        time_budget_ms=500,
        min_iterations=100,
        samples_per_solve=10
    )
    
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Example 1: Flop - samples turn cards
    print("1. Flop (samples turn cards):")
    state_flop = TableState(
        street=Street.FLOP,
        pot=100.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
    )
    our_cards = [Card('J', 'c'), Card('T', 'c')]
    subgame_flop = SubgameTree([Street.FLOP], state_flop, our_cards)
    
    strategy_flop = resolver.solve_with_sampling(
        subgame_flop, "flop_infoset", our_cards, street=Street.FLOP
    )
    print(f"   Got strategy with {len(strategy_flop)} actions")
    
    # Example 2: Turn - samples river cards
    print("\n2. Turn (samples river cards):")
    state_turn = TableState(
        street=Street.TURN,
        pot=150.0,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd'), Card('J', 'h')]
    )
    subgame_turn = SubgameTree([Street.TURN], state_turn, our_cards)
    
    strategy_turn = resolver.solve_with_sampling(
        subgame_turn, "turn_infoset", our_cards, street=Street.TURN
    )
    print(f"   Got strategy with {len(strategy_turn)} actions")
    
    # Example 3: River - no sampling (already at final street)
    print("\n3. River (no sampling - already at final street):")
    state_river = TableState(
        street=Street.RIVER,
        pot=200.0,
        board=[
            Card('A', 'h'), Card('K', 's'), Card('Q', 'd'),
            Card('J', 'h'), Card('T', 's')
        ]
    )
    subgame_river = SubgameTree([Street.RIVER], state_river, our_cards)
    
    strategy_river = resolver.solve_with_sampling(
        subgame_river, "river_infoset", our_cards, street=Street.RIVER
    )
    print(f"   Got strategy with {len(strategy_river)} actions")
    print("   (automatically falls back to single solve on river)")
    
    print("\n✓ Example complete\n")


def example_configuration_tuning():
    """Example of tuning sampling configuration."""
    print("=== Example 4: Configuration Tuning ===\n")
    
    print("Recommended configurations by use case:\n")
    
    # Fast real-time play (online poker)
    print("1. Fast Real-time Play (online poker):")
    config_fast = SearchConfig(
        time_budget_ms=80,         # Very tight time budget
        min_iterations=50,
        samples_per_solve=5,       # Few samples for speed
        kl_weight_flop=0.30
    )
    print(f"   samples_per_solve: {config_fast.samples_per_solve}")
    print(f"   time_budget_ms: {config_fast.time_budget_ms}")
    print(f"   Expected overhead: ~5x (still under 500ms total)")
    
    # Balanced (tournament play)
    print("\n2. Balanced (tournament play):")
    config_balanced = SearchConfig(
        time_budget_ms=200,        # Moderate time budget
        min_iterations=100,
        samples_per_solve=10,      # Good variance reduction
        kl_weight_flop=0.30
    )
    print(f"   samples_per_solve: {config_balanced.samples_per_solve}")
    print(f"   time_budget_ms: {config_balanced.time_budget_ms}")
    print(f"   Expected overhead: ~10x (under 2 seconds total)")
    
    # High quality (analysis/study)
    print("\n3. High Quality (analysis/study):")
    config_quality = SearchConfig(
        time_budget_ms=1000,       # Large time budget
        min_iterations=500,
        samples_per_solve=50,      # Maximum variance reduction
        kl_weight_flop=0.30
    )
    print(f"   samples_per_solve: {config_quality.samples_per_solve}")
    print(f"   time_budget_ms: {config_quality.time_budget_ms}")
    print(f"   Expected overhead: ~50x (under 50 seconds total)")
    
    # Disabled (testing/debugging)
    print("\n4. Disabled (testing/debugging):")
    config_disabled = SearchConfig(
        time_budget_ms=100,
        min_iterations=100,
        samples_per_solve=1,       # No sampling
        kl_weight_flop=0.30
    )
    print(f"   samples_per_solve: {config_disabled.samples_per_solve}")
    print(f"   time_budget_ms: {config_disabled.time_budget_ms}")
    print(f"   Expected overhead: 1x (baseline)")
    
    print("\n✓ Example complete\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("PUBLIC CARD SAMPLING - USAGE EXAMPLES")
    print("="*60 + "\n")
    
    example_basic_usage()
    example_comparison()
    example_different_streets()
    example_configuration_tuning()
    
    print("="*60)
    print("All examples completed successfully!")
    print("="*60 + "\n")
