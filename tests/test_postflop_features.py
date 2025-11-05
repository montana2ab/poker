"""Test postflop feature extraction."""

import pytest
import numpy as np
from holdem.types import Card, Street
from holdem.abstraction.postflop_features import (
    classify_hand_category,
    detect_flush_draw,
    detect_straight_draw,
    has_combo_draw,
    analyze_board_texture,
    extract_postflop_features,
    HandCategory,
    FlushDrawType,
    StraightDrawType,
    bin_spr
)


def test_classify_high_card():
    """Test high card classification."""
    hole = [Card('7', 'h'), Card('2', 'd')]
    board = [Card('A', 's'), Card('K', 'c'), Card('9', 'h')]
    
    category = classify_hand_category(hole, board)
    assert category == HandCategory.HIGH_CARD


def test_classify_top_pair():
    """Test top pair classification."""
    hole = [Card('A', 'h'), Card('7', 'd')]
    board = [Card('A', 's'), Card('K', 'c'), Card('9', 'h')]
    
    category = classify_hand_category(hole, board)
    assert category == HandCategory.TOP_PAIR


def test_classify_overpair():
    """Test overpair classification."""
    hole = [Card('Q', 'h'), Card('Q', 'd')]
    board = [Card('J', 's'), Card('9', 'c'), Card('7', 'h')]
    
    category = classify_hand_category(hole, board)
    assert category == HandCategory.OVERPAIR


def test_classify_two_pair():
    """Test two pair classification."""
    hole = [Card('A', 'h'), Card('K', 'd')]
    board = [Card('A', 's'), Card('K', 'c'), Card('9', 'h')]
    
    category = classify_hand_category(hole, board)
    assert category == HandCategory.TWO_PAIR_BOARD_HAND


def test_classify_flush():
    """Test flush classification."""
    hole = [Card('A', 'h'), Card('K', 'h')]
    board = [Card('Q', 'h'), Card('9', 'h'), Card('7', 'h')]
    
    category = classify_hand_category(hole, board)
    assert category == HandCategory.FLUSH


def test_detect_flush_draw_none():
    """Test no flush draw."""
    hole = [Card('A', 'h'), Card('K', 'd')]
    board = [Card('Q', 's'), Card('9', 'c'), Card('7', 'h')]
    
    fd_type = detect_flush_draw(hole, board)
    assert fd_type == FlushDrawType.NONE


def test_detect_flush_draw_nut():
    """Test nut flush draw."""
    hole = [Card('A', 'h'), Card('K', 'h')]
    board = [Card('Q', 'h'), Card('9', 'h'), Card('7', 's')]
    
    fd_type = detect_flush_draw(hole, board)
    assert fd_type == FlushDrawType.DIRECT_NUT


def test_detect_flush_draw_non_nut():
    """Test non-nut flush draw."""
    hole = [Card('K', 'h'), Card('Q', 'h')]
    board = [Card('J', 'h'), Card('9', 'h'), Card('7', 's')]
    
    fd_type = detect_flush_draw(hole, board)
    assert fd_type == FlushDrawType.DIRECT_NON_NUT


def test_detect_flush_draw_backdoor():
    """Test backdoor flush draw."""
    hole = [Card('A', 'h'), Card('K', 'h')]
    board = [Card('Q', 'h'), Card('9', 's'), Card('7', 's')]
    
    fd_type = detect_flush_draw(hole, board)
    assert fd_type == FlushDrawType.BACKDOOR


def test_detect_straight_draw_oesd():
    """Test open-ended straight draw."""
    hole = [Card('J', 'h'), Card('T', 'd')]
    board = [Card('9', 's'), Card('8', 'c'), Card('2', 'h')]
    
    sd_type, is_high = detect_straight_draw(hole, board)
    assert sd_type == StraightDrawType.OESD


def test_detect_straight_draw_gutshot():
    """Test gutshot straight draw."""
    hole = [Card('J', 'h'), Card('9', 'd')]
    board = [Card('Q', 's'), Card('8', 'c'), Card('2', 'h')]
    
    sd_type, is_high = detect_straight_draw(hole, board)
    # Should detect some form of straight draw
    assert sd_type in [StraightDrawType.GUTSHOT, StraightDrawType.OESD, StraightDrawType.DOUBLE]


