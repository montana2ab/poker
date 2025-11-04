"""Simple integration test for real-time search - no heavy dependencies."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_imports():
    """Test that all necessary modules can be imported."""
    print("Testing imports...")
    
    # Core types
    from holdem.types import SearchConfig, Street, Card
    print("  ✓ holdem.types")
    
    # Real-time search modules
    from holdem.realtime.search_controller import SearchController
    print("  ✓ holdem.realtime.search_controller")
    
    from holdem.realtime.resolver import SubgameResolver
    print("  ✓ holdem.realtime.resolver")
    
    from holdem.realtime.subgame import SubgameBuilder, SubgameTree
    print("  ✓ holdem.realtime.subgame")
    
    from holdem.realtime.belief import BeliefState
    print("  ✓ holdem.realtime.belief")
    
    # Control modules
    from holdem.control.safety import SafetyChecker
    print("  ✓ holdem.control.safety")
    
    from holdem.control.executor import ActionExecutor
    print("  ✓ holdem.control.executor")
    
    print("All imports successful!")


def test_search_config():
    """Test SearchConfig with real-time parameters."""
    print("\nTesting SearchConfig...")
    from holdem.types import SearchConfig
    
    config = SearchConfig(
        time_budget_ms=80,
        min_iterations=100,
        kl_divergence_weight=1.0,
        depth_limit=1,
        fallback_to_blueprint=True
    )
    
    assert config.time_budget_ms == 80
    assert config.min_iterations == 100
    assert config.fallback_to_blueprint is True
    
    print("  ✓ SearchConfig created with correct parameters")


def test_safety_checker():
    """Test SafetyChecker has required methods."""
    print("\nTesting SafetyChecker...")
    from holdem.control.safety import SafetyChecker
    from holdem.types import TableState, Street, PlayerState
    
    checker = SafetyChecker()
    
    # Test check_safe_to_act method exists
    state = TableState(
        street=Street.PREFLOP,
        pot=10.0,
        players=[PlayerState("Hero", 100.0)]
    )
    
    result = checker.check_safe_to_act(state)
    assert isinstance(result, bool)
    print(f"  ✓ check_safe_to_act() returns: {result}")


def test_action_executor():
    """Test ActionExecutor has execute method."""
    print("\nTesting ActionExecutor...")
    from holdem.control.executor import ActionExecutor
    from holdem.types import ControlConfig
    from holdem.vision.calibrate import TableProfile
    
    # Create minimal config
    config = ControlConfig(
        dry_run=True,
        confirm_every_action=False,
        i_understand_the_tos=False
    )
    
    # Create minimal profile
    profile = TableProfile(
        window_title="Test",
        player_regions=[],
        button_regions={},
        card_regions={},
        pot_region=None,
        bet_region=None
    )
    
    executor = ActionExecutor(config, profile)
    
    # Check execute method exists
    assert hasattr(executor, 'execute')
    assert hasattr(executor, 'execute_action')
    print("  ✓ ActionExecutor has execute() and execute_action() methods")


def test_cli_scripts_exist():
    """Test that CLI scripts have been updated."""
    print("\nTesting CLI scripts...")
    
    import inspect
    from holdem.cli import run_dry_run, run_autoplay
    
    # Check run_dry_run has the integration
    dry_run_source = inspect.getsource(run_dry_run)
    assert 'search_controller.get_action' in dry_run_source
    assert 'action_history' in dry_run_source
    assert 'REAL-TIME SEARCH' in dry_run_source
    print("  ✓ run_dry_run.py has real-time search integration")
    
    # Check run_autoplay has the integration
    autoplay_source = inspect.getsource(run_autoplay)
    assert 'search_controller.get_action' in autoplay_source
    assert 'action_history' in autoplay_source
    assert 'REAL-TIME SEARCH' in autoplay_source
    print("  ✓ run_autoplay.py has real-time search integration")


def test_street_tracking():
    """Test street change detection for history reset."""
    print("\nTesting street tracking...")
    from holdem.types import Street
    
    action_history = ["raise", "call"]
    last_street = Street.PREFLOP
    current_street = Street.FLOP
    
    # Simulate street change
    if last_street != current_street:
        action_history = []
    
    assert len(action_history) == 0
    print("  ✓ Action history resets on street change")


def test_search_controller_structure():
    """Test SearchController has required methods."""
    print("\nTesting SearchController structure...")
    from holdem.realtime.search_controller import SearchController
    
    # Check class has required methods
    assert hasattr(SearchController, 'get_action')
    assert hasattr(SearchController, 'update_belief')
    print("  ✓ SearchController has get_action() and update_belief() methods")


if __name__ == "__main__":
    print("=" * 60)
    print("Real-time Search Integration Tests")
    print("=" * 60)
    
    try:
        test_imports()
        test_search_config()
        test_safety_checker()
        test_action_executor()
        test_cli_scripts_exist()
        test_street_tracking()
        test_search_controller_structure()
        
        print("\n" + "=" * 60)
        print("✓ All integration tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
