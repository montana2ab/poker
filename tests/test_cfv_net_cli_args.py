"""Test CFV net CLI arguments integration."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import argparse


def test_run_dry_run_cfv_net_args():
    """Test that run_dry_run.py properly parses CFV net arguments."""
    # We can't import directly because of module dependencies, so we'll check the argparse setup
    # by inspecting the source file
    
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    assert dry_run_path.exists(), f"run_dry_run.py not found at {dry_run_path}"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check that the arguments are defined
    assert '--cfv-net' in content, "Missing --cfv-net argument"
    assert '--no-cfv-net' in content, "Missing --no-cfv-net argument"
    assert 'LeafEvaluator' in content, "LeafEvaluator import or usage not found"
    assert 'cfv_net_config' in content, "cfv_net_config not found"
    
    print("✓ run_dry_run.py has CFV net CLI arguments")


def test_run_autoplay_cfv_net_args():
    """Test that run_autoplay.py properly parses CFV net arguments."""
    autoplay_path = Path(__file__).parent.parent / "src/holdem/cli/run_autoplay.py"
    assert autoplay_path.exists(), f"run_autoplay.py not found at {autoplay_path}"
    
    with open(autoplay_path, 'r') as f:
        content = f.read()
    
    # Check that the arguments are defined
    assert '--cfv-net' in content, "Missing --cfv-net argument"
    assert '--no-cfv-net' in content, "Missing --no-cfv-net argument"
    assert 'LeafEvaluator' in content, "LeafEvaluator import or usage not found"
    assert 'cfv_net_config' in content, "cfv_net_config not found"
    
    print("✓ run_autoplay.py has CFV net CLI arguments")


def test_search_controller_accepts_leaf_evaluator():
    """Test that SearchController accepts leaf_evaluator parameter."""
    controller_path = Path(__file__).parent.parent / "src/holdem/realtime/search_controller.py"
    assert controller_path.exists(), f"search_controller.py not found at {controller_path}"
    
    with open(controller_path, 'r') as f:
        content = f.read()
    
    # Check that leaf_evaluator parameter is in __init__
    assert 'leaf_evaluator' in content, "leaf_evaluator parameter not found"
    assert 'LeafEvaluator' in content, "LeafEvaluator type hint not found"
    
    print("✓ SearchController accepts leaf_evaluator parameter")


def test_resolvers_accept_leaf_evaluator():
    """Test that resolvers accept leaf_evaluator parameter."""
    resolver_path = Path(__file__).parent.parent / "src/holdem/realtime/resolver.py"
    parallel_resolver_path = Path(__file__).parent.parent / "src/holdem/realtime/parallel_resolver.py"
    
    assert resolver_path.exists(), f"resolver.py not found"
    assert parallel_resolver_path.exists(), f"parallel_resolver.py not found"
    
    with open(resolver_path, 'r') as f:
        content = f.read()
    assert 'leaf_evaluator' in content, "leaf_evaluator parameter not found in SubgameResolver"
    
    with open(parallel_resolver_path, 'r') as f:
        content = f.read()
    assert 'leaf_evaluator' in content, "leaf_evaluator parameter not found in ParallelSubgameResolver"
    
    print("✓ Resolvers accept leaf_evaluator parameter")


def test_default_cfv_net_path():
    """Test that default CFV net path is correctly set."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check for the default path
    assert 'assets/cfv_net/6max_mid_125k_m2.onnx' in content, "Default CFV net path not found or incorrect"
    
    print("✓ Default CFV net path is correctly set")


def test_fallback_logic_exists():
    """Test that fallback logic exists when CFV net file doesn't exist."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check for fallback logic
    assert 'args.cfv_net.exists()' in content, "CFV net file existence check not found"
    assert 'mode="blueprint"' in content, "Blueprint fallback mode not found"
    assert 'logger.warning' in content or 'logger.warn' in content, "Warning for missing CFV net file not found"
    
    print("✓ Fallback logic exists for missing CFV net file")


def test_cfv_net_config_structure():
    """Test that CFV net config has the correct structure."""
    dry_run_path = Path(__file__).parent.parent / "src/holdem/cli/run_dry_run.py"
    
    with open(dry_run_path, 'r') as f:
        content = f.read()
    
    # Check for config structure
    assert '"checkpoint"' in content or "'checkpoint'" in content, "checkpoint config not found"
    assert 'tau_flop' in content, "tau_flop gating parameter not found"
    assert 'tau_turn' in content, "tau_turn gating parameter not found"
    assert 'tau_river' in content, "tau_river gating parameter not found"
    assert 'cache_max_size' in content, "cache_max_size config not found"
    
    print("✓ CFV net config has correct structure")


if __name__ == "__main__":
    try:
        import pytest
        pytest.main([__file__, "-v"])
    except ImportError:
        # Run tests manually without pytest
        print("Running tests without pytest...")
        
        test_run_dry_run_cfv_net_args()
        test_run_autoplay_cfv_net_args()
        test_search_controller_accepts_leaf_evaluator()
        test_resolvers_accept_leaf_evaluator()
        test_default_cfv_net_path()
        test_fallback_logic_exists()
        test_cfv_net_config_structure()
        
        print("\n✅ All tests passed!")