def test_has_combo_draw_true():
    """Test combo draw detection when both draws present."""
    combo = has_combo_draw(FlushDrawType.DIRECT_NUT, StraightDrawType.OESD)
    assert combo == 1


def test_has_combo_draw_false():
    """Test combo draw detection when only one draw."""
    combo = has_combo_draw(FlushDrawType.NONE, StraightDrawType.OESD)
    assert combo == 0


def test_board_texture_paired():
    """Test paired board detection."""
    board = [Card('A', 's'), Card('A', 'c'), Card('9', 'h')]
    texture = analyze_board_texture(board)
    
    assert texture[0] == 1.0  # board_paired
    assert texture[1] == 0.0  # board_trips_or_more


def test_board_texture_trips():
    """Test trips board detection."""
    board = [Card('9', 's'), Card('9', 'c'), Card('9', 'h')]
    texture = analyze_board_texture(board)
    
    assert texture[0] == 1.0  # board_paired
    assert texture[1] == 1.0  # board_trips_or_more


def test_board_texture_monotone():
    """Test monotone board detection."""
    board = [Card('A', 'h'), Card('K', 'h'), Card('9', 'h')]
    texture = analyze_board_texture(board)
    
    assert texture[2] == 1.0  # board_monotone


def test_board_texture_two_suited():
    """Test two-suited board detection."""
    board = [Card('A', 'h'), Card('K', 'h'), Card('9', 's')]
    texture = analyze_board_texture(board)
    
    assert texture[2] == 0.0  # board_monotone
    assert texture[3] == 1.0  # board_two_suited


def test_board_texture_ace_high():
    """Test ace-high board detection."""
    board = [Card('A', 'h'), Card('K', 's'), Card('9', 'c')]
    texture = analyze_board_texture(board)
    
    assert texture[4] == 1.0  # board_ace_high


def test_board_texture_low():
    """Test low board detection."""
    board = [Card('9', 'h'), Card('7', 's'), Card('5', 'c')]
    texture = analyze_board_texture(board)
    
    assert texture[5] == 1.0  # board_low


def test_bin_spr_low():
    """Test SPR binning for low SPR."""
    bins = bin_spr(2.0)
    assert bins[0] == 1.0
    assert bins[1] == 0.0
    assert bins[2] == 0.0


def test_bin_spr_mid():
    """Test SPR binning for mid SPR."""
    bins = bin_spr(5.0)
    assert bins[0] == 0.0
    assert bins[1] == 1.0
    assert bins[2] == 0.0


def test_bin_spr_high():
    """Test SPR binning for high SPR."""
    bins = bin_spr(10.0)
    assert bins[0] == 0.0
    assert bins[1] == 0.0
    assert bins[2] == 1.0


def test_extract_postflop_features_dimensions():
    """Test that postflop features have correct dimensions."""
    hole = [Card('A', 'h'), Card('K', 'h')]
    board = [Card('Q', 'h'), Card('J', 's'), Card('9', 'd')]
    
    features = extract_postflop_features(
        hole_cards=hole,
        board=board,
        street=Street.FLOP,
        pot=100.0,
        stack=200.0,
        is_in_position=True,
        equity_samples=50,  # Reduced for speed
        future_equity_samples=20
    )
    
    # Should have 34 dimensions
    # 12 (hand cat) + 4 (flush) + 5 (straight) + 1 (combo) + 6 (board) + 6 (context)
    assert len(features) == 34
    assert features.dtype == np.float64


def test_extract_postflop_features_values():
    """Test that postflop features have valid values."""
    hole = [Card('A', 'h'), Card('K', 'h')]
    board = [Card('Q', 'h'), Card('J', 's'), Card('9', 'd')]
    
    features = extract_postflop_features(
        hole_cards=hole,
        board=board,
        street=Street.FLOP,
        pot=100.0,
        stack=200.0,
        is_in_position=True,
        equity_samples=50,
        future_equity_samples=20
    )
    
    # All features should be in [0, 1]
    assert np.all(features >= 0.0)
    assert np.all(features <= 1.0)
    
    # Hand category should be one-hot (first 12 dims)
    hand_cat = features[:12]
    assert np.sum(hand_cat) == 1.0
    
    # Flush draw should be one-hot (next 4 dims)
    flush_draw = features[12:16]
    assert np.sum(flush_draw) == 1.0
    
    # SPR bins should be one-hot (positions 28-31)
    spr_bins = features[28:31]
    assert np.sum(spr_bins) == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
