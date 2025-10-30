"""Evaluation loop for testing policies."""

import numpy as np
from typing import List, Dict
from holdem.mccfr.policy_store import PolicyStore
from holdem.rl_eval.baselines import RandomAgent, AlwaysCallAgent, TightAgent, AggressiveAgent
from holdem.utils.logging import get_logger

logger = get_logger("rl_eval.eval_loop")


class Evaluator:
    """Evaluates policy against baseline agents."""
    
    def __init__(self, policy: PolicyStore):
        self.policy = policy
        self.baselines = [
            RandomAgent(),
            AlwaysCallAgent(),
            TightAgent(),
            AggressiveAgent()
        ]
    
    def evaluate(self, num_episodes: int = 10000) -> Dict[str, float]:
        """Evaluate policy against baselines."""
        logger.info(f"Evaluating policy over {num_episodes} episodes")
        
        results = {}
        
        for baseline in self.baselines:
            logger.info(f"Playing against {baseline.name}...")
            
            winnings = []
            for episode in range(num_episodes):
                # Simplified game simulation
                result = self._play_episode(baseline)
                winnings.append(result)
                
                if (episode + 1) % 1000 == 0:
                    avg_winnings = np.mean(winnings)
                    logger.info(f"  Episode {episode+1}/{num_episodes}: Avg={avg_winnings:.2f}")
            
            avg_winnings = np.mean(winnings)
            std_winnings = np.std(winnings)
            
            results[baseline.name] = {
                'mean': avg_winnings,
                'std': std_winnings,
                'episodes': num_episodes
            }
            
            logger.info(
                f"  Results vs {baseline.name}: "
                f"Mean={avg_winnings:.2f} ± {std_winnings:.2f}"
            )
        
        return results
    
    def _play_episode(self, opponent) -> float:
        """Play one episode (simplified simulation)."""
        # Simplified: return random outcome
        # In full implementation, would simulate actual poker game
        return np.random.normal(0, 10)
