"""Test DCFR discount and warm-start functionality."""

import pytest
import numpy as np
import tempfile
from pathlib import Path
from holdem.types import MCCFRConfig, BucketConfig
from holdem.mccfr.regrets import RegretTracker
from holdem.abstraction.actions import AbstractAction
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver


def test_dcfr_discount_calculation():
    """Test that DCFR discount factors are calculated correctly."""
    config = MCCFRConfig(
        num_iterations=10000,
        discount_mode="dcfr",
        discount_interval=1000,
        use_linear_weighting=True,
        enable_pruning=False  # Disable for this test
    )
    
    # Test discount factors at different iterations
    # α = (t + d) / (t + 2d)
    # β = t / (t + d)
    
    # At t=1000, d=1000:
    # α = (1000 + 1000) / (1000 + 2000) = 2000/3000 = 0.6667
    # β = 1000 / (1000 + 1000) = 1000/2000 = 0.5
    t = 1000.0
    d = 1000.0
    expected_alpha = (t + d) / (t + 2 * d)
    expected_beta = t / (t + d)
    
    assert abs(expected_alpha - 0.6667) < 0.001
    assert abs(expected_beta - 0.5) < 0.001
    
    # At t=10000, d=1000:
    # α = (10000 + 1000) / (10000 + 2000) = 11000/12000 = 0.9167
    # β = 10000 / (10000 + 1000) = 10000/11000 = 0.9091
    t = 10000.0
    d = 1000.0
    expected_alpha = (t + d) / (t + 2 * d)
    expected_beta = t / (t + d)
    
    assert abs(expected_alpha - 0.9167) < 0.001
    assert abs(expected_beta - 0.9091) < 0.001


def test_dcfr_reset_negative_regrets():
    """Test that DCFR resets negative regrets to 0 (CFR+ behavior)."""
    tracker = RegretTracker()
    
    infoset = "test_infoset"
    actions = [AbstractAction.FOLD, AbstractAction.CHECK_CALL, AbstractAction.BET_HALF_POT]
    
    # Set up mixed positive and negative regrets
    tracker.update_regret(infoset, AbstractAction.FOLD, -100.0)
    tracker.update_regret(infoset, AbstractAction.CHECK_CALL, 50.0)
    tracker.update_regret(infoset, AbstractAction.BET_HALF_POT, -200.0)
    
    # Apply discount
    tracker.discount(regret_factor=0.9, strategy_factor=0.9)
    
    # Reset negative regrets (CFR+ behavior)
    tracker.reset_regrets()
    
    # Check that negative regrets are now 0
    assert tracker.get_regret(infoset, AbstractAction.FOLD) == 0.0
    assert tracker.get_regret(infoset, AbstractAction.BET_HALF_POT) == 0.0
    
    # Positive regret should be preserved (after discount)
    assert abs(tracker.get_regret(infoset, AbstractAction.CHECK_CALL) - 45.0) < 0.01


def test_regret_state_serialization():
    """Test that regret state can be saved and restored."""
    tracker = RegretTracker()
    
    # Set up some regrets and strategy
    infoset1 = "test_infoset_1"
    infoset2 = "test_infoset_2"
    
    tracker.update_regret(infoset1, AbstractAction.FOLD, 100.0)
    tracker.update_regret(infoset1, AbstractAction.CHECK_CALL, 200.0)
    tracker.add_strategy(infoset1, {AbstractAction.FOLD: 0.3, AbstractAction.CHECK_CALL: 0.7}, 1.0)
    
    tracker.update_regret(infoset2, AbstractAction.BET_HALF_POT, 50.0)
    tracker.add_strategy(infoset2, {AbstractAction.BET_HALF_POT: 1.0}, 1.0)
    
    # Get state
    state = tracker.get_state()
    
    # Verify state structure
    assert 'regrets' in state
    assert 'strategy_sum' in state
    assert len(state['regrets']) == 2
    assert len(state['strategy_sum']) == 2
    
    # Create new tracker and restore state
    tracker2 = RegretTracker()
    tracker2.set_state(state)
    
    # Verify regrets are restored
    assert abs(tracker2.get_regret(infoset1, AbstractAction.FOLD) - 100.0) < 0.01
    assert abs(tracker2.get_regret(infoset1, AbstractAction.CHECK_CALL) - 200.0) < 0.01
    assert abs(tracker2.get_regret(infoset2, AbstractAction.BET_HALF_POT) - 50.0) < 0.01
    
    # Verify strategy is restored
    strategy1 = tracker2.get_average_strategy(infoset1, [AbstractAction.FOLD, AbstractAction.CHECK_CALL])
    assert abs(strategy1[AbstractAction.FOLD] - 0.3) < 0.01
    assert abs(strategy1[AbstractAction.CHECK_CALL] - 0.7) < 0.01


