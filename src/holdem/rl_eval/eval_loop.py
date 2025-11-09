"""Evaluation loop for testing policies."""

import numpy as np
from typing import List, Dict, Optional, Any
from holdem.mccfr.policy_store import PolicyStore
from holdem.rl_eval.baselines import RandomAgent, AlwaysCallAgent, TightAgent, AggressiveAgent
from holdem.rl_eval.aivat import AIVATEvaluator
from holdem.rl_eval.statistics import (
    compute_confidence_interval,
    required_sample_size,
    check_margin_adequacy,
    format_ci_result
)
from holdem.utils.logging import get_logger

logger = get_logger("rl_eval.eval_loop")


class Evaluator:
    """Evaluates policy against baseline agents."""
    
    def __init__(self, policy: PolicyStore, use_aivat: bool = False, num_players: int = 9,
                 confidence_level: float = 0.95, target_margin: Optional[float] = None,
                 duplicate: int = 0, translator: str = "balanced", seed: int = 42):
        """Initialize evaluator.
        
        Args:
            policy: The policy to evaluate
            use_aivat: Whether to use AIVAT for variance reduction
            num_players: Number of players (for AIVAT). Use 2 for heads-up evaluation.
            confidence_level: Confidence level for CI (default: 0.95 for 95% CI)
            target_margin: Target margin of error for evaluation (optional)
            duplicate: Duplicate parameter for evaluation
            translator: Translator type for evaluation
            seed: Random seed for evaluation
        """
        self.policy = policy
        self.use_aivat = use_aivat
        self.num_players = num_players
        self.confidence_level = confidence_level
        self.target_margin = target_margin
        self.duplicate = duplicate
        self.translator = translator
        self.seed = seed
        self.baselines = [
            RandomAgent(),
            AlwaysCallAgent(),
            TightAgent(),
            AggressiveAgent()
        ]
        
        # Initialize AIVAT if enabled
        # For heads-up evaluation (policy vs baseline), use num_players=2
        self.aivat: Optional[AIVATEvaluator] = None
        if use_aivat:
            # In simplified evaluation, we're doing heads-up against each baseline
            # So we only need to track 2 players (player 0 = our policy, player 1 = baseline)
            actual_num_players = 2 if num_players == 9 else num_players
            self.aivat = AIVATEvaluator(num_players=actual_num_players)
            logger.info(f"AIVAT variance reduction enabled (heads-up mode: {actual_num_players} players)")
    
    def evaluate(self, num_episodes: int = 10000, warmup_episodes: int = 1000) -> Dict[str, Any]:
        """Evaluate policy against baselines.
        
        Args:
            num_episodes: Number of evaluation episodes
            warmup_episodes: Number of warmup episodes for AIVAT training (if enabled)
            
        Returns:
            Dictionary with evaluation results including variance metrics
        """
        logger.info(f"Evaluating policy over {num_episodes} episodes")
        if self.use_aivat:
            logger.info(f"  AIVAT warmup: {warmup_episodes} episodes")
        
        results = {}
        
        for baseline in self.baselines:
            logger.info(f"Playing against {baseline.name}...")
            
            # Phase 1: Warmup for AIVAT (if enabled)
            if self.use_aivat and self.aivat is not None:
                logger.info(f"  AIVAT warmup phase: collecting {warmup_episodes} samples...")
                for episode in range(warmup_episodes):
                    result, state_key = self._play_episode_with_state(baseline)
                    # Add sample for player 0 (our policy)
                    self.aivat.add_sample(
                        player_id=0,
                        state_key=state_key,
                        payoff=result
                    )
                    # Add sample for player 1 (baseline opponent) with opposite payoff
                    # In zero-sum games, opponent gets the negative of our result
                    self.aivat.add_sample(
                        player_id=1,
                        state_key=state_key,
                        payoff=-result
                    )
                
                # Train value functions
                self.aivat.train_value_functions(min_samples=warmup_episodes)
                logger.info("  AIVAT value functions trained")
            
            # Phase 2: Evaluation
            vanilla_winnings = []
            aivat_advantages = []
            
            for episode in range(num_episodes):
                if self.use_aivat and self.aivat is not None and self.aivat.trained:
                    # AIVAT evaluation
                    result, state_key = self._play_episode_with_state(baseline)
                    vanilla_winnings.append(result)
                    
                    # Compute advantage with AIVAT baseline
                    advantage = self.aivat.compute_advantage(
                        player_id=0,
                        state_key=state_key,
                        actual_payoff=result
                    )
                    aivat_advantages.append(advantage)
                else:
                    # Vanilla evaluation
                    result = self._play_episode(baseline)
                    vanilla_winnings.append(result)
                
                if (episode + 1) % 1000 == 0:
                    avg_winnings = np.mean(vanilla_winnings)
                    logger.info(f"  Episode {episode+1}/{num_episodes}: Avg={avg_winnings:.2f}")
            
            # Compute results
            avg_winnings = np.mean(vanilla_winnings)
            std_winnings = np.std(vanilla_winnings)
            variance = std_winnings ** 2
            
            # Compute confidence interval
            ci_info = compute_confidence_interval(
                vanilla_winnings,
                confidence=self.confidence_level,
                method="bootstrap"
            )
            
            baseline_results = {
                'mean': avg_winnings,
                'std': std_winnings,
                'variance': variance,
                'episodes': num_episodes,
                'confidence_interval': ci_info
            }
            
            # Check if margin is adequate and recommend sample size if needed
            if self.target_margin is not None:
                adequacy_check = check_margin_adequacy(
                    current_margin=ci_info['margin'],
                    target_margin=self.target_margin,
                    current_n=num_episodes,
                    estimated_variance=variance,
                    confidence=self.confidence_level
                )
                baseline_results['margin_adequacy'] = adequacy_check
                
                if not adequacy_check['is_adequate']:
                    logger.warning(f"  {adequacy_check['recommendation']}")
            
            # Add AIVAT metrics if enabled
            if self.use_aivat and self.aivat is not None and len(aivat_advantages) > 0:
                variance_stats = self.aivat.compute_variance_reduction(
                    vanilla_winnings,
                    aivat_advantages
                )
                baseline_results['aivat'] = variance_stats
                
                # Compute CI for AIVAT advantages as well
                aivat_ci = compute_confidence_interval(
                    aivat_advantages,
                    confidence=self.confidence_level,
                    method="bootstrap"
                )
                baseline_results['aivat_confidence_interval'] = aivat_ci
                
                logger.info(
                    f"  Results vs {baseline.name}: "
                    f"{format_ci_result(avg_winnings, ci_info, decimals=2, unit='bb/100')}"
                )
                logger.info(
                    f"  AIVAT variance reduction: {variance_stats['variance_reduction_pct']:.1f}% "
                    f"({variance_stats['vanilla_variance']:.2f} → {variance_stats['aivat_variance']:.2f})"
                )
                logger.info(
                    f"  AIVAT CI: {format_ci_result(aivat_ci['mean'], aivat_ci, decimals=2, unit='bb/100')}"
                )
            else:
                logger.info(
                    f"  Results vs {baseline.name}: "
                    f"{format_ci_result(avg_winnings, ci_info, decimals=2, unit='bb/100')}"
                )
            
            results[baseline.name] = baseline_results
        
        # Add overall AIVAT statistics if available
        if self.use_aivat and self.aivat is not None:
            results['aivat_stats'] = self.aivat.get_statistics()
        
        return results
    
    def _play_episode(self, opponent) -> float:
        """Play one episode (simplified simulation)."""
        # Simplified: return random outcome
        # In full implementation, would simulate actual poker game
        return np.random.normal(0, 10)
    
    def _play_episode_with_state(self, opponent) -> tuple[float, str]:
        """Play one episode and return result with state key.
        
        Returns:
            Tuple of (payoff, state_key) where state_key identifies the game state
        """
        # Simplified: return random outcome with synthetic state
        # In full implementation, would simulate actual poker game and extract state
        payoff = np.random.normal(0, 10)
        
        # Create a synthetic state key based on episode characteristics
        # In a real implementation, this would be based on:
        # - Cards dealt
        # - Board state
        # - Position
        # - Stack sizes
        # - Betting history
        state_key = f"state_{hash(payoff) % 100}"
        
        return payoff, state_key
