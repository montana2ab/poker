"""Policy storage and retrieval."""

import json
from pathlib import Path
from typing import Dict, List
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.regrets import RegretTracker
from holdem.utils.serialization import save_pickle, load_pickle
from holdem.utils.logging import get_logger

logger = get_logger("mccfr.policy_store")


class PolicyStore:
    """Stores and retrieves trained policies."""
    
    def __init__(self, regret_tracker: RegretTracker = None):
        self.regret_tracker = regret_tracker
        self.policy: Dict[str, Dict[str, float]] = {}
        
        if regret_tracker:
            self._build_policy()
    
    def _build_policy(self):
        """Build policy from regret tracker."""
        for infoset in self.regret_tracker.strategy_sum:
            actions_dict = self.regret_tracker.strategy_sum[infoset]
            actions = list(actions_dict.keys())
            
            avg_strategy = self.regret_tracker.get_average_strategy(infoset, actions)
            
            # Convert AbstractAction keys to strings for JSON serialization
            self.policy[infoset] = {
                action.value: prob for action, prob in avg_strategy.items()
            }
    
    def get_strategy(self, infoset: str) -> Dict[AbstractAction, float]:
        """Get strategy for infoset."""
        if infoset not in self.policy:
            # Return uniform distribution over common actions
            actions = [
                AbstractAction.FOLD,
                AbstractAction.CHECK_CALL,
                AbstractAction.BET_HALF_POT
            ]
            uniform_prob = 1.0 / len(actions)
            return {action: uniform_prob for action in actions}
        
        strategy_dict = self.policy[infoset]
        
        # Convert string keys back to AbstractAction
        strategy = {}
        for action_str, prob in strategy_dict.items():
            try:
                action = AbstractAction(action_str)
                strategy[action] = prob
            except ValueError:
                logger.warning(f"Unknown action in policy: {action_str}")
        
        return strategy
    
    def sample_action(self, infoset: str, rng) -> AbstractAction:
        """Sample action from policy."""
        strategy = self.get_strategy(infoset)
        actions = list(strategy.keys())
        probs = [strategy[a] for a in actions]
        
        return rng.choice(actions, p=probs)
    
    def save(self, path: Path):
        """Save policy as pickle."""
        data = {
            'policy': self.policy,
        }
        save_pickle(data, path)
        logger.info(f"Saved policy to {path}")
    
    def save_json(self, path: Path, use_gzip: bool = False):
        """Save policy as JSON.
        
        Args:
            path: Target file path
            use_gzip: If True, save as gzipped JSON
        """
        from holdem.utils.serialization import save_json
        save_json(self.policy, path, use_gzip=use_gzip)
        logger.info(f"Saved policy to {path}")
    
    @classmethod
    def load(cls, path: Path) -> "PolicyStore":
        """Load policy from pickle."""
        data = load_pickle(path)
        
        store = cls()
        store.policy = data['policy']
        
        logger.info(f"Loaded policy from {path}")
        return store
    
    @classmethod
    def load_json(cls, path: Path) -> "PolicyStore":
        """Load policy from JSON (supports gzip)."""
        from holdem.utils.serialization import load_json
        policy_dict = load_json(path)
        
        store = cls()
        store.policy = policy_dict
        
        logger.info(f"Loaded policy from {path}")
        return store
    
    def num_infosets(self) -> int:
        """Get number of infosets in policy."""
        return len(self.policy)
