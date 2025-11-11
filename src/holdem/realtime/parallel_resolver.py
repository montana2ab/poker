"""Parallel subgame resolver using multiprocessing."""

import numpy as np
import multiprocessing as mp
import time
from typing import Dict, List, Optional, TYPE_CHECKING
from holdem.types import SearchConfig, Card, Street
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.realtime.subgame import SubgameTree
from holdem.utils.rng import get_rng
from holdem.utils.logging import get_logger

if TYPE_CHECKING:
    from holdem.rt_resolver.leaf_evaluator import LeafEvaluator

logger = get_logger("realtime.parallel_resolver")


def worker_cfr_iteration(
    worker_id: int,
    subgame: SubgameTree,
    infoset: str,
    blueprint_strategy: Dict[AbstractAction, float],
    kl_weight: float,
    num_iterations: int,
    result_queue: mp.Queue
):
    """Worker process that runs CFR iterations with warm-start from blueprint.
    
    Each worker starts with regrets initialized from the blueprint strategy,
    then runs independent CFR iterations. This improves convergence speed
    and solution quality.
    
    LIMITATION: Uses simplified utility calculation (placeholder).
    Production implementation should perform complete subgame traversal.
    
    Args:
        worker_id: ID of this worker
        subgame: Subgame tree
        infoset: Information set
        blueprint_strategy: Blueprint strategy for regularization and warm-start
        kl_weight: KL divergence weight
        num_iterations: Number of iterations to run
        result_queue: Queue to put results
    """
    regret_tracker = RegretTracker()
    rng = get_rng()
    
    # Warm-start regrets from blueprint
    actions = subgame.get_actions(infoset)
    total_prob = sum(blueprint_strategy.values())
    if total_prob > 0:
        for action in actions:
            prob = blueprint_strategy.get(action, 0.0)
            initial_regret = prob * 10.0  # Warm-start strength
            regret_tracker.update_regret(infoset, action, initial_regret, weight=1.0)
    
    for _ in range(num_iterations):
        current_strategy = regret_tracker.get_strategy(infoset, actions)
        
        # Sample action
        action_probs = [current_strategy.get(a, 0.0) for a in actions]
        if sum(action_probs) == 0:
            action_probs = [1.0 / len(actions)] * len(actions)
        else:
            action_probs = np.array(action_probs)
            action_probs /= action_probs.sum()
        
        sampled_action = rng.choice(actions, p=action_probs)
        
        # PLACEHOLDER: Simplified utility calculation
        # TODO: Implement proper subgame traversal:
        # - Recursive game tree traversal from current state
        # - Sample opponent actions and board outcomes
        # - Calculate exact utilities at terminal nodes
        # - Backpropagate counterfactual values
        utility = rng.uniform(-1.0, 1.0)
        
        # Add KL divergence penalty to regularize toward blueprint
        kl_penalty = 0.0
        for action in current_strategy:
            p_val = current_strategy.get(action, 1e-10)
            q_val = blueprint_strategy.get(action, 1e-10)
            if p_val > 0:
                kl_penalty += p_val * np.log(p_val / q_val)
        
        utility -= kl_weight * kl_penalty
        
        # Update regrets
        for action in actions:
            regret = 0.0
            if action == sampled_action:
                regret = utility
            regret_tracker.update_regret(infoset, action, regret)
        
        # Add to strategy sum
        regret_tracker.add_strategy(infoset, current_strategy, 1.0)
    
    # Get final strategy
    final_strategy = regret_tracker.get_average_strategy(infoset, actions)
    
    # Put result in queue
    result = {
        'worker_id': worker_id,
        'strategy': {action: prob for action, prob in final_strategy.items()}
    }
    result_queue.put(result)


