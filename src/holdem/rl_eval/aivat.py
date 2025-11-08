"""AIVAT (Actor-Independent Variance-reduced Advantage Technique) for multi-player evaluation.

This module implements variance reduction for poker policy evaluation by learning
baseline value functions conditional on opponent actions, reducing sample variance
while maintaining unbiased estimates.

Reference:
    Brown & Sandholm (2019). "Superhuman AI for multiplayer poker" - Science
"""

from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import logging


logger = logging.getLogger("rl_eval.aivat")


class AIVATEvaluator:
    """AIVAT evaluator for variance-reduced policy evaluation.
    
    AIVAT reduces evaluation variance by subtracting learned baseline values
    that are independent of the player's actions. This is especially valuable
    in multi-player settings where variance is naturally high.
    
    Formula:
        Advantage_i = Payoff_i - V_i(s, a_{-i})
    
    where:
        - Payoff_i: actual payoff for player i
        - V_i(s, a_{-i}): baseline value conditional on opponent actions
        - s: game state
        - a_{-i}): actions of all opponents
    
    Attributes:
        num_players: Number of players in the game
        min_samples: Minimum samples before training value functions
        samples: Collected samples for training baselines
        value_functions: Learned baseline value functions per player
        trained: Whether value functions have been trained
    """
    
    def __init__(self, num_players: int = 9, min_samples: int = 1000):
        """Initialize AIVAT evaluator.
        
        Args:
            num_players: Number of players in the game
            min_samples: Minimum samples needed before training value functions
        """
        self.num_players = num_players
        self.min_samples = min_samples
        
        # Storage for training samples: player_id -> list of (state_key, payoff)
        self.samples: Dict[int, List[Tuple[str, float]]] = defaultdict(list)
        
        # Learned value functions: player_id -> state_key -> baseline_value
        self.value_functions: Dict[int, Dict[str, float]] = defaultdict(dict)
        
        # Track if we've trained the value functions
        self.trained = False
        
        # Statistics tracking
        self.vanilla_variance: Optional[float] = None
        self.aivat_variance: Optional[float] = None
        
        logger.info(
            f"Initialized AIVAT evaluator for {num_players} players, "
            f"min_samples={min_samples}"
        )
    
    def add_sample(
        self,
        player_id: int,
        state_key: str,
        actions_taken: Optional[Dict[int, str]] = None,
        payoff: float = 0.0
    ) -> None:
        """Add a sample for training value functions.
        
        During the warm-up phase, we collect samples of (state, payoff) pairs
        to learn baseline value functions.
        
        Args:
            player_id: ID of the player (0 to num_players-1)
            state_key: String representation of game state (for hashing)
            actions_taken: Optional dict of actions taken by each player
            payoff: Actual payoff received by the player
        """
        if player_id < 0 or player_id >= self.num_players:
            raise ValueError(f"Invalid player_id {player_id}, must be 0-{self.num_players-1}")
        
        self.samples[player_id].append((state_key, payoff))
    
    def can_train(self) -> bool:
        """Check if we have enough samples to train value functions.
        
        Returns:
            True if all players have at least min_samples samples
        """
        if len(self.samples) < self.num_players:
            return False
        
        for player_id in range(self.num_players):
            if len(self.samples[player_id]) < self.min_samples:
                return False
        
        return True
    
    def train_value_functions(self, min_samples: Optional[int] = None) -> None:
        """Train baseline value functions from collected samples.
        
        For each player, we learn V_i(s) as the average payoff observed in state s.
        This is a simple but effective baseline that's independent of the player's
        own actions (assuming opponent policies are fixed).
        
        Args:
            min_samples: Override minimum samples requirement
        """
        if min_samples is not None:
            self.min_samples = min_samples
        
        if not self.can_train():
            logger.warning(
                f"Not enough samples to train. Have {len(self.samples)} player groups, "
                f"need {self.num_players} with {self.min_samples} samples each."
            )
            return
        
        logger.info("Training AIVAT value functions...")
        
        # For each player, aggregate payoffs by state
        for player_id in range(self.num_players):
            state_payoffs: Dict[str, List[float]] = defaultdict(list)
            
            for state_key, payoff in self.samples[player_id]:
                state_payoffs[state_key].append(payoff)
            
            # Compute average payoff per state (baseline value)
            for state_key, payoffs in state_payoffs.items():
                self.value_functions[player_id][state_key] = sum(payoffs) / len(payoffs)
            
            logger.info(
                f"  Player {player_id}: {len(state_payoffs)} unique states, "
                f"{len(self.samples[player_id])} total samples"
            )
        
        self.trained = True
        logger.info("Value functions trained successfully")
    
    def get_baseline_value(self, player_id: int, state_key: str) -> float:
        """Get baseline value for a state.
        
        If the state hasn't been seen during training, returns 0.0 as a
        conservative baseline.
        
        Args:
            player_id: ID of the player
            state_key: String representation of the state
            
        Returns:
            Baseline value for the state, or 0.0 if unseen
        """
        if not self.trained:
            return 0.0
        
        return self.value_functions[player_id].get(state_key, 0.0)
    
    def compute_advantage(
        self,
        player_id: int,
        state_key: str,
        actual_payoff: float
    ) -> float:
        """Compute variance-reduced advantage for a sample.
        
        The advantage is the actual payoff minus the baseline value.
        This has the same expectation as the payoff (unbiased) but
        lower variance if the baseline is good.
        
        Args:
            player_id: ID of the player
            state_key: String representation of the state
            actual_payoff: Actual payoff received
            
        Returns:
            Advantage = actual_payoff - baseline_value
        """
        baseline = self.get_baseline_value(player_id, state_key)
        return actual_payoff - baseline
    
    def compute_variance_reduction(
        self,
        vanilla_results: List[float],
        aivat_results: List[float]
    ) -> Dict[str, Any]:
        """Compute variance reduction statistics.
        
        Compares the variance of vanilla evaluation vs AIVAT evaluation.
        
        Args:
            vanilla_results: List of raw payoffs
            aivat_results: List of advantages (with AIVAT baseline subtracted)
            
        Returns:
            Dictionary with variance statistics and reduction percentage
        """
        if len(vanilla_results) == 0 or len(aivat_results) == 0:
            return {
                'vanilla_variance': 0.0,
                'aivat_variance': 0.0,
                'variance_reduction_pct': 0.0,
                'variance_reduction_ratio': 1.0
            }
        
        # Calculate variance (using population variance)
        vanilla_mean = sum(vanilla_results) / len(vanilla_results)
        vanilla_var = sum((x - vanilla_mean) ** 2 for x in vanilla_results) / len(vanilla_results)
        
        aivat_mean = sum(aivat_results) / len(aivat_results)
        aivat_var = sum((x - aivat_mean) ** 2 for x in aivat_results) / len(aivat_results)
        
        # Store for later reference
        self.vanilla_variance = vanilla_var
        self.aivat_variance = aivat_var
        
        # Compute reduction
        if vanilla_var > 0:
            reduction_pct = ((vanilla_var - aivat_var) / vanilla_var) * 100
            reduction_ratio = aivat_var / vanilla_var
        else:
            reduction_pct = 0.0
            reduction_ratio = 1.0
        
        return {
            'vanilla_variance': vanilla_var,
            'aivat_variance': aivat_var,
            'vanilla_std': vanilla_var ** 0.5,
            'aivat_std': aivat_var ** 0.5,
            'variance_reduction_pct': reduction_pct,
            'variance_reduction_ratio': reduction_ratio,
            'num_samples': len(vanilla_results)
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current statistics about the AIVAT evaluator.
        
        Returns:
            Dictionary with statistics about samples, training status, etc.
        """
        total_samples = sum(len(samples) for samples in self.samples.values())
        
        stats = {
            'num_players': self.num_players,
            'min_samples': self.min_samples,
            'total_samples': total_samples,
            'trained': self.trained,
            'can_train': self.can_train(),
        }
        
        if self.trained:
            total_states = sum(len(vf) for vf in self.value_functions.values())
            stats['total_unique_states'] = total_states
        
        if self.vanilla_variance is not None and self.aivat_variance is not None:
            stats['vanilla_variance'] = self.vanilla_variance
            stats['aivat_variance'] = self.aivat_variance
            if self.vanilla_variance > 0:
                stats['variance_reduction_pct'] = (
                    (self.vanilla_variance - self.aivat_variance) / self.vanilla_variance * 100
                )
        
        return stats
