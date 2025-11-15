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


class Position(Enum):
    """Player positions for 6-max poker.
    
    Position values indicate order relative to button:
    - BTN (Button): 0 - Best position, acts last postflop
    - SB (Small Blind): 1 - Acts first postflop (worst position)
    - BB (Big Blind): 2 - Acts second postflop
    - UTG (Under The Gun): 3 - First to act preflop (after blinds)
    - MP (Middle Position): 4 - Middle position
    - CO (Cutoff): 5 - Second best position, one before button
    
    For heads-up (2-player), only BTN and BB are used:
    - BTN acts first preflop, last postflop (SB+BTN combined)
    - BB acts last preflop, first postflop
    """
    BTN = 0  # Button
    SB = 1   # Small Blind
    BB = 2   # Big Blind  
    UTG = 3  # Under The Gun
    MP = 4   # Middle Position
    CO = 5   # Cutoff
    
    @classmethod
    def from_player_count_and_seat(cls, num_players: int, seat_offset: int) -> "Position":
        """Get position from number of players and seat offset from button.
        
        Args:
            num_players: Total number of players (2-6)
            seat_offset: Seats from button (0=BTN, 1=SB/next, etc.)
            
        Returns:
            Position enum value
        """
        if num_players == 2:
            # Heads-up: BTN (0) and BB (1)
            return cls.BTN if seat_offset == 0 else cls.BB
        elif num_players == 3:
            # 3-max: BTN, SB, BB
            positions = [cls.BTN, cls.SB, cls.BB]
            return positions[seat_offset % 3]
        elif num_players == 4:
            # 4-max: BTN, SB, BB, CO
            positions = [cls.BTN, cls.SB, cls.BB, cls.CO]
            return positions[seat_offset % 4]
        elif num_players == 5:
            # 5-max: BTN, SB, BB, UTG, CO
            positions = [cls.BTN, cls.SB, cls.BB, cls.UTG, cls.CO]
            return positions[seat_offset % 5]
        elif num_players == 6:
            # 6-max: BTN, SB, BB, UTG, MP, CO (full lineup)
            positions = [cls.BTN, cls.SB, cls.BB, cls.UTG, cls.MP, cls.CO]
            return positions[seat_offset % 6]
        else:
            raise ValueError(f"Unsupported number of players: {num_players}. Must be 2-6.")
    
    def is_in_position_postflop(self, num_players: int) -> bool:
        """Check if this position is 'in position' (IP) postflop.
        
        In position means acting after most opponents postflop.
        
        Args:
            num_players: Total number of players
            
        Returns:
            True if position is considered IP postflop
        """
        # CO and BTN are always in position
        if self in [Position.CO, Position.BTN]:
            return True
        # MP is in position in 6-max
        if self == Position.MP and num_players >= 5:
            return True
        # Other positions (SB, BB, UTG) are out of position
        return False


