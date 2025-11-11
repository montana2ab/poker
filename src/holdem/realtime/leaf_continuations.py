"""Leaf continuation strategies for depth-limited resolving.

Implements k=4 policy variants at leaf nodes:
1. Blueprint: Use blueprint strategy (baseline)
2. Fold-biased: Prefer defensive play (fold more, call less, raise less)
3. Call-biased: Prefer passive play (call more, fold less, raise less)
4. Raise-biased: Prefer aggressive play (raise more, call less, fold less)

These policies allow for strategic diversity at leaves, improving the
resolver's ability to explore different play styles and find robust strategies.
"""

from enum import Enum
from typing import Dict, List
from holdem.abstraction.actions import AbstractAction
from holdem.utils.logging import get_logger

logger = get_logger("realtime.leaf_continuations")


class LeafPolicy(Enum):
    """Available leaf continuation policies."""
    BLUEPRINT = "blueprint"
    FOLD_BIASED = "fold_biased"
    CALL_BIASED = "call_biased"
    RAISE_BIASED = "raise_biased"


class LeafContinuationStrategy:
    """Manages leaf continuation strategies.
    
    Provides k=4 policy variants at leaf nodes to allow strategic
    diversity during depth-limited resolving.
    """
    
    def __init__(self, default_policy: LeafPolicy = LeafPolicy.BLUEPRINT):
        """Initialize leaf continuation strategy.
        
        Args:
            default_policy: Default policy to use when not specified
        """
        self.default_policy = default_policy
        
        # Bias weights for each policy type
        # Higher weight = stronger bias toward that action type
        self.bias_weights = {
            LeafPolicy.BLUEPRINT: {
                'fold': 1.0,
                'call': 1.0,
                'raise': 1.0
            },
            LeafPolicy.FOLD_BIASED: {
                'fold': 2.0,   # 2x more likely to fold
                'call': 0.8,   # 20% less likely to call
                'raise': 0.5   # 50% less likely to raise
            },
            LeafPolicy.CALL_BIASED: {
                'fold': 0.7,   # 30% less likely to fold
                'call': 2.0,   # 2x more likely to call
                'raise': 0.6   # 40% less likely to raise
            },
            LeafPolicy.RAISE_BIASED: {
                'fold': 0.5,   # 50% less likely to fold
                'call': 0.7,   # 30% less likely to call
                'raise': 2.5   # 2.5x more likely to raise
            }
        }
        
        logger.info(f"LeafContinuationStrategy initialized with default_policy={default_policy.value}")
    
    def get_biased_strategy(
        self,
        blueprint_strategy: Dict[AbstractAction, float],
        policy: LeafPolicy = None,
        available_actions: List[AbstractAction] = None
    ) -> Dict[AbstractAction, float]:
        """Apply policy bias to blueprint strategy.
        
        Args:
            blueprint_strategy: Base strategy from blueprint
            policy: Policy type to apply (uses default if None)
            available_actions: List of available actions (for validation)
            
        Returns:
            Biased strategy (probability distribution)
        """
        if policy is None:
            policy = self.default_policy
        
        # For blueprint policy, return unchanged
        if policy == LeafPolicy.BLUEPRINT:
            return blueprint_strategy.copy()
        
        # Get bias weights for this policy
        weights = self.bias_weights[policy]
        
        # Apply biases to strategy
        biased = {}
        for action, prob in blueprint_strategy.items():
            # Determine action category
            action_type = self._categorize_action(action)
            
            # Apply bias weight
            bias = weights.get(action_type, 1.0)
            biased[action] = prob * bias
        
        # Normalize to ensure probabilities sum to 1.0
        total = sum(biased.values())
        if total > 0:
            biased = {action: prob / total for action, prob in biased.items()}
        else:
            # Fallback to uniform if all probabilities are 0
            if available_actions:
                uniform_prob = 1.0 / len(available_actions)
                biased = {action: uniform_prob for action in available_actions}
            else:
                uniform_prob = 1.0 / len(blueprint_strategy)
                biased = {action: uniform_prob for action in blueprint_strategy}
        
        logger.debug(
            f"Applied {policy.value} bias: "
            f"blueprint={list(blueprint_strategy.values())[:3]}, "
            f"biased={list(biased.values())[:3]}"
        )
        
        return biased
    
    def _categorize_action(self, action: AbstractAction) -> str:
        """Categorize action as fold, call, or raise.
        
        Args:
            action: Action to categorize
            
        Returns:
            Action category: 'fold', 'call', or 'raise'
        """
        # Fold actions
        if action == AbstractAction.FOLD:
            return 'fold'
        
        # Call/check actions (passive)
        if action == AbstractAction.CHECK_CALL:
            return 'call'
        
        # All bet/raise actions (aggressive)
        # This includes BET_*, RAISE_*, ALLIN
        return 'raise'
    
    def get_policy_description(self, policy: LeafPolicy) -> str:
        """Get human-readable description of a policy.
        
        Args:
            policy: Policy type
            
        Returns:
            Description string
        """
        descriptions = {
            LeafPolicy.BLUEPRINT: "Uses blueprint strategy unchanged",
            LeafPolicy.FOLD_BIASED: "Defensive play - folds more, raises less",
            LeafPolicy.CALL_BIASED: "Passive play - calls more, raises less",
            LeafPolicy.RAISE_BIASED: "Aggressive play - raises more, folds less"
        }
        return descriptions.get(policy, "Unknown policy")
    
    def get_all_policies(self) -> List[LeafPolicy]:
        """Get list of all available policies.
        
        Returns:
            List of all LeafPolicy enum values
        """
        return list(LeafPolicy)


def create_leaf_strategy(
    blueprint_strategy: Dict[AbstractAction, float],
    policy: LeafPolicy = LeafPolicy.BLUEPRINT,
    available_actions: List[AbstractAction] = None
) -> Dict[AbstractAction, float]:
    """Convenience function to create biased leaf strategy.
    
    Args:
        blueprint_strategy: Base strategy from blueprint
        policy: Policy type to apply
        available_actions: List of available actions
        
    Returns:
        Biased strategy
    """
    strategy_manager = LeafContinuationStrategy()
    return strategy_manager.get_biased_strategy(
        blueprint_strategy,
        policy,
        available_actions
    )
