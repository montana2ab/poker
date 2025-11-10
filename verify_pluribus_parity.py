#!/usr/bin/env python3
"""
Verification script for Pluribus feature parity.

This script systematically checks the implementation status of all Pluribus
features mentioned in the feature parity CSV and updates the documentation
with current evidence.
"""

import os
import sys
from pathlib import Path
import re
from typing import Dict, List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))


def check_file_exists(filepath: str) -> bool:
    """Check if a file exists."""
    return Path(filepath).exists()


def check_function_in_file(filepath: str, function_name: str) -> Tuple[bool, int]:
    """Check if a function exists in a file and return line number."""
    if not check_file_exists(filepath):
        return False, 0
    
    with open(filepath, 'r') as f:
        for i, line in enumerate(f, 1):
            if f'def {function_name}' in line:
                return True, i
    return False, 0


def check_class_in_file(filepath: str, class_name: str) -> Tuple[bool, int]:
    """Check if a class exists in a file and return line number."""
    if not check_file_exists(filepath):
        return False, 0
    
    with open(filepath, 'r') as f:
        for i, line in enumerate(f, 1):
            if f'class {class_name}' in line:
                return True, i
    return False, 0


def check_keyword_in_file(filepath: str, keyword: str, case_insensitive: bool = True) -> Tuple[bool, List[int]]:
    """Check if a keyword exists in a file and return line numbers."""
    if not check_file_exists(filepath):
        return False, []
    
    lines = []
    with open(filepath, 'r') as f:
        for i, line in enumerate(f, 1):
            if case_insensitive:
                if keyword.lower() in line.lower():
                    lines.append(i)
            else:
                if keyword in line:
                    lines.append(i)
    return len(lines) > 0, lines


def verify_vision_ocr_features():
    """Verify Vision/OCR implementation."""
    print("\n=== Vision/OCR Features ===")
    
    checks = [
        ("Table Detection", "src/holdem/vision/detect_table.py", None, None),
        ("Card Recognition", "src/holdem/vision/cards.py", "CardRecognizer", None),
        ("OCR Engine", "src/holdem/vision/ocr.py", None, None),
        ("Region Detection", "src/holdem/vision/calibrate.py", "TableProfile", None),
        ("Parse State", "src/holdem/vision/parse_state.py", None, None),
    ]
    
    for name, filepath, class_name, func_name in checks:
        exists = check_file_exists(filepath)
        print(f"  {name}: {'✓' if exists else '✗'} ({filepath})")
        
        if exists and class_name:
            found, line = check_class_in_file(filepath, class_name)
            print(f"    Class {class_name}: {'✓' if found else '✗'} (line {line})")


def verify_mccfr_features():
    """Verify MCCFR training features."""
    print("\n=== MCCFR Training Features ===")
    
    # Check for key implementations
    checks = [
        ("MCCFR Solver", "src/holdem/mccfr/solver.py", "MCCFRSolver"),
        ("Outcome Sampling", "src/holdem/mccfr/mccfr_os.py", "OutcomeSampler"),
        ("Parallel Solver", "src/holdem/mccfr/parallel_solver.py", "ParallelSolver"),
        ("Adaptive Epsilon", "src/holdem/mccfr/adaptive_epsilon.py", "AdaptiveEpsilonScheduler"),
        ("Policy Store", "src/holdem/mccfr/policy_store.py", "PolicyStore"),
        ("Regret Tracker", "src/holdem/mccfr/regrets.py", "RegretTracker"),
    ]
    
    for name, filepath, class_name in checks:
        if check_file_exists(filepath):
            found, line = check_class_in_file(filepath, class_name)
            print(f"  {name}: {'✓' if found else '✗'} ({filepath}:{line})")
        else:
            print(f"  {name}: ✗ (file not found)")
    
    # Check for specific features
    print("\n  Specific Features:")
    
    # Linear weighting
    found, lines = check_keyword_in_file("src/holdem/mccfr/solver.py", "linear")
    print(f"    Linear weighting: {'✓' if found else '✗'} (lines: {lines[:3] if found else ''})")
    
    # Negative regret pruning
    found, lines = check_keyword_in_file("src/holdem/mccfr/solver.py", "pruning")
    print(f"    Negative regret pruning: {'✓' if found else '✗'} (lines: {lines[:3] if found else ''})")
    
    # RNG state saving
    found, lines = check_keyword_in_file("src/holdem/mccfr/solver.py", "rng.get_state")
    print(f"    RNG state saving: {'✓' if found else '✗'} (lines: {lines[:3] if found else ''})")
    
    # Checkpointing
    found, lines = check_keyword_in_file("src/holdem/mccfr/solver.py", "checkpoint")
    print(f"    Checkpointing: {'✓' if found else '✗'} (lines: {lines[:3] if found else ''})")


