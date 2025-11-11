"""Leaf node evaluator for depth-limited resolving.

Evaluates terminal states (leaves) using:
- Blueprint counterfactual values (CFV)
- Rollouts using blueprint strategy
- CFV Net: Neural network-based leaf evaluation
- Reduced action set for speed
- Caching of CFV/rollouts by (bucket_public, bucket_ranges, action_set_id, street)
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from holdem.types import Card, Street, Position
from holdem.abstraction.actions import AbstractAction
from holdem.mccfr.policy_store import PolicyStore
from holdem.rt_resolver.subgame_builder import SubgameState
from holdem.utils.rng import get_rng
from holdem.utils.logging import get_logger

logger = get_logger("rt_resolver.leaf_evaluator")


class LeafEvaluator:
    """Evaluates leaf nodes in depth-limited subgames.
    
    Methods:
    1. Blueprint CFV: Use blueprint's counterfactual values directly
    2. Rollout: Sample game continuations using blueprint strategy
    3. CFV Net: Neural network-based fast evaluation with gating
    4. Caching: Cache CFV/rollouts by (bucket_public, bucket_ranges, action_set_id, street)
    """
    
    def __init__(
        self,
        blueprint: PolicyStore,
        num_rollout_samples: int = 10,
        use_cfv: bool = True,
        enable_cache: bool = True,
        cache_max_size: int = 10000,
        mode: str = "rollout",
        cfv_net_config: Optional[Dict] = None
    ):
        """Initialize leaf evaluator.
        
        Args:
            blueprint: Blueprint policy store
            num_rollout_samples: Number of rollout samples per leaf
            use_cfv: Use blueprint CFV if available, else rollout
            enable_cache: Enable caching of leaf values
            cache_max_size: Maximum cache entries (LRU eviction)
            mode: Evaluation mode: "rollout", "blueprint", or "cfv_net"
            cfv_net_config: Configuration for CFV Net mode (if mode="cfv_net")
        """
        self.blueprint = blueprint
        self.num_rollout_samples = num_rollout_samples
        self.use_cfv = use_cfv
        self.enable_cache = enable_cache
        self.cache_max_size = cache_max_size
        self.mode = mode
        self.rng = get_rng()
        
        # Cache: (bucket_public, bucket_ranges_hash, action_set_id, street) -> value
        self._cache: Dict[Tuple, float] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        # CFV Net inference (lazy initialization)
        self.cfv_net_inference = None
        self.cfv_feature_builder = None
        self.cfv_net_config = cfv_net_config or {}
        
        # CFV Net metrics
        self._cfv_net_accepts = 0
        self._cfv_net_rejects = 0
        self._cfv_net_latency_samples = []
        
        # Initialize CFV Net if needed
        if self.mode == "cfv_net":
            self._init_cfv_net()
        
        logger.info(
            f"LeafEvaluator initialized: mode={mode}, use_cfv={use_cfv}, "
            f"rollout_samples={num_rollout_samples}, cache={enable_cache} (max={cache_max_size})"
        )
    
    def _init_cfv_net(self):
        """Initialize CFV Net inference."""
        try:
            from holdem.value_net import CFVInference, CFVFeatureBuilder, create_bucket_embeddings
            
            # Get config
            model_path = self.cfv_net_config.get('checkpoint', 'assets/cfv_net/6max_best.onnx')
            stats_path = self.cfv_net_config.get('stats', str(Path(model_path).parent / 'stats.json'))
            cache_size = self.cfv_net_config.get('cache_max_size', 10000)
            gating_config = self.cfv_net_config.get('gating', None)
            
            # Initialize inference
            self.cfv_net_inference = CFVInference(
                model_path=model_path,
                stats_path=stats_path,
                cache_max_size=cache_size,
                gating_config=gating_config,
                use_torch_fallback=True
            )
            
            # Initialize feature builder
            # TODO: Load actual bucket embeddings from blueprint
            num_buckets = 1000  # Placeholder
            embed_dim = 64
            bucket_embeddings = create_bucket_embeddings(num_buckets, embed_dim, seed=42)
            
            self.cfv_feature_builder = CFVFeatureBuilder(
                bucket_embeddings=bucket_embeddings,
                topk_range=16,
                embed_dim=embed_dim
            )
            
            logger.info(f"CFV Net initialized: model={model_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize CFV Net: {e}")
            logger.warning("Falling back to rollout mode")
            self.mode = "rollout"
    
    def evaluate(
        self,
        state: SubgameState,
        hero_hand: List[Card],
        villain_range: Dict[str, float],
        hero_position: int,
        bucket_public: Optional[int] = None,
        bucket_ranges: Optional[Tuple[int, ...]] = None,
        action_set_id: Optional[int] = None
    ) -> float:
        """Evaluate leaf node value.
        
        Args:
            state: Leaf state to evaluate
            hero_hand: Hero's hole cards
            villain_range: Villain's hand range (hand_str -> probability)
            hero_position: Hero's position (0, 1, ...)
            bucket_public: Public card bucket (optional, for caching)
            bucket_ranges: Hand range buckets (optional, for caching)
            action_set_id: Action set identifier (optional, for caching)
            
        Returns:
            Expected value for hero
        """
        # Try cache first
        if self.enable_cache and bucket_public is not None and bucket_ranges is not None:
            cache_key = self._make_cache_key(
                bucket_public, bucket_ranges, action_set_id, state.street
            )
            
            if cache_key in self._cache:
                self._cache_hits += 1
                value = self._cache[cache_key]
                logger.debug(f"Cache HIT for key {cache_key[:3]}... -> {value:.2f}")
                return value
            else:
                self._cache_misses += 1
        
        # Compute value based on mode
        if self.mode == "cfv_net" and self.cfv_net_inference is not None:
            # Try CFV Net first
            value = self._cfv_net_value(
                state, hero_hand, villain_range, hero_position,
                bucket_public, bucket_ranges, action_set_id
            )
            
            # If CFV Net rejects, fallback to rollout/blueprint
            if value is None:
                if self.use_cfv:
                    cfv = self._get_blueprint_cfv(state, hero_hand, hero_position)
                    value = cfv if cfv is not None else self._rollout_value(
                        state, hero_hand, villain_range, hero_position
                    )
                else:
                    value = self._rollout_value(state, hero_hand, villain_range, hero_position)
        
        elif self.use_cfv:
            # Try blueprint CFV first
            cfv = self._get_blueprint_cfv(state, hero_hand, hero_position)
            if cfv is not None:
                value = cfv
            else:
                # Fall back to rollout
                value = self._rollout_value(state, hero_hand, villain_range, hero_position)
        else:
            value = self._rollout_value(state, hero_hand, villain_range, hero_position)
        
        # Cache the result
        if self.enable_cache and bucket_public is not None and bucket_ranges is not None:
            cache_key = self._make_cache_key(
                bucket_public, bucket_ranges, action_set_id, state.street
            )
            self._add_to_cache(cache_key, value)
        
        return value
    
    def _cfv_net_value(
        self,
        state: SubgameState,
        hero_hand: List[Card],
        villain_range: Dict[str, float],
        hero_position: int,
        bucket_public: Optional[int],
        bucket_ranges: Optional[Tuple[int, ...]],
        action_set_id: Optional[int]
    ) -> Optional[float]:
        """Compute value using CFV Net.
        
        Returns:
            Value if accepted by gating, None if rejected (fallback needed)
        """
        import time
        
        if self.cfv_net_inference is None or self.cfv_feature_builder is None:
            return None
        
        try:
            start_time = time.perf_counter()
            
            # Build features
            # Convert hero_position to Position enum
            num_players = state.active_players if hasattr(state, 'active_players') else 6
            hero_pos_enum = Position.from_player_count_and_seat(num_players, hero_position)
            
            # Build range dict (placeholder - should use actual ranges)
            ranges = {}
            if bucket_ranges:
                # Convert bucket_ranges to position-specific ranges
                # Placeholder: distribute buckets across positions
                positions = [Position.BTN, Position.SB, Position.BB, Position.UTG, Position.MP, Position.CO]
                for i, pos in enumerate(positions[:num_players]):
                    if i < len(bucket_ranges):
                        ranges[pos] = [(bucket_ranges[i], 1.0)]
            
            # Build features
            features_obj = self.cfv_feature_builder.build_features(
                street=state.street,
                num_players=num_players,
                hero_position=hero_pos_enum,
                spr=state.spr if hasattr(state, 'spr') else 10.0,
                pot_size=state.pot / 100.0 if hasattr(state, 'pot') else 1.0,  # Convert to bb
                to_call=0.0,  # Placeholder
                last_bet=state.pot * 0.5 / 100.0 if hasattr(state, 'pot') else 0.5,
                action_set="balanced",  # Placeholder
                public_bucket=bucket_public if bucket_public is not None else 0,
                ranges=ranges
            )
            
            feature_vector = features_obj.to_vector()
            
            # Check if hero is in position
            is_ip = hero_pos_enum.is_in_position_postflop(num_players)
            
            # Predict
            mean_cfv, q10, q90, accept = self.cfv_net_inference.predict(
                feature_vector,
                state.street,
                is_ip
            )
            
            # Record latency
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            self._cfv_net_latency_samples.append(latency_ms)
            
            # Keep only recent samples (for p95 calculation)
            if len(self._cfv_net_latency_samples) > 1000:
                self._cfv_net_latency_samples = self._cfv_net_latency_samples[-1000:]
            
            if accept:
                self._cfv_net_accepts += 1
                logger.debug(f"CFV Net ACCEPT: mean={mean_cfv:.2f} bb, PI=[{q10:.2f}, {q90:.2f}], latency={latency_ms:.2f}ms")
                return mean_cfv
            else:
                self._cfv_net_rejects += 1
                logger.debug(f"CFV Net REJECT: mean={mean_cfv:.2f} bb, PI=[{q10:.2f}, {q90:.2f}], latency={latency_ms:.2f}ms")
                return None
        
        except Exception as e:
            logger.error(f"CFV Net error: {e}")
            return None
    
    def get_cfv_net_stats(self) -> Dict[str, float]:
        """Get CFV Net statistics.
        
        Returns:
            Dictionary with CFV Net metrics
        """
        total = self._cfv_net_accepts + self._cfv_net_rejects
        accept_rate = self._cfv_net_accepts / total if total > 0 else 0.0
        
        stats = {
            'cfv_net_accepts': self._cfv_net_accepts,
            'cfv_net_rejects': self._cfv_net_rejects,
            'cfv_net_accept_rate': accept_rate
        }
        
        if self._cfv_net_latency_samples:
            latencies = np.array(self._cfv_net_latency_samples)
            stats['cfv_net_latency_p50'] = np.percentile(latencies, 50)
            stats['cfv_net_latency_p95'] = np.percentile(latencies, 95)
            stats['cfv_net_latency_mean'] = latencies.mean()
        
        if self.cfv_net_inference is not None:
            cache_stats = self.cfv_net_inference.get_cache_stats()
            stats.update({
                'cfv_net_cache_hit_rate': cache_stats['cache_hit_rate'],
                'cfv_net_cache_size': cache_stats['cache_size']
            })
        
        return stats
    
    def _make_cache_key(
        self,
        bucket_public: int,
        bucket_ranges: Tuple[int, ...],
        action_set_id: Optional[int],
        street: Street
    ) -> Tuple:
        """Create cache key from bucket information.
        
        Args:
            bucket_public: Public card bucket
            bucket_ranges: Range buckets (tuple of ints)
            action_set_id: Action set identifier
            street: Current street
            
        Returns:
            Cache key tuple
        """
        # Hash the range buckets to keep key compact
        ranges_hash = hash(bucket_ranges)
        return (bucket_public, ranges_hash, action_set_id, street.value)
    
    def _add_to_cache(self, key: Tuple, value: float):
        """Add entry to cache with LRU eviction.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        # Simple LRU: if cache is full, remove oldest entry
        if len(self._cache) >= self.cache_max_size:
            # Remove first entry (FIFO approximation of LRU)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Cache evicted key {oldest_key[:3]}... (size={len(self._cache)})")
        
        self._cache[key] = value
    
    def get_cache_stats(self) -> Dict[str, float]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        total_accesses = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_accesses if total_accesses > 0 else 0.0
        
        return {
            'cache_size': len(self._cache),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'cache_hit_rate': hit_rate
        }
    
    def clear_cache(self):
        """Clear the cache and reset statistics."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Cache cleared")
    
    def _get_blueprint_cfv(
        self,
        state: SubgameState,
        hero_hand: List[Card],
        hero_position: int
    ) -> Optional[float]:
        """Get blueprint counterfactual value if available.
        
        Args:
            state: Current state
            hero_hand: Hero's cards
            hero_position: Hero's position
            
        Returns:
            CFV if available, else None
        """
        # Create infoset identifier
        # This is a simplified placeholder - in production, use proper encoding
        hand_str = ''.join([str(c) for c in hero_hand])
        board_str = ''.join([str(c) for c in state.board])
        history_str = '-'.join(state.history)
        infoset = f"{hand_str}|{board_str}|{history_str}"
        
        # Try to get strategy from blueprint
        strategy = self.blueprint.get_strategy(infoset)
        
        if not strategy:
            # No blueprint value available
            return None
        
        # Estimate value from strategy (simplified)
        # In production, this should use proper CFV calculation
        # For now, return weighted average assuming balanced strategy
        avg_value = 0.0
        for action, prob in strategy.items():
            # Rough heuristic: aggressive actions -> positive value
            if action in [AbstractAction.BET_POT, AbstractAction.BET_OVERBET_150]:
                avg_value += prob * state.pot * 0.5
            elif action in [AbstractAction.CHECK_CALL]:
                avg_value += prob * 0.0
            elif action == AbstractAction.FOLD:
                avg_value -= prob * (state.pot * 0.3)
        
        logger.debug(f"Blueprint CFV for infoset {infoset[:20]}...: {avg_value:.2f}")
        return avg_value
    
    def _rollout_value(
        self,
        state: SubgameState,
        hero_hand: List[Card],
        villain_range: Dict[str, float],
        hero_position: int
    ) -> float:
        """Rollout to estimate leaf value.
        
        Args:
            state: Current state
            hero_hand: Hero's cards
            villain_range: Villain's hand distribution
            hero_position: Hero's position
            
        Returns:
            Average value over rollouts
        """
        total_value = 0.0
        
        for _ in range(self.num_rollout_samples):
            # Sample villain hand from range
            villain_hand = self._sample_from_range(villain_range)
            
            # Simulate continuation using blueprint
            value = self._simulate_continuation(
                state, hero_hand, villain_hand, hero_position
            )
            total_value += value
        
        avg_value = total_value / self.num_rollout_samples
        logger.debug(
            f"Rollout value ({self.num_rollout_samples} samples): {avg_value:.2f}"
        )
        return avg_value
    
    def _sample_from_range(self, hand_range: Dict[str, float]) -> List[Card]:
        """Sample a hand from probability distribution.
        
        Args:
            hand_range: hand_str -> probability
            
        Returns:
            Sampled hand as list of Cards
        """
        if not hand_range:
            # Empty range, return random hand
            return self._random_hand()
        
        hands = list(hand_range.keys())
        probs = list(hand_range.values())
        
        # Normalize probabilities
        total = sum(probs)
        if total > 0:
            probs = [p / total for p in probs]
        else:
            probs = [1.0 / len(hands)] * len(hands)
        
        sampled_hand_str = self.rng.choice(hands, p=probs)
        return self._parse_hand(sampled_hand_str)
    
    def _random_hand(self) -> List[Card]:
        """Generate random hand."""
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
        suits = ['h', 'd', 'c', 's']
        
        deck = [Card(rank, suit) for rank in ranks for suit in suits]
        self.rng.shuffle(deck)
        return [deck[0], deck[1]]
    
    def _parse_hand(self, hand_str: str) -> List[Card]:
        """Parse hand string to Card objects.
        
        Args:
            hand_str: e.g., "AhKs" or "AA"
            
        Returns:
            List of Card objects
        """
        # Simplified parsing - in production, handle all formats
        if len(hand_str) == 4:
            # "AhKs"
            return [
                Card(hand_str[0], hand_str[1]),
                Card(hand_str[2], hand_str[3])
            ]
        elif len(hand_str) == 2:
            # "AA" - assign random suits
            rank = hand_str[0]
            suits = ['h', 'd']
            return [Card(rank, suits[0]), Card(rank, suits[1])]
        else:
            # Fallback to random
            return self._random_hand()
    
    def _simulate_continuation(
        self,
        state: SubgameState,
        hero_hand: List[Card],
        villain_hand: List[Card],
        hero_position: int
    ) -> float:
        """Simulate game continuation using blueprint strategy.
        
        Args:
            state: Current state
            hero_hand: Hero's cards
            villain_hand: Villain's cards
            hero_position: Hero's position
            
        Returns:
            Simulated payoff for hero
        """
        # Simplified simulation - in production, run full game tree
        # For now, estimate based on hand strength
        
        # Estimate hand strengths (placeholder)
        hero_strength = self._estimate_strength(hero_hand, state.board)
        villain_strength = self._estimate_strength(villain_hand, state.board)
        
        # Simplified payoff
        if hero_strength > villain_strength:
            return state.pot * 0.7  # Win most of pot (rake adjustment)
        elif hero_strength < villain_strength:
            return -state.pot * 0.3  # Lose
        else:
            return 0.0  # Chop
    
    def _estimate_strength(self, hand: List[Card], board: List[Card]) -> float:
        """Rough hand strength estimate.
        
        Args:
            hand: Player's cards
            board: Community cards
            
        Returns:
            Strength value (0-1)
        """
        # Very simplified - just use high card
        rank_values = {
            '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
            '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
        }
        
        max_rank = max(rank_values.get(c.rank, 0) for c in hand)
        return max_rank / 14.0
