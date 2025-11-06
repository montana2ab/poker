"""Tests for epsilon schedule functionality."""

import pytest
import tempfile
from pathlib import Path
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver


def test_epsilon_schedule_config():
    """Test that epsilon schedule is properly configured."""
    schedule = [(0, 0.6), (1000, 0.3), (2000, 0.1)]
    
    config = MCCFRConfig(
        num_iterations=3000,
        epsilon_schedule=schedule
    )
    
    assert config.epsilon_schedule == schedule
    assert config.exploration_epsilon == 0.6  # Default value


def test_epsilon_schedule_updates():
    """Test that epsilon updates according to schedule during training."""
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    schedule = [(0, 0.6), (50, 0.3), (100, 0.1)]
    config = MCCFRConfig(
        num_iterations=150,
        checkpoint_interval=1000,  # Disable checkpoints
        epsilon_schedule=schedule,
        tensorboard_log_interval=10
    )
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Train and check epsilon updates
        # We can't easily test the exact iterations, but we can verify
        # the solver initializes correctly
        assert solver._current_epsilon == 0.6
        
        # Manually test epsilon update logic
        solver.iteration = 0
        solver._update_epsilon_schedule()
        assert solver._current_epsilon == 0.6
        
        solver.iteration = 50
        solver._update_epsilon_schedule()
        assert solver._current_epsilon == 0.3
        
        solver.iteration = 100
        solver._update_epsilon_schedule()
        assert solver._current_epsilon == 0.1
        
        solver.iteration = 150
        solver._update_epsilon_schedule()
        assert solver._current_epsilon == 0.1  # Should stay at last value


def test_static_epsilon_without_schedule():
    """Test that static epsilon works when schedule is not provided."""
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    config = MCCFRConfig(
        num_iterations=100,
        exploration_epsilon=0.5,
        epsilon_schedule=None  # No schedule
    )
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    # Should use static epsilon
    assert solver._current_epsilon == 0.5
    
    # Update should do nothing
    solver.iteration = 50
    solver._update_epsilon_schedule()
    assert solver._current_epsilon == 0.5


def test_epsilon_set_in_sampler():
    """Test that epsilon is properly set in the outcome sampler."""
    bucketing = HandBucketing(k_preflop=2, k_flop=2, k_turn=2, k_river=2)
    
    schedule = [(0, 0.6), (50, 0.3)]
    config = MCCFRConfig(
        num_iterations=100,
        epsilon_schedule=schedule
    )
    
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=2
    )
    
    # Initial epsilon
    assert solver.sampler.epsilon == 0.6
    
    # Update and check sampler
    solver.iteration = 50
    solver._update_epsilon_schedule()
    assert solver.sampler.epsilon == 0.3


def test_yaml_epsilon_schedule_parsing():
    """Test that epsilon schedule can be loaded from YAML format."""
    import yaml
    
    yaml_content = """
    num_iterations: 1000
    epsilon_schedule:
      - [0, 0.6]
      - [500, 0.3]
      - [800, 0.1]
    """
    
    config_dict = yaml.safe_load(yaml_content)
    
    # Convert to tuples as done in train_blueprint.py
    if 'epsilon_schedule' in config_dict and config_dict['epsilon_schedule'] is not None:
        config_dict['epsilon_schedule'] = [tuple(item) for item in config_dict['epsilon_schedule']]
    
    config = MCCFRConfig(**config_dict)
    
    assert config.epsilon_schedule == [(0, 0.6), (500, 0.3), (800, 0.1)]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
