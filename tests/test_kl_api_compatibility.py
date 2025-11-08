"""Quick integration test for KL regularization API compatibility."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np
from holdem.types import SearchConfig, Street
from holdem.realtime.resolver import SubgameResolver
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.abstraction.actions import AbstractAction


def test_backward_compatibility():
    """Test that existing API still works."""
    print("\nTesting backward compatibility...")
    
    # Create a simple policy
    tracker = RegretTracker()
    infoset = "TEST:0:initial"
    tracker.add_strategy(infoset, {
        AbstractAction.FOLD: 0.1,
        AbstractAction.CHECK_CALL: 0.4,
        AbstractAction.BET_POT: 0.5
    }, 10.0)
    policy = PolicyStore(tracker)
    
    # Test 1: Old API without street/position parameters still works
    config = SearchConfig(min_iterations=5, time_budget_ms=50)
    resolver = SubgameResolver(config, policy)
    
    class MockSubgame:
        def __init__(self):
            self.state = type('obj', (object,), {'street': Street.FLOP})()
        def get_actions(self, infoset):
            return [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_POT]
    
    subgame = MockSubgame()
    
    # This should work (street defaults to subgame.state.street if available)
    strategy = resolver.solve(subgame, infoset)
    assert isinstance(strategy, dict)
    assert len(strategy) > 0
    print("  ✓ Old API without street/position works")
    
    # Test 2: New API with street/position parameters
    strategy = resolver.solve(subgame, infoset, street=Street.RIVER, is_oop=True)
    assert isinstance(strategy, dict)
    assert len(strategy) > 0
    print("  ✓ New API with street/position works")
    
    # Test 3: Config with old kl_weight parameter still works
    config = SearchConfig(kl_weight=0.5)
    resolver = SubgameResolver(config, policy)
    assert config.kl_weight == 0.5
    assert config.kl_divergence_weight == 0.5  # Backward compatibility alias
    print("  ✓ Old kl_weight parameter still works")
    
    # Test 4: Config with new street-specific parameters
    config = SearchConfig(
        kl_weight_flop=0.30,
        kl_weight_turn=0.50,
        kl_weight_river=0.70
    )
    assert config.kl_weight_flop == 0.30
    assert config.kl_weight_turn == 0.50
    assert config.kl_weight_river == 0.70
    print("  ✓ New street-specific parameters work")


def test_integration_with_parallel_resolver():
    """Test that the changes work with ParallelSubgameResolver."""
    print("\nTesting integration with parallel resolver...")
    
    try:
        from holdem.realtime.parallel_resolver import ParallelSubgameResolver
        
        # Create a simple policy
        tracker = RegretTracker()
        infoset = "TEST:0:initial"
        tracker.add_strategy(infoset, {
            AbstractAction.FOLD: 0.1,
            AbstractAction.CHECK_CALL: 0.4,
            AbstractAction.BET_POT: 0.5
        }, 10.0)
        policy = PolicyStore(tracker)
        
        config = SearchConfig(
            min_iterations=5,
            time_budget_ms=50,
            num_workers=1  # Single worker for testing
        )
        
        # This should not crash
        resolver = ParallelSubgameResolver(config, policy)
        print("  ✓ ParallelSubgameResolver can be instantiated with new config")
        
    except ImportError as e:
        print(f"  ⚠ ParallelSubgameResolver not available (missing dependencies): {e}")
    except Exception as e:
        print(f"  ✗ Error with ParallelSubgameResolver: {e}")
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("KL Regularization API Compatibility Tests")
    print("=" * 60)
    
    try:
        test_backward_compatibility()
        test_integration_with_parallel_resolver()
        
        print("\n" + "=" * 60)
        print("✓ All API compatibility tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