class ActionType(Enum):
    """Available action types."""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALLIN = "allin"
    # Quick bet actions that use predefined UI buttons (½ POT, POT) + confirmation
    BET_HALF_POT = "bet_half_pot"  # Click "½ POT" button, then "Miser" (confirm)
    BET_POT = "bet_pot"            # Click "POT" button, then "Miser" (confirm)


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
class PlayerSeatState:
    """State of a player seat with stable identity tracking.
    
    This structure helps distinguish between:
    - Canonical player name (stable throughout the hand)
    - Overlay text (action bubble that may show "Call", "Bet", etc. instead of name)
    """
    seat_index: int
    canonical_name: Optional[str] = None  # Real player name, stable throughout hand
    overlay_text: Optional[str] = None  # Current text in name/action region
    last_action: Optional[ActionType] = None
    last_action_amount: Optional[float] = None
    
    def update_from_ocr(self, raw_text: str, action_keywords: set) -> Optional['GameEvent']:
        """Update seat state from OCR text and potentially create an action event.
        
        Args:
            raw_text: Raw text from name/action region
            action_keywords: Set of action keywords to check against
            
        Returns:
            GameEvent if an action was detected, None otherwise
        """
        from holdem.vision.chat_parser import GameEvent, EventSource
        from datetime import datetime
        
        self.overlay_text = raw_text
        raw_lower = raw_text.lower().strip()
        
        # Check if this is an action keyword (not a player name)
        if raw_lower in action_keywords or any(kw in raw_lower for kw in action_keywords):
            # This is an action overlay, not a name
            # Don't update canonical_name
            # Parse the action and create event if we have a canonical name
            if self.canonical_name:
                return self._parse_action_overlay(raw_text)
            return None
        else:
            # This looks like a player name
            if not self.canonical_name:
                # First time seeing this player
                self.canonical_name = raw_text
            elif self.canonical_name.lower() != raw_lower:
                # Name changed - could be truncation or OCR error
                # Use edit distance to decide if it's the same player
                if self._is_similar_name(self.canonical_name, raw_text):
                    # Probably same player, keep original name
                    pass
                else:
                    # Different player took this seat
                    self.canonical_name = raw_text
            return None
    
    def _parse_action_overlay(self, overlay_text: str) -> Optional['GameEvent']:
        """Parse action from overlay text like 'Call 850', 'Bet 2055', 'Check', etc."""
        from holdem.vision.chat_parser import GameEvent, EventSource
        from datetime import datetime
        import re
        
        overlay_lower = overlay_text.lower().strip()
        
        # Pattern matching for actions
        if 'fold' in overlay_lower:
            self.last_action = ActionType.FOLD
            return GameEvent(
                event_type="action",
                player=self.canonical_name,
                action=ActionType.FOLD,
                sources=[EventSource.VISION],
                timestamp=datetime.now()
            )
        
        if 'check' in overlay_lower:
            self.last_action = ActionType.CHECK
            return GameEvent(
                event_type="action",
                player=self.canonical_name,
                action=ActionType.CHECK,
                sources=[EventSource.VISION],
                timestamp=datetime.now()
            )
        
        # Match "Call 850" or "Call" with amount
        call_match = re.search(r'call\s*([\d,\.]+)?', overlay_lower)
        if call_match:
            amount = None
            if call_match.group(1):
                amount = float(call_match.group(1).replace(',', ''))
            self.last_action = ActionType.CALL
            self.last_action_amount = amount
            return GameEvent(
                event_type="action",
                player=self.canonical_name,
                action=ActionType.CALL,
                amount=amount,
                sources=[EventSource.VISION],
                timestamp=datetime.now()
            )
        
        # Match "Bet 2055" or "Bet" with amount
        bet_match = re.search(r'bet\s*([\d,\.]+)?', overlay_lower)
        if bet_match:
            amount = None
            if bet_match.group(1):
                amount = float(bet_match.group(1).replace(',', ''))
            self.last_action = ActionType.BET
            self.last_action_amount = amount
            return GameEvent(
                event_type="action",
                player=self.canonical_name,
                action=ActionType.BET,
                amount=amount,
                sources=[EventSource.VISION],
                timestamp=datetime.now()
            )
        
        # Match "Raise to 4736" or "Raise 4736"
        raise_match = re.search(r'raise\s*(?:to\s*)?([\d,\.]+)?', overlay_lower)
        if raise_match:
            amount = None
            if raise_match.group(1):
                amount = float(raise_match.group(1).replace(',', ''))
            self.last_action = ActionType.RAISE
            self.last_action_amount = amount
            return GameEvent(
                event_type="action",
                player=self.canonical_name,
                action=ActionType.RAISE,
                amount=amount,
                sources=[EventSource.VISION],
                timestamp=datetime.now()
            )
        
        # Match "All-in" or "All in"
        if 'all' in overlay_lower and 'in' in overlay_lower:
            self.last_action = ActionType.ALLIN
            return GameEvent(
                event_type="action",
                player=self.canonical_name,
                action=ActionType.ALLIN,
                sources=[EventSource.VISION],
                timestamp=datetime.now()
            )
        
        return None
    
    def _is_similar_name(self, name1: str, name2: str) -> bool:
        """Check if two names are similar (for handling OCR errors/truncation).
        
        This method tries to distinguish between:
        - Truncation: "hilanderjojo" vs "hilanderj" -> similar
        - Different players: "player1" vs "player2" -> not similar
        """
        # Simple similarity check - could use Levenshtein distance
        name1_lower = name1.lower().strip()
        name2_lower = name2.lower().strip()
        
        # If names are identical, they're similar
        if name1_lower == name2_lower:
            return True
        
        # Check if one is prefix of other (for truncation)
        # The shorter must be at least 70% of the longer
        if name1_lower.startswith(name2_lower) or name2_lower.startswith(name1_lower):
            shorter_len = min(len(name1_lower), len(name2_lower))
            longer_len = max(len(name1_lower), len(name2_lower))
            if shorter_len >= longer_len * 0.7:
                return True
        
        # For other cases (not prefix match), be very conservative
        # This avoids false positives like "player1" vs "player2"
        return False


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
    last_action: Optional[ActionType] = None  # Last action taken by this player


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
    last_valid_hero_cards: Optional[List[Card]] = None  # Cache of hero cards for current hand
    hand_id: Optional[str] = None  # Unique ID for current hand (reset triggers hero cards cache clear)
    
    # State machine flags for robust vision/decision making
    frame_has_showdown_label: bool = False  # True if current frame has "Won X,XXX" labels
    hero_active: bool = True  # True if hero is still active in the hand (not folded)
    hand_in_progress: bool = True  # True if a hand is currently being played
    state_inconsistent: bool = False  # True if state appears inconsistent (pot regression, etc.)
    last_pot: float = 0.0  # Track previous pot to detect regressions
    
    @property
    def num_players(self) -> int:
        return len([p for p in self.players if not p.folded])
    
    @property
    def active_players(self) -> List[PlayerState]:
        return [p for p in self.players if not p.folded]
    
    def get_hero_cards(self) -> Optional[List[Card]]:
        """Get hero cards, using cache if current cards are not available.
        
        Returns hero cards from:
        1. Current hero player's hole_cards if available
        2. Cached last_valid_hero_cards if current not available
        3. None if neither available
        """
        if self.hero_position is not None and self.hero_position < len(self.players):
            hero = self.players[self.hero_position]
            if hero.hole_cards and len(hero.hole_cards) > 0:
                # Update cache with current cards
                self.last_valid_hero_cards = hero.hole_cards
                return hero.hole_cards
        
        # Fallback to cached cards
        return self.last_valid_hero_cards
    
    def reset_hand(self):
        """Reset state for a new hand - clears hero cards cache and resets flags."""
        self.last_valid_hero_cards = None
        self.hand_id = None
        self.hero_active = True
        self.hand_in_progress = True
        self.frame_has_showdown_label = False
        self.state_inconsistent = False


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
    num_players: int = 2  # Number of players (2-6); affects position-aware features


