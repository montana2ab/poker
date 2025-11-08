"""Leaf node evaluator for depth-limited resolving.

Evaluates terminal states (leaves) using:
- Blueprint counterfactual values (CFV)
- Rollouts using blueprint strategy
- Reduced action set for speed
"""

import numpy as np
from typing import List, Dict, Optional
from holdem.types import Card, Street
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.policy_store import PolicyStore
from holdem.rt_resolver.subgame_builder import SubgameState
from holdem.utils.rng import get_rng
from holdem.utils.logging import get_logger

logger = get_logger("rt_resolver.leaf_evaluator")


class LeafEvaluator:
    """Evaluates leaf nodes in depth-limited subgames.
    
    Methods:
    1. Blueprint CFV: Use blueprint's counterfactual values directly
    2. Rollout: Sample game continuations using blueprint strategy
    """
    
    def __init__(
        self,
        blueprint: PolicyStore,
        num_rollout_samples: int = 10,
        use_cfv: bool = True
    ):
        """Initialize leaf evaluator.
        
        Args:
            blueprint: Blueprint policy store
            num_rollout_samples: Number of rollout samples per leaf
            use_cfv: Use blueprint CFV if available, else rollout
        """
        self.blueprint = blueprint
        self.num_rollout_samples = num_rollout_samples
        self.use_cfv = use_cfv
        self.rng = get_rng()
        
        logger.info(
            f"LeafEvaluator initialized: use_cfv={use_cfv}, "
            f"rollout_samples={num_rollout_samples}"
        )
    
    def evaluate(
        self,
        state: SubgameState,
        hero_hand: List[Card],
        villain_range: Dict[str, float],
        hero_position: int
    ) -> float:
        """Evaluate leaf node value.
        
        Args:
            state: Leaf state to evaluate
            hero_hand: Hero's hole cards
            villain_range: Villain's hand range (hand_str -> probability)
            hero_position: Hero's position (0, 1, ...)
            
        Returns:
            Expected value for hero
        """
        if self.use_cfv:
            # Try blueprint CFV first
            cfv = self._get_blueprint_cfv(state, hero_hand, hero_position)
            if cfv is not None:
                return cfv
        
        # Fall back to rollout
        return self._rollout_value(state, hero_hand, villain_range, hero_position)
    
    def _get_blueprint_cfv(
        self,
        state: SubgameState,
        hero_hand: List[Card],
        hero_position: int
    ) -> Optional[float]:
        """Get blueprint counterfactual value if available.
        
        Args:
            state: Current state
            hero_hand: Hero's cards
            hero_position: Hero's position
            
        Returns:
            CFV if available, else None
        """
        # Create infoset identifier
        # This is a simplified placeholder - in production, use proper encoding
        hand_str = ''.join([str(c) for c in hero_hand])
        board_str = ''.join([str(c) for c in state.board])
        history_str = '-'.join(state.history)
        infoset = f"{hand_str}|{board_str}|{history_str}"
        
        # Try to get strategy from blueprint
        strategy = self.blueprint.get_strategy(infoset)
        
        if not strategy:
            # No blueprint value available
            return None
        
        # Estimate value from strategy (simplified)
        # In production, this should use proper CFV calculation
        # For now, return weighted average assuming balanced strategy
        avg_value = 0.0
        for action, prob in strategy.items():
            # Rough heuristic: aggressive actions -> positive value
            if action in [AbstractAction.BET_POT, AbstractAction.BET_OVERBET_150]:
                avg_value += prob * state.pot * 0.5
            elif action in [AbstractAction.CHECK_CALL]:
                avg_value += prob * 0.0
            elif action == AbstractAction.FOLD:
                avg_value -= prob * (state.pot * 0.3)
        
        logger.debug(f"Blueprint CFV for infoset {infoset[:20]}...: {avg_value:.2f}")
        return avg_value
    
    def _rollout_value(
        self,
        state: SubgameState,
        hero_hand: List[Card],
        villain_range: Dict[str, float],
        hero_position: int
    ) -> float:
        """Rollout to estimate leaf value.
        
        Args:
            state: Current state
            hero_hand: Hero's cards
            villain_range: Villain's hand distribution
            hero_position: Hero's position
            
        Returns:
            Average value over rollouts
        """
        total_value = 0.0
        
        for _ in range(self.num_rollout_samples):
            # Sample villain hand from range
            villain_hand = self._sample_from_range(villain_range)
            
            # Simulate continuation using blueprint
            value = self._simulate_continuation(
                state, hero_hand, villain_hand, hero_position
            )
            total_value += value
        
        avg_value = total_value / self.num_rollout_samples
        logger.debug(
            f"Rollout value ({self.num_rollout_samples} samples): {avg_value:.2f}"
        )
        return avg_value
    
    def _sample_from_range(self, hand_range: Dict[str, float]) -> List[Card]:
        """Sample a hand from probability distribution.
        
        Args:
            hand_range: hand_str -> probability
            
        Returns:
            Sampled hand as list of Cards
        """
        if not hand_range:
            # Empty range, return random hand
            return self._random_hand()
        
        hands = list(hand_range.keys())
        probs = list(hand_range.values())
        
        # Normalize probabilities
        total = sum(probs)
        if total > 0:
            probs = [p / total for p in probs]
        else:
            probs = [1.0 / len(hands)] * len(hands)
        
        sampled_hand_str = self.rng.choice(hands, p=probs)
        return self._parse_hand(sampled_hand_str)
    
    def _random_hand(self) -> List[Card]:
        """Generate random hand."""
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
        suits = ['h', 'd', 'c', 's']
        
        deck = [Card(rank, suit) for rank in ranks for suit in suits]
        self.rng.shuffle(deck)
        return [deck[0], deck[1]]
    
    def _parse_hand(self, hand_str: str) -> List[Card]:
        """Parse hand string to Card objects.
        
        Args:
            hand_str: e.g., "AhKs" or "AA"
            
        Returns:
            List of Card objects
        """
        # Simplified parsing - in production, handle all formats
        if len(hand_str) == 4:
            # "AhKs"
            return [
                Card(hand_str[0], hand_str[1]),
                Card(hand_str[2], hand_str[3])
            ]
        elif len(hand_str) == 2:
            # "AA" - assign random suits
            rank = hand_str[0]
            suits = ['h', 'd']
            return [Card(rank, suits[0]), Card(rank, suits[1])]
        else:
            # Fallback to random
            return self._random_hand()
    
    def _simulate_continuation(
        self,
        state: SubgameState,
        hero_hand: List[Card],
        villain_hand: List[Card],
        hero_position: int
    ) -> float:
        """Simulate game continuation using blueprint strategy.
        
        Args:
            state: Current state
            hero_hand: Hero's cards
            villain_hand: Villain's cards
            hero_position: Hero's position
            
        Returns:
            Simulated payoff for hero
        """
        # Simplified simulation - in production, run full game tree
        # For now, estimate based on hand strength
        
        # Estimate hand strengths (placeholder)
        hero_strength = self._estimate_strength(hero_hand, state.board)
        villain_strength = self._estimate_strength(villain_hand, state.board)
        
        # Simplified payoff
        if hero_strength > villain_strength:
            return state.pot * 0.7  # Win most of pot (rake adjustment)
        elif hero_strength < villain_strength:
            return -state.pot * 0.3  # Lose
        else:
            return 0.0  # Chop
    
    def _estimate_strength(self, hand: List[Card], board: List[Card]) -> float:
        """Rough hand strength estimate.
        
        Args:
            hand: Player's cards
            board: Community cards
            
        Returns:
            Strength value (0-1)
        """
        # Very simplified - just use high card
        rank_values = {
            '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
            '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
        }
        
        max_rank = max(rank_values.get(c.rank, 0) for c in hand)
        return max_rank / 14.0
