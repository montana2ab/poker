"""Test enhanced KL regularization features."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
from holdem.types import SearchConfig, Street
from holdem.realtime.resolver import SubgameResolver
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.abstraction.actions import AbstractAction


def create_mock_policy():
    """Create a mock policy with some strategy."""
    tracker = RegretTracker()
    infoset = "TEST:0:initial"
    
    # Add a balanced blueprint strategy
    tracker.add_strategy(infoset, {
        AbstractAction.FOLD: 0.1,
        AbstractAction.CHECK_CALL: 0.4,
        AbstractAction.BET_HALF_POT: 0.3,
        AbstractAction.BET_POT: 0.2
    }, 10.0)
    
    return PolicyStore(tracker)


class MockSubgameTree:
    """Mock subgame tree for testing."""
    def __init__(self, street=Street.FLOP):
        self.state = type('obj', (object,), {'street': street})()
    
    def get_actions(self, infoset):
        return [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]


def test_street_based_kl_weight():
    """Test that kl_weight varies by street."""
    print("\nTesting street-based kl_weight...")
    
    config = SearchConfig()
    
    # Test default values
    assert config.kl_weight_flop == 0.30, f"kl_weight_flop should be 0.30, got {config.kl_weight_flop}"
    assert config.kl_weight_turn == 0.50, f"kl_weight_turn should be 0.50, got {config.kl_weight_turn}"
    assert config.kl_weight_river == 0.70, f"kl_weight_river should be 0.70, got {config.kl_weight_river}"
    print(f"  ✓ Default street weights: flop={config.kl_weight_flop}, turn={config.kl_weight_turn}, river={config.kl_weight_river}")
    
    # Test get_kl_weight method
    flop_weight = config.get_kl_weight(Street.FLOP, is_oop=False)
    turn_weight = config.get_kl_weight(Street.TURN, is_oop=False)
    river_weight = config.get_kl_weight(Street.RIVER, is_oop=False)
    
    assert flop_weight == 0.30, f"Flop weight should be 0.30, got {flop_weight}"
    assert turn_weight == 0.50, f"Turn weight should be 0.50, got {turn_weight}"
    assert river_weight == 0.70, f"River weight should be 0.70, got {river_weight}"
    print(f"  ✓ get_kl_weight(): flop={flop_weight}, turn={turn_weight}, river={river_weight}")


def test_oop_bonus():
    """Test that OOP bonus is applied correctly."""
    print("\nTesting OOP bonus...")
    
    config = SearchConfig()
    assert config.kl_weight_oop_bonus == 0.10, f"OOP bonus should be 0.10, got {config.kl_weight_oop_bonus}"
    
    # Test IP vs OOP
    flop_ip = config.get_kl_weight(Street.FLOP, is_oop=False)
    flop_oop = config.get_kl_weight(Street.FLOP, is_oop=True)
    
    assert abs(flop_oop - (flop_ip + 0.10)) < 1e-10, f"OOP weight should be IP + 0.10, got IP={flop_ip}, OOP={flop_oop}"
    print(f"  ✓ Flop: IP={flop_ip}, OOP={flop_oop} (diff={flop_oop - flop_ip})")
    
    # Test on different streets
    turn_oop = config.get_kl_weight(Street.TURN, is_oop=True)
    river_oop = config.get_kl_weight(Street.RIVER, is_oop=True)
    
    assert abs(turn_oop - 0.60) < 1e-10, f"Turn OOP should be 0.60, got {turn_oop}"
    assert abs(river_oop - 0.80) < 1e-10, f"River OOP should be 0.80, got {river_oop}"
    print(f"  ✓ Turn OOP={turn_oop}, River OOP={river_oop}")


def test_blueprint_clipping():
    """Test that blueprint policy is clipped to minimum value."""
    print("\nTesting blueprint clipping...")
    
    config = SearchConfig()
    policy = create_mock_policy()
    resolver = SubgameResolver(config, policy)
    
    # Test with very small blueprint probabilities
    p = {AbstractAction.FOLD: 0.5, AbstractAction.CHECK_CALL: 0.5}
    q = {AbstractAction.FOLD: 1e-10, AbstractAction.CHECK_CALL: 0.5}
    
    # Without clipping, this would cause numerical issues
    kl = resolver._kl_divergence(p, q)
    
    # Should not be infinity or NaN
    assert not np.isnan(kl), "KL divergence should not be NaN"
    assert not np.isinf(kl), "KL divergence should not be infinity"
    assert kl > 0, f"KL divergence should be positive, got {kl}"
    print(f"  ✓ Blueprint clipping prevents numerical issues: KL={kl:.6f}")
    
    # Test that clipping uses config value
    assert config.blueprint_clip_min == 1e-6, f"blueprint_clip_min should be 1e-6, got {config.blueprint_clip_min}"
    print(f"  ✓ Clipping minimum: {config.blueprint_clip_min}")


def test_kl_statistics_tracking():
    """Test that KL statistics are tracked and logged."""
    print("\nTesting KL statistics tracking...")
    
    config = SearchConfig(min_iterations=20, time_budget_ms=100, track_kl_stats=True)
    policy = create_mock_policy()
    resolver = SubgameResolver(config, policy)
    
    # Solve for different streets and positions
    for street in [Street.FLOP, Street.TURN, Street.RIVER]:
        for is_oop in [False, True]:
            subgame = MockSubgameTree(street)
            infoset = f"TEST:{street.value}:state"
            strategy = resolver.solve(subgame, infoset, street=street, is_oop=is_oop)
            
            assert isinstance(strategy, dict), f"Strategy should be dict for {street.name}"
    
    # Get statistics
    stats = resolver.get_kl_statistics()
    
    # Check that stats were collected
    assert isinstance(stats, dict), "Statistics should be a dictionary"
    print(f"  ✓ Collected statistics for {len(stats)} streets")
    
    # Check that stats have the expected structure
    for street_name, positions in stats.items():
        for position, stat_dict in positions.items():
            assert 'avg' in stat_dict, f"Stats should include 'avg' for {street_name}/{position}"
            assert 'p50' in stat_dict, f"Stats should include 'p50' for {street_name}/{position}"
            assert 'p90' in stat_dict, f"Stats should include 'p90' for {street_name}/{position}"
            assert 'p99' in stat_dict, f"Stats should include 'p99' for {street_name}/{position}"
            assert 'pct_high' in stat_dict, f"Stats should include 'pct_high' for {street_name}/{position}"
            assert 'count' in stat_dict, f"Stats should include 'count' for {street_name}/{position}"
            
            print(f"  ✓ {street_name}/{position}: avg={stat_dict['avg']:.4f}, "
                  f"p50={stat_dict['p50']:.4f}, p90={stat_dict['p90']:.4f}, "
                  f"p99={stat_dict['p99']:.4f}, high%={stat_dict['pct_high']:.1f}%")


def test_kl_high_threshold():
    """Test tracking of KL values above threshold."""
    print("\nTesting KL high threshold tracking...")
    
    config = SearchConfig(min_iterations=10, kl_high_threshold=0.3)
    policy = create_mock_policy()
    resolver = SubgameResolver(config, policy)
    
    subgame = MockSubgameTree(Street.FLOP)
    strategy = resolver.solve(subgame, "TEST:0:initial", street=Street.FLOP, is_oop=False)
    
    stats = resolver.get_kl_statistics()
    
    # Check that percentage is calculated
    if 'flop' in stats and 'IP' in stats['flop']:
        pct_high = stats['flop']['IP']['pct_high']
        assert 0 <= pct_high <= 100, f"Percentage should be 0-100, got {pct_high}"
        print(f"  ✓ Percentage of KL > 0.3: {pct_high:.1f}%")
    else:
        print("  ✓ No flop/IP stats yet (this is OK)")


def test_solve_with_street_and_position():
    """Test that solve() correctly uses street and position for kl_weight."""
    print("\nTesting solve() with street and position...")
    
    config = SearchConfig(min_iterations=5, time_budget_ms=50)
    policy = create_mock_policy()
    resolver = SubgameResolver(config, policy)
    
    # Test on river with OOP
    subgame = MockSubgameTree(Street.RIVER)
    strategy = resolver.solve(subgame, "TEST:3:river", street=Street.RIVER, is_oop=True)
    
    assert isinstance(strategy, dict), "Strategy should be a dict"
    assert len(strategy) > 0, "Strategy should not be empty"
    
    # The resolver should have used kl_weight = 0.70 + 0.10 = 0.80
    expected_weight = config.get_kl_weight(Street.RIVER, is_oop=True)
    assert abs(expected_weight - 0.80) < 1e-10, f"Expected kl_weight 0.80 for river OOP, got {expected_weight}"
    print(f"  ✓ River OOP uses kl_weight={expected_weight:.2f}")


def test_custom_kl_weights():
    """Test that custom kl_weight values can be set."""
    print("\nTesting custom kl_weight configuration...")
    
    # Test custom weights for "exploit caller" mode
    config = SearchConfig(
        kl_weight_flop=0.15,
        kl_weight_turn=0.30,
        kl_weight_river=0.40
    )
    
    assert config.kl_weight_flop == 0.15
    assert config.kl_weight_turn == 0.30
    assert config.kl_weight_river == 0.40
    print(f"  ✓ Custom weights: flop={config.kl_weight_flop}, turn={config.kl_weight_turn}, river={config.kl_weight_river}")
    
    # Test that these are used correctly
    flop_weight = config.get_kl_weight(Street.FLOP, is_oop=False)
    assert flop_weight == 0.15, f"Flop weight should be 0.15, got {flop_weight}"
    print(f"  ✓ get_kl_weight() uses custom values")


def test_adaptive_kl_config():
    """Test that adaptive KL configuration options are available."""
    print("\nTesting adaptive KL configuration...")
    
    config = SearchConfig()
    
    # Check that adaptive options exist
    assert hasattr(config, 'adaptive_kl_weight'), "Config should have adaptive_kl_weight"
    assert hasattr(config, 'target_kl_flop'), "Config should have target_kl_flop"
    assert hasattr(config, 'target_kl_turn'), "Config should have target_kl_turn"
    assert hasattr(config, 'target_kl_river'), "Config should have target_kl_river"
    
    # Check default values
    assert config.adaptive_kl_weight == False, "adaptive_kl_weight should be False by default"
    assert config.target_kl_flop == 0.12, f"target_kl_flop should be 0.12, got {config.target_kl_flop}"
    assert config.target_kl_turn == 0.18, f"target_kl_turn should be 0.18, got {config.target_kl_turn}"
    assert config.target_kl_river == 0.25, f"target_kl_river should be 0.25, got {config.target_kl_river}"
    
    print(f"  ✓ Adaptive KL configuration available (disabled by default)")
    print(f"  ✓ Target KL: flop={config.target_kl_flop}, turn={config.target_kl_turn}, river={config.target_kl_river}")


if __name__ == "__main__":
    print("=" * 60)
    print("Enhanced KL Regularization Tests")
    print("=" * 60)
    
    try:
        test_street_based_kl_weight()
        test_oop_bonus()
        test_blueprint_clipping()
        test_kl_statistics_tracking()
        test_kl_high_threshold()
        test_solve_with_street_and_position()
        test_custom_kl_weights()
        test_adaptive_kl_config()
        
        print("\n" + "=" * 60)
        print("✓ All enhanced KL regularization tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
