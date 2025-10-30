"""Subgame resolver with KL regularization."""

import numpy as np
from typing import Dict, List
from holdem.types import SearchConfig, Card, Street
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.realtime.subgame import SubgameTree
from holdem.utils.rng import get_rng
from holdem.utils.logging import get_logger

logger = get_logger("realtime.resolver")


class SubgameResolver:
    """Resolves subgames with KL regularization toward blueprint."""
    
    def __init__(
        self,
        config: SearchConfig,
        blueprint: PolicyStore
    ):
        self.config = config
        self.blueprint = blueprint
        self.regret_tracker = RegretTracker()
        self.rng = get_rng()
    
    def solve(
        self,
        subgame: SubgameTree,
        infoset: str,
        time_budget_ms: int = None
    ) -> Dict[AbstractAction, float]:
        """Solve subgame and return strategy."""
        if time_budget_ms is None:
            time_budget_ms = self.config.time_budget_ms
        
        # Get blueprint strategy for regularization
        blueprint_strategy = self.blueprint.get_strategy(infoset)
        
        # Run MCCFR with time budget
        import time
        start_time = time.time()
        iterations = 0
        
        while iterations < self.config.min_iterations:
            self._cfr_iteration(subgame, infoset, blueprint_strategy)
            iterations += 1
            
            # Check time budget
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > time_budget_ms and iterations >= self.config.min_iterations:
                break
        
        # Get solution strategy
        actions = subgame.get_actions(infoset)
        strategy = self.regret_tracker.get_average_strategy(infoset, actions)
        
        logger.debug(f"Resolved subgame in {iterations} iterations ({elapsed_ms:.1f}ms)")
        
        return strategy
    
    def _cfr_iteration(
        self,
        subgame: SubgameTree,
        infoset: str,
        blueprint_strategy: Dict[AbstractAction, float]
    ):
        """Run one CFR iteration with KL regularization."""
        actions = subgame.get_actions(infoset)
        
        # Get current strategy
        current_strategy = self.regret_tracker.get_strategy(infoset, actions)
        
        # Sample action
        action_probs = [current_strategy.get(a, 0.0) for a in actions]
        if sum(action_probs) == 0:
            action_probs = [1.0 / len(actions)] * len(actions)
        else:
            action_probs = np.array(action_probs)
            action_probs /= action_probs.sum()
        
        sampled_action = self.rng.choice(actions, p=action_probs)
        
        # Simplified utility calculation
        utility = self.rng.uniform(-1.0, 1.0)
        
        # Add KL divergence penalty
        kl_penalty = self._kl_divergence(current_strategy, blueprint_strategy)
        utility -= self.config.kl_divergence_weight * kl_penalty
        
        # Update regrets
        for action in actions:
            regret = 0.0
            if action == sampled_action:
                regret = utility
            self.regret_tracker.update_regret(infoset, action, regret)
        
        # Add to strategy sum
        self.regret_tracker.add_strategy(infoset, current_strategy, 1.0)
    
    def _kl_divergence(
        self,
        p: Dict[AbstractAction, float],
        q: Dict[AbstractAction, float]
    ) -> float:
        """Calculate KL divergence KL(p||q)."""
        kl = 0.0
        for action in p:
            p_val = p.get(action, 1e-10)
            q_val = q.get(action, 1e-10)
            if p_val > 0:
                kl += p_val * np.log(p_val / q_val)
        return kl
