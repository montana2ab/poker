"""Tests for street-based action history encoding in infosets."""

import sys
sys.path.insert(0, 'src')

from holdem.types import Card, Street, MCCFRConfig
from holdem.abstraction.state_encode import (
    StateEncoder,
    INFOSET_VERSION,
    parse_infoset_key
)
from holdem.abstraction.bucketing import HandBucketing, BucketConfig


def test_encode_action_history_by_street_basic():
    """Test basic street-based action history encoding."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Test empty history
    assert encoder.encode_action_history_by_street({}) == ""
    
    # Test single street with single action
    actions = {Street.PREFLOP: ["check_call"]}
    assert encoder.encode_action_history_by_street(actions) == "PREFLOP:C"
    
    # Test single street with multiple actions
    actions = {Street.PREFLOP: ["check_call", "bet_0.5p", "call"]}
    assert encoder.encode_action_history_by_street(actions) == "PREFLOP:C-B50-C"


def test_encode_action_history_by_street_multiple_streets():
    """Test encoding across multiple streets."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Two streets
    actions = {
        Street.PREFLOP: ["check_call", "bet_0.5p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "call"]
    }
    result = encoder.encode_action_history_by_street(actions)
    assert result == "PREFLOP:C-B50-C|FLOP:C-B75-C"
    
    # Three streets
    actions = {
        Street.PREFLOP: ["bet_0.5p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "call"],
        Street.TURN: ["bet_1.0p", "fold"]
    }
    result = encoder.encode_action_history_by_street(actions)
    assert result == "PREFLOP:B50-C|FLOP:C-B75-C|TURN:B100-F"
    
    # All four streets
    actions = {
        Street.PREFLOP: ["bet_0.5p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "call"],
        Street.TURN: ["bet_1.0p", "call"],
        Street.RIVER: ["bet_1.5p", "fold"]
    }
    result = encoder.encode_action_history_by_street(actions)
    assert result == "PREFLOP:B50-C|FLOP:C-B75-C|TURN:B100-C|RIVER:B150-F"


def test_encode_action_history_by_street_order():
    """Test that streets are encoded in correct order regardless of input order."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Input streets out of order
    actions = {
        Street.TURN: ["bet_1.0p", "call"],
        Street.PREFLOP: ["bet_0.5p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "call"]
    }
    result = encoder.encode_action_history_by_street(actions)
    # Should still be in order: PREFLOP, FLOP, TURN
    assert result == "PREFLOP:B50-C|FLOP:C-B75-C|TURN:B100-C"


def test_encode_action_history_by_street_all_action_types():
    """Test all action types in street-based encoding."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    actions = {
        Street.PREFLOP: ["check", "bet_0.33p", "raise_0.66p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "all_in"],
        Street.TURN: ["fold"]
    }
    result = encoder.encode_action_history_by_street(actions)
    assert result == "PREFLOP:C-B33-B66-C|FLOP:C-B75-A|TURN:F"


def test_encode_action_history_by_street_empty_streets():
    """Test handling of empty street action lists."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Street with empty list should be skipped
    actions = {
        Street.PREFLOP: ["check_call"],
        Street.FLOP: [],  # Empty
        Street.TURN: ["bet_1.0p"]
    }
    result = encoder.encode_action_history_by_street(actions)
    # FLOP should be omitted
    assert result == "PREFLOP:C|TURN:B100"


def test_street_based_format_deterministic():
    """Test that same action sequence produces same encoding."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    actions = {
        Street.PREFLOP: ["check_call", "bet_0.5p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "call"]
    }
    
    # Encode multiple times
    result1 = encoder.encode_action_history_by_street(actions)
    result2 = encoder.encode_action_history_by_street(actions)
    result3 = encoder.encode_action_history_by_street(actions)
    
    # Should be identical
    assert result1 == result2 == result3


def test_street_based_different_sequences_different_keys():
    """Test that different sequences produce different encodings."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Different preflop actions
    actions1 = {
        Street.PREFLOP: ["check_call", "bet_0.5p"],
        Street.FLOP: ["check"]
    }
    actions2 = {
        Street.PREFLOP: ["bet_0.5p", "call"],
        Street.FLOP: ["check"]
    }
    
    result1 = encoder.encode_action_history_by_street(actions1)
    result2 = encoder.encode_action_history_by_street(actions2)
    
    assert result1 != result2
    
    # Different flop actions
    actions3 = {
        Street.PREFLOP: ["check_call"],
        Street.FLOP: ["check", "bet_0.75p"]
    }
    actions4 = {
        Street.PREFLOP: ["check_call"],
        Street.FLOP: ["bet_0.75p", "call"]
    }
    
    result3 = encoder.encode_action_history_by_street(actions3)
    result4 = encoder.encode_action_history_by_street(actions4)
    
    assert result3 != result4


def test_street_based_long_sequences():
    """Test handling of long action sequences."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Long preflop sequence (multiple raises)
    actions = {
        Street.PREFLOP: [
            "bet_0.5p", "raise_1.0p", "raise_1.5p", "call"
        ],
        Street.FLOP: [
            "check", "bet_0.75p", "raise_1.5p", "call"
        ],
        Street.TURN: [
            "check", "bet_1.0p", "call"
        ],
        Street.RIVER: [
            "bet_1.5p", "raise_2.0p", "fold"
        ]
    }
    
    result = encoder.encode_action_history_by_street(actions)
    
    # Should handle without crashes
    assert "PREFLOP:" in result
    assert "FLOP:" in result
    assert "TURN:" in result
    assert "RIVER:" in result
    assert result.count("|") == 3  # Three separators for four streets


def test_mccfr_config_has_action_history_option():
    """Test that MCCFRConfig has the new configuration option."""
    config = MCCFRConfig()
    
    # Check that the option exists
    assert hasattr(config, 'include_action_history_in_infoset')
    
    # Check default value is True
    assert config.include_action_history_in_infoset is True
    
    # Test that it can be set to False
    config.include_action_history_in_infoset = False
    assert config.include_action_history_in_infoset is False


def test_backward_compatibility_simple_format():
    """Test that simple format still works (backward compatibility)."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    # Old simple format (no street separation)
    simple_actions = ["check_call", "bet_0.75p", "check_call"]
    simple_encoded = encoder.encode_action_history(simple_actions)
    
    assert simple_encoded == "C-B75-C"
    
    # New street-based format
    street_actions = {
        Street.FLOP: ["check_call", "bet_0.75p", "check_call"]
    }
    street_encoded = encoder.encode_action_history_by_street(street_actions)
    
    assert street_encoded == "FLOP:C-B75-C"
    
    # Both methods should work independently


def test_parse_street_based_infoset():
    """Test parsing infoset keys with street-based history."""
    # Street-based format
    infoset = "v2:FLOP:12:PREFLOP:C-B50-C|FLOP:C-B75"
    street_name, bucket, history = parse_infoset_key(infoset)
    
    assert street_name == "FLOP"
    assert bucket == 12
    assert history == "PREFLOP:C-B50-C|FLOP:C-B75"
    
    # History should contain street separators
    assert "|" in history
    assert "PREFLOP:" in history
    assert "FLOP:" in history


def test_street_based_format_compact():
    """Test that street-based format is reasonably compact."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    actions = {
        Street.PREFLOP: ["check_call", "bet_0.5p", "call"],
        Street.FLOP: ["check", "bet_0.75p", "call"],
        Street.TURN: ["bet_1.0p", "fold"]
    }
    
    result = encoder.encode_action_history_by_street(actions)
    
    # Format should be compact
    # Example: "PREFLOP:C-B50-C|FLOP:C-B75-C|TURN:B100-F"
    assert len(result) < 100  # Reasonable length
    
    # Should not contain verbose text
    assert "check_call" not in result
    assert "bet_" not in result
    assert "0.5p" not in result


def test_edge_case_single_action_per_street():
    """Test encoding with single action per street."""
    config = BucketConfig(k_preflop=8, k_flop=8, k_turn=8, k_river=8)
    bucketing = HandBucketing(config)
    encoder = StateEncoder(bucketing)
    
    actions = {
        Street.PREFLOP: ["call"],
        Street.FLOP: ["check"],
        Street.TURN: ["bet_1.0p"],
        Street.RIVER: ["fold"]
    }
    
    result = encoder.encode_action_history_by_street(actions)
    assert result == "PREFLOP:C|FLOP:C|TURN:B100|RIVER:F"


if __name__ == "__main__":
    # Run tests manually
    print("Running street-based action encoding tests...")
    
    test_encode_action_history_by_street_basic()
    print("✓ test_encode_action_history_by_street_basic")
    
    test_encode_action_history_by_street_multiple_streets()
    print("✓ test_encode_action_history_by_street_multiple_streets")
    
    test_encode_action_history_by_street_order()
    print("✓ test_encode_action_history_by_street_order")
    
    test_encode_action_history_by_street_all_action_types()
    print("✓ test_encode_action_history_by_street_all_action_types")
    
    test_encode_action_history_by_street_empty_streets()
    print("✓ test_encode_action_history_by_street_empty_streets")
    
    test_street_based_format_deterministic()
    print("✓ test_street_based_format_deterministic")
    
    test_street_based_different_sequences_different_keys()
    print("✓ test_street_based_different_sequences_different_keys")
    
    test_street_based_long_sequences()
    print("✓ test_street_based_long_sequences")
    
    test_mccfr_config_has_action_history_option()
    print("✓ test_mccfr_config_has_action_history_option")
    
    test_backward_compatibility_simple_format()
    print("✓ test_backward_compatibility_simple_format")
    
    test_parse_street_based_infoset()
    print("✓ test_parse_street_based_infoset")
    
    test_street_based_format_compact()
    print("✓ test_street_based_format_compact")
    
    test_edge_case_single_action_per_street()
    print("✓ test_edge_case_single_action_per_street")
    
    print("\nAll street-based encoding tests passed! ✨")