class ParallelSubgameResolver:
    """Resolves subgames with KL regularization using parallel workers."""
    
    def __init__(
        self,
        config: SearchConfig,
        blueprint: PolicyStore,
        leaf_evaluator: Optional['LeafEvaluator'] = None
    ):
        self.config = config
        self.blueprint = blueprint
        self.leaf_evaluator = leaf_evaluator
        
        # Create multiprocessing context with 'spawn' for cross-platform compatibility
        # Use get_context() instead of set_start_method() to avoid conflicts
        self.mp_context = mp.get_context('spawn')
        
        # Determine number of workers
        if self.config.num_workers == 0:
            self.num_workers = self.mp_context.cpu_count()
        else:
            self.num_workers = max(1, self.config.num_workers)
        
        logger.debug(f"Initialized parallel resolver with {self.num_workers} worker(s)")
    
    def solve(
        self,
        subgame: SubgameTree,
        infoset: str,
        time_budget_ms: int = None
    ) -> Dict[AbstractAction, float]:
        """Solve subgame using parallel workers and return strategy.
        
        Workers run independent CFR iterations in parallel, each starting with
        warm-started regrets from the blueprint. Results are averaged to get
        the final strategy.
        
        LIMITATION: Current implementation uses simplified utility calculation.
        For production use, implement proper subgame traversal with:
        - Complete recursive game tree traversal
        - Opponent range sampling
        - Board outcome sampling
        - Exact terminal node utilities
        
        Args:
            subgame: Subgame tree
            infoset: Information set
            time_budget_ms: Time budget in milliseconds
            
        Returns:
            Strategy dictionary mapping actions to probabilities
        """
        # Using 'spawn' context initialized in __init__
        
        if time_budget_ms is None:
            time_budget_ms = self.config.time_budget_ms
        
        # Get blueprint strategy for regularization and warm-start
        blueprint_strategy = self.blueprint.get_strategy(infoset)
        
        # If only one worker, fall back to sequential
        if self.num_workers == 1:
            return self._solve_sequential(subgame, infoset, blueprint_strategy, time_budget_ms)
        
        # Calculate iterations per worker
        total_iterations = self.config.min_iterations
        iterations_per_worker = total_iterations // self.num_workers
        
        # Create result queue using the spawn context
        result_queue = self.mp_context.Queue()
        
        # Start time
        start_time = time.time()
        
        # Start workers
        workers = []
        for worker_id in range(self.num_workers):
            p = self.mp_context.Process(
                target=worker_cfr_iteration,
                args=(
                    worker_id,
                    subgame,
                    infoset,
                    blueprint_strategy,
                    self.config.kl_divergence_weight,
                    iterations_per_worker,
                    result_queue
                )
            )
            p.start()
            workers.append(p)
        
        # Wait for all workers to complete or timeout
        timeout = time_budget_ms / 1000.0
        start_wait = time.time()
        
        for p in workers:
            remaining = timeout - (time.time() - start_wait)
            if remaining > 0:
                p.join(timeout=remaining)
                # If process didn't finish, terminate it
                if p.is_alive():
                    logger.warning(f"Worker process did not complete in time, terminating")
                    p.terminate()
                    p.join(timeout=1.0)  # Give it a second to clean up
            else:
                # Timeout exceeded, terminate remaining workers
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=1.0)
        
        # Collect results
        strategies = []
        while not result_queue.empty():
            result = result_queue.get()
            strategies.append(result['strategy'])
        
        # If no results collected (timeout), fall back to blueprint
        if not strategies:
            logger.warning("Parallel solving timed out, falling back to blueprint")
            return blueprint_strategy
        
        # Average strategies from all workers
        actions = subgame.get_actions(infoset)
        merged_strategy = {}
        for action in actions:
            merged_strategy[action] = sum(s.get(action, 0.0) for s in strategies) / len(strategies)
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"Resolved subgame with {len(strategies)} workers in {elapsed_ms:.1f}ms")
        
        return merged_strategy
    
    def _solve_sequential(
        self,
        subgame: SubgameTree,
        infoset: str,
        blueprint_strategy: Dict[AbstractAction, float],
        time_budget_ms: int
    ) -> Dict[AbstractAction, float]:
        """Sequential solving (fallback for single worker) with warm-start.
        
        Args:
            subgame: Subgame tree
            infoset: Information set
            blueprint_strategy: Blueprint strategy for regularization and warm-start
            time_budget_ms: Time budget in milliseconds
            
        Returns:
            Strategy dictionary
        """
        regret_tracker = RegretTracker()
        rng = get_rng()
        
        # Warm-start regrets from blueprint
        actions = subgame.get_actions(infoset)
        total_prob = sum(blueprint_strategy.values())
        if total_prob > 0:
            for action in actions:
                prob = blueprint_strategy.get(action, 0.0)
                initial_regret = prob * 10.0  # Warm-start strength
                regret_tracker.update_regret(infoset, action, initial_regret, weight=1.0)
        
        start_time = time.time()
        iterations = 0
        
        while iterations < self.config.min_iterations:
            current_strategy = regret_tracker.get_strategy(infoset, actions)
            
            # Sample action
            action_probs = [current_strategy.get(a, 0.0) for a in actions]
            if sum(action_probs) == 0:
                action_probs = [1.0 / len(actions)] * len(actions)
            else:
                action_probs = np.array(action_probs)
                action_probs /= action_probs.sum()
            
            sampled_action = rng.choice(actions, p=action_probs)
            
            # PLACEHOLDER: Simplified utility calculation
            # Should be replaced with proper game tree traversal and CFR utility calculation.
            utility = rng.uniform(-1.0, 1.0)
            
            # Add KL divergence penalty
            kl_penalty = 0.0
            for action in current_strategy:
                p_val = current_strategy.get(action, 1e-10)
                q_val = blueprint_strategy.get(action, 1e-10)
                if p_val > 0:
                    kl_penalty += p_val * np.log(p_val / q_val)
            
            utility -= self.config.kl_divergence_weight * kl_penalty
            
            # Update regrets
            for action in actions:
                regret = 0.0
                if action == sampled_action:
                    regret = utility
                regret_tracker.update_regret(infoset, action, regret)
            
            # Add to strategy sum
            regret_tracker.add_strategy(infoset, current_strategy, 1.0)
            
            iterations += 1
            
            # Check time budget
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > time_budget_ms and iterations >= self.config.min_iterations:
                break
        
        # Get solution strategy
        strategy = regret_tracker.get_average_strategy(infoset, actions)
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"Resolved subgame sequentially in {iterations} iterations ({elapsed_ms:.1f}ms)")
        
        return strategy
