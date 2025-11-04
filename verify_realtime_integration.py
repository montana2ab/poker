"""Verification script for real-time search integration.

This script validates that the real-time re-solving has been properly integrated
into the poker AI system without requiring heavy dependencies like eval7, torch, etc.
"""

import sys
import os
import ast

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def check_file_contains(filepath, patterns, description):
    """Check if a file contains all the specified patterns."""
    print(f"\nChecking {description}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    all_found = True
    for pattern in patterns:
        if pattern in content:
            print(f"  ✓ Found: '{pattern[:60]}...'")
        else:
            print(f"  ✗ Missing: '{pattern}'")
            all_found = False
    
    return all_found


def check_method_exists(module_path, class_name, method_names):
    """Check if a class has the required methods by parsing the AST."""
    print(f"\nChecking {class_name} methods...")
    
    with open(module_path, 'r') as f:
        tree = ast.parse(f.read())
    
    # Find the class
    class_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_node = node
            break
    
    if not class_node:
        print(f"  ✗ Class {class_name} not found")
        return False
    
    # Find methods
    methods_found = []
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef):
            methods_found.append(item.name)
    
    all_found = True
    for method_name in method_names:
        if method_name in methods_found:
            print(f"  ✓ Method '{method_name}' exists")
        else:
            print(f"  ✗ Method '{method_name}' missing")
            all_found = False
    
    return all_found


def main():
    print("=" * 70)
    print("REAL-TIME RE-SOLVING INTEGRATION VERIFICATION")
    print("=" * 70)
    
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    
    # Test 1: Check run_dry_run.py integration
    print("\n" + "=" * 70)
    print("TEST 1: Dry-Run Mode Integration")
    print("=" * 70)
    
    dry_run_path = os.path.join(repo_root, 'src/holdem/cli/run_dry_run.py')
    dry_run_patterns = [
        'from holdem.realtime.search_controller import SearchController',
        'search_controller = SearchController(search_config, bucketing, policy)',
        'action_history = []',
        'last_street = None',
        'if last_street != state.street:',
        'action_history = []',
        'search_controller.get_action(',
        'state=state,',
        'our_cards=hero_cards,',
        'history=action_history',
        '[REAL-TIME SEARCH]',
    ]
    
    dry_run_ok = check_file_contains(dry_run_path, dry_run_patterns, 
                                      "run_dry_run.py for real-time search integration")
    
    # Test 2: Check run_autoplay.py integration
    print("\n" + "=" * 70)
    print("TEST 2: Auto-Play Mode Integration")
    print("=" * 70)
    
    autoplay_path = os.path.join(repo_root, 'src/holdem/cli/run_autoplay.py')
    autoplay_patterns = [
        'from holdem.realtime.search_controller import SearchController',
        'search_controller = SearchController(search_config, bucketing, policy)',
        'action_history = []',
        'last_street = None',
        'if last_street != state.street:',
        'search_controller.get_action(',
        'executor.execute(suggested_action, state)',
        '[REAL-TIME SEARCH]',
    ]
    
    autoplay_ok = check_file_contains(autoplay_path, autoplay_patterns,
                                       "run_autoplay.py for real-time search integration")
    
    # Test 3: Check SafetyChecker has check_safe_to_act
    print("\n" + "=" * 70)
    print("TEST 3: SafetyChecker Enhancement")
    print("=" * 70)
    
    safety_path = os.path.join(repo_root, 'src/holdem/control/safety.py')
    safety_ok = check_method_exists(safety_path, 'SafetyChecker', 
                                     ['check_safe_to_act', 'check_action'])
    
    # Test 4: Check ActionExecutor has execute method
    print("\n" + "=" * 70)
    print("TEST 4: ActionExecutor Enhancement")
    print("=" * 70)
    
    executor_path = os.path.join(repo_root, 'src/holdem/control/executor.py')
    executor_ok = check_method_exists(executor_path, 'ActionExecutor',
                                       ['execute', 'execute_action'])
    
    # Test 5: Check SearchController structure
    print("\n" + "=" * 70)
    print("TEST 5: SearchController API")
    print("=" * 70)
    
    search_controller_path = os.path.join(repo_root, 'src/holdem/realtime/search_controller.py')
    search_ok = check_method_exists(search_controller_path, 'SearchController',
                                     ['get_action', 'update_belief'])
    
    # Test 6: Verify imports work (basic ones)
    print("\n" + "=" * 70)
    print("TEST 6: Basic Module Imports")
    print("=" * 70)
    
    imports_ok = True
    try:
        from holdem.types import SearchConfig, Street, Card
        print("  ✓ holdem.types imports successfully")
        
        # Test SearchConfig has the right fields
        config = SearchConfig()
        assert hasattr(config, 'time_budget_ms')
        assert hasattr(config, 'min_iterations')
        assert hasattr(config, 'fallback_to_blueprint')
        print("  ✓ SearchConfig has required fields")
        
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        imports_ok = False
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_tests = [
        ("Dry-Run Integration", dry_run_ok),
        ("Auto-Play Integration", autoplay_ok),
        ("SafetyChecker Enhancement", safety_ok),
        ("ActionExecutor Enhancement", executor_ok),
        ("SearchController API", search_ok),
        ("Basic Imports", imports_ok),
    ]
    
    passed = sum(1 for _, ok in all_tests if ok)
    total = len(all_tests)
    
    for name, ok in all_tests:
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED - Real-time re-solving successfully integrated!")
        print("=" * 70)
        return 0
    else:
        print("\n" + "=" * 70)
        print("✗ SOME TESTS FAILED - Please review the output above")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
