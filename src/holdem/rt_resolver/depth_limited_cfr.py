"""Depth-limited CFR solver for real-time resolving.

Runs CFR with small iteration budget (400-1200) and time constraints.
Used for real-time subgame resolution during play.
"""

import time
from typing import Dict, Optional
from holdem.types import Card, Street
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.rt_resolver.subgame_builder import SubgameBuilder, SubgameState
from holdem.rt_resolver.leaf_evaluator import LeafEvaluator
from holdem.utils.rng import get_rng
from holdem.utils.logging import get_logger

logger = get_logger("rt_resolver.depth_limited_cfr")


class DepthLimitedCFR:
    """CFR solver with depth and time limits for real-time play.
    
    Features:
    - Small iteration budget (400-1200 iterations)
    - Hard time limit (e.g., 80ms per decision)
    - Depth-limited subgame construction
    - Leaf evaluation via blueprint CFV or rollouts
    - KL regularization toward blueprint
    """
    
    def __init__(
        self,
        blueprint: PolicyStore,
        subgame_builder: SubgameBuilder,
        leaf_evaluator: LeafEvaluator,
        min_iterations: int = 400,
        max_iterations: int = 1200,
        time_limit_ms: int = 80,
        kl_weight: float = 0.5
    ):
        """Initialize depth-limited CFR solver.
        
        Args:
            blueprint: Blueprint policy for warm-start and KL regularization
            subgame_builder: Subgame construction module
            leaf_evaluator: Leaf node evaluation module
            min_iterations: Minimum iterations before time limit check
            max_iterations: Maximum iterations (hard cap)
            time_limit_ms: Time limit in milliseconds
            kl_weight: KL divergence weight toward blueprint
        """
        self.blueprint = blueprint
        self.subgame_builder = subgame_builder
        self.leaf_evaluator = leaf_evaluator
        self.min_iterations = min_iterations
        self.max_iterations = max_iterations
        self.time_limit_ms = time_limit_ms
        self.kl_weight = kl_weight
        
        self.regret_tracker = RegretTracker()
        self.rng = get_rng()
        
        # Metrics
        self.last_solve_time_ms = 0.0
        self.last_iterations = 0
        self.ev_delta_vs_blueprint = 0.0
        
        logger.info(
            f"DepthLimitedCFR initialized: "
            f"iterations={min_iterations}-{max_iterations}, "
            f"time_limit={time_limit_ms}ms, kl_weight={kl_weight}"
        )
    
    def solve(
        self,
        root_state: SubgameState,
        hero_hand: list,
        villain_range: Dict[str, float],
        hero_position: int
    ) -> Dict[AbstractAction, float]:
        """Solve subgame and return strategy.
        
        Args:
            root_state: Root state of subgame
            hero_hand: Hero's hole cards
            villain_range: Villain's hand range
            hero_position: Hero's position (0, 1, ...)
            
        Returns:
            Strategy (probability distribution over actions)
        """
        start_time = time.time()
        
        # Warm-start from blueprint
        self._warm_start(root_state, hero_hand)
        
        # Run CFR iterations with time budget
        iteration = 0
        while iteration < self.max_iterations:
            self._cfr_iteration(
                root_state, hero_hand, villain_range, hero_position, iteration
            )
            iteration += 1
            
            # Check time limit (after minimum iterations)
            if iteration >= self.min_iterations:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms >= self.time_limit_ms:
                    break
        
        # Compute final strategy
        actions = self.subgame_builder.get_actions(
            root_state,
            stack=100.0,  # Placeholder
            in_position=True
        )
        strategy = self.regret_tracker.get_average_strategy(
            self._make_infoset(root_state, hero_hand),
            actions
        )
        
        # Update metrics
        self.last_solve_time_ms = (time.time() - start_time) * 1000
        self.last_iterations = iteration
        
        # Calculate EV delta vs blueprint
        blueprint_infoset = self._make_infoset(root_state, hero_hand)
        blueprint_strategy = self.blueprint.get_strategy(blueprint_infoset)
        self.ev_delta_vs_blueprint = self._compute_ev_delta(
            strategy, blueprint_strategy, root_state.pot
        )
        
        logger.info(
            f"Solved subgame: {iteration} iterations in {self.last_solve_time_ms:.1f}ms, "
            f"EV delta vs blueprint: {self.ev_delta_vs_blueprint:+.2f} BBs"
        )
        
        return strategy
    
    def _warm_start(self, state: SubgameState, hero_hand: list):
        """Warm-start regrets from blueprint strategy.
        
        Args:
            state: Root state
            hero_hand: Hero's cards
        """
        infoset = self._make_infoset(state, hero_hand)
        blueprint_strategy = self.blueprint.get_strategy(infoset)
        
        if not blueprint_strategy:
            return
        
        # Initialize regrets to favor blueprint actions
        actions = self.subgame_builder.get_actions(
            state, stack=100.0, in_position=True
        )
        
        for action in actions:
            prob = blueprint_strategy.get(action, 0.0)
            initial_regret = prob * 10.0  # Warm-start strength
            self.regret_tracker.update_regret(infoset, action, initial_regret, 1.0)
        
        logger.debug(f"Warm-started from blueprint: {len(blueprint_strategy)} actions")
    
    def _cfr_iteration(
        self,
        state: SubgameState,
        hero_hand: list,
        villain_range: Dict[str, float],
        hero_position: int,
        iteration: int
    ):
        """Run one CFR iteration.
        
        Args:
            state: Current state
            hero_hand: Hero's cards
            villain_range: Villain's range
            hero_position: Hero's position
            iteration: Iteration number
        """
        # Check if terminal
        if self.subgame_builder.is_terminal(state):
            # Evaluate leaf
            return self.leaf_evaluator.evaluate(
                state, hero_hand, villain_range, hero_position
            )
        
        # Get actions
        actions = self.subgame_builder.get_actions(
            state, stack=100.0, in_position=True
        )
        
        infoset = self._make_infoset(state, hero_hand)
        
        # Get current strategy
        strategy = self.regret_tracker.get_strategy(infoset, actions)
        
        # Sample action
        action_probs = [strategy.get(a, 0.0) for a in actions]
        if sum(action_probs) == 0:
            action_probs = [1.0 / len(actions)] * len(actions)
        
        sampled_action = self.rng.choice(actions, p=action_probs)
        
        # Simplified utility (placeholder)
        utility = self.rng.uniform(-state.pot, state.pot)
        
        # Apply KL penalty toward blueprint
        blueprint_strategy = self.blueprint.get_strategy(infoset)
        kl_div = self._kl_divergence(strategy, blueprint_strategy)
        utility -= self.kl_weight * kl_div
        
        # Update regrets
        for action in actions:
            regret = 0.0
            if action == sampled_action:
                regret = utility
            self.regret_tracker.update_regret(infoset, action, regret, 1.0)
        
        # Add to strategy sum
        self.regret_tracker.add_strategy(infoset, strategy, 1.0)
    
    def _make_infoset(self, state: SubgameState, hero_hand: list) -> str:
        """Create infoset identifier.
        
        Args:
            state: Current state
            hero_hand: Hero's cards
            
        Returns:
            Infoset string
        """
        hand_str = ''.join([str(c) for c in hero_hand])
        board_str = ''.join([str(c) for c in state.board])
        history_str = '-'.join(state.history)
        return f"{hand_str}|{board_str}|{history_str}"
    
    def _kl_divergence(
        self,
        p: Dict[AbstractAction, float],
        q: Dict[AbstractAction, float]
    ) -> float:
        """Calculate KL divergence KL(p||q).
        
        Args:
            p: Current strategy
            q: Blueprint strategy
            
        Returns:
            KL divergence
        """
        kl = 0.0
        for action in p:
            p_val = p.get(action, 1e-10)
            q_val = max(q.get(action, 1e-6), 1e-6)
            if p_val > 0:
                kl += p_val * np.log(p_val / q_val)
        return kl
    
    def _compute_ev_delta(
        self,
        strategy: Dict[AbstractAction, float],
        blueprint_strategy: Dict[AbstractAction, float],
        pot: float
    ) -> float:
        """Compute EV difference between strategies.
        
        Args:
            strategy: Resolved strategy
            blueprint_strategy: Blueprint strategy
            pot: Current pot size
            
        Returns:
            EV delta in big blinds
        """
        # Simplified EV calculation
        # In production, compute proper expected values
        ev_resolved = sum(
            prob * pot * 0.1  # Simplified utility
            for action, prob in strategy.items()
        )
        ev_blueprint = sum(
            prob * pot * 0.1
            for action, prob in blueprint_strategy.items()
        )
        
        # Convert to BBs (assuming BB = 2.0)
        return (ev_resolved - ev_blueprint) / 2.0
    
    def get_metrics(self) -> Dict[str, float]:
        """Get solving metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            'solve_time_ms': self.last_solve_time_ms,
            'iterations': self.last_iterations,
            'ev_delta_bbs': self.ev_delta_vs_blueprint,
            'time_per_iteration_ms': self.last_solve_time_ms / max(self.last_iterations, 1)
        }


# Fix missing import
import numpy as np
