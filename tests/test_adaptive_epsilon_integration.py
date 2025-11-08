"""Integration test for adaptive epsilon scheduler with MCCFRSolver."""

import pytest
from unittest.mock import Mock, MagicMock
from holdem.types import MCCFRConfig
from holdem.mccfr.adaptive_epsilon import AdaptiveEpsilonScheduler


class TestAdaptiveEpsilonIntegration:
    """Test adaptive epsilon scheduler integration with solver."""
    
    def test_adaptive_scheduler_disabled_by_default(self):
        """Test that adaptive scheduler is disabled by default."""
        config = MCCFRConfig(
            num_iterations=1000,
            epsilon_schedule=[(0, 0.6), (500, 0.5)]
        )
        
        assert config.adaptive_epsilon_enabled is False
    
    def test_config_with_adaptive_parameters(self):
        """Test config with all adaptive parameters set."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=35.0,
            adaptive_window_merges=10,
            adaptive_min_infoset_growth=10.0,
            adaptive_early_shift_ratio=0.1,
            adaptive_extension_ratio=0.15,
            adaptive_force_after_ratio=0.30,
            epsilon_schedule=[(0, 0.6), (100000, 0.5), (200000, 0.4)]
        )
        
        assert config.adaptive_epsilon_enabled is True
        assert config.adaptive_target_ips == 35.0
        assert config.adaptive_window_merges == 10
        assert config.adaptive_min_infoset_growth == 10.0
        assert config.adaptive_early_shift_ratio == 0.1
        assert config.adaptive_extension_ratio == 0.15
        assert config.adaptive_force_after_ratio == 0.30
    
    def test_scheduler_creation_with_config(self):
        """Test creating scheduler from config."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=40.0,
            adaptive_min_infoset_growth=15.0,
            epsilon_schedule=[(0, 0.6), (100000, 0.5)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        assert scheduler.target_ips == 40.0
        assert scheduler.min_infoset_growth == 15.0
        assert len(scheduler.base_schedule) == 2
    
    def test_realistic_training_scenario(self):
        """Test a realistic training scenario with varying performance."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            adaptive_min_infoset_growth=10.0,
            adaptive_window_merges=5,
            epsilon_schedule=[
                (0, 0.60),
                (110000, 0.50),
                (240000, 0.40),
                (480000, 0.30),
                (720000, 0.20),
                (960000, 0.12),
                (1020000, 0.08)
            ]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # Simulate initial training phase with good performance
        # Should reach first transition (110k) around 100k with early shift
        scheduler.record_merge(10000, 1000, 250.0, 10000)  # 40 iter/s
        scheduler.record_merge(20000, 1200, 250.0, 10000)  # 40 iter/s, 20 growth/k
        scheduler.record_merge(50000, 2000, 750.0, 30000)  # 40 iter/s, ~27 growth/k
        
        # At 99k (90% of 110k), with good performance, should transition early
        epsilon = scheduler.get_epsilon(99000)
        assert epsilon == 0.50  # Early transition
        
        # Clear the window and simulate mid-training with slower performance
        # Need to record enough new data to replace the window
        scheduler.record_merge(150000, 6000, 2000.0, 10000)  # 5 iter/s (slow!)
        scheduler.record_merge(160000, 6050, 2000.0, 10000)  # 5 iter/s, 5 growth/k
        scheduler.record_merge(170000, 6100, 2000.0, 10000)  # 5 iter/s, 5 growth/k
        scheduler.record_merge(180000, 6150, 2000.0, 10000)  # 5 iter/s, 5 growth/k
        scheduler.record_merge(190000, 6200, 2000.0, 10000)  # 5 iter/s, 5 growth/k
        scheduler.record_merge(200000, 6250, 2000.0, 10000)  # 5 iter/s, 5 growth/k
        
        # At 240k target with poor performance, should delay
        epsilon = scheduler.get_epsilon(240000)
        assert epsilon == 0.50  # Still at previous epsilon
        
        # At extension limit (240k * 1.15 = 276k), should transition anyway
        epsilon = scheduler.get_epsilon(276000)
        assert epsilon == 0.40  # Delayed transition
        
        # Simulate late training with excellent performance again
        scheduler.record_merge(450000, 15000, 250.0, 10000)  # 40 iter/s
        scheduler.record_merge(460000, 15250, 250.0, 10000)  # 40 iter/s, 25 growth/k
        scheduler.record_merge(470000, 15500, 250.0, 10000)  # 40 iter/s, 25 growth/k
        scheduler.record_merge(475000, 15625, 125.0, 5000)   # 40 iter/s, 25 growth/k
        
        # At 480k with strong performance, should transition on time
        epsilon = scheduler.get_epsilon(480000)
        assert epsilon == 0.30
    
    def test_default_parameters_are_reasonable(self):
        """Test that default adaptive parameters are reasonable."""
        config = MCCFRConfig()
        
        # Check defaults match problem specification
        assert config.adaptive_target_ips == 35.0  # As specified in requirements
        assert config.adaptive_min_infoset_growth == 10.0  # Per 1000 iterations
        assert config.adaptive_early_shift_ratio == 0.1  # 10% early shift
        assert config.adaptive_extension_ratio == 0.15  # 15% extension
        assert config.adaptive_force_after_ratio == 0.30  # 30% force threshold
        assert config.adaptive_window_merges == 10  # 10 recent merges
    
    def test_tensorboard_metrics_format(self):
        """Test that TensorBoard metrics have correct format."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            adaptive_min_infoset_growth=10.0,
            epsilon_schedule=[(0, 0.6), (100000, 0.5)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # Record some data
        scheduler.record_merge(10000, 1000, 250.0, 10000)
        scheduler.record_merge(20000, 1200, 250.0, 10000)
        
        metrics = scheduler.get_metrics()
        
        # Check all expected metrics are present
        assert 'adaptive/ips' in metrics
        assert 'adaptive/ips_ratio' in metrics
        assert 'adaptive/infoset_growth' in metrics
        assert 'adaptive/growth_ratio' in metrics
        
        # Check metrics have reasonable values
        assert metrics['adaptive/ips'] > 0
        assert metrics['adaptive/ips_ratio'] > 0
        assert metrics['adaptive/infoset_growth'] > 0
        assert metrics['adaptive/growth_ratio'] > 0
