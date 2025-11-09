"""Tests for leaf evaluator caching (P1 requirement)."""

import pytest
from unittest.mock import Mock
from holdem.rt_resolver.leaf_evaluator import LeafEvaluator
from holdem.rt_resolver.subgame_builder import SubgameState
from holdem.mccfr.policy_store import PolicyStore
from holdem.types import Street, Card


def test_cache_initialization():
    """Test that cache is initialized correctly."""
    blueprint = Mock(spec=PolicyStore)
    
    # With cache enabled
    evaluator = LeafEvaluator(
        blueprint=blueprint,
        num_rollout_samples=10,
        use_cfv=True,
        enable_cache=True,
        cache_max_size=1000
    )
    
    assert evaluator.enable_cache is True
    assert evaluator.cache_max_size == 1000
    assert evaluator._cache_hits == 0
    assert evaluator._cache_misses == 0
    
    # With cache disabled
    evaluator2 = LeafEvaluator(
        blueprint=blueprint,
        enable_cache=False
    )
    
    assert evaluator2.enable_cache is False


def test_cache_hit():
    """Test that cache returns cached values on subsequent calls."""
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {}  # No strategy, will use rollout
    
    evaluator = LeafEvaluator(
        blueprint=blueprint,
        num_rollout_samples=5,
        use_cfv=False,  # Use rollout
        enable_cache=True,
        cache_max_size=100
    )
    
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    hero_hand = [Card('A', 's'), Card('K', 'h')]
    villain_range = {'AsKh': 1.0}
    
    # First call - should be cache miss
    value1 = evaluator.evaluate(
        state=state,
        hero_hand=hero_hand,
        villain_range=villain_range,
        hero_position=0,
        bucket_public=10,
        bucket_ranges=(5, 8),
        action_set_id=1
    )
    
    stats = evaluator.get_cache_stats()
    assert stats['cache_misses'] == 1
    assert stats['cache_hits'] == 0
    
    # Second call with same cache key - should be cache hit
    value2 = evaluator.evaluate(
        state=state,
        hero_hand=hero_hand,
        villain_range=villain_range,
        hero_position=0,
        bucket_public=10,
        bucket_ranges=(5, 8),
        action_set_id=1
    )
    
    stats = evaluator.get_cache_stats()
    assert stats['cache_hits'] == 1
    assert stats['cache_misses'] == 1
    
    # Values should be identical (cached)
    assert value1 == value2


def test_cache_different_keys():
    """Test that different cache keys produce different lookups."""
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {}
    
    evaluator = LeafEvaluator(
        blueprint=blueprint,
        num_rollout_samples=5,
        use_cfv=False,
        enable_cache=True
    )
    
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    hero_hand = [Card('A', 's'), Card('K', 'h')]
    villain_range = {'AsKh': 1.0}
    
    # Call with different bucket_public - should be cache miss
    value1 = evaluator.evaluate(
        state, hero_hand, villain_range, 0,
        bucket_public=10, bucket_ranges=(5, 8), action_set_id=1
    )
    
    value2 = evaluator.evaluate(
        state, hero_hand, villain_range, 0,
        bucket_public=11, bucket_ranges=(5, 8), action_set_id=1
    )
    
    stats = evaluator.get_cache_stats()
    assert stats['cache_misses'] == 2
    assert stats['cache_hits'] == 0
    
    # Call with different bucket_ranges - should be cache miss
    value3 = evaluator.evaluate(
        state, hero_hand, villain_range, 0,
        bucket_public=10, bucket_ranges=(6, 9), action_set_id=1
    )
    
    stats = evaluator.get_cache_stats()
    assert stats['cache_misses'] == 3
    
    # Call with different action_set_id - should be cache miss
    value4 = evaluator.evaluate(
        state, hero_hand, villain_range, 0,
        bucket_public=10, bucket_ranges=(5, 8), action_set_id=2
    )
    
    stats = evaluator.get_cache_stats()
    assert stats['cache_misses'] == 4


