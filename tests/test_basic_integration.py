"""Simple integration test for new features (no dependencies required)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def test_imports():
    """Test that all new modules can be imported."""
    
    try:
        from holdem.types import RTResolverConfig
        print("✓ RTResolverConfig import works")
    except Exception as e:
        print(f"✗ RTResolverConfig import failed: {e}")
        return False
    
    try:
        from holdem.abstraction.action_translator import ActionTranslator, ActionSetMode, LegalConstraints
        print("✓ ActionTranslator imports work")
    except Exception as e:
        print(f"✗ ActionTranslator import failed: {e}")
        return False
    
    try:
        from holdem.rt_resolver.subgame_builder import SubgameBuilder, SubgameState
        print("✓ SubgameBuilder imports work")
    except Exception as e:
        print(f"✗ SubgameBuilder import failed: {e}")
        return False
    
    try:
        from holdem.rt_resolver.leaf_evaluator import LeafEvaluator
        print("✓ LeafEvaluator import works")
    except Exception as e:
        print(f"✗ LeafEvaluator import failed: {e}")
        return False
    
    try:
        from holdem.rt_resolver.depth_limited_cfr import DepthLimitedCFR
        print("✓ DepthLimitedCFR import works")
    except Exception as e:
        print(f"✗ DepthLimitedCFR import failed: {e}")
        return False
    
    return True


def test_config_integration():
    """Test that Config includes RTResolverConfig."""
    try:
        from holdem.config import Config, DEFAULT_RT_RESOLVER_CONFIG
        
        config = Config()
        assert hasattr(config, 'rt')
        assert config.rt is not None
        
        # Check default config
        assert DEFAULT_RT_RESOLVER_CONFIG is not None
        
        print("✓ Config integration works")
        return True
    except Exception as e:
        print(f"✗ Config integration failed: {e}")
        return False


def test_action_translator_basic():
    """Basic test of ActionTranslator without numpy."""
    try:
        from holdem.types import Action, ActionType, Street
        from holdem.abstraction.action_translator import ActionTranslator, ActionSetMode, LegalConstraints
        
        translator = ActionTranslator(mode=ActionSetMode.BALANCED)
        
        # Test fold
        action = translator.to_client(
            action_id=0,
            pot=100.0,
            stack=200.0,
            constraints=LegalConstraints(min_raise=2.0, max_bet=200.0, min_chip=0.01),
            street=Street.FLOP
        )
        assert action.action_type == ActionType.FOLD
        
        # Test check
        action = translator.to_client(
            action_id=1,
            pot=100.0,
            stack=200.0,
            constraints=LegalConstraints(min_raise=2.0, max_bet=200.0, min_chip=0.01),
            street=Street.FLOP,
            current_bet=0.0,
            player_bet=0.0
        )
        assert action.action_type == ActionType.CHECK
        
        print("✓ ActionTranslator basic tests work")
        return True
    except Exception as e:
        print(f"✗ ActionTranslator basic tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rt_resolver_config():
    """Test RTResolverConfig."""
    try:
        from holdem.types import RTResolverConfig
        
        config = RTResolverConfig(
            max_depth=2,
            time_ms=100,
            min_iterations=500,
            max_iterations=1500,
            samples_per_leaf=15,
            action_set_mode="tight",
            kl_weight=0.6
        )
        
        assert config.max_depth == 2
        assert config.time_ms == 100
        assert config.min_iterations == 500
        assert config.max_iterations == 1500
        assert config.samples_per_leaf == 15
        assert config.action_set_mode == "tight"
        assert config.kl_weight == 0.6
        
        print("✓ RTResolverConfig works")
        return True
    except Exception as e:
        print(f"✗ RTResolverConfig failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing new features (basic integration)...")
    print()
    
    all_passed = True
    
    if not test_imports():
        all_passed = False
    print()
    
    if not test_config_integration():
        all_passed = False
    print()
    
    if not test_action_translator_basic():
        all_passed = False
    print()
    
    if not test_rt_resolver_config():
        all_passed = False
    print()
    
    if all_passed:
        print("All basic integration tests passed! ✓")
        print()
        print("Note: Full tests require numpy, scikit-learn, and other dependencies.")
        print("To run full tests:")
        print("  pip install -e .")
        print("  python tests/test_action_translator.py")
        print("  python tests/test_external_sampling.py")
        print("  python tests/test_rt_resolver.py")
    else:
        print("Some tests failed! ✗")
        sys.exit(1)
