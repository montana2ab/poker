"""Tests for new TensorBoard metrics (policy entropy and regret norm)."""

import pytest
import tempfile
from pathlib import Path
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver


def test_policy_entropy_calculation():
    """Test that policy entropy metrics are calculated correctly."""
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    config = MCCFRConfig(
        num_iterations=100,
        exploration_epsilon=0.6,
        tensorboard_log_interval=10
    )
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    # Run a few iterations to populate strategy_sum
    for i in range(50):
        solver.sampler.sample_iteration(i + 1)
    
    # Calculate policy entropy metrics
    entropy_metrics = solver._calculate_policy_entropy_metrics()
    
    # Check that we get metrics for streets
    # Note: metrics may be empty if no infosets for that street
    assert isinstance(entropy_metrics, dict)
    
    # If we have any metrics, they should be non-negative (entropy >= 0)
    for metric_name, value in entropy_metrics.items():
        assert value >= 0, f"{metric_name} should be non-negative"
        assert metric_name.startswith('policy_entropy/'), f"Unexpected metric: {metric_name}"


def test_regret_norm_calculation():
    """Test that regret norm metrics are calculated correctly."""
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    config = MCCFRConfig(
        num_iterations=100,
        exploration_epsilon=0.6,
        tensorboard_log_interval=10
    )
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    # Run a few iterations to populate regrets
    for i in range(50):
        solver.sampler.sample_iteration(i + 1)
    
    # Calculate regret norm metrics
    regret_metrics = solver._calculate_regret_norm_metrics()
    
    # Check that we get metrics
    assert isinstance(regret_metrics, dict)
    
    # If we have any metrics, they should be non-negative (L2 norm >= 0)
    for metric_name, value in regret_metrics.items():
        assert value >= 0, f"{metric_name} should be non-negative"
        assert metric_name.startswith('avg_regret_norm/'), f"Unexpected metric: {metric_name}"


def test_tensorboard_metrics_logged():
    """Test that new metrics are logged to TensorBoard."""
    try:
        from torch.utils.tensorboard import SummaryWriter
    except ImportError:
        pytest.skip("TensorBoard not installed")
    
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    config = MCCFRConfig(
        num_iterations=1100,  # Need enough to trigger logging
        exploration_epsilon=0.6,
        tensorboard_log_interval=1000
    )
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Train with TensorBoard enabled
        solver.train(logdir=logdir, use_tensorboard=True)
        
        # Check that TensorBoard directory exists
        tensorboard_dir = logdir / "tensorboard"
        assert tensorboard_dir.exists(), "TensorBoard directory should be created"
        
        # Check for event files
        event_files = list(tensorboard_dir.glob("events.out.tfevents.*"))
        assert len(event_files) > 0, "Should create TensorBoard event files"
        assert event_files[0].stat().st_size > 0, "Event file should contain data"


def test_position_extraction():
    """Test position extraction from infoset."""
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    config = MCCFRConfig(num_iterations=10)
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    # Test various infoset formats
    # Note: These are simplified tests of the heuristic
    
    # Infoset with call/check (should be IP)
    infoset_ip = "preflop|bc"
    position = solver._extract_position_from_infoset(infoset_ip)
    assert position == 'IP'
    
    # Infoset with bet/raise (should be OOP)
    infoset_oop = "flop|br"
    position = solver._extract_position_from_infoset(infoset_oop)
    assert position == 'OOP'
    
    # Empty history
    infoset_none = "turn|"
    position = solver._extract_position_from_infoset(infoset_none)
    assert position is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
