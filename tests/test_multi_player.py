"""Tests for multi-player (6-max) support."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import Position, BucketConfig, MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.utils.positions import (
    get_positions_for_player_count,
    get_num_opponents,
    calculate_pot_for_players,
    is_position_in_position,
    get_position_name,
    validate_num_players
)


def test_position_enum():
    """Test Position enum basics."""
    assert Position.BTN.value == 0
    assert Position.SB.value == 1
    assert Position.BB.value == 2
    assert Position.UTG.value == 3
    assert Position.MP.value == 4
    assert Position.CO.value == 5
    print("✓ Position enum values correct")


def test_position_from_player_count():
    """Test position assignment for different player counts."""
    # Heads-up (2 players)
    pos = Position.from_player_count_and_seat(2, 0)
    assert pos == Position.BTN
    pos = Position.from_player_count_and_seat(2, 1)
    assert pos == Position.BB
    print("✓ Heads-up positions correct")
    
    # 6-max
    positions_6max = [
        Position.BTN, Position.SB, Position.BB,
        Position.UTG, Position.MP, Position.CO
    ]
    for i, expected_pos in enumerate(positions_6max):
        pos = Position.from_player_count_and_seat(6, i)
        assert pos == expected_pos, f"Expected {expected_pos} at seat {i}, got {pos}"
    print("✓ 6-max positions correct")


def test_is_in_position():
    """Test position detection (IP vs OOP)."""
    # BTN and CO are always in position
    assert Position.BTN.is_in_position_postflop(6) == True
    assert Position.CO.is_in_position_postflop(6) == True
    
    # SB and BB are always out of position
    assert Position.SB.is_in_position_postflop(6) == False
    assert Position.BB.is_in_position_postflop(6) == False
    
    # MP is in position in 6-max
    assert Position.MP.is_in_position_postflop(6) == True
    assert Position.MP.is_in_position_postflop(5) == True
    
    print("✓ Position detection (IP/OOP) correct")


def test_get_positions_for_player_count():
    """Test getting position lists."""
    # 2-player
    positions = get_positions_for_player_count(2)
    assert len(positions) == 2
    assert positions == [Position.BTN, Position.BB]
    
    # 6-max
    positions = get_positions_for_player_count(6)
    assert len(positions) == 6
    assert Position.BTN in positions
    assert Position.SB in positions
    assert Position.BB in positions
    assert Position.UTG in positions
    assert Position.MP in positions
    assert Position.CO in positions
    
    print("✓ Position list generation correct")


def test_get_num_opponents():
    """Test opponent count calculation."""
    assert get_num_opponents(2) == 1
    assert get_num_opponents(3) == 2
    assert get_num_opponents(6) == 5
    print("✓ Opponent count calculation correct")


def test_calculate_pot():
    """Test pot calculation for different player counts."""
    # Standard blinds
    pot = calculate_pot_for_players(2, 1.0, 2.0)
    assert pot == 3.0  # SB + BB
    
    pot = calculate_pot_for_players(6, 1.0, 2.0)
    assert pot == 3.0  # SB + BB (same for all)
    
    print("✓ Pot calculation correct")


def test_validate_num_players():
    """Test num_players validation."""
    # Valid values
    for n in [2, 3, 4, 5, 6]:
        validate_num_players(n)  # Should not raise
    
    # Invalid values
    try:
        validate_num_players(1)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    
    try:
        validate_num_players(7)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    
    print("✓ Num players validation correct")


def test_bucket_config_with_num_players():
    """Test BucketConfig with num_players parameter."""
    # Default (2 players)
    config = BucketConfig()
    assert config.num_players == 2
    
    # 6-max
    config = BucketConfig(num_players=6)
    assert config.num_players == 6
    
    print("✓ BucketConfig num_players field correct")


def test_mccfr_config_with_num_players():
    """Test MCCFRConfig with num_players parameter."""
    # Default (2 players)
    config = MCCFRConfig()
    assert config.num_players == 2
    
    # 6-max
    config = MCCFRConfig(num_players=6)
    assert config.num_players == 6
    
    print("✓ MCCFRConfig num_players field correct")


def test_bucketing_with_multi_player():
    """Test that bucketing works with different player counts."""
    # Create bucketing for 6-max
    config = BucketConfig(
        k_preflop=8,  # Small for testing
        k_flop=8,
        k_turn=8,
        k_river=8,
        num_samples=100,  # Very small for fast testing
        num_players=6
    )
    
    bucketing = HandBucketing(config)
    # Just verify it initializes without error
    assert bucketing.config.num_players == 6
    
    print("✓ HandBucketing with 6 players initializes correctly")


def test_position_names():
    """Test position name retrieval."""
    assert get_position_name(Position.BTN) == "BTN"
    assert get_position_name(Position.SB) == "SB"
    assert get_position_name(Position.BB) == "BB"
    assert get_position_name(Position.UTG) == "UTG"
    assert get_position_name(Position.MP) == "MP"
    assert get_position_name(Position.CO) == "CO"
    print("✓ Position names correct")


if __name__ == "__main__":
    print("Testing multi-player (6-max) support...")
    print()
    
    test_position_enum()
    print()
    
    test_position_from_player_count()
    print()
    
    test_is_in_position()
    print()
    
    test_get_positions_for_player_count()
    print()
    
    test_get_num_opponents()
    print()
    
    test_calculate_pot()
    print()
    
    test_validate_num_players()
    print()
    
    test_bucket_config_with_num_players()
    print()
    
    test_mccfr_config_with_num_players()
    print()
    
    test_bucketing_with_multi_player()
    print()
    
    test_position_names()
    print()
    
    print("All multi-player tests passed! ✓")
