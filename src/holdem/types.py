"""Core data types for Texas Hold'em."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Tuple


class Street(Enum):
    """Game streets/rounds."""
    PREFLOP = 0
    FLOP = 1
    TURN = 2
    RIVER = 3


class ActionType(Enum):
    """Available action types."""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALLIN = "allin"


@dataclass
class Card:
    """Represents a playing card."""
    rank: str  # '2'-'9', 'T', 'J', 'Q', 'K', 'A'
    suit: str  # 'h', 'd', 'c', 's'
    
    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"
    
    @classmethod
    def from_string(cls, s: str) -> "Card":
        """Create card from string like 'Ah' or 'Ts'."""
        if len(s) != 2:
            raise ValueError(f"Invalid card string: {s}")
        return cls(rank=s[0], suit=s[1])


@dataclass
class Action:
    """Represents a poker action."""
    action_type: ActionType
    amount: float = 0.0  # For bets/raises
    
    def __str__(self) -> str:
        if self.amount > 0:
            return f"{self.action_type.value}({self.amount:.2f})"
        return self.action_type.value


@dataclass
class PlayerState:
    """State of a single player."""
    name: str
    stack: float
    bet_this_round: float = 0.0
    folded: bool = False
    all_in: bool = False
    position: int = 0  # 0=BTN, 1=SB, 2=BB, etc.
    hole_cards: Optional[List[Card]] = None


@dataclass
class TableState:
    """Complete state of the poker table."""
    street: Street
    pot: float
    board: List[Card] = field(default_factory=list)
    players: List[PlayerState] = field(default_factory=list)
    current_bet: float = 0.0
    small_blind: float = 1.0
    big_blind: float = 2.0
    button_position: int = 0
    
    @property
    def num_players(self) -> int:
        return len([p for p in self.players if not p.folded])
    
    @property
    def active_players(self) -> List[PlayerState]:
        return [p for p in self.players if not p.folded]


@dataclass
class HandHistory:
    """Record of a single hand."""
    hand_id: str
    players: List[str]
    actions: List[Tuple[str, Action]]  # (player_name, action)
    board: List[Card]
    winner: Optional[str] = None
    pot: float = 0.0


@dataclass
class BucketConfig:
    """Configuration for hand bucketing."""
    k_preflop: int = 24
    k_flop: int = 80
    k_turn: int = 80
    k_river: int = 64
    num_samples: int = 500000
    seed: int = 42


@dataclass
class MCCFRConfig:
    """Configuration for MCCFR training."""
    num_iterations: int = 2500000
    checkpoint_interval: int = 100000
    discount_factor: float = 1.0  # CFR+ uses adaptive discount
    exploration_epsilon: float = 0.6  # For outcome sampling
    
    # Linear MCCFR parameters
    use_linear_weighting: bool = True  # Use Linear MCCFR (weighting ∝ t)
    discount_interval: int = 1000  # Apply discounting every N iterations
    regret_discount_alpha: float = 1.0  # Regret discount factor (α)
    strategy_discount_beta: float = 1.0  # Strategy discount factor (β)
    
    # Dynamic pruning parameters (Pluribus paper values)
    enable_pruning: bool = True  # Enable dynamic pruning
    # Pluribus uses -300,000,000 as the regret threshold for pruning
    # Reference: "Superhuman AI for multiplayer poker" (Brown & Sandholm, 2019)
    PLURIBUS_PRUNING_THRESHOLD: float = -300_000_000.0
    pruning_threshold: float = PLURIBUS_PRUNING_THRESHOLD  # Regret threshold for pruning
    pruning_probability: float = 0.95  # Probability to skip iteration when below threshold
    

@dataclass
class SearchConfig:
    """Configuration for real-time search."""
    time_budget_ms: int = 80
    min_iterations: int = 100
    kl_divergence_weight: float = 1.0
    depth_limit: int = 1  # Number of streets to look ahead
    fallback_to_blueprint: bool = True


@dataclass
class VisionConfig:
    """Configuration for vision system."""
    window_title: str = ""
    screen_region: Optional[Tuple[int, int, int, int]] = None  # (x, y, width, height)
    detection_method: str = "orb"  # 'orb' or 'akaze'
    card_recognition_method: str = "template"  # 'template' or 'cnn'
    ocr_backend: str = "paddleocr"  # 'paddleocr' or 'pytesseract'
    confidence_threshold: float = 0.8


@dataclass
class ControlConfig:
    """Configuration for action execution."""
    dry_run: bool = True
    confirm_every_action: bool = False
    min_action_delay_ms: int = 500
    i_understand_the_tos: bool = False
    enable_hotkeys: bool = True
