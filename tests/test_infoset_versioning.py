"""Tests for infoset versioning and action sequence encoding."""

import sys
sys.path.insert(0, 'src')

from holdem.types import Card, Street
from holdem.abstraction.state_encode import (
    StateEncoder,
    INFOSET_VERSION,
    parse_infoset_key,
    get_infoset_version,
    create_infoset_key
)
from holdem.abstraction.bucketing import HandBucketing, BucketConfig


def test_encode_action_history_basic():
    """Test basic action history encoding."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Test empty history
    assert encoder.encode_action_history([]) == ""
    
    # Test single actions
    assert encoder.encode_action_history(["fold"]) == "F"
    assert encoder.encode_action_history(["check_call"]) == "C"
    assert encoder.encode_action_history(["check"]) == "C"
    assert encoder.encode_action_history(["call"]) == "C"
    assert encoder.encode_action_history(["all_in"]) == "A"
    
    # Test bet actions
    assert encoder.encode_action_history(["bet_0.33p"]) == "B33"
    assert encoder.encode_action_history(["bet_0.5p"]) == "B50"
    assert encoder.encode_action_history(["bet_0.66p"]) == "B66"
    assert encoder.encode_action_history(["bet_0.75p"]) == "B75"
    assert encoder.encode_action_history(["bet_1.0p"]) == "B100"
    assert encoder.encode_action_history(["bet_1.5p"]) == "B150"
    assert encoder.encode_action_history(["bet_2.0p"]) == "B200"
    
    # Test sequences
    actions = ["check_call", "bet_0.75p", "check_call"]
    assert encoder.encode_action_history(actions) == "C-B75-C"
    
    actions = ["bet_0.5p", "call", "bet_1.0p", "fold"]
    assert encoder.encode_action_history(actions) == "B50-C-B100-F"


def test_encode_action_history_raises():
    """Test raise actions are encoded correctly."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Raise actions should be encoded similarly to bets
    assert encoder.encode_action_history(["raise_0.75p"]) == "B75"
    assert encoder.encode_action_history(["raise_1.0p"]) == "B100"


def test_infoset_versioning():
    """Test infoset versioning in encoded keys."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    hole_cards = [Card("A", "h"), Card("K", "h")]
    board = [Card("Q", "h"), Card("J", "h"), Card("T", "h")]
    
    # Test with versioning enabled (default)
    infoset, street = encoder.encode_infoset(
        hole_cards=hole_cards,
        board=board,
        street=Street.FLOP,
        betting_history="C-B75-C",
        use_versioning=True
    )
    
    assert infoset.startswith(f"{INFOSET_VERSION}:")
    assert f":{Street.FLOP.name}:" in infoset
    assert infoset.endswith(":C-B75-C")
    
    # Test with versioning disabled (legacy mode)
    infoset_legacy, street = encoder.encode_infoset(
        hole_cards=hole_cards,
        board=board,
        street=Street.FLOP,
        betting_history="C-B75-C",
        use_versioning=False
    )
    
    assert not infoset_legacy.startswith("v")
    assert infoset_legacy.startswith(f"{Street.FLOP.name}:")
    assert infoset_legacy.endswith(":C-B75-C")


def test_parse_infoset_key_versioned():
    """Test parsing versioned infoset keys."""
    # Versioned format: v2:FLOP:12:C-B75-C
    infoset = "v2:FLOP:12:C-B75-C"
    street_name, bucket, history = parse_infoset_key(infoset)
    
    assert street_name == "FLOP"
    assert bucket == 12
    assert history == "C-B75-C"


def test_parse_infoset_key_legacy():
    """Test parsing legacy infoset keys."""
    # Legacy format: FLOP:12:check_call.bet_0.75p.check_call
    infoset = "FLOP:12:check_call.bet_0.75p.check_call"
    street_name, bucket, history = parse_infoset_key(infoset)
    
    assert street_name == "FLOP"
    assert bucket == 12
    assert history == "check_call.bet_0.75p.check_call"


def test_parse_infoset_key_complex_history():
    """Test parsing with complex action sequences."""
    # With colons in history (should work with split limit)
    infoset = "v2:TURN:42:B50-C-B100-C-B150"
    street_name, bucket, history = parse_infoset_key(infoset)
    
    assert street_name == "TURN"
    assert bucket == 42
    assert history == "B50-C-B100-C-B150"


def test_get_infoset_version():
    """Test extracting version from infoset strings."""
    # Versioned infoset
    assert get_infoset_version("v2:FLOP:12:C-B75-C") == "v2"
    assert get_infoset_version("v1:RIVER:5:F") == "v1"
    
    # Legacy infoset (no version)
    assert get_infoset_version("FLOP:12:check_call.bet_0.75p") is None
    assert get_infoset_version("RIVER:5:fold") is None


def test_create_infoset_key_with_versioning():
    """Test creating infoset keys with versioning."""
    # With versioning (default)
    infoset, street = create_infoset_key(
        Street.FLOP,
        bucket=15,
        history="C-B75-C",
        use_versioning=True
    )
    
    assert infoset == f"{INFOSET_VERSION}:FLOP:15:C-B75-C"
    assert street == Street.FLOP


def test_create_infoset_key_without_versioning():
    """Test creating infoset keys without versioning."""
    # Without versioning (legacy)
    infoset, street = create_infoset_key(
        Street.TURN,
        bucket=20,
        history="check_call.bet_1.0p",
        use_versioning=False
    )
    
    assert infoset == "TURN:20:check_call.bet_1.0p"
    assert street == Street.TURN
    assert not infoset.startswith("v")


def test_infoset_format_consistency():
    """Test that format is consistent across streets."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    hole_cards = [Card("A", "h"), Card("K", "h")]
    
    # Test each street with versioning
    for street, board_size in [
        (Street.PREFLOP, 0),
        (Street.FLOP, 3),
        (Street.TURN, 4),
        (Street.RIVER, 5)
    ]:
        board = [Card("Q", "h"), Card("J", "h"), Card("T", "h"), 
                 Card("9", "h"), Card("8", "h")][:board_size]
        
        infoset, _ = encoder.encode_infoset(
            hole_cards=hole_cards,
            board=board,
            street=street,
            betting_history="C-B75",
            use_versioning=True
        )
        
        # All should have version prefix
        assert infoset.startswith(f"{INFOSET_VERSION}:")
        # All should have street name
        assert f":{street.name}:" in infoset
        # All should end with history
        assert infoset.endswith(":C-B75")


