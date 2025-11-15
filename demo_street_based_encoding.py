#!/usr/bin/env python3
"""Demo of street-based action history encoding in infosets.

This script demonstrates the enhanced infoset encoding with street-separated
action histories, matching the Pluribus paper style.
"""

import sys
sys.path.insert(0, 'src')

from holdem.types import Card, Street, MCCFRConfig
from holdem.abstraction.state_encode import StateEncoder, INFOSET_VERSION
from holdem.abstraction.bucketing import HandBucketing, BucketConfig


def print_section(title):
    """Print a section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)


def demo_basic_encoding():
    """Demonstrate basic action encoding."""
    print_section("Basic Action Encoding")
    
    config = BucketConfig(k_preflop=24, k_flop=80, k_turn=80, k_river=64)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Simple action list
    actions = ["check_call", "bet_0.75p", "check_call"]
    encoded = encoder.encode_action_history(actions)
    
    print("\nSimple format (no street separation):")
    print(f"  Input:  {actions}")
    print(f"  Output: {encoded}")
    print(f"\n  Compact representation: {len(encoded)} chars vs {len(str(actions))} chars")


def demo_street_based_encoding():
    """Demonstrate street-based action encoding."""
    print_section("Street-Based Action Encoding (Pluribus-style)")
    
    config = BucketConfig(k_preflop=24, k_flop=80, k_turn=80, k_river=64)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Example 1: Two streets
    print("\nExample 1: Preflop and Flop actions")
    actions_1 = {
        Street.PREFLOP: ["check_call", "bet_0.5p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "call"]
    }
    encoded_1 = encoder.encode_action_history_by_street(actions_1)
    print(f"  Input:")
    print(f"    PREFLOP: {actions_1[Street.PREFLOP]}")
    print(f"    FLOP:    {actions_1[Street.FLOP]}")
    print(f"  Output: {encoded_1}")
    
    # Example 2: Three streets
    print("\nExample 2: Preflop, Flop, and Turn actions")
    actions_2 = {
        Street.PREFLOP: ["bet_0.5p", "raise_1.0p", "call"],
        Street.FLOP: ["check", "bet_0.66p", "call"],
        Street.TURN: ["bet_1.0p", "raise_1.5p", "fold"]
    }
    encoded_2 = encoder.encode_action_history_by_street(actions_2)
    print(f"  Input:")
    print(f"    PREFLOP: {actions_2[Street.PREFLOP]}")
    print(f"    FLOP:    {actions_2[Street.FLOP]}")
    print(f"    TURN:    {actions_2[Street.TURN]}")
    print(f"  Output: {encoded_2}")
    
    # Example 3: All four streets
    print("\nExample 3: All four streets (Preflop through River)")
    actions_3 = {
        Street.PREFLOP: ["bet_0.5p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "call"],
        Street.TURN: ["check", "bet_1.0p", "call"],
        Street.RIVER: ["bet_1.5p", "all_in"]
    }
    encoded_3 = encoder.encode_action_history_by_street(actions_3)
    print(f"  Input:")
    print(f"    PREFLOP: {actions_3[Street.PREFLOP]}")
    print(f"    FLOP:    {actions_3[Street.FLOP]}")
    print(f"    TURN:    {actions_3[Street.TURN]}")
    print(f"    RIVER:   {actions_3[Street.RIVER]}")
    print(f"  Output: {encoded_3}")


def demo_infoset_generation():
    """Demonstrate complete infoset generation."""
    print_section("Complete Infoset Generation")
    
    # Note: This would normally require building buckets, which takes time
    # For demo purposes, we'll show the format without actually computing buckets
    
    print("\nWithout street separation (simple format):")
    print("  Format: v2:STREET:bucket:action_sequence")
    print("  Example: v2:FLOP:12:C-B75-C")
    print("    - Version: v2")
    print("    - Street: FLOP")
    print("    - Bucket: 12 (hand strength abstraction)")
    print("    - Actions: Check, Bet 75% pot, Call")
    
    print("\nWith street separation (Pluribus-style):")
    print("  Format: v2:STREET:bucket:PREFLOP:actions|FLOP:actions|...")
    print("  Example: v2:TURN:42:PREFLOP:C-B50-C|FLOP:C-B75-C|TURN:B100")
    print("    - Version: v2")
    print("    - Street: TURN (current street)")
    print("    - Bucket: 42")
    print("    - Actions:")
    print("        PREFLOP: Check, Bet 50% pot, Call")
    print("        FLOP:    Check, Bet 75% pot, Call")
    print("        TURN:    Bet 100% pot")


def demo_configuration():
    """Demonstrate configuration options."""
    print_section("Configuration")
    
    print("\nMCCFRConfig has new option for action history in infosets:")
    config = MCCFRConfig()
    print(f"  include_action_history_in_infoset: {config.include_action_history_in_infoset}")
    print(f"  Default: True (enabled)")
    
    print("\nTo disable (for backward compatibility):")
    print("  config = MCCFRConfig(include_action_history_in_infoset=False)")


def demo_benefits():
    """Show benefits of street-based encoding."""
    print_section("Benefits of Street-Based Encoding")
    
    config = BucketConfig(k_preflop=24, k_flop=80, k_turn=80, k_river=64)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    print("\n1. BETTER DIFFERENTIATION")
    print("   Different sequences on different streets create different infosets:")
    
    actions_a = {
        Street.PREFLOP: ["bet_0.5p", "call"],
        Street.FLOP: ["check"]
    }
    actions_b = {
        Street.PREFLOP: ["check"],
        Street.FLOP: ["bet_0.5p", "call"]
    }
    
    encoded_a = encoder.encode_action_history_by_street(actions_a)
    encoded_b = encoder.encode_action_history_by_street(actions_b)
    
    print(f"   Scenario A: {encoded_a}")
    print(f"   Scenario B: {encoded_b}")
    print(f"   Different: {encoded_a != encoded_b} ✓")
    
    print("\n2. CLARITY")
    print("   Easy to see which actions happened on which street:")
    
    actions_complex = {
        Street.PREFLOP: ["bet_0.5p", "raise_1.0p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "raise_1.5p", "call"],
        Street.TURN: ["bet_1.0p", "fold"]
    }
    encoded_complex = encoder.encode_action_history_by_street(actions_complex)
    print(f"   {encoded_complex}")
    print("   Street boundaries clearly marked with | separators")
    
    print("\n3. COMPACTNESS")
    print("   Still very compact compared to verbose format:")
    verbose = "PREFLOP:check_call.bet_0.5p.call|FLOP:check.bet_0.75p.call"
    compact = "PREFLOP:C-B50-C|FLOP:C-B75-C"
    print(f"   Verbose: {verbose} ({len(verbose)} chars)")
    print(f"   Compact: {compact} ({len(compact)} chars)")
    print(f"   Space saved: {100 * (1 - len(compact)/len(verbose)):.1f}%")
    
    print("\n4. PLURIBUS ALIGNMENT")
    print("   Matches the encoding style from Pluribus paper")
    print("   Enables better comparison and benchmarking")


def demo_determinism():
    """Demonstrate deterministic encoding."""
    print_section("Deterministic Encoding")
    
    config = BucketConfig(k_preflop=24, k_flop=80, k_turn=80, k_river=64)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    actions = {
        Street.PREFLOP: ["check_call", "bet_0.5p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "call"]
    }
    
    # Encode multiple times
    results = [encoder.encode_action_history_by_street(actions) for _ in range(5)]
    
    print("\nSame input encoded 5 times:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result}")
    
    all_same = len(set(results)) == 1
    print(f"\nAll identical: {all_same} ✓")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("  Street-Based Action History Encoding Demo")
    print("  Pluribus-style infoset encoding for MCCFR")
    print("=" * 70)
    
    try:
        demo_basic_encoding()
        demo_street_based_encoding()
        demo_infoset_generation()
        demo_configuration()
        demo_benefits()
        demo_determinism()
        
        print("\n" + "=" * 70)
        print("  Demo Complete! ✨")
        print("=" * 70)
        print("\nFor more information:")
        print("  - INFOSET_ENCODING.md: Complete reference guide")
        print("  - INFOSET_VERSIONING.md: Implementation details")
        print("  - tests/test_street_based_action_encoding.py: Test suite")
        print()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
