"""State encoding for MCCFR."""

from typing import Tuple, List
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
        betting_history: str
    ) -> str:
        """Encode information set as a string key."""
        # Get bucket for current hand
        bucket = self.bucketing.get_bucket(hole_cards, board, street)
        
        # Create infoset key
        infoset = f"{street.name}:{bucket}:{betting_history}"
        return infoset
    
    def encode_history(self, actions: List[str]) -> str:
        """Encode betting history as a string."""
        return ".".join(actions)
    
    def decode_history(self, history: str) -> List[str]:
        """Decode betting history from string."""
        if not history:
            return []
        return history.split(".")


def create_infoset_key(street: Street, bucket: int, history: str) -> str:
    """Create information set key."""
    return f"{street.name}:{bucket}:{history}"


def parse_infoset_key(infoset: str) -> Tuple[str, int, str]:
    """Parse information set key."""
    parts = infoset.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid infoset key: {infoset}")
    
    street_name = parts[0]
    bucket = int(parts[1])
    history = parts[2]
    
    return street_name, bucket, history
