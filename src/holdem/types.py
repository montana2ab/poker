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
    hero_position: Optional[int] = None  # Position of hero player (0-N)
    is_in_position: bool = False  # Whether hero is in position postflop
    to_call: float = 0.0  # Amount hero needs to call
    effective_stack: float = 0.0  # Min(hero_stack, max_opponent_stack)
    spr: float = 0.0  # Stack-to-pot ratio (effective_stack / pot)
    
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
    exploration_epsilon: float = 0.6  # For outcome sampling (static value if epsilon_schedule not provided)
    
    # Epsilon schedule - list of (iteration, epsilon) tuples for step-based decay
    # Example: [(0, 0.6), (1000000, 0.3), (2000000, 0.1)]
    epsilon_schedule: Optional[List[Tuple[int, float]]] = None
    
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
    
    # Time-budget based training (alternative to num_iterations)
    time_budget_seconds: Optional[float] = None  # Run for specified time (e.g., 8 days = 691200s)
    snapshot_interval_seconds: float = 600  # Save snapshots every X seconds (default: 10 minutes)
    
    # Logging and I/O optimization
    tensorboard_log_interval: int = 1000  # Log to TensorBoard every N iterations (default: 1000 to reduce overhead)
    
    # Preflop equity optimization
    preflop_equity_samples: int = 100  # Number of equity samples for preflop (0 to disable during training)
    
    # Multiprocessing parameters
    num_workers: int = 1  # Number of parallel worker processes (1 = single process, 0 = use all CPU cores)
    batch_size: int = 100  # Number of iterations per worker batch
    
    # Adaptive epsilon schedule parameters
    adaptive_epsilon_enabled: bool = False  # Enable adaptive epsilon scheduling based on performance
    adaptive_target_ips: float = 35.0  # Target iterations per second for the machine
    adaptive_window_merges: int = 10  # Number of recent merges to average for IPS calculation
    adaptive_min_infoset_growth: float = 10.0  # Minimum new infosets per 1000 iterations
    adaptive_early_shift_ratio: float = 0.1  # Allow epsilon decrease up to 10% earlier if criteria exceeded
    adaptive_extension_ratio: float = 0.15  # Allow epsilon decrease delay up to 15% if criteria not met
    adaptive_force_after_ratio: float = 0.30  # Force epsilon decrease after 30% extension if never met
    

@dataclass
class SearchConfig:
    """Configuration for real-time search."""
    time_budget_ms: int = 80
    min_iterations: int = 100
    kl_weight: float = 1.0  # KL regularization weight toward blueprint strategy
    depth_limit: int = 1  # Number of streets to look ahead
    fallback_to_blueprint: bool = True
    num_workers: int = 1  # Number of parallel worker processes for real-time solving (1 = single process)
    
    # Street-based kl_weight configuration (flop/turn/river)
    kl_weight_flop: float = 0.30
    kl_weight_turn: float = 0.50
    kl_weight_river: float = 0.70
    kl_weight_oop_bonus: float = 0.10  # Additional weight when Out Of Position
    
    # Blueprint policy clipping (minimum probability before KL calculation)
    blueprint_clip_min: float = 1e-6
    
    # KL divergence statistics tracking
    track_kl_stats: bool = True
    kl_high_threshold: float = 0.3  # Threshold for "high KL" tracking
    
    # Optional: adaptive kl_weight to target KL divergence
    adaptive_kl_weight: bool = False
    target_kl_flop: float = 0.12
    target_kl_turn: float = 0.18
    target_kl_river: float = 0.25
    
    def get_kl_weight(self, street: Street, is_oop: bool = False) -> float:
        """Get kl_weight for a specific street and position.
        
        Args:
            street: Current game street
            is_oop: Whether player is out of position
            
        Returns:
            KL weight for the given street and position
        """
        # Use street-specific weights if on postflop streets
        if street == Street.FLOP:
            weight = self.kl_weight_flop
        elif street == Street.TURN:
            weight = self.kl_weight_turn
        elif street == Street.RIVER:
            weight = self.kl_weight_river
        else:  # PREFLOP
            weight = self.kl_weight
        
        # Add bonus if out of position
        if is_oop:
            weight += self.kl_weight_oop_bonus
        
        return weight
    
    # Backward compatibility alias
    @property
    def kl_divergence_weight(self) -> float:
        """Alias for kl_weight (backward compatibility)."""
        return self.kl_weight


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
