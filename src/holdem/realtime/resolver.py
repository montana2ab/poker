"""Subgame resolver with KL regularization."""

import numpy as np
from typing import Dict, List, Optional
from holdem.types import SearchConfig, Card, Street, TableState
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.realtime.subgame import SubgameTree
from holdem.utils.rng import get_rng
from holdem.utils.logging import get_logger
from holdem.utils.deck import sample_public_cards

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
        
        # KL divergence statistics tracking
        self.kl_history = {
            'preflop': {'IP': [], 'OOP': []},
            'flop': {'IP': [], 'OOP': []},
            'turn': {'IP': [], 'OOP': []},
            'river': {'IP': [], 'OOP': []}
        }
    
    def warm_start_from_blueprint(self, infoset: str, actions: List[AbstractAction]):
        """Warm-start regrets from blueprint strategy.
        
        This initializes the regret tracker with values that bias the search
        toward the blueprint strategy, improving convergence speed and quality.
        
        Args:
            infoset: Information set to warm-start
            actions: Available actions at this infoset
        """
        blueprint_strategy = self.blueprint.get_strategy(infoset)
        
        # Initialize regrets to favor blueprint actions
        # Higher blueprint probability -> higher initial regret
        total_prob = sum(blueprint_strategy.values())
        if total_prob > 0:
            for action in actions:
                prob = blueprint_strategy.get(action, 0.0)
                # Scale regrets to reasonable initial values
                initial_regret = prob * 10.0  # Tunable warm-start strength
                self.regret_tracker.update_regret(infoset, action, initial_regret, weight=1.0)
            
            logger.debug(f"Warm-started infoset {infoset} from blueprint")
    
    def solve_with_sampling(
        self,
        subgame: SubgameTree,
        infoset: str,
        our_cards: List[Card],
        time_budget_ms: int = None,
        street: Street = None,
        is_oop: bool = False
    ) -> Dict[AbstractAction, float]:
        """Solve subgame with public card sampling (board sampling).
        
        This implements the Pluribus technique of sampling future boards
        to reduce variance. The subgame is solved on K sampled boards and
        the resulting strategies are averaged.
        
        Args:
            subgame: Subgame tree to solve
            infoset: Information set to solve for
            our_cards: Hero's hole cards
            time_budget_ms: Time budget in milliseconds (overrides config)
            street: Current game street (for KL weight calculation)
            is_oop: Whether player is out of position (for KL weight calculation)
            
        Returns:
            Averaged strategy (probability distribution over actions)
        """
        num_samples = self.config.samples_per_solve
        
        # If samples_per_solve is 1, use standard solve (no sampling)
        if num_samples <= 1:
            return self.solve(subgame, infoset, time_budget_ms, street, is_oop)
        
        # Determine street from subgame if not provided
        if street is None:
            street = subgame.state.street if hasattr(subgame, 'state') else Street.FLOP
        
        # Only sample if we're not on river (can't sample future cards on river)
        if street == Street.RIVER:
            logger.debug("River street - no public card sampling needed")
            return self.solve(subgame, infoset, time_budget_ms, street, is_oop)
        
        # Get current board and determine target street
        current_board = subgame.state.board if hasattr(subgame, 'state') else []
        
        # Determine target number of board cards based on current street
        target_cards = {
            Street.PREFLOP: 3,  # Sample flop
            Street.FLOP: 4,     # Sample turn
            Street.TURN: 5,     # Sample river
            Street.RIVER: 5     # Already at river
        }[street]
        
        # Get known cards (board + our hole cards)
        known_cards = current_board + our_cards
        
        # Sample future boards
        try:
            sampled_boards = sample_public_cards(
                num_samples=num_samples,
                current_board=current_board,
                known_cards=known_cards,
                target_street_cards=target_cards,
                rng=self.rng
            )
        except ValueError as e:
            logger.warning(f"Public card sampling failed: {e}. Falling back to single solve.")
            return self.solve(subgame, infoset, time_budget_ms, street, is_oop)
        
        # Divide time budget across samples
        time_per_sample = time_budget_ms // num_samples if time_budget_ms else None
        
        # Solve on each sampled board and collect strategies
        strategies = []
        variances = []
        
        for i, board in enumerate(sampled_boards):
            # Create subgame with sampled board
            sampled_subgame = self._create_subgame_with_board(subgame, board)
            
            # Solve on this board sample
            strategy = self.solve(
                sampled_subgame, 
                infoset, 
                time_per_sample, 
                street, 
                is_oop
            )
            strategies.append(strategy)
            
            # Track variance in strategies for logging
            if strategies:
                avg_so_far = self._average_strategies(strategies)
                variance = self._strategy_variance(strategy, avg_so_far)
                variances.append(variance)
        
        # Average strategies across all samples
        averaged_strategy = self._average_strategies(strategies)
        
        # Log sampling statistics
        if variances:
            avg_variance = np.mean(variances)
            max_variance = np.max(variances)
            logger.info(
                f"Public card sampling: {num_samples} boards | "
                f"variance - avg: {avg_variance:.4f}, max: {max_variance:.4f}"
            )
        
        return averaged_strategy
    
    def _create_subgame_with_board(self, original_subgame: SubgameTree, board: List[Card]) -> SubgameTree:
        """Create a new subgame with a different board.
        
        Args:
            original_subgame: Original subgame
            board: New board cards
            
        Returns:
            New subgame with updated board
        """
        # Create a copy of the subgame with the new board
        from copy import deepcopy
        new_subgame = deepcopy(original_subgame)
        if hasattr(new_subgame, 'state'):
            new_subgame.state.board = board.copy()
        return new_subgame
    
    def _average_strategies(self, strategies: List[Dict[AbstractAction, float]]) -> Dict[AbstractAction, float]:
        """Average multiple strategies.
        
        Args:
            strategies: List of strategy dictionaries
            
        Returns:
            Averaged strategy
        """
        if not strategies:
            return {}
        
        # Get all actions
        all_actions = set()
        for strategy in strategies:
            all_actions.update(strategy.keys())
        
        # Average probabilities for each action
        averaged = {}
        for action in all_actions:
            probs = [strategy.get(action, 0.0) for strategy in strategies]
            averaged[action] = np.mean(probs)
        
        # Normalize to ensure probabilities sum to 1.0
        total = sum(averaged.values())
        if total > 0:
            averaged = {action: prob / total for action, prob in averaged.items()}
        
        return averaged
    
    def _strategy_variance(
        self, 
        strategy: Dict[AbstractAction, float], 
        reference: Dict[AbstractAction, float]
    ) -> float:
        """Calculate variance between a strategy and reference strategy.
        
        Uses L2 distance (Euclidean distance) between probability vectors.
        
        Args:
            strategy: Strategy to compare
            reference: Reference strategy
            
        Returns:
            L2 distance between strategies
        """
        all_actions = set(strategy.keys()) | set(reference.keys())
        
        diff_sum = 0.0
        for action in all_actions:
            p1 = strategy.get(action, 0.0)
            p2 = reference.get(action, 0.0)
            diff_sum += (p1 - p2) ** 2
        
        return np.sqrt(diff_sum)
    
    def solve(
        self,
        subgame: SubgameTree,
        infoset: str,
        time_budget_ms: int = None,
        street: Street = None,
        is_oop: bool = False
    ) -> Dict[AbstractAction, float]:
        """Solve subgame and return strategy.
        
        Note: This method does NOT use public card sampling. To enable sampling,
        use solve_with_sampling() instead.
        
        Args:
            subgame: Subgame tree to solve
            infoset: Information set to solve for
            time_budget_ms: Time budget in milliseconds (overrides config)
            street: Current game street (for KL weight calculation)
            is_oop: Whether player is out of position (for KL weight calculation)
            
        Returns:
            Strategy (probability distribution over actions)
        """
        if time_budget_ms is None:
            time_budget_ms = self.config.time_budget_ms
        
        # Determine street from subgame if not provided
        if street is None:
            street = subgame.state.street if hasattr(subgame, 'state') else Street.FLOP
        
        # Get dynamic KL weight based on street and position
        kl_weight = self.config.get_kl_weight(street, is_oop)
        
        # Get actions for this infoset
        actions = subgame.get_actions(infoset)
        
        # Warm-start from blueprint strategy
        self.warm_start_from_blueprint(infoset, actions)
        
        # Get blueprint strategy for regularization
        blueprint_strategy = self.blueprint.get_strategy(infoset)
        
        # Run MCCFR with time budget
        import time
        start_time = time.time()
        iterations = 0
        kl_values = []  # Track KL values for statistics
        
        while iterations < self.config.min_iterations:
            kl_div = self._cfr_iteration(subgame, infoset, blueprint_strategy, kl_weight)
            kl_values.append(kl_div)
            iterations += 1
            
            # Check time budget
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > time_budget_ms and iterations >= self.config.min_iterations:
                break
        
        # Get solution strategy
        strategy = self.regret_tracker.get_average_strategy(infoset, actions)
        
        # Track and log KL divergence statistics
        if self.config.track_kl_stats and kl_values:
            # Store KL values for later analysis
            street_name = street.name.lower()
            position = 'OOP' if is_oop else 'IP'
            self.kl_history[street_name][position].extend(kl_values)
            
            # Calculate statistics
            kl_array = np.array(kl_values)
            avg_kl = np.mean(kl_array)
            p50_kl = np.percentile(kl_array, 50)
            p90_kl = np.percentile(kl_array, 90)
            p99_kl = np.percentile(kl_array, 99)
            pct_high_kl = np.mean(kl_array > self.config.kl_high_threshold) * 100
            
            logger.info(
                f"Resolved subgame in {iterations} iterations ({elapsed_ms:.1f}ms) | "
                f"Street: {street_name} | Position: {position} | "
                f"KL weight: {kl_weight:.2f} | "
                f"KL stats - avg: {avg_kl:.4f}, p50: {p50_kl:.4f}, p90: {p90_kl:.4f}, p99: {p99_kl:.4f} | "
                f"KL>{self.config.kl_high_threshold}: {pct_high_kl:.1f}%"
            )
        else:
            avg_kl = np.mean(kl_values) if kl_values else 0.0
            logger.debug(f"Resolved subgame in {iterations} iterations ({elapsed_ms:.1f}ms), avg KL divergence: {avg_kl:.6f}")
        
        return strategy
    
    def _cfr_iteration(
        self,
        subgame: SubgameTree,
        infoset: str,
        blueprint_strategy: Dict[AbstractAction, float],
        kl_weight: float
    ) -> float:
        """Run one CFR iteration with KL regularization.
        
        LIMITATION: This is a simplified utility calculation that does not fully
        traverse the subgame tree. In production, this should:
        1. Perform a complete recursive traversal of the subgame
        2. Sample opponent actions and board outcomes
        3. Calculate exact expected utilities at terminal nodes
        4. Use warm-start regrets from the blueprint strategy
        
        The current placeholder implementation limits decision quality until
        proper subgame traversal is implemented.
        
        Args:
            subgame: Subgame tree to solve
            infoset: Current information set
            blueprint_strategy: Blueprint strategy for KL regularization
            kl_weight: KL regularization weight for this iteration
            
        Returns:
            KL divergence from blueprint strategy
        """
        actions = subgame.get_actions(infoset)
        
        # Get current strategy (warm-started from blueprint if available)
        current_strategy = self.regret_tracker.get_strategy(infoset, actions)
        
        # Calculate KL divergence from blueprint (explicit calculation)
        kl_divergence = self._kl_divergence(current_strategy, blueprint_strategy)
        
        # Sample action
        action_probs = [current_strategy.get(a, 0.0) for a in actions]
        if sum(action_probs) == 0:
            action_probs = [1.0 / len(actions)] * len(actions)
        else:
            action_probs = np.array(action_probs)
            action_probs /= action_probs.sum()
        
        sampled_action = self.rng.choice(actions, p=action_probs)
        
        # PLACEHOLDER: Simplified utility calculation
        # TODO: Replace with proper subgame traversal:
        # - Recursively traverse game tree from current state
        # - Sample opponent ranges and board outcomes
        # - Compute exact utilities at terminal nodes (showdown/fold)
        # - Backpropagate values through the tree
        utility = self.rng.uniform(-1.0, 1.0)
        
        # Apply KL divergence penalty to stay close to blueprint
        utility -= kl_weight * kl_divergence
        
        # Update regrets
        for action in actions:
            regret = 0.0
            if action == sampled_action:
                regret = utility
            self.regret_tracker.update_regret(infoset, action, regret)
        
        # Add to strategy sum
        self.regret_tracker.add_strategy(infoset, current_strategy, 1.0)
        
        return kl_divergence
    
    def _kl_divergence(
        self,
        p: Dict[AbstractAction, float],
        q: Dict[AbstractAction, float]
    ) -> float:
        """Calculate KL divergence KL(p||q) with blueprint clipping.
        
        Blueprint probabilities (q) are clipped to a minimum value to prevent
        numerical instability and ensure well-defined KL divergence.
        
        Args:
            p: Current strategy distribution
            q: Blueprint strategy distribution (will be clipped)
            
        Returns:
            KL divergence KL(p||q)
        """
        kl = 0.0
        clip_min = self.config.blueprint_clip_min
        
        for action in p:
            p_val = p.get(action, 1e-10)
            # Clip blueprint probability to minimum value
            q_val = max(q.get(action, clip_min), clip_min)
            if p_val > 0:
                kl += p_val * np.log(p_val / q_val)
        return kl
    
    def get_kl_statistics(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Get KL divergence statistics aggregated by street and position.
        
        Returns:
            Dictionary with structure: {street: {position: {stat_name: value}}}
            Stats include: avg, p50, p90, p99, pct_high
        """
        stats = {}
        
        for street, positions in self.kl_history.items():
            stats[street] = {}
            for position, kl_values in positions.items():
                if not kl_values:
                    continue
                
                kl_array = np.array(kl_values)
                stats[street][position] = {
                    'avg': float(np.mean(kl_array)),
                    'p50': float(np.percentile(kl_array, 50)),
                    'p90': float(np.percentile(kl_array, 90)),
                    'p99': float(np.percentile(kl_array, 99)),
                    'pct_high': float(np.mean(kl_array > self.config.kl_high_threshold) * 100),
                    'count': len(kl_values)
                }
        
        return stats
