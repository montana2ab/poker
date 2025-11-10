"""MCCFR with outcome sampling."""

import numpy as np
from typing import List, Dict, Tuple
from holdem.types import Card, Street
from holdem.abstraction.actions import AbstractAction, ActionAbstraction
from holdem.abstraction.bucketing import HandBucketing
from holdem.abstraction.state_encode import StateEncoder
from holdem.mccfr.regrets import RegretTracker
from holdem.utils.rng import get_rng
from holdem.utils.logging import get_logger

logger = get_logger("mccfr.outcome_sampling")


class OutcomeSampler:
    """Monte Carlo CFR with outcome sampling."""
    
    def __init__(
        self,
        bucketing: HandBucketing,
        num_players: int = 2,
        epsilon: float = 0.6,
        use_linear_weighting: bool = True,
        enable_pruning: bool = True,
        pruning_threshold: float = -300_000_000.0,
        pruning_probability: float = 0.95
    ):
        self.bucketing = bucketing
        self.num_players = num_players
        self.epsilon = epsilon  # Exploration probability
        self.encoder = StateEncoder(bucketing)
        self.regret_tracker = RegretTracker()
        self.rng = get_rng()
        
        # Linear MCCFR parameters
        self.use_linear_weighting = use_linear_weighting
        
        # Dynamic pruning parameters
        self.enable_pruning = enable_pruning
        self.pruning_threshold = pruning_threshold
        self.pruning_probability = pruning_probability
    
    def set_epsilon(self, epsilon: float):
        """Update exploration epsilon.
        
        Args:
            epsilon: New epsilon value
        """
        self.epsilon = epsilon
    
    def sample_iteration(self, iteration: int) -> float:
        """Run one iteration of outcome sampling MCCFR."""
        # Sample hands for all players
        hands = self._deal_hands()
        
        # Run MCCFR recursion for each player
        utility_sum = 0.0
        for player in range(self.num_players):
            utility = self._cfr_recursive(
                hands=hands,
                history=[],
                street=Street.PREFLOP,
                board=[],
                pot=3.0,  # SB + BB
                player=player,
                reach_prob=1.0,
                sample_player=player,
                iteration=iteration
            )
            utility_sum += utility
        
        return utility_sum / self.num_players
    
    def _deal_hands(self) -> List[List[Card]]:
        """Deal hands for all players."""
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
        suits = ['h', 'd', 'c', 's']
        
        deck = [Card(rank, suit) for rank in ranks for suit in suits]
        self.rng.shuffle(deck)
        
        hands = []
        for i in range(self.num_players):
            hands.append([deck[i*2], deck[i*2+1]])
        
        return hands
    
    def _cfr_recursive(
        self,
        hands: List[List[Card]],
        history: List[str],
        street: Street,
        board: List[Card],
        pot: float,
        player: int,
        reach_prob: float,
        sample_player: int,
        iteration: int
    ) -> float:
        """CFR recursion with outcome sampling."""
        
        # Check for terminal states
        if self._is_terminal(history):
            return self._get_payoff(hands, history, board, pot, sample_player)
        
        # Get current player
        current_player = self._get_acting_player(history, self.num_players)
        
        # Get available actions based on street and position
        actions = self._get_available_actions(pot, street, history)
        
        # Create infoset with versioned encoding
        # Convert action history to abbreviated format (e.g., ["check_call", "bet_0.75p"] -> "C-B75")
        action_sequence = self.encoder.encode_action_history(history)
        infoset, _ = self.encoder.encode_infoset(
            hands[current_player],
            board,
            street,
            action_sequence,
            use_versioning=True  # Use new versioned format (v2)
        )
        
        # Dynamic pruning: skip iteration if conditions are met
        # Don't prune at river or terminal nodes
        # Note: Each infoset is visited at most once per iteration in outcome sampling,
        # so this check is not repeated unnecessarily within the same iteration.
        is_river = (street == Street.RIVER)
        if (self.enable_pruning and 
            not is_river and 
            current_player == sample_player and
            self.regret_tracker.should_prune(infoset, actions, self.pruning_threshold)):
            # Sample q ∈ [0,1) and skip with pruning_probability
            if self.rng.random() < self.pruning_probability:
                # Skip this iteration - return neutral utility
                return 0.0
        
        # Get current strategy
        strategy = self.regret_tracker.get_strategy(infoset, actions)
        
        # Linear weighting: use iteration number as weight
        weight = float(iteration) if self.use_linear_weighting else 1.0
        
        if current_player == sample_player:
            # Sample player: explore with epsilon-greedy
            if self.rng.random() < self.epsilon:
                # Explore: sample uniformly
                action_probs = {a: 1.0 / len(actions) for a in actions}
            else:
                # Exploit: use current strategy
                action_probs = strategy
            
            # Sample one action
            sampled_action = self.rng.choice(actions, p=[action_probs[a] for a in actions])
            
            # Recurse
            new_history = history + [sampled_action.value]
            utility = self._cfr_recursive(
                hands, new_history, street, board, pot,
                player, reach_prob, sample_player, iteration
            )
            
            # Update regrets with linear weighting
            action_utilities = {sampled_action: utility}
            for action in actions:
                if action != sampled_action:
                    action_utilities[action] = 0.0  # Not sampled
            
            expected_utility = utility  # Since we only sampled one action
            
            for action in actions:
                regret = action_utilities.get(action, 0.0) - expected_utility
                self.regret_tracker.update_regret(infoset, action, regret, weight)
            
            # Add to strategy sum with linear weighting
            strategy_weight = weight * reach_prob
            self.regret_tracker.add_strategy(infoset, strategy, strategy_weight)
            
            return utility
        
        else:
            # Opponent: sample according to strategy
            action_probs = [strategy[a] for a in actions]
            sampled_action = self.rng.choice(actions, p=action_probs)
            
            new_history = history + [sampled_action.value]
            new_reach_prob = reach_prob * strategy[sampled_action]
            
            return self._cfr_recursive(
                hands, new_history, street, board, pot,
                player, new_reach_prob, sample_player, iteration
            )
    
    def _is_terminal(self, history: List[str]) -> bool:
        """Check if history represents a terminal state."""
        if not history:
            return False
        
        # Simplified terminal detection
        if "fold" in history:
            return True
        
        # Both players checked or called
        if len(history) >= 2:
            if history[-1] in ["check_call", "check"] and history[-2] in ["check_call", "check"]:
                return True
        
        return False
    
    def _get_payoff(
        self,
        hands: List[List[Card]],
        history: List[str],
        board: List[Card],
        pot: float,
        player: int
    ) -> float:
        """Calculate payoff for terminal state."""
        # Simplified payoff calculation
        if "fold" in history:
            folder_idx = len([h for h in history if h != "fold"])
            if folder_idx == player:
                return -pot / 2
            else:
                return pot / 2
        
        # Showdown - would need actual hand evaluation
        return 0.0
    
    def _get_acting_player(self, history: List[str], num_players: int) -> int:
        """Get player to act based on history."""
        return len(history) % num_players
    
    def _get_available_actions(
        self,
        pot: float,
        street: Street = Street.PREFLOP,
        history: List[str] = None
    ) -> List[AbstractAction]:
        """Get available actions based on street and position.
        
        Args:
            pot: Current pot size
            street: Current game street
            history: Action history to infer position
        
        Returns:
            List of available abstract actions
        
        Note:
            Position determination for heads-up play:
            - Preflop: even history length (0, 2, 4...) -> OOP, odd -> IP
            - Postflop: positions flip! even history length -> IP, odd -> OOP
            
            This is because in HU:
            - Preflop: SB acts first (OOP), BB second (IP)
            - Postflop: SB (button) has position, BB is OOP
            
            **Future 6-max support**: For multi-way pots, position should be 
            retrieved from the game state encoder (button/IP per street) rather 
            than inferred from action history modulo. The current HU heuristic 
            will need to be replaced with explicit position tracking.
        """
        if history is None:
            history = []
        
        # Determine if player is in position (IP) or out of position (OOP)
        # For heads-up poker, position determination depends on street
        action_count = len(history)
        
        if street == Street.PREFLOP:
            # Preflop: even length -> OOP (SB), odd -> IP (BB)
            in_position = action_count % 2 == 1
        else:
            # Postflop: positions flip! even length -> IP (button/SB), odd -> OOP (BB)
            in_position = action_count % 2 == 0
        
        # Use ActionAbstraction with large stack to get all available actions
        # (we'll filter by actual stack in the solver)
        large_stack = pot * 10  # Large enough to include all actions
        return ActionAbstraction.get_available_actions(
            pot=pot,
            stack=large_stack,
            current_bet=0,
            player_bet=0,
            can_check=True,
            street=street,
            in_position=in_position
        )