def test_backward_compatibility():
    """Test that both old and new formats can be parsed."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Create both formats
    hole_cards = [Card("A", "h"), Card("K", "h")]
    board = [Card("Q", "h"), Card("J", "h"), Card("T", "h")]
    
    # New format
    infoset_new, _ = encoder.encode_infoset(
        hole_cards=hole_cards,
        board=board,
        street=Street.FLOP,
        betting_history="C-B75-C",
        use_versioning=True
    )
    
    # Legacy format
    infoset_old, _ = encoder.encode_infoset(
        hole_cards=hole_cards,
        board=board,
        street=Street.FLOP,
        betting_history="check_call.bet_0.75p.check_call",
        use_versioning=False
    )
    
    # Both should be parseable
    street_new, bucket_new, history_new = parse_infoset_key(infoset_new)
    street_old, bucket_old, history_old = parse_infoset_key(infoset_old)
    
    assert street_new == "FLOP"
    assert street_old == "FLOP"
    assert bucket_new == bucket_old  # Same cards should map to same bucket
    

def test_action_encoding_edge_cases():
    """Test edge cases in action encoding."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Test with quarter pot (0.25)
    assert encoder.encode_action_history(["bet_0.25p"]) == "B25"
    
    # Test mixed sequence with all-in
    actions = ["bet_0.5p", "call", "all_in"]
    assert encoder.encode_action_history(actions) == "B50-C-A"
    
    # Test fold ending sequence
    actions = ["bet_1.0p", "fold"]
    assert encoder.encode_action_history(actions) == "B100-F"


if __name__ == "__main__":
    # Run tests manually
    print("Running infoset versioning tests...")
    
    test_encode_action_history_basic()
    print("✓ test_encode_action_history_basic")
    
    test_encode_action_history_raises()
    print("✓ test_encode_action_history_raises")
    
    test_infoset_versioning()
    print("✓ test_infoset_versioning")
    
    test_parse_infoset_key_versioned()
    print("✓ test_parse_infoset_key_versioned")
    
    test_parse_infoset_key_legacy()
    print("✓ test_parse_infoset_key_legacy")
    
    test_parse_infoset_key_complex_history()
    print("✓ test_parse_infoset_key_complex_history")
    
    test_get_infoset_version()
    print("✓ test_get_infoset_version")
    
    test_create_infoset_key_with_versioning()
    print("✓ test_create_infoset_key_with_versioning")
    
    test_create_infoset_key_without_versioning()
    print("✓ test_create_infoset_key_without_versioning")
    
    test_infoset_format_consistency()
    print("✓ test_infoset_format_consistency")
    
    test_backward_compatibility()
    print("✓ test_backward_compatibility")
    
    test_action_encoding_edge_cases()
    print("✓ test_action_encoding_edge_cases")
    
    print("\nAll tests passed! ✨")
