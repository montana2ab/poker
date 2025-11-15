"""Policy storage and retrieval."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.regrets import RegretTracker
from holdem.utils.serialization import save_pickle, load_pickle
from holdem.utils.logging import get_logger

logger = get_logger("mccfr.policy_store")


class PolicyStore:
    """Stores and retrieves trained policies."""
    
    def __init__(self, regret_tracker: RegretTracker = None, bucket_metadata: Optional[Dict] = None):
        self.regret_tracker = regret_tracker
        self.policy: Dict[str, Dict[str, float]] = {}
        self.bucket_metadata: Optional[Dict] = bucket_metadata
        
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
    
    def save(self, path: Path, bucket_metadata: Optional[Dict] = None):
        """Save policy as pickle with optional bucket metadata.
        
        Args:
            path: Path to save the policy
            bucket_metadata: Optional bucket configuration metadata including SHA256 hash
        """
        # Use provided metadata, fall back to instance metadata
        metadata = bucket_metadata if bucket_metadata is not None else self.bucket_metadata
        
        data = {
            'policy': self.policy,
        }
        
        # Include bucket metadata if available
        if metadata:
            data['bucket_metadata'] = metadata
        
        save_pickle(data, path)
        
        if metadata:
            logger.info(f"Saved policy to {path} with bucket metadata (SHA: {metadata.get('bucket_file_sha', 'N/A')[:8]}...)")
        else:
            logger.warning(f"Saved policy to {path} WITHOUT bucket metadata (not recommended for production)")
            logger.warning("Strategies without bucket metadata cannot be validated against abstraction mismatches")
    
    def save_json(self, path: Path, use_gzip: bool = False, bucket_metadata: Optional[Dict] = None):
        """Save policy as JSON with optional bucket metadata.
        
        Args:
            path: Target file path
            use_gzip: If True, save as gzipped JSON
            bucket_metadata: Optional bucket configuration metadata including SHA256 hash
        """
        from holdem.utils.serialization import save_json
        
        # Use provided metadata, fall back to instance metadata
        metadata = bucket_metadata if bucket_metadata is not None else self.bucket_metadata
        
        data = {
            'policy': self.policy,
        }
        
        # Include bucket metadata if available
        if metadata:
            data['bucket_metadata'] = metadata
        
        save_json(data, path, use_gzip=use_gzip)
        
        if metadata:
            logger.info(f"Saved policy to {path} with bucket metadata (SHA: {metadata.get('bucket_file_sha', 'N/A')[:8]}...)")
        else:
            logger.warning(f"Saved policy to {path} WITHOUT bucket metadata (not recommended for production)")
            logger.warning("Strategies without bucket metadata cannot be validated against abstraction mismatches")
    
    @classmethod
    def load(cls, path: Path, expected_bucket_hash: Optional[str] = None, 
             validate_buckets: bool = True) -> "PolicyStore":
        """Load policy from pickle with optional bucket validation.
        
        Args:
            path: Path to the policy file
            expected_bucket_hash: Expected SHA256 hash of bucket configuration.
                                 If None and validate_buckets=True, will warn but not fail.
            validate_buckets: If True, validate bucket hash matches expected (if both available)
            
        Returns:
            PolicyStore instance
            
        Raises:
            ValueError: If bucket validation fails (hash mismatch)
        """
        data = load_pickle(path)
        
        store = cls()
        store.policy = data['policy']
        
        # Extract bucket metadata if present
        stored_metadata = data.get('bucket_metadata', None)
        store.bucket_metadata = stored_metadata
        
        # Validate bucket configuration if requested
        if validate_buckets:
            cls._validate_bucket_metadata(path, stored_metadata, expected_bucket_hash)
        
        logger.info(f"Loaded policy from {path} ({len(store.policy)} infosets)")
        return store
    
    @classmethod
    def load_json(cls, path: Path, expected_bucket_hash: Optional[str] = None,
                  validate_buckets: bool = True) -> "PolicyStore":
        """Load policy from JSON (supports gzip) with optional bucket validation.
        
        Args:
            path: Path to the policy file
            expected_bucket_hash: Expected SHA256 hash of bucket configuration.
                                 If None and validate_buckets=True, will warn but not fail.
            validate_buckets: If True, validate bucket hash matches expected (if both available)
            
        Returns:
            PolicyStore instance
            
        Raises:
            ValueError: If bucket validation fails (hash mismatch)
        """
        from holdem.utils.serialization import load_json
        data = load_json(path)
        
        store = cls()
        
        # Handle both legacy format (raw policy dict) and new format (with metadata)
        if isinstance(data, dict) and 'policy' in data:
            # New format with metadata
            store.policy = data['policy']
            stored_metadata = data.get('bucket_metadata', None)
            store.bucket_metadata = stored_metadata
        else:
            # Legacy format: raw policy dict
            store.policy = data
            stored_metadata = None
            store.bucket_metadata = None
        
        # Validate bucket configuration if requested
        if validate_buckets:
            cls._validate_bucket_metadata(path, stored_metadata, expected_bucket_hash)
        
        logger.info(f"Loaded policy from {path} ({len(store.policy)} infosets)")
        return store
    
    @staticmethod
    def _validate_bucket_metadata(path: Path, stored_metadata: Optional[Dict], 
                                   expected_bucket_hash: Optional[str]):
        """Validate bucket metadata against expected hash.
        
        Args:
            path: Path to policy file (for error messages)
            stored_metadata: Metadata stored in the policy file
            expected_bucket_hash: Expected SHA256 hash
            
        Raises:
            ValueError: If validation fails (hash mismatch)
        """
        # Case 1: No stored metadata
        if stored_metadata is None:
            logger.warning(f"⚠️  Policy {path.name} has NO bucket metadata")
            logger.warning("   This is a legacy policy or was saved without bucket configuration")
            logger.warning("   Cannot verify abstraction compatibility - USE AT YOUR OWN RISK")
            logger.warning("   Recommendation: Retrain policy with current code version")
            return
        
        stored_hash = stored_metadata.get('bucket_file_sha', None)
        
        # Case 2: Stored metadata exists but no hash
        if stored_hash is None:
            logger.warning(f"⚠️  Policy {path.name} has incomplete bucket metadata (missing SHA)")
            logger.warning("   Cannot verify abstraction compatibility - USE AT YOUR OWN RISK")
            return
        
        # Case 3: No expected hash provided - informational only
        if expected_bucket_hash is None:
            logger.info(f"✓ Policy has bucket metadata (SHA: {stored_hash[:8]}...)")
            logger.info("  No expected hash provided - skipping validation")
            logger.info("  Pass expected_bucket_hash parameter to enable validation")
            return
        
        # Case 4: Both hashes available - validate
        if stored_hash != expected_bucket_hash:
            # CRITICAL ERROR: Hash mismatch
            logger.error("=" * 80)
            logger.error("🚨 ABSTRACTION HASH MISMATCH DETECTED 🚨")
            logger.error("=" * 80)
            logger.error(f"Policy file: {path}")
            logger.error(f"Expected SHA256: {expected_bucket_hash}")
            logger.error(f"Stored SHA256:   {stored_hash}")
            logger.error("")
            logger.error("This policy was trained with DIFFERENT bucket configuration!")
            logger.error("")
            logger.error("Consequences of using incompatible abstraction:")
            logger.error("  • Infosets will not match correctly")
            logger.error("  • Strategy will be applied to wrong game states")
            logger.error("  • Play quality will be severely degraded")
            logger.error("  • Training progress will be corrupted if resuming")
            logger.error("")
            logger.error("Action required:")
            logger.error("  1. Verify you are using the correct bucket file")
            logger.error("  2. If buckets changed, retrain the policy from scratch")
            logger.error("  3. Use '--no-validate-buckets' flag ONLY for debugging (NOT RECOMMENDED)")
            logger.error("=" * 80)
            
            # Include detailed bucket configuration comparison if available
            if 'k_preflop' in stored_metadata:
                logger.error("")
                logger.error("Stored bucket configuration:")
                logger.error(f"  k_preflop: {stored_metadata.get('k_preflop')}")
                logger.error(f"  k_flop:    {stored_metadata.get('k_flop')}")
                logger.error(f"  k_turn:    {stored_metadata.get('k_turn')}")
                logger.error(f"  k_river:   {stored_metadata.get('k_river')}")
                logger.error(f"  seed:      {stored_metadata.get('seed')}")
                logger.error(f"  num_players: {stored_metadata.get('num_players')}")
            
            raise ValueError(
                f"Abstraction hash mismatch! Cannot safely use policy trained with different buckets.\n"
                f"Expected: {expected_bucket_hash}\n"
                f"Stored:   {stored_hash}\n"
                f"See log above for detailed explanation and recommendations."
            )
        
        # Case 5: Validation passed
        logger.info(f"✓ Bucket configuration validated successfully")
        logger.info(f"  SHA256: {stored_hash[:16]}...")
        if 'k_preflop' in stored_metadata:
            logger.info(f"  Buckets: preflop={stored_metadata.get('k_preflop')}, "
                       f"flop={stored_metadata.get('k_flop')}, "
                       f"turn={stored_metadata.get('k_turn')}, "
                       f"river={stored_metadata.get('k_river')}")
    
    def num_infosets(self) -> int:
        """Get number of infosets in policy."""
        return len(self.policy)