def verify_realtime_search_features():
    """Verify real-time search features."""
    print("\n=== Real-time Search Features ===")
    
    checks = [
        ("Subgame Resolver", "src/holdem/realtime/resolver.py", "SubgameResolver"),
        ("Subgame Tree", "src/holdem/realtime/subgame.py", "SubgameTree"),
        ("Belief State", "src/holdem/realtime/belief.py", "BeliefState"),
        ("Search Controller", "src/holdem/realtime/search_controller.py", None),
    ]
    
    for name, filepath, class_name in checks:
        if check_file_exists(filepath):
            if class_name:
                found, line = check_class_in_file(filepath, class_name)
                print(f"  {name}: {'✓' if found else '✗'} ({filepath}:{line})")
            else:
                print(f"  {name}: ✓ ({filepath})")
        else:
            print(f"  {name}: ✗ (file not found)")
    
    print("\n  Specific Features:")
    
    # KL regularization
    found, lines = check_keyword_in_file("src/holdem/realtime/resolver.py", "kl")
    print(f"    KL regularization: {'✓' if found else '✗'} (lines: {lines[:5] if found else ''})")
    
    # Warm start
    found, lines = check_keyword_in_file("src/holdem/realtime/resolver.py", "warm_start")
    print(f"    Warm start from blueprint: {'✓' if found else '✗'} (lines: {lines[:3] if found else ''})")
    
    # Time budget
    found, lines = check_keyword_in_file("src/holdem/realtime/resolver.py", "time_budget")
    print(f"    Time budget: {'✓' if found else '✗'} (lines: {lines[:3] if found else ''})")


def verify_evaluation_features():
    """Verify evaluation features."""
    print("\n=== Evaluation Features ===")
    
    checks = [
        ("AIVAT", "src/holdem/rl_eval/aivat.py", "AIVATEvaluator"),
        ("Eval Loop", "src/holdem/rl_eval/eval_loop.py", None),
        ("Statistics", "src/holdem/rl_eval/statistics.py", None),
        ("Baselines", "src/holdem/rl_eval/baselines.py", None),
    ]
    
    for name, filepath, class_name in checks:
        if check_file_exists(filepath):
            if class_name:
                found, line = check_class_in_file(filepath, class_name)
                print(f"  {name}: {'✓' if found else '✗'} ({filepath}:{line})")
            else:
                print(f"  {name}: ✓ ({filepath})")
        else:
            print(f"  {name}: ✗ (file not found)")


def verify_abstraction_features():
    """Verify abstraction features."""
    print("\n=== Abstraction Features ===")
    
    checks = [
        ("Bucketing", "src/holdem/abstraction/bucketing.py", "BucketBuilder"),
        ("Preflop Features", "src/holdem/abstraction/preflop_features.py", None),
        ("Postflop Features", "src/holdem/abstraction/postflop_features.py", None),
        ("Actions", "src/holdem/abstraction/actions.py", None),
        ("Action Translator", "src/holdem/abstraction/action_translator.py", None),
    ]
    
    for name, filepath, class_name in checks:
        if check_file_exists(filepath):
            if class_name:
                found, line = check_class_in_file(filepath, class_name)
                print(f"  {name}: {'✓' if found else '✗'} ({filepath}:{line})")
            else:
                print(f"  {name}: ✓ ({filepath})")
        else:
            print(f"  {name}: ✗ (file not found)")
    
    print("\n  Specific Features:")
    
    # Bucket counts
    found, lines = check_keyword_in_file("src/holdem/abstraction/bucketing.py", "n_buckets")
    print(f"    Bucket configuration: {'✓' if found else '✗'}")
    
    # Action sizing
    found, lines = check_keyword_in_file("src/holdem/abstraction/actions.py", "BET_")
    print(f"    Action sizing: {'✓' if found else '✗'}")


def main():
    """Run all verification checks."""
    print("=" * 80)
    print("PLURIBUS FEATURE PARITY VERIFICATION")
    print("=" * 80)
    
    verify_vision_ocr_features()
    verify_mccfr_features()
    verify_realtime_search_features()
    verify_evaluation_features()
    verify_abstraction_features()
    
    print("\n" + "=" * 80)
    print("Verification complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
