"""Tests for adaptive epsilon scheduler."""

import pytest
import time
from holdem.types import MCCFRConfig
from holdem.mccfr.adaptive_epsilon import AdaptiveEpsilonScheduler


class TestAdaptiveEpsilonScheduler:
    """Test adaptive epsilon scheduler functionality."""
    
    def test_initialization(self):
        """Test scheduler initialization."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=35.0,
            adaptive_min_infoset_growth=10.0,
            epsilon_schedule=[(0, 0.6), (100000, 0.5), (200000, 0.4)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        assert scheduler.target_ips == 35.0
        assert scheduler.min_infoset_growth == 10.0
        assert len(scheduler.base_schedule) == 3
        assert scheduler._current_epsilon == 0.6
    
    def test_initialization_no_schedule(self):
        """Test scheduler initialization without epsilon schedule."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=35.0
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        assert len(scheduler.base_schedule) == 0
        assert scheduler.get_epsilon(0) == config.exploration_epsilon
    
    def test_record_merge(self):
        """Test recording merge events."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=35.0,
            adaptive_window_merges=5,
            epsilon_schedule=[(0, 0.6), (100000, 0.5)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # Record some merges
        scheduler.record_merge(1000, 500, 10.0, 1000)  # 100 iter/s
        scheduler.record_merge(2000, 550, 10.0, 1000)  # 100 iter/s
        scheduler.record_merge(3000, 620, 10.0, 1000)  # 100 iter/s
        
        # Check IPS calculation
        avg_ips = scheduler.get_average_ips()
        assert avg_ips is not None
        assert abs(avg_ips - 100.0) < 0.1
        
        # Check infoset growth calculation
        growth_rate = scheduler.get_infoset_growth_rate()
        assert growth_rate is not None
        # Growth: (620 - 500) / (3000 - 1000) * 1000 = 60 per 1000 iterations
        assert abs(growth_rate - 60.0) < 0.1
    
    def test_ips_window_limit(self):
        """Test that IPS window respects maxlen."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_window_merges=3,
            epsilon_schedule=[(0, 0.6)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # Record more than window size
        scheduler.record_merge(1000, 500, 10.0, 1000)  # 100 iter/s
        scheduler.record_merge(2000, 600, 10.0, 1000)  # 100 iter/s
        scheduler.record_merge(3000, 700, 10.0, 1000)  # 100 iter/s
        scheduler.record_merge(4000, 800, 5.0, 1000)   # 200 iter/s (newest)
        
        # Only last 3 should be in window
        assert len(scheduler._ips_window) == 3
        avg_ips = scheduler.get_average_ips()
        # Average of last 3: (100 + 100 + 200) / 3 = 133.33
        assert abs(avg_ips - 133.33) < 0.1
    
    def test_standard_transition(self):
        """Test standard transition at target iteration with criteria met."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            adaptive_min_infoset_growth=10.0,
            epsilon_schedule=[(0, 0.6), (100000, 0.5)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # Record good performance
        scheduler.record_merge(95000, 5000, 250.0, 10000)  # 40 iter/s > 30
        scheduler.record_merge(99000, 5100, 100.0, 4000)   # 40 iter/s
        # Growth: (5100 - 5000) / (99000 - 95000) * 1000 = 25 per 1000 > 10
        
        # At target iteration with criteria met
        epsilon = scheduler.get_epsilon(100000)
        assert epsilon == 0.5
    
    def test_early_transition(self):
        """Test early transition when performance exceeds targets."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            adaptive_min_infoset_growth=10.0,
            adaptive_early_shift_ratio=0.1,
            epsilon_schedule=[(0, 0.6), (100000, 0.5)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # Record excellent performance
        scheduler.record_merge(85000, 5000, 200.0, 10000)  # 50 iter/s >> 30
        scheduler.record_merge(89000, 5200, 100.0, 4000)   # 40 iter/s
        # Growth: (5200 - 5000) / (89000 - 85000) * 1000 = 50 per 1000 >> 10
        
        # Early transition at 90% of target iteration (90000 < 100000)
        epsilon = scheduler.get_epsilon(90000)
        assert epsilon == 0.5  # Should transition early
    
    def test_delayed_transition(self):
        """Test delayed transition when performance is below targets."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            adaptive_min_infoset_growth=10.0,
            adaptive_extension_ratio=0.15,
            epsilon_schedule=[(0, 0.6), (100000, 0.5)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # Record poor performance
        scheduler.record_merge(95000, 5000, 500.0, 10000)  # 20 iter/s < 30
        scheduler.record_merge(99000, 5020, 200.0, 4000)   # 20 iter/s
        # Growth: (5020 - 5000) / (99000 - 95000) * 1000 = 5 per 1000 < 10
        
        # At target iteration, should wait
        epsilon = scheduler.get_epsilon(100000)
        assert epsilon == 0.6  # Should stay at current
        
        # At extension limit, should transition
        epsilon = scheduler.get_epsilon(115000)  # 100000 * 1.15
        assert epsilon == 0.5  # Should transition despite poor performance
    
    def test_forced_transition(self):
        """Test forced transition after maximum extension."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            adaptive_min_infoset_growth=10.0,
            adaptive_force_after_ratio=0.30,
            epsilon_schedule=[(0, 0.6), (100000, 0.5)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # Record poor performance
        scheduler.record_merge(95000, 5000, 500.0, 10000)  # 20 iter/s
        scheduler.record_merge(120000, 5100, 500.0, 10000)  # 20 iter/s
        
        # At force threshold, must transition
        epsilon = scheduler.get_epsilon(130000)  # 100000 * 1.30
        assert epsilon == 0.5  # Forced transition
    
    def test_no_early_transition_without_strong_performance(self):
        """Test that early transition requires strong performance."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            adaptive_min_infoset_growth=10.0,
            adaptive_early_shift_ratio=0.1,
            epsilon_schedule=[(0, 0.6), (100000, 0.5)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # Record marginal performance (just meeting thresholds, not exceeding)
        scheduler.record_merge(85000, 5000, 333.0, 10000)  # 30 iter/s = target
        scheduler.record_merge(89000, 5040, 400.0, 4000)   # 10 iter/s
        # Growth: exactly at threshold
        
        # Should not transition early with marginal performance
        epsilon = scheduler.get_epsilon(90000)
        assert epsilon == 0.6
    
    def test_insufficient_data_fallback(self):
        """Test behavior with insufficient data for adaptive decision."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            epsilon_schedule=[(0, 0.6), (100000, 0.5)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # No data recorded
        
        # At target iteration, should transition (fallback behavior)
        epsilon = scheduler.get_epsilon(100000)
        assert epsilon == 0.5
    
    def test_multiple_transitions(self):
        """Test multiple epsilon transitions in sequence."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            adaptive_min_infoset_growth=10.0,
            epsilon_schedule=[(0, 0.6), (100000, 0.5), (200000, 0.4), (300000, 0.3)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # First transition
        scheduler.record_merge(95000, 5000, 250.0, 10000)
        scheduler.record_merge(99000, 5100, 100.0, 4000)
        epsilon = scheduler.get_epsilon(100000)
        assert epsilon == 0.5
        
        # Second transition
        scheduler.record_merge(195000, 10000, 250.0, 10000)
        scheduler.record_merge(199000, 10200, 100.0, 4000)
        epsilon = scheduler.get_epsilon(200000)
        assert epsilon == 0.4
        
        # Third transition
        scheduler.record_merge(295000, 15000, 250.0, 10000)
        scheduler.record_merge(299000, 15300, 100.0, 4000)
        epsilon = scheduler.get_epsilon(300000)
        assert epsilon == 0.3
    
    def test_get_metrics(self):
        """Test metrics retrieval."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            adaptive_min_infoset_growth=10.0,
            epsilon_schedule=[(0, 0.6)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # No data
        metrics = scheduler.get_metrics()
        assert len(metrics) == 0
        
        # Add data
        scheduler.record_merge(10000, 1000, 250.0, 10000)  # 40 iter/s
        scheduler.record_merge(20000, 1150, 250.0, 10000)  # 40 iter/s
        
        metrics = scheduler.get_metrics()
        assert 'adaptive/ips' in metrics
        assert 'adaptive/ips_ratio' in metrics
        assert 'adaptive/infoset_growth' in metrics
        assert 'adaptive/growth_ratio' in metrics
        
        # Check values
        assert abs(metrics['adaptive/ips'] - 40.0) < 0.1
        assert abs(metrics['adaptive/ips_ratio'] - (40.0 / 30.0)) < 0.1
        # Growth: (1150 - 1000) / (20000 - 10000) * 1000 = 15
        assert abs(metrics['adaptive/infoset_growth'] - 15.0) < 0.1
        assert abs(metrics['adaptive/growth_ratio'] - (15.0 / 10.0)) < 0.1
    
    def test_transition_before_earliest(self):
        """Test that no transition occurs before earliest possible iteration."""
        config = MCCFRConfig(
            adaptive_epsilon_enabled=True,
            adaptive_target_ips=30.0,
            adaptive_min_infoset_growth=10.0,
            adaptive_early_shift_ratio=0.1,
            epsilon_schedule=[(0, 0.6), (100000, 0.5)]
        )
        
        scheduler = AdaptiveEpsilonScheduler(config)
        
        # Record excellent performance
        scheduler.record_merge(80000, 5000, 200.0, 10000)
        scheduler.record_merge(85000, 5500, 125.0, 5000)
        
        # Before earliest (90% of 100000 = 90000)
        epsilon = scheduler.get_epsilon(85000)
        assert epsilon == 0.6  # Should not transition yet
        
        # At earliest with good performance
        epsilon = scheduler.get_epsilon(90000)
        assert epsilon == 0.5  # Now should transition
