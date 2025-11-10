"""Utility functions for multi-player position handling."""

from typing import List, Tuple
from holdem.types import Position


def get_positions_for_player_count(num_players: int) -> List[Position]:
    """Get list of positions for given player count.
    
    Args:
        num_players: Number of players (2-6)
        
    Returns:
        List of Position enums in order from button
        
    Raises:
        ValueError: If num_players not in range 2-6
    """
    if num_players == 2:
        return [Position.BTN, Position.BB]
    elif num_players == 3:
        return [Position.BTN, Position.SB, Position.BB]
    elif num_players == 4:
        return [Position.BTN, Position.SB, Position.BB, Position.CO]
    elif num_players == 5:
        return [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.CO]
    elif num_players == 6:
        return [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.MP, Position.CO]
    else:
        raise ValueError(f"Unsupported number of players: {num_players}. Must be 2-6.")


def get_num_opponents(num_players: int) -> int:
    """Get number of opponents for given player count.
    
    Args:
        num_players: Total number of players
        
    Returns:
        Number of opponents (num_players - 1)
    """
    return max(1, num_players - 1)


def calculate_pot_for_players(num_players: int, small_blind: float = 1.0, big_blind: float = 2.0) -> float:
    """Calculate starting pot for given number of players.
    
    For heads-up (2 players): SB + BB
    For 3+ players: SB + BB (other players don't post yet)
    
    Args:
        num_players: Number of players
        small_blind: Small blind amount
        big_blind: Big blind amount
        
    Returns:
        Starting pot size
    """
    # Standard: SB + BB regardless of player count
    return small_blind + big_blind


def is_position_in_position(position: Position, num_players: int) -> bool:
    """Check if position is 'in position' (IP) postflop.
    
    Args:
        position: Player position
        num_players: Total number of players
        
    Returns:
        True if position is IP postflop
    """
    return position.is_in_position_postflop(num_players)


def get_position_name(position: Position) -> str:
    """Get human-readable name for position.
    
    Args:
        position: Player position
        
    Returns:
        Position name (e.g., "BTN", "SB", "BB", etc.)
    """
    return position.name


def get_relative_position(hero_pos: int, villain_pos: int, num_players: int) -> int:
    """Get relative position of villain from hero's perspective.
    
    Args:
        hero_pos: Hero's position (0-indexed from button)
        villain_pos: Villain's position (0-indexed from button)
        num_players: Total number of players
        
    Returns:
        Relative position (0 = same position, 1 = one seat after hero, etc.)
    """
    return (villain_pos - hero_pos) % num_players


def get_preflop_action_order(num_players: int, button_pos: int = 0) -> List[int]:
    """Get preflop action order starting from UTG.
    
    Args:
        num_players: Number of players
        button_pos: Button position (default 0)
        
    Returns:
        List of player positions in preflop action order
    """
    if num_players == 2:
        # Heads-up: BTN acts first preflop, BB acts second
        return [(button_pos + 0) % 2, (button_pos + 1) % 2]
    else:
        # Multi-way: Start from player after BB (UTG)
        start_pos = (button_pos + 3) % num_players  # UTG is 3 positions after button
        return [(start_pos + i) % num_players for i in range(num_players)]


def get_postflop_action_order(num_players: int, button_pos: int = 0) -> List[int]:
    """Get postflop action order starting from SB/first to act.
    
    Args:
        num_players: Number of players
        button_pos: Button position (default 0)
        
    Returns:
        List of player positions in postflop action order
    """
    if num_players == 2:
        # Heads-up: BB acts first postflop, BTN acts second
        return [(button_pos + 1) % 2, (button_pos + 0) % 2]
    else:
        # Multi-way: Start from SB (first after button)
        start_pos = (button_pos + 1) % num_players
        return [(start_pos + i) % num_players for i in range(num_players)]


def validate_num_players(num_players: int) -> None:
    """Validate that number of players is supported.
    
    Args:
        num_players: Number of players to validate
        
    Raises:
        ValueError: If num_players not in range 2-6
    """
    if not (2 <= num_players <= 6):
        raise ValueError(f"Unsupported number of players: {num_players}. Must be 2-6.")
