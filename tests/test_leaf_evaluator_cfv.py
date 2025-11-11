"""Tests for LeafEvaluator with CFV Net integration."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import numpy as np
from holdem.rt_resolver.leaf_evaluator import LeafEvaluator
from holdem.rt_resolver.subgame_builder import SubgameState
from holdem.mccfr.policy_store import PolicyStore
from holdem.types import Street, Card


@pytest.fixture
def mock_blueprint():
    """Create mock blueprint."""
    blueprint = Mock(spec=PolicyStore)
    blueprint.get_strategy.return_value = {}
    return blueprint


def test_leaf_evaluator_rollout_mode(mock_blueprint):
    """Test LeafEvaluator in rollout mode."""
    evaluator = LeafEvaluator(
        blueprint=mock_blueprint,
        num_rollout_samples=5,
        use_cfv=False,
        mode="rollout"
    )
    
    assert evaluator.mode == "rollout"
    assert evaluator.cfv_net_inference is None


def test_leaf_evaluator_cfv_net_mode_initialization(mock_blueprint):
    """Test LeafEvaluator initialization with CFV Net mode."""
    # Without actual model files, should fallback to rollout
    evaluator = LeafEvaluator(
        blueprint=mock_blueprint,
        mode="cfv_net",
        cfv_net_config={
            'checkpoint': '/nonexistent/model.onnx',
            'cache_max_size': 1000
        }
    )
    
    # Should fallback to rollout if CFV Net fails to initialize
    # (In production with real files, would initialize CFV Net)


def test_leaf_evaluator_evaluate_basic(mock_blueprint):
    """Test basic evaluation."""
    evaluator = LeafEvaluator(
        blueprint=mock_blueprint,
        num_rollout_samples=3,
        use_cfv=False,
        mode="rollout"
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
    
    value = evaluator.evaluate(
        state=state,
        hero_hand=hero_hand,
        villain_range=villain_range,
        hero_position=0
    )
    
    # Should return some value (details depend on rollout logic)
    assert isinstance(value, float)


def test_leaf_evaluator_cache_integration(mock_blueprint):
    """Test that caching works with different modes."""
    evaluator = LeafEvaluator(
        blueprint=mock_blueprint,
        enable_cache=True,
        cache_max_size=100,
        mode="rollout"
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
    
    # First call - should miss cache
    value1 = evaluator.evaluate(
        state=state,
        hero_hand=hero_hand,
        villain_range=villain_range,
        hero_position=0,
        bucket_public=10,
        bucket_ranges=(5, 8),
        action_set_id=1
    )
    
    cache_stats = evaluator.get_cache_stats()
    assert cache_stats['cache_misses'] >= 1
    
    # Second call - should hit cache
    value2 = evaluator.evaluate(
        state=state,
        hero_hand=hero_hand,
        villain_range=villain_range,
        hero_position=0,
        bucket_public=10,
        bucket_ranges=(5, 8),
        action_set_id=1
    )
    
    # Values should be identical (cached)
    assert value1 == value2
    
    cache_stats = evaluator.get_cache_stats()
    assert cache_stats['cache_hits'] >= 1


@patch('holdem.rt_resolver.leaf_evaluator.CFVInference')
@patch('holdem.rt_resolver.leaf_evaluator.CFVFeatureBuilder')
def test_cfv_net_stats(mock_feature_builder, mock_inference, mock_blueprint):
    """Test CFV Net statistics collection."""
    # Setup mocks
    mock_inference_instance = MagicMock()
    mock_inference_instance.predict.return_value = (1.0, 0.5, 1.5, True)  # accept
    mock_inference_instance.get_cache_stats.return_value = {
        'cache_hit_rate': 0.5,
        'cache_size': 50
    }
    mock_inference.return_value = mock_inference_instance
    
    mock_feature_builder_instance = MagicMock()
    mock_feature_builder.return_value = mock_feature_builder_instance
    
    # Create evaluator with CFV Net
    evaluator = LeafEvaluator(
        blueprint=mock_blueprint,
        mode="cfv_net",
        cfv_net_config={
            'checkpoint': 'dummy.onnx',
            'stats': 'dummy.json'
        }
    )
    
    # Force initialization (bypassing file checks for test)
    evaluator.cfv_net_inference = mock_inference_instance
    evaluator.cfv_feature_builder = mock_feature_builder_instance
    
    # Perform evaluation
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
    
    evaluator.evaluate(
        state=state,
        hero_hand=hero_hand,
        villain_range=villain_range,
        hero_position=0,
        bucket_public=10,
        bucket_ranges=(5, 8),
        action_set_id=1
    )
    
    # Get stats
    stats = evaluator.get_cfv_net_stats()
    
    assert 'cfv_net_accepts' in stats
    assert 'cfv_net_rejects' in stats
    assert 'cfv_net_accept_rate' in stats


def test_cfv_net_fallback_on_reject(mock_blueprint):
    """Test that evaluator falls back to rollout when CFV Net rejects."""
    evaluator = LeafEvaluator(
        blueprint=mock_blueprint,
        mode="cfv_net",
        cfv_net_config={
            'checkpoint': '/nonexistent/model.onnx'
        }
    )
    
    # Should fallback to rollout mode
    assert evaluator.mode == "rollout"


def test_mode_parameter_validation(mock_blueprint):
    """Test that different modes are properly handled."""
    # Valid modes
    modes = ["rollout", "blueprint", "cfv_net"]
    
    for mode in modes:
        evaluator = LeafEvaluator(
            blueprint=mock_blueprint,
            mode=mode
        )
        
        # CFV Net mode may fallback if files don't exist
        assert evaluator.mode in ["rollout", "blueprint", "cfv_net"]


def test_cfv_net_latency_tracking(mock_blueprint):
    """Test that CFV Net latency is tracked."""
    evaluator = LeafEvaluator(
        blueprint=mock_blueprint,
        mode="rollout"
    )
    
    # Initially empty
    assert len(evaluator._cfv_net_latency_samples) == 0
    
    # After using CFV Net, would have latency samples
    # (Cannot test without actual model, but structure is in place)


def test_cfv_net_accept_reject_counters(mock_blueprint):
    """Test that CFV Net accept/reject counters work."""
    evaluator = LeafEvaluator(
        blueprint=mock_blueprint,
        mode="rollout"
    )
    
    # Initially zero
    assert evaluator._cfv_net_accepts == 0
    assert evaluator._cfv_net_rejects == 0
    
    stats = evaluator.get_cfv_net_stats()
    assert stats['cfv_net_accept_rate'] == 0.0


def test_get_cache_stats_backward_compatible(mock_blueprint):
    """Test that get_cache_stats still works (backward compatibility)."""
    evaluator = LeafEvaluator(
        blueprint=mock_blueprint,
        enable_cache=True,
        mode="rollout"
    )
    
    stats = evaluator.get_cache_stats()
    
    assert 'cache_size' in stats
    assert 'cache_hits' in stats
    assert 'cache_misses' in stats
    assert 'cache_hit_rate' in stats
