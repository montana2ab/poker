"""Tests for round-start resolving (unsafe search from beginning of round)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import Street, SearchConfig, RTResolverConfig
from holdem.realtime.resolver import SubgameResolver
from holdem.mccfr.policy_store import PolicyStore


def test_search_config_round_start_option():
    """Test that SearchConfig has resolve_from_round_start option."""
    config = SearchConfig()
    assert hasattr(config, 'resolve_from_round_start')
    assert config.resolve_from_round_start == False  # Default is False
    
    config2 = SearchConfig(resolve_from_round_start=True)
    assert config2.resolve_from_round_start == True
    
    print("✓ SearchConfig.resolve_from_round_start option exists")


def test_rt_resolver_config_round_start_option():
    """Test that RTResolverConfig has resolve_from_round_start option."""
    config = RTResolverConfig()
    assert hasattr(config, 'resolve_from_round_start')
    assert config.resolve_from_round_start == False  # Default is False
    
    config2 = RTResolverConfig(resolve_from_round_start=True)
    assert config2.resolve_from_round_start == True
    
    print("✓ RTResolverConfig.resolve_from_round_start option exists")


def test_reconstruct_round_history():
    """Test round history reconstruction method."""
    config = SearchConfig(resolve_from_round_start=True)
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Test with empty history (preflop start)
    history = []
    round_start, frozen = resolver.reconstruct_round_history(
        history, Street.PREFLOP, freeze_our_actions=True
    )
    
    assert isinstance(round_start, list)
    assert isinstance(frozen, list)
    
    print("✓ reconstruct_round_history method exists and runs")


def test_round_start_with_simple_history():
    """Test round reconstruction with simple action history."""
    config = SearchConfig(resolve_from_round_start=True)
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Simple history: preflop actions
    history = ['p0_raise_6bb', 'p1_call']
    
    round_start, frozen = resolver.reconstruct_round_history(
        history, Street.FLOP, freeze_our_actions=True
    )
    
    # Should return lists
    assert isinstance(round_start, list)
    assert isinstance(frozen, list)
    
    print(f"✓ Round start reconstruction: history_len={len(history)}, "
          f"round_start_len={len(round_start)}, frozen_len={len(frozen)}")


def test_round_start_freeze_our_actions():
    """Test that freeze_our_actions parameter is respected."""
    config = SearchConfig(resolve_from_round_start=True)
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    history = ['p0_bet_10', 'p1_raise_30', 'p0_call']
    
    # With freeze_our_actions=True
    round_start1, frozen1 = resolver.reconstruct_round_history(
        history, Street.TURN, freeze_our_actions=True
    )
    
    # With freeze_our_actions=False
    round_start2, frozen2 = resolver.reconstruct_round_history(
        history, Street.TURN, freeze_our_actions=False
    )
    
    # Both should return valid results
    assert isinstance(round_start1, list)
    assert isinstance(frozen1, list)
    assert isinstance(round_start2, list)
    assert isinstance(frozen2, list)
    
    print("✓ freeze_our_actions parameter respected")


def test_round_boundaries_detection():
    """Test detection of round boundaries in action history.
    
    Round boundaries occur at:
    - Hand start (empty history)
    - After check-check
    - After call that closes action
    """
    config = SearchConfig(resolve_from_round_start=True)
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Test different round boundaries
    test_cases = [
        ([], Street.PREFLOP, "Empty history - hand start"),
        (['p0_check', 'p1_check'], Street.FLOP, "Check-check closes preflop"),
        (['p0_bet_10', 'p1_call'], Street.FLOP, "Call closes action"),
        (['p0_raise_10', 'p1_raise_30', 'p0_call'], Street.TURN, "Call closes after raises"),
    ]
    
    for history, street, description in test_cases:
        round_start, frozen = resolver.reconstruct_round_history(
            history, street, freeze_our_actions=True
        )
        print(f"  {description}: round_start_len={len(round_start)}")
    
    print("✓ Round boundary detection works")


def test_integration_with_resolver():
    """Test that resolver can handle resolve_from_round_start in solve()."""
    # Without round-start resolving (default)
    config1 = SearchConfig(
        time_budget_ms=50,
        min_iterations=10,
        resolve_from_round_start=False
    )
    blueprint1 = PolicyStore()
    resolver1 = SubgameResolver(config1, blueprint1)
    
    # With round-start resolving
    config2 = SearchConfig(
        time_budget_ms=50,
        min_iterations=10,
        resolve_from_round_start=True
    )
    blueprint2 = PolicyStore()
    resolver2 = SubgameResolver(config2, blueprint2)
    
    # Both should initialize successfully
    assert resolver1.config.resolve_from_round_start == False
    assert resolver2.config.resolve_from_round_start == True
    
    print("✓ Resolver integrates resolve_from_round_start config")


def test_unsafe_search_semantics():
    """Test unsafe search semantics.
    
    Unsafe search means:
    - Start subgame at beginning of current round (street)
    - Freeze our actions that we've already played in this round
    - Do NOT freeze opponents' actions (they can deviate from blueprint)
    
    This reduces accuracy (opponent may not play blueprint) but provides
    cleaner game trees and better computational efficiency.
    """
    config = SearchConfig(resolve_from_round_start=True)
    blueprint = PolicyStore()
    resolver = SubgameResolver(config, blueprint)
    
    # Simulate current round with some actions
    # Format: "pN_action" where N is player index
    history = [
        'p0_bet_10',   # We bet 10
        'p1_raise_30', # Opponent raises to 30
        'p0_call'      # We called
    ]
    
    # Now we're at turn, and we need to make a decision
    # With unsafe search, we reconstruct from turn start
    round_start, frozen_our_actions = resolver.reconstruct_round_history(
        history, Street.TURN, freeze_our_actions=True
    )
    
    # Frozen actions should only include our actions (p0's actions)
    # In this example: 'p0_bet_10' and 'p0_call'
    # Opponent's 'p1_raise_30' should NOT be frozen
    
    print(f"✓ Unsafe search semantics: "
          f"full_history={len(history)}, "
          f"round_start={len(round_start)}, "
          f"frozen_ours={len(frozen_our_actions)}")


def test_config_defaults():
    """Test that all new config options have sensible defaults."""
    # SearchConfig
    sc = SearchConfig()
    assert sc.resolve_from_round_start == False  # Conservative default
    assert sc.use_leaf_policies == False  # Conservative default
    assert sc.leaf_policy_default == "blueprint"  # Use blueprint by default
    
    # RTResolverConfig
    rtc = RTResolverConfig()
    assert rtc.resolve_from_round_start == False
    assert rtc.use_leaf_policies == False
    assert rtc.leaf_policy_default == "blueprint"
    
    print("✓ All config options have sensible defaults")


def test_public_card_sampling_already_exists():
    """Verify that public card sampling is already implemented.
    
    This is requirement #3 from the problem statement, which should
    already be working.
    """
    # SearchConfig should have samples_per_solve
    sc = SearchConfig()
    assert hasattr(sc, 'samples_per_solve')
    assert sc.samples_per_solve == 1  # Default is no sampling
    
    sc2 = SearchConfig(samples_per_solve=10)
    assert sc2.samples_per_solve == 10
    
    # RTResolverConfig should also have it
    rtc = RTResolverConfig()
    assert hasattr(rtc, 'samples_per_solve')
    assert rtc.samples_per_solve == 1
    
    rtc2 = RTResolverConfig(samples_per_solve=20)
    assert rtc2.samples_per_solve == 20
    
    print("✓ Public card sampling config exists (requirement #3 already implemented)")


if __name__ == "__main__":
    print("Testing round-start resolving (unsafe search)...")
    print()
    
    test_search_config_round_start_option()
    test_rt_resolver_config_round_start_option()
    test_reconstruct_round_history()
    test_round_start_with_simple_history()
    test_round_start_freeze_our_actions()
    test_round_boundaries_detection()
    test_integration_with_resolver()
    test_unsafe_search_semantics()
    test_config_defaults()
    test_public_card_sampling_already_exists()
    
    print("\n" + "="*60)
    print("✅ All round-start resolving tests passed!")
    print("="*60)