def test_cache_eviction():
    """Test LRU cache eviction when max size is reached."""
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {}
    
    # Small cache size to test eviction
    evaluator = LeafEvaluator(
        blueprint=blueprint,
        num_rollout_samples=5,
        use_cfv=False,
        enable_cache=True,
        cache_max_size=3  # Only 3 entries
    )
    
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    hero_hand = [Card('A', 's'), Card('K', 'h')]
    villain_range = {'AsKh': 1.0}
    
    # Add 3 entries
    for i in range(3):
        evaluator.evaluate(
            state, hero_hand, villain_range, 0,
            bucket_public=i, bucket_ranges=(5, 8), action_set_id=1
        )
    
    stats = evaluator.get_cache_stats()
    assert stats['cache_size'] == 3
    
    # Add 4th entry - should evict first entry
    evaluator.evaluate(
        state, hero_hand, villain_range, 0,
        bucket_public=3, bucket_ranges=(5, 8), action_set_id=1
    )
    
    stats = evaluator.get_cache_stats()
    assert stats['cache_size'] == 3  # Still 3 due to eviction
    
    # Accessing first entry again should be a miss (evicted)
    evaluator.evaluate(
        state, hero_hand, villain_range, 0,
        bucket_public=0, bucket_ranges=(5, 8), action_set_id=1
    )
    
    stats = evaluator.get_cache_stats()
    # Should have one more miss (first entry was evicted)
    assert stats['cache_misses'] == 5  # 4 initial + 1 re-access


def test_cache_hit_rate():
    """Test cache hit rate calculation."""
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {}
    
    evaluator = LeafEvaluator(
        blueprint=blueprint,
        num_rollout_samples=5,
        use_cfv=False,
        enable_cache=True
    )
    
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    hero_hand = [Card('A', 's'), Card('K', 'h')]
    villain_range = {'AsKh': 1.0}
    
    # 2 unique calls
    for i in range(2):
        evaluator.evaluate(
            state, hero_hand, villain_range, 0,
            bucket_public=i, bucket_ranges=(5, 8), action_set_id=1
        )
    
    # 8 repeated calls (should hit cache)
    for i in range(2):
        for _ in range(4):
            evaluator.evaluate(
                state, hero_hand, villain_range, 0,
                bucket_public=i, bucket_ranges=(5, 8), action_set_id=1
            )
    
    stats = evaluator.get_cache_stats()
    # 2 misses + 8 hits = 10 total
    assert stats['cache_misses'] == 2
    assert stats['cache_hits'] == 8
    assert stats['cache_hit_rate'] == pytest.approx(0.8)


def test_clear_cache():
    """Test clearing the cache."""
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {}
    
    evaluator = LeafEvaluator(
        blueprint=blueprint,
        num_rollout_samples=5,
        use_cfv=False,
        enable_cache=True
    )
    
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    hero_hand = [Card('A', 's'), Card('K', 'h')]
    villain_range = {'AsKh': 1.0}
    
    # Add some entries
    for i in range(5):
        evaluator.evaluate(
            state, hero_hand, villain_range, 0,
            bucket_public=i, bucket_ranges=(5, 8), action_set_id=1
        )
    
    stats = evaluator.get_cache_stats()
    assert stats['cache_size'] == 5
    assert stats['cache_misses'] == 5
    
    # Clear cache
    evaluator.clear_cache()
    
    stats = evaluator.get_cache_stats()
    assert stats['cache_size'] == 0
    assert stats['cache_hits'] == 0
    assert stats['cache_misses'] == 0


def test_cache_disabled():
    """Test that caching can be disabled."""
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {}
    
    evaluator = LeafEvaluator(
        blueprint=blueprint,
        num_rollout_samples=5,
        use_cfv=False,
        enable_cache=False  # Disabled
    )
    
    state = SubgameState(
        street=Street.FLOP,
        board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')],
        pot=100.0,
        history=[],
        active_players=2,
        depth=0
    )
    
    hero_hand = [Card('A', 's'), Card('K', 'h')]
    villain_range = {'AsKh': 1.0}
    
    # Multiple calls with same key
    for _ in range(5):
        evaluator.evaluate(
            state, hero_hand, villain_range, 0,
            bucket_public=10, bucket_ranges=(5, 8), action_set_id=1
        )
    
    # With cache disabled, should have no hits
    stats = evaluator.get_cache_stats()
    assert stats['cache_hits'] == 0
    assert stats['cache_size'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
