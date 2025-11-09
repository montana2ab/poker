"""External sampling MCCFR for multi-player poker.

External sampling is more stable than outcome sampling for multi-player games.
It alternates player updates to avoid simultaneous updates and uses negative
regret pruning with a scheduled threshold.
"""

import numpy as np
from typing import List, Dict, Callable
from holdem.types import Card, Street
from holdem.abstraction.actions import AbstractAction, ActionAbstraction
from holdem.abstraction.bucketing import HandBucketing
from holdem.abstraction.state_encode import StateEncoder
from holdem.mccfr.regrets import RegretTracker
from holdem.utils.rng import get_rng
from holdem.utils.logging import get_logger

logger = get_logger("mccfr.external_sampling")


class ExternalSampler:
    """External sampling MCCFR with negative regret pruning.
    
    External sampling: sample opponent actions from their strategies, but
    traverse all actions for the updating player. More stable than outcome
    sampling for multi-player games.
    
    Negative Regret Pruning (NRP): Use scheduled threshold τ(t) = c / √t to
    prune actions with large negative regrets, reducing computation.
    """
    
    def __init__(
        self,
        bucketing: HandBucketing,
        num_players: int = 2,
        use_linear_weighting: bool = True,
        enable_nrp: bool = True,
        nrp_coefficient: float = 1.0,
        strategy_freezing: bool = False
    ):
        """Initialize external sampler.
        
        Args:
            bucketing: Hand bucketing for abstraction
            num_players: Number of players (typically 2 or 6)
            use_linear_weighting: Use Linear CFR (weight = iteration t)
            enable_nrp: Enable Negative Regret Pruning
            nrp_coefficient: Coefficient c for NRP threshold τ(t) = c / √t
            strategy_freezing: Enable strategy freezing (only update regrets, not strategy)
        """
        self.bucketing = bucketing
        self.num_players = num_players
        self.encoder = StateEncoder(bucketing)
        self.regret_tracker = RegretTracker()
        self.rng = get_rng()
        
        # Linear MCCFR
        self.use_linear_weighting = use_linear_weighting
        
        # Negative Regret Pruning
        self.enable_nrp = enable_nrp
        self.nrp_coefficient = nrp_coefficient
        
        # Strategy freezing for blueprint generation
        self.strategy_freezing = strategy_freezing
    
    def get_nrp_threshold(self, iteration: int) -> float:
        """Calculate NRP threshold τ(t) = c / √t.
        
        Args:
            iteration: Current iteration number
            
        Returns:
            Negative regret threshold
        """
        if iteration <= 0:
            return 0.0
        return -self.nrp_coefficient / np.sqrt(iteration)
    
    def sample_iteration(self, iteration: int, updating_player: int = None) -> float:
        """Run one iteration of external sampling MCCFR.
        
        Args:
            iteration: Current iteration number (for linear weighting and NRP)
            updating_player: Player to update (if None, cycle through all players)
            
        Returns:
            Expected utility for the updating player
        """
        # Cycle through players if not specified
        if updating_player is None:
            updating_player = iteration % self.num_players
        
        # Sample hands for all players
        hands = self._deal_hands()
        
        # Run external sampling CFR
        utility = self._cfr_external(
            hands=hands,
            history=[],
            street=Street.PREFLOP,
            board=[],
            pot=3.0,  # SB + BB for 2-player
            reach_probs=[1.0] * self.num_players,
            updating_player=updating_player,
            iteration=iteration
        )
        
        return utility
    
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
    
    def _cfr_external(
        self,
        hands: List[List[Card]],
        history: List[str],
        street: Street,
        board: List[Card],
        pot: float,
        reach_probs: List[float],
        updating_player: int,
        iteration: int
    ) -> float:
        """CFR recursion with external sampling.
        
        External sampling: traverse ALL actions for updating_player,
        sample ONE action for other players.
        """
        # Check for terminal states
        if self._is_terminal(history):
            return self._get_payoff(hands, history, board, pot, updating_player)
        
        # Get current player
        current_player = self._get_acting_player(history, self.num_players)
        
        # Get available actions
        actions = self._get_available_actions(pot, street, history)
        
        # Create infoset
        infoset, _ = self.encoder.encode_infoset(
            hands[current_player],
            board,
            street,
            self.encoder.encode_history(history)
        )
        
        # Get current strategy
        strategy = self.regret_tracker.get_strategy(infoset, actions)
        
        # Apply NRP if enabled
        if self.enable_nrp and current_player == updating_player:
            threshold = self.get_nrp_threshold(iteration)
            pruned_actions = []
            for action in actions:
                regret = self.regret_tracker.get_regret(infoset, action)
                if regret >= threshold:
                    pruned_actions.append(action)
            
            # Use pruned actions if we have at least one
            if pruned_actions:
                actions = pruned_actions
                # Recompute strategy with pruned actions
                strategy = self.regret_tracker.get_strategy(infoset, actions)
        
        # Linear weighting
        weight = float(iteration) if self.use_linear_weighting else 1.0
        
        if current_player == updating_player:
            # Updating player: traverse ALL actions
            action_utilities = {}
            
            for action in actions:
                new_history = history + [action.value]
                new_reach_probs = reach_probs.copy()
                new_reach_probs[current_player] *= strategy[action]
                
                action_utilities[action] = self._cfr_external(
                    hands, new_history, street, board, pot,
                    new_reach_probs, updating_player, iteration
                )
            
            # Expected utility
            expected_utility = sum(strategy[a] * action_utilities[a] for a in actions)
            
            # Update regrets with linear weighting
            for action in actions:
                regret = action_utilities[action] - expected_utility
                self.regret_tracker.update_regret(infoset, action, regret, weight)
            
            # Add to strategy sum (unless strategy is frozen)
            if not self.strategy_freezing:
                # Counterfactual reach probability (all players except current)
                cf_reach = 1.0
                for p in range(self.num_players):
                    if p != current_player:
                        cf_reach *= reach_probs[p]
                
                strategy_weight = weight * cf_reach
                self.regret_tracker.add_strategy(infoset, strategy, strategy_weight)
            
            return expected_utility
        
        else:
            # Other player: sample according to strategy
            action_probs = [strategy[a] for a in actions]
            sampled_action = self.rng.choice(actions, p=action_probs)
            
            new_history = history + [sampled_action.value]
            new_reach_probs = reach_probs.copy()
            new_reach_probs[current_player] *= strategy[sampled_action]
            
            return self._cfr_external(
                hands, new_history, street, board, pot,
                new_reach_probs, updating_player, iteration
            )
    
    def _is_terminal(self, history: List[str]) -> bool:
        """Check if history represents a terminal state."""
        if not history:
            return False
        
        if "fold" in history:
            return True
        
        # Simplified: both players acted and last action was check/call
        if len(history) >= 2:
            last_action = history[-1]
            if last_action in ["check_call", "call"]:
                return True
        
        return False
    
    def _get_acting_player(self, history: List[str], num_players: int) -> int:
        """Get player to act based on history."""
        # Simple alternation for 2-player
        return len(history) % num_players
    
    def _get_available_actions(self, pot: float, street: Street, history: List[str]) -> List[AbstractAction]:
        """Get available actions at current state."""
        # Simplified: return a reasonable action set
        actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL]
        
        # Add betting actions based on street
        if street == Street.PREFLOP:
            actions.extend([
                AbstractAction.BET_HALF_POT,
                AbstractAction.BET_POT,
                AbstractAction.ALL_IN
            ])
        elif street == Street.FLOP:
            actions.extend([
                AbstractAction.BET_THIRD_POT,
                AbstractAction.BET_THREE_QUARTERS_POT,
                AbstractAction.BET_POT,
                AbstractAction.ALL_IN
            ])
        elif street == Street.TURN:
            actions.extend([
                AbstractAction.BET_TWO_THIRDS_POT,
                AbstractAction.BET_POT,
                AbstractAction.BET_OVERBET_150,
                AbstractAction.ALL_IN
            ])
        else:  # RIVER
            actions.extend([
                AbstractAction.BET_THREE_QUARTERS_POT,
                AbstractAction.BET_POT,
                AbstractAction.BET_OVERBET_150,
                AbstractAction.ALL_IN
            ])
        
        return actions
    
    def _get_payoff(
        self,
        hands: List[List[Card]],
        history: List[str],
        board: List[Card],
        pot: float,
        player: int
    ) -> float:
        """Get payoff for player at terminal node."""
        # Simplified: return random utility (placeholder)
        # In production, this should evaluate hands and determine winner
        return self.rng.uniform(-pot, pot)