@dataclass
class MCCFRConfig:
    """Configuration for MCCFR training."""
    num_iterations: int = 2500000
    checkpoint_interval: int = 100000
    discount_factor: float = 1.0  # CFR+ uses adaptive discount
    exploration_epsilon: float = 0.6  # For outcome sampling (static value if epsilon_schedule not provided)
    
    # Multi-player configuration
    num_players: int = 2  # Number of players (2-6). Default: 2 (heads-up)
    
    # Epsilon schedule - list of (iteration, epsilon) tuples for step-based decay
    # Example: [(0, 0.6), (1000000, 0.3), (2000000, 0.1)]
    epsilon_schedule: Optional[List[Tuple[int, float]]] = None
    
    # Linear MCCFR parameters
    use_linear_weighting: bool = True  # Use Linear MCCFR (weighting ∝ t)
    discount_interval: int = 1000  # Apply discounting every N iterations
    
    # Discount mode: "none", "static", or "dcfr"
    # - "none": No discounting (α=1.0, β=1.0)
    # - "static": Use fixed regret_discount_alpha and strategy_discount_beta
    # - "dcfr": Use DCFR/CFR+ adaptive discounting (recommended)
    discount_mode: str = "dcfr"
    
    # Static discount factors (used when discount_mode="static")
    regret_discount_alpha: float = 1.0  # Regret discount factor (α)
    strategy_discount_beta: float = 1.0  # Strategy discount factor (β)
    
    # DCFR parameters (used when discount_mode="dcfr")
    # Based on CFR+ paper: https://arxiv.org/abs/1407.5042
    # α = (t + discount_interval) / (t + 2*discount_interval)  for regrets
    # β = t / (t + discount_interval)  for strategy
    # Additionally, reset negative regrets to 0 (CFR+ property)
    dcfr_reset_negative_regrets: bool = True  # Reset negative regrets to 0 on discount (CFR+ behavior)
    
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
    
    # Chunked training parameters
    enable_chunked_training: bool = False  # Enable chunked training mode (process restart after each chunk)
    chunk_size_iterations: Optional[int] = None  # Number of iterations per chunk (e.g., 100000)
    chunk_size_minutes: Optional[float] = None  # Time duration per chunk in minutes (e.g., 60.0 for 1 hour)
    chunk_restart_delay_seconds: float = 5.0  # Delay between chunk restarts to allow RAM to clear (default: 5 seconds)
    
    # Infoset encoding parameters (Pluribus parity)
    include_action_history_in_infoset: bool = True  # Include street-based action history in infoset encoding
    
    # Storage mode for regrets and strategies
    # - "dense": Standard dict-based storage (default, backward compatible)
    # - "compact": Numpy-based compact storage (40-50% memory savings)
    storage_mode: str = "dense"  # Storage backend: "dense" or "compact"
    

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
    
    # Public card sampling (board sampling) - Pluribus technique
    # This reduces variance in real-time subgame solving by sampling multiple future boards
    enable_public_card_sampling: bool = False  # Enable/disable public card sampling (for ablation tests)
    num_future_boards_samples: int = 1  # Number of future board samples (1 = disabled, 10-50 recommended)
    samples_per_solve: int = 1  # DEPRECATED: Use num_future_boards_samples instead (kept for backward compatibility)
    sampling_mode: str = "uniform"  # Sampling mode: "uniform" (uniform sampling, current implementation) or "weighted" (future: equity-weighted)
    max_samples_warning_threshold: int = 100  # Warn if num_future_boards_samples exceeds this (performance concern)
    
    # Leaf continuation strategies (k=4 policies at leaves)
    use_leaf_policies: bool = False  # Enable multiple leaf policies (blueprint/fold-biased/call-biased/raise-biased)
    leaf_policy_default: str = "blueprint"  # Default leaf policy: "blueprint", "fold_biased", "call_biased", "raise_biased"
    
    # Unsafe search from round start
    resolve_from_round_start: bool = False  # Start re-solve at beginning of current round, freeze only our actions
    
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
    
    def get_effective_num_samples(self) -> int:
        """Get effective number of board samples to use.
        
        Priority:
        1. If enable_public_card_sampling is False, return 1 (disabled)
        2. Otherwise, use num_future_boards_samples if > 1
        3. Fall back to samples_per_solve for backward compatibility
        
        Returns:
            Effective number of board samples (1 = disabled, >1 = enabled)
        """
        if not self.enable_public_card_sampling:
            return 1
        
        # Use num_future_boards_samples if explicitly set
        if self.num_future_boards_samples > 1:
            return self.num_future_boards_samples
        
        # Fall back to samples_per_solve for backward compatibility
        return max(1, self.samples_per_solve)


