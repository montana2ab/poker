"""State encoding for MCCFR."""

from typing import Tuple, List, Dict, Optional
from holdem.types import Card, Street, TableState
from holdem.abstraction.bucketing import HandBucketing

# Infoset version constant
INFOSET_VERSION = "v2"


class StateEncoder:
    """Encodes game state for MCCFR."""
    
    def __init__(self, bucketing: HandBucketing):
        self.bucketing = bucketing
    
    def encode_action_history(self, actions: List[str]) -> str:
        """Encode action history to standardized format.
        
        Converts action list to abbreviated format:
        - "fold" -> "F"
        - "check_call" or "check" -> "C"
        - "bet_0.33p" -> "B33"
        - "bet_0.5p" -> "B50"
        - "bet_0.66p" -> "B66"
        - "bet_0.75p" -> "B75"
        - "bet_1.0p" -> "B100"
        - "bet_1.5p" -> "B150"
        - "bet_2.0p" -> "B200"
        - "all_in" -> "A"
        
        Args:
            actions: List of action strings
            
        Returns:
            Abbreviated action sequence joined with "-" (e.g., "C-B75-C")
        """
        if not actions:
            return ""
        
        encoded = []
        for action in actions:
            if action == "fold":
                encoded.append("F")
            elif action in ["check_call", "check", "call"]:
                encoded.append("C")
            elif action == "all_in":
                encoded.append("A")
            elif action.startswith("bet_") or action.startswith("raise_"):
                # Extract pot fraction from action string
                # Examples: "bet_0.33p", "bet_0.5p", "bet_1.0p", "bet_1.5p"
                try:
                    # Remove "bet_" or "raise_" prefix and "p" suffix
                    action_cleaned = action.replace("bet_", "").replace("raise_", "").replace("p", "")
                    fraction = float(action_cleaned)
                    # Convert to percentage (0.33 -> 33, 1.0 -> 100, 1.5 -> 150)
                    percentage = int(fraction * 100)
                    encoded.append(f"B{percentage}")
                except (ValueError, IndexError):
                    # Fallback for unexpected format
                    encoded.append("B100")
            else:
                # Unknown action, use generic bet marker
                encoded.append("B100")
        
        return "-".join(encoded)
    
    def encode_infoset(
        self,
        hole_cards: List[Card],
        board: List[Card],
        street: Street,
        betting_history: str,
        pot: float = 100.0,
        stack: float = 200.0,
        is_in_position: bool = True,
        use_versioning: bool = True
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
            use_versioning: Whether to include version prefix (default True)
            
        Returns:
            Tuple of (infoset_key, street) to avoid fragile string parsing
            
        Note:
            With versioning (default): "v2:FLOP:12:C-B75-C"
            Without versioning (legacy): "FLOP:12:check_call.bet_0.75p.check_call"
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
        
        # Create infoset key with optional versioning
        if use_versioning:
            # New format: v2:STREET:bucket:action_seq
            # Position is implicit in action sequence order
            infoset = f"{INFOSET_VERSION}:{street.name}:{bucket}:{betting_history}"
        else:
            # Legacy format: STREET:bucket:history
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


def create_infoset_key(street: Street, bucket: int, history: str, use_versioning: bool = True) -> Tuple[str, Street]:
    """Create information set key.
    
    Args:
        street: Current street
        bucket: Bucket number
        history: Betting history
        use_versioning: Whether to include version prefix (default True)
        
    Returns:
        Tuple of (infoset_key, street)
    """
    if use_versioning:
        infoset = f"{INFOSET_VERSION}:{street.name}:{bucket}:{history}"
    else:
        infoset = f"{street.name}:{bucket}:{history}"
    return infoset, street


def parse_infoset_key(infoset: str) -> Tuple[str, int, str]:
    """Parse information set key (supports both versioned and legacy formats).
    
    Args:
        infoset: Infoset string (e.g., "v2:FLOP:12:C-B75-C" or "FLOP:12:check_call.bet_0.75p")
        
    Returns:
        Tuple of (street_name, bucket, history)
        
    Raises:
        ValueError: If infoset format is invalid
    """
    # Check if infoset has version prefix
    if infoset.startswith("v") and ":" in infoset:
        # Try to parse as versioned format: v2:STREET:bucket:history
        parts = infoset.split(":", 3)
        if len(parts) == 4:
            # Skip version prefix
            version = parts[0]
            street_name = parts[1]
            try:
                bucket = int(parts[2])
                history = parts[3]
                return street_name, bucket, history
            except ValueError:
                pass  # Fall through to legacy parsing or error
    
    # Legacy format: STREET:bucket:history (no version prefix)
    parts = infoset.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid infoset key: {infoset}")
    
    street_name = parts[0]
    bucket = int(parts[1])
    history = parts[2]
    
    return street_name, bucket, history


def get_infoset_version(infoset: str) -> Optional[str]:
    """Extract version from infoset string.
    
    Args:
        infoset: Infoset string
        
    Returns:
        Version string (e.g., "v2") or None for legacy format
    """
    if infoset.startswith("v") and ":" in infoset:
        parts = infoset.split(":", 1)
        if len(parts) >= 1 and parts[0].startswith("v"):
            return parts[0]
    return None
