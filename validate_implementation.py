#!/usr/bin/env python3
"""Simple validation script to verify the evaluation tool structure.

This script performs basic validation without requiring numpy or running
full simulations. It checks:
1. Module imports work
2. Data structures are valid
3. Configuration is correct
4. File structure is correct

Run with: python validate_implementation.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_imports():
    """Test that all necessary modules can be imported."""
    print("Testing imports...")
    
    try:
        from holdem.types import SearchConfig, Card, Street, TableState
        print("  ✅ holdem.types imports successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import holdem.types: {e}")
        return False
    
    try:
        from holdem.mccfr.policy_store import PolicyStore
        print("  ✅ PolicyStore imports successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import PolicyStore: {e}")
        return False
    
    try:
        from holdem.realtime.resolver import SubgameResolver
        print("  ✅ SubgameResolver imports successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import SubgameResolver: {e}")
        return False
    
    try:
        from holdem.realtime.subgame import SubgameTree
        print("  ✅ SubgameTree imports successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import SubgameTree: {e}")
        return False
    
    try:
        from holdem.rl_eval.statistics import compute_confidence_interval
        print("  ✅ statistics module imports successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import statistics: {e}")
        return False
    
    return True


def test_search_config():
    """Test SearchConfig with samples_per_solve."""
    print("\nTesting SearchConfig...")
    
    try:
        from holdem.types import SearchConfig
        
        # Test default config
        config = SearchConfig()
        assert hasattr(config, 'samples_per_solve'), "samples_per_solve not in SearchConfig"
        assert config.samples_per_solve == 1, f"Default samples_per_solve should be 1, got {config.samples_per_solve}"
        print(f"  ✅ Default samples_per_solve = {config.samples_per_solve}")
        
        # Test with 16 samples
        config16 = SearchConfig(samples_per_solve=16)
        assert config16.samples_per_solve == 16
        print(f"  ✅ Can set samples_per_solve = 16")
        
        # Test with 32 samples
        config32 = SearchConfig(samples_per_solve=32)
        assert config32.samples_per_solve == 32
        print(f"  ✅ Can set samples_per_solve = 32")
        
        # Test with 64 samples
        config64 = SearchConfig(samples_per_solve=64)
        assert config64.samples_per_solve == 64
        print(f"  ✅ Can set samples_per_solve = 64")
        
        return True
    except Exception as e:
        print(f"  ❌ SearchConfig test failed: {e}")
        return False


def test_file_structure():
    """Test that all required files exist."""
    print("\nTesting file structure...")
    
    files = [
        'tools/eval_rt_vs_blueprint.py',
        'tests/test_eval_rt_vs_blueprint.py',
        'tests/test_public_card_sampling_extended.py',
        'docs/RT_VS_BLUEPRINT_EVALUATION.md',
        'docs/RT_VS_BLUEPRINT_EVALUATION_FR.md',
    ]
    
    all_exist = True
    for file_path in files:
        path = Path(__file__).parent / file_path
        if path.exists():
            print(f"  ✅ {file_path} exists")
        else:
            print(f"  ❌ {file_path} not found")
            all_exist = False
    
    return all_exist


def test_eval_tool_structure():
    """Test that the evaluation tool has the right structure."""
    print("\nTesting evaluation tool structure...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent / 'tools'))
        import eval_rt_vs_blueprint as eval_module
        
        # Check classes exist
        assert hasattr(eval_module, 'SimplifiedPokerSim'), "SimplifiedPokerSim class not found"
        print("  ✅ SimplifiedPokerSim class exists")
        
        assert hasattr(eval_module, 'HandResult'), "HandResult class not found"
        print("  ✅ HandResult class exists")
        
        assert hasattr(eval_module, 'EvaluationResult'), "EvaluationResult class not found"
        print("  ✅ EvaluationResult class exists")
        
        # Check functions exist
        assert hasattr(eval_module, 'run_evaluation'), "run_evaluation function not found"
        print("  ✅ run_evaluation function exists")
        
        assert hasattr(eval_module, 'print_results'), "print_results function not found"
        print("  ✅ print_results function exists")
        
        assert hasattr(eval_module, 'main'), "main function not found"
        print("  ✅ main function exists")
        
        return True
    except Exception as e:
        print(f"  ❌ Evaluation tool test failed: {e}")
        return False


def test_bootstrap_ci_available():
    """Test that bootstrap CI function is available."""
    print("\nTesting bootstrap CI availability...")
    
    try:
        from holdem.rl_eval.statistics import compute_confidence_interval
        
        # Test function signature
        import inspect
        sig = inspect.signature(compute_confidence_interval)
        params = list(sig.parameters.keys())
        
        required_params = ['results', 'confidence', 'method', 'n_bootstrap']
        for param in required_params:
            if param in params:
                print(f"  ✅ Parameter '{param}' exists")
            else:
                print(f"  ⚠️  Parameter '{param}' not found (might use defaults)")
        
        return True
    except Exception as e:
        print(f"  ❌ Bootstrap CI test failed: {e}")
        return False


def main():
    """Run all validation tests."""
    print("="*70)
    print("VALIDATION: RT Search vs Blueprint Evaluation Implementation")
    print("="*70)
    
    results = {
        'imports': test_imports(),
        'search_config': test_search_config(),
        'file_structure': test_file_structure(),
        'eval_tool': test_eval_tool_structure(),
        'bootstrap_ci': test_bootstrap_ci_available(),
    }
    
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL VALIDATION TESTS PASSED")
        print("\nThe implementation is ready. To run full tests, install dependencies:")
        print("  pip install -r requirements.txt")
        print("  pytest tests/test_eval_rt_vs_blueprint.py -v")
        print("  pytest tests/test_public_card_sampling_extended.py -v -s")
    else:
        print("❌ SOME VALIDATION TESTS FAILED")
        print("\nPlease fix the issues before running full tests.")
    print("="*70)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
