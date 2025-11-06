"""Test street detection improvements."""

import pytest
from holdem.types import Card, Street, BucketConfig
from holdem.abstraction.state_encode import StateEncoder, parse_infoset_key, create_infoset_key
from holdem.abstraction.bucketing import HandBucketing


def test_encode_infoset_returns_street():
    """Test that encode_infoset returns both infoset and street."""
    config = BucketConfig(k_preflop=8, k_flop=20, num_samples=100, seed=42)
    bucketing = HandBucketing(config)
    bucketing.build(num_samples=100)
    
    encoder = StateEncoder(bucketing)
    
    hole_cards = [Card('A', 'h'), Card('K', 's')]
    board = []
    
    # Should return tuple of (infoset, street)
    result = encoder.encode_infoset(hole_cards, board, Street.PREFLOP, "")
    
    assert isinstance(result, tuple)
    assert len(result) == 2
    
    infoset, street = result
    assert isinstance(infoset, str)
    assert isinstance(street, Street)
    assert street == Street.PREFLOP


def test_parse_infoset_key():
    """Test that parse_infoset_key correctly extracts street."""
    # Test preflop infoset
    infoset = "PREFLOP:5:raise.call"
    street_name, bucket, history = parse_infoset_key(infoset)
    
    assert street_name == "PREFLOP"
    assert bucket == 5
    assert history == "raise.call"
    
    # Test flop infoset
    infoset = "FLOP:12:check.bet"
    street_name, bucket, history = parse_infoset_key(infoset)
    
    assert street_name == "FLOP"
    assert bucket == 12
    assert history == "check.bet"


def test_parse_infoset_key_invalid():
    """Test that parse_infoset_key raises error for invalid format."""
    with pytest.raises(ValueError):
        parse_infoset_key("invalid_format")
    
    with pytest.raises(ValueError):
        parse_infoset_key("PREFLOP:5")  # Missing history


def test_create_infoset_key():
    """Test that create_infoset_key returns both infoset and street."""
    result = create_infoset_key(Street.RIVER, 10, "bet.raise.call")
    
    assert isinstance(result, tuple)
    assert len(result) == 2
    
    infoset, street = result
    assert infoset == "RIVER:10:bet.raise.call"
    assert street == Street.RIVER


def test_street_extraction_all_streets():
    """Test street extraction for all game streets."""
    config = BucketConfig(k_preflop=8, k_flop=20, k_turn=20, k_river=16, num_samples=100, seed=42)
    bucketing = HandBucketing(config)
    bucketing.build(num_samples=100)
    
    encoder = StateEncoder(bucketing)
    
    hole_cards = [Card('A', 'h'), Card('K', 's')]
    
    # Preflop
    infoset_pf, street_pf = encoder.encode_infoset(hole_cards, [], Street.PREFLOP, "")
    assert street_pf == Street.PREFLOP
    assert "PREFLOP" in infoset_pf
    
    # Flop
    board_flop = [Card('T', 'h'), Card('9', 's'), Card('2', 'c')]
    infoset_f, street_f = encoder.encode_infoset(hole_cards, board_flop, Street.FLOP, "bet")
    assert street_f == Street.FLOP
    assert "FLOP" in infoset_f
    
    # Turn
    board_turn = board_flop + [Card('5', 'd')]
    infoset_t, street_t = encoder.encode_infoset(hole_cards, board_turn, Street.TURN, "bet.call")
    assert street_t == Street.TURN
    assert "TURN" in infoset_t
    
    # River
    board_river = board_turn + [Card('3', 'h')]
    infoset_r, street_r = encoder.encode_infoset(hole_cards, board_river, Street.RIVER, "bet.call.raise")
    assert street_r == Street.RIVER
    assert "RIVER" in infoset_r


def test_solver_extract_street_from_infoset():
    """Test that solver can extract street from infoset using parse function."""
    from holdem.mccfr.solver import MCCFRSolver
    from holdem.types import MCCFRConfig
    
    config = BucketConfig(k_preflop=8, k_flop=20, num_samples=100, seed=42)
    bucketing = HandBucketing(config)
    bucketing.build(num_samples=100)
    
    mccfr_config = MCCFRConfig(num_iterations=10)
    solver = MCCFRSolver(mccfr_config, bucketing, num_players=2)
    
    # Test extracting street from valid infosets
    assert solver._extract_street_from_infoset("PREFLOP:5:bet") == "preflop"
    assert solver._extract_street_from_infoset("FLOP:12:check.bet") == "flop"
    assert solver._extract_street_from_infoset("TURN:8:raise") == "turn"
    assert solver._extract_street_from_infoset("RIVER:15:bet.call.raise") == "river"
    
    # Test fallback for malformed infoset
    assert solver._extract_street_from_infoset("invalid") == "preflop"


def test_street_detection_no_string_matching():
    """Test that we're using structured parsing, not fragile string matching."""
    # This infoset has "river" in the betting history but is actually preflop
    # Old string matching would incorrectly identify this as river street
    infoset = "PREFLOP:5:riverbet"
    
    street_name, bucket, history = parse_infoset_key(infoset)
    
    # Should correctly identify as PREFLOP, not be confused by "river" in history
    assert street_name == "PREFLOP"
    assert bucket == 5
    assert history == "riverbet"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