@dataclass
class VisionConfig:
    """Configuration for vision system."""
    window_title: str = ""
    screen_region: Optional[Tuple[int, int, int, int]] = None  # (x, y, width, height)
    detection_method: str = "orb"  # 'orb' or 'akaze'
    card_recognition_method: str = "template"  # 'template' or 'cnn'
    ocr_backend: str = "paddleocr"  # 'paddleocr', 'easyocr', or 'pytesseract'
    confidence_threshold: float = 0.8


@dataclass
class RTResolverConfig:
    """Configuration for real-time depth-limited resolver."""
    max_depth: int = 1  # Number of streets to look ahead (1 = current street only)
    time_ms: int = 80  # Time budget per decision in milliseconds
    min_iterations: int = 400  # Minimum CFR iterations
    max_iterations: int = 1200  # Maximum CFR iterations
    samples_per_leaf: int = 10  # Number of rollout samples per leaf node
    action_set_mode: str = "balanced"  # Action set mode: tight, balanced, or loose
    use_cfv: bool = True  # Use blueprint CFV at leaves if available
    kl_weight: float = 0.5  # KL divergence weight toward blueprint
    
    # Metrics tracking
    track_metrics: bool = True  # Track solve time, iterations, EV delta
    
    # Public card sampling (board sampling) - Pluribus technique
    # This reduces variance in real-time subgame solving by sampling multiple future boards
    enable_public_card_sampling: bool = False  # Enable/disable public card sampling (for ablation tests)
    num_future_boards_samples: int = 1  # Number of future board samples (1 = disabled, 10-50 recommended)
    samples_per_solve: int = 1  # DEPRECATED: Use num_future_boards_samples instead (kept for backward compatibility)
    sampling_mode: str = "uniform"  # Sampling mode: "uniform" (current) or "weighted" (future)
    max_samples_warning_threshold: int = 100  # Warn if num_future_boards_samples exceeds this
    
    # Leaf continuation strategies (k=4 policies at leaves)
    use_leaf_policies: bool = False  # Enable multiple leaf policies at leaves
    leaf_policy_default: str = "blueprint"  # Default leaf policy
    
    # Unsafe search from round start
    resolve_from_round_start: bool = False  # Start re-solve at beginning of current round
    
    def get_effective_num_samples(self) -> int:
        """Get effective number of board samples to use.
        
        Priority:
        1. If enable_public_card_sampling is False, return 1 (disabled)
        2. Otherwise, use num_future_boards_samples if > 1
        3. Fall back to samples_per_solve for backward compatibility
        
        Returns:
            Effective number of board samples (1 = disabled, >1 = enabled)
        """
        if not self.enable_public_card_sampling:
            return 1
        
        # Use num_future_boards_samples if explicitly set
        if self.num_future_boards_samples > 1:
            return self.num_future_boards_samples
        
        # Fall back to samples_per_solve for backward compatibility
        return max(1, self.samples_per_solve)


@dataclass
class ControlConfig:
    """Configuration for action execution."""
    dry_run: bool = True
    confirm_every_action: bool = False
    min_action_delay_ms: int = 500
    i_understand_the_tos: bool = False
    enable_hotkeys: bool = True
    safe_click_enabled: bool = True  # Enable safe click verification for action buttons
