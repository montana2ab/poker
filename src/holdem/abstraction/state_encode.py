"""State encoding for MCCFR."""

from typing import Tuple, List, Dict, Optional
from holdem.types import Card, Street, TableState
from holdem.abstraction.bucketing import HandBucketing


class StateEncoder:
    """Encodes game state for MCCFR."""
    
    def __init__(self, bucketing: HandBucketing):
        self.bucketing = bucketing
    
    def encode_infoset(
        self,
        hole_cards: List[Card],
        board: List[Card],
        street: Street,
        betting_history: str,
        pot: float = 100.0,
        stack: float = 200.0,
        is_in_position: bool = True
    ) -> Tuple[str, Street]:
        """Encode information set as a string key.
        
        Args:
            hole_cards: Player's hole cards
            board: Community cards
            street: Current street
            betting_history: Encoded betting history
            pot: Current pot size (for SPR calculation, default 100.0)
            stack: Player's stack (for SPR calculation, default 200.0)
            is_in_position: Whether player is in position (default True)
            
        Returns:
            Tuple of (infoset_key, street) to avoid fragile string parsing
        """
        # Get bucket for current hand with context
        bucket = self.bucketing.get_bucket(
            hole_cards, 
            board, 
            street,
            pot=pot,
            stack=stack,
            is_in_position=is_in_position
        )
        
        # Create infoset key
        infoset = f"{street.name}:{bucket}:{betting_history}"
        return infoset, street
    
    def encode_infoset_from_state(
        self,
        hole_cards: List[Card],
        state: TableState,
        betting_history: str
    ) -> Tuple[str, Street]:
        """Encode information set from a complete TableState.
        
        This is a convenience method that extracts necessary values from TableState.
        
        Args:
            hole_cards: Player's hole cards
            state: Complete table state
            betting_history: Encoded betting history
            
        Returns:
            Tuple of (infoset_key, street)
        """
        # Use effective_stack if available, otherwise use pot-based SPR estimation
        stack = state.effective_stack if state.effective_stack > 0 else state.pot * 2.0
        
        return self.encode_infoset(
            hole_cards=hole_cards,
            board=state.board,
            street=state.street,
            betting_history=betting_history,
            pot=state.pot,
            stack=stack,
            is_in_position=state.is_in_position
        )
    
    def encode_history(self, actions: List[str]) -> str:
        """Encode betting history as a string."""
        return ".".join(actions)
    
    def decode_history(self, history: str) -> List[str]:
        """Decode betting history from string."""
        if not history:
            return []
        return history.split(".")


def create_infoset_key(street: Street, bucket: int, history: str) -> Tuple[str, Street]:
    """Create information set key.
    
    Args:
        street: Current street
        bucket: Bucket number
        history: Betting history
        
    Returns:
        Tuple of (infoset_key, street)
    """
    infoset = f"{street.name}:{bucket}:{history}"
    return infoset, street


def parse_infoset_key(infoset: str) -> Tuple[str, int, str]:
    """Parse information set key."""
    parts = infoset.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid infoset key: {infoset}")
    
    street_name = parts[0]
    bucket = int(parts[1])
    history = parts[2]
    
    return street_name, bucket, history