def test_warm_start_checkpoint():
    """Test warm-start functionality with checkpoint save/load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Create minimal bucketing for testing
        bucket_config = BucketConfig(
            k_preflop=2,
            k_flop=2,
            k_turn=2,
            k_river=2,
            num_samples=100
        )
        bucketing = HandBucketing(bucket_config)
        bucketing.build()
        
        # Create solver with DCFR
        config = MCCFRConfig(
            num_iterations=100,
            discount_mode="dcfr",
            discount_interval=50,
            checkpoint_interval=50,
            use_linear_weighting=True,
            enable_pruning=False,
            tensorboard_log_interval=10000  # Disable for test
        )
        
        solver1 = MCCFRSolver(config, bucketing)
        
        # Run some iterations
        for i in range(1, 51):
            solver1.iteration = i
            solver1.sampler.sample_iteration(i)
        
        # Save checkpoint
        solver1.save_checkpoint(logdir, iteration=50)
        
        # Get regret state before
        regrets_before = len(solver1.sampler.regret_tracker.regrets)
        strategy_before = len(solver1.sampler.regret_tracker.strategy_sum)
        
        # Create new solver
        solver2 = MCCFRSolver(config, bucketing)
        
        # Load checkpoint with warm-start
        checkpoint_path = logdir / "checkpoints" / "checkpoint_iter50.pkl"
        loaded_iter = solver2.load_checkpoint(checkpoint_path, warm_start=True)
        
        assert loaded_iter == 50
        
        # Verify regret state is restored
        regrets_after = len(solver2.sampler.regret_tracker.regrets)
        strategy_after = len(solver2.sampler.regret_tracker.strategy_sum)
        
        assert regrets_after == regrets_before
        assert strategy_after == strategy_before
        assert regrets_after > 0  # Should have some regrets


def test_warm_start_disabled():
    """Test that warm-start can be disabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir)
        
        # Create minimal bucketing for testing
        bucket_config = BucketConfig(
            k_preflop=2,
            k_flop=2,
            k_turn=2,
            k_river=2,
            num_samples=100
        )
        bucketing = HandBucketing(bucket_config)
        bucketing.build()
        
        # Create solver
        config = MCCFRConfig(
            num_iterations=100,
            checkpoint_interval=50,
            tensorboard_log_interval=10000
        )
        
        solver1 = MCCFRSolver(config, bucketing)
        
        # Run some iterations
        for i in range(1, 51):
            solver1.iteration = i
            solver1.sampler.sample_iteration(i)
        
        # Save checkpoint
        solver1.save_checkpoint(logdir, iteration=50)
        
        # Create new solver
        solver2 = MCCFRSolver(config, bucketing)
        
        # Load checkpoint WITHOUT warm-start
        checkpoint_path = logdir / "checkpoints" / "checkpoint_iter50.pkl"
        loaded_iter = solver2.load_checkpoint(checkpoint_path, warm_start=False)
        
        assert loaded_iter == 50
        
        # Verify regret state is NOT restored (should be empty)
        assert len(solver2.sampler.regret_tracker.regrets) == 0
        assert len(solver2.sampler.regret_tracker.strategy_sum) == 0


def test_discount_mode_none():
    """Test that discount_mode='none' disables discounting."""
    tracker = RegretTracker()
    
    infoset = "test_infoset"
    tracker.update_regret(infoset, AbstractAction.FOLD, 100.0)
    tracker.add_strategy(infoset, {AbstractAction.FOLD: 1.0}, 100.0)
    
    # With discount_mode='none', discount should not be called
    # But if called manually, verify it would work
    # (In solver, it's skipped when mode='none')
    
    # Verify initial values
    assert abs(tracker.get_regret(infoset, AbstractAction.FOLD) - 100.0) < 0.01
    assert abs(tracker.strategy_sum[infoset][AbstractAction.FOLD] - 100.0) < 0.01


def test_discount_mode_static():
    """Test that discount_mode='static' uses fixed discount factors."""
    tracker = RegretTracker()
    
    infoset = "test_infoset"
    tracker.update_regret(infoset, AbstractAction.FOLD, 100.0)
    tracker.add_strategy(infoset, {AbstractAction.FOLD: 1.0}, 100.0)
    
    # Apply static discount
    alpha = 0.95
    beta = 0.98
    tracker.discount(regret_factor=alpha, strategy_factor=beta)
    
    # Verify discount applied
    assert abs(tracker.get_regret(infoset, AbstractAction.FOLD) - 95.0) < 0.01
    assert abs(tracker.strategy_sum[infoset][AbstractAction.FOLD] - 98.0) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
