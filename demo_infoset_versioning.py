"""Demo script showing infoset versioning and action sequence encoding."""

import sys
sys.path.insert(0, 'src')

from holdem.abstraction.state_encode import (
    StateEncoder,
    INFOSET_VERSION,
    parse_infoset_key,
    get_infoset_version
)
from holdem.abstraction.bucketing import HandBucketing, BucketConfig
from holdem.types import Card, Street


def main():
    """Demonstrate the new infoset format."""
    print("=" * 70)
    print("INFOSET VERSIONING AND ACTION SEQUENCE ENCODING DEMO")
    print("=" * 70)
    print()
    
    # Setup
    config = BucketConfig(k_preflop=24, k_flop=80, k_turn=80, k_river=64)
    # Note: This will fail without full dependencies, but shows the API
    try:
        bucketing = HandBucketing(config)
        encoder = StateEncoder(bucketing)
        
        print(f"Current Infoset Version: {INFOSET_VERSION}")
        print()
        
        # Example 1: Action history encoding
        print("1. ACTION HISTORY ENCODING")
        print("-" * 70)
        
        actions = ["check_call", "bet_0.75p", "check_call"]
        encoded = encoder.encode_action_history(actions)
        print(f"Actions: {actions}")
        print(f"Encoded: {encoded}")
        print()
        
        actions = ["bet_0.5p", "call", "bet_1.0p", "fold"]
        encoded = encoder.encode_action_history(actions)
        print(f"Actions: {actions}")
        print(f"Encoded: {encoded}")
        print()
        
        # Example 2: Versioned infoset format
        print("2. VERSIONED INFOSET FORMAT")
        print("-" * 70)
        
        hole_cards = [Card("A", "h"), Card("K", "h")]
        board = [Card("Q", "h"), Card("J", "h"), Card("T", "h")]
        
        infoset_new, _ = encoder.encode_infoset(
            hole_cards=hole_cards,
            board=board,
            street=Street.FLOP,
            betting_history="C-B75-C",
            use_versioning=True
        )
        print(f"New format: {infoset_new}")
        
        infoset_old, _ = encoder.encode_infoset(
            hole_cards=hole_cards,
            board=board,
            street=Street.FLOP,
            betting_history="check_call.bet_0.75p.check_call",
            use_versioning=False
        )
        print(f"Legacy format: {infoset_old}")
        print()
        
        # Example 3: Parsing both formats
        print("3. PARSING INFOSET KEYS")
        print("-" * 70)
        
        # Parse new format
        street_name, bucket, history = parse_infoset_key(infoset_new)
        version = get_infoset_version(infoset_new)
        print(f"New format parsing:")
        print(f"  Version: {version}")
        print(f"  Street: {street_name}")
        print(f"  Bucket: {bucket}")
        print(f"  History: {history}")
        print()
        
        # Parse legacy format
        street_name, bucket, history = parse_infoset_key(infoset_old)
        version = get_infoset_version(infoset_old)
        print(f"Legacy format parsing:")
        print(f"  Version: {version}")
        print(f"  Street: {street_name}")
        print(f"  Bucket: {bucket}")
        print(f"  History: {history}")
        print()
        
        # Example 4: Action abbreviations
        print("4. ACTION ABBREVIATIONS")
        print("-" * 70)
        print("fold         -> F")
        print("check_call   -> C")
        print("bet_0.33p    -> B33")
        print("bet_0.5p     -> B50")
        print("bet_0.66p    -> B66")
        print("bet_0.75p    -> B75")
        print("bet_1.0p     -> B100")
        print("bet_1.5p     -> B150")
        print("bet_2.0p     -> B200")
        print("all_in       -> A")
        print()
        
        # Example 5: Benefits
        print("5. BENEFITS OF NEW FORMAT")
        print("-" * 70)
        print("✓ More compact representation")
        print("✓ Clear versioning for compatibility")
        print("✓ Better distinction between game situations")
        print("✓ Backward compatible parsing")
        print("✓ Checkpoint version validation")
        print()
        
        print("=" * 70)
        print("Demo completed successfully!")
        print("=" * 70)
        
    except ImportError as e:
        print(f"Note: Full functionality requires all dependencies installed.")
        print(f"Error: {e}")
        print()
        print("However, the core API demonstrated above is:")
        print("  - StateEncoder.encode_action_history(actions) -> abbreviated string")
        print("  - StateEncoder.encode_infoset(..., use_versioning=True) -> versioned key")
        print("  - parse_infoset_key(infoset) -> (street, bucket, history)")
        print("  - get_infoset_version(infoset) -> version or None")


if __name__ == "__main__":
    main()
