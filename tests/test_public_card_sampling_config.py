"""Tests for public card sampling configuration and ablation mode.

This test suite validates:
1. Configuration parameters work correctly
2. Enable/disable functionality (ablation mode)
3. Backward compatibility with samples_per_solve
4. Warning system for excessive samples
5. Logging and timing statistics
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
import logging
from holdem.types import Card, Street, SearchConfig, RTResolverConfig, TableState
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.resolver import SubgameResolver
from holdem.realtime.subgame import SubgameTree


class TestPublicCardSamplingConfig:
    """Tests for public card sampling configuration."""
    
    @pytest.fixture
    def test_state(self):
        """Create a test game state."""
        return TableState(
            street=Street.FLOP,
            pot=100.0,
            board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
        )
    
    @pytest.fixture
    def our_cards(self):
        """Create test hole cards."""
        return [Card('J', 'c'), Card('T', 'c')]
    
    def test_default_config_disables_sampling(self):
        """Test that default config has sampling disabled."""
        config = SearchConfig()
        
        # Default should have sampling disabled
        assert config.enable_public_card_sampling is False
        assert config.get_effective_num_samples() == 1
    
    def test_enable_public_card_sampling_flag(self):
        """Test enable_public_card_sampling flag controls sampling."""
        # Disabled
        config_off = SearchConfig(
            enable_public_card_sampling=False,
            num_future_boards_samples=10
        )
        assert config_off.get_effective_num_samples() == 1
        
        # Enabled
        config_on = SearchConfig(
            enable_public_card_sampling=True,
            num_future_boards_samples=10
        )
        assert config_on.get_effective_num_samples() == 10
    
    def test_num_future_boards_samples_parameter(self):
        """Test num_future_boards_samples parameter."""
        config = SearchConfig(
            enable_public_card_sampling=True,
            num_future_boards_samples=25
        )
        assert config.get_effective_num_samples() == 25
    
    def test_backward_compatibility_samples_per_solve(self):
        """Test backward compatibility with samples_per_solve."""
        # Old style: using samples_per_solve
        config_old = SearchConfig(
            enable_public_card_sampling=True,
            samples_per_solve=15
        )
        assert config_old.get_effective_num_samples() == 15
        
        # New style takes precedence
        config_new = SearchConfig(
            enable_public_card_sampling=True,
            num_future_boards_samples=20,
            samples_per_solve=15
        )
        assert config_new.get_effective_num_samples() == 20
    
    def test_sampling_mode_parameter(self):
        """Test sampling_mode parameter exists and is configurable."""
        config = SearchConfig(sampling_mode="uniform")
        assert config.sampling_mode == "uniform"
        
        config2 = SearchConfig(sampling_mode="weighted")
        assert config2.sampling_mode == "weighted"
    
    def test_max_samples_warning_threshold(self):
        """Test max_samples_warning_threshold parameter."""
        config = SearchConfig(max_samples_warning_threshold=50)
        assert config.max_samples_warning_threshold == 50
    
    def test_rt_resolver_config_same_parameters(self):
        """Test RTResolverConfig has same parameters."""
        config = RTResolverConfig(
            enable_public_card_sampling=True,
            num_future_boards_samples=30,
            sampling_mode="uniform",
            max_samples_warning_threshold=75
        )
        
        assert config.enable_public_card_sampling is True
        assert config.num_future_boards_samples == 30
        assert config.sampling_mode == "uniform"
        assert config.max_samples_warning_threshold == 75
        assert config.get_effective_num_samples() == 30
    
    def test_disabled_sampling_uses_single_solve(self, test_state, our_cards):
        """Test that disabled sampling uses single solve (no board sampling)."""
        config = SearchConfig(
            time_budget_ms=100,
            min_iterations=50,
            enable_public_card_sampling=False,
            num_future_boards_samples=10  # Should be ignored
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        # Should use single solve
        strategy = resolver.solve_with_sampling(
            subgame, "test_infoset", our_cards, street=Street.FLOP
        )
        
        # Should return a valid strategy
        assert len(strategy) > 0
        total_prob = sum(strategy.values())
        assert abs(total_prob - 1.0) < 0.01
    
    def test_enabled_sampling_with_small_count(self, test_state, our_cards):
        """Test enabled sampling with small sample count."""
        config = SearchConfig(
            time_budget_ms=250,
            min_iterations=25,
            enable_public_card_sampling=True,
            num_future_boards_samples=5
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        strategy = resolver.solve_with_sampling(
            subgame, "test_infoset", our_cards, street=Street.FLOP
        )
        
        # Should return a valid strategy
        assert len(strategy) > 0
        total_prob = sum(strategy.values())
        assert abs(total_prob - 1.0) < 0.01
    
    def test_enabled_sampling_with_medium_count(self, test_state, our_cards):
        """Test enabled sampling with medium sample count."""
        config = SearchConfig(
            time_budget_ms=500,
            min_iterations=25,
            enable_public_card_sampling=True,
            num_future_boards_samples=10
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        strategy = resolver.solve_with_sampling(
            subgame, "test_infoset", our_cards, street=Street.FLOP
        )
        
        # Should return a valid strategy
        assert len(strategy) > 0
        total_prob = sum(strategy.values())
        assert abs(total_prob - 1.0) < 0.01
    
    def test_warning_for_excessive_samples(self, test_state, our_cards, caplog):
        """Test that warning is logged for excessive sample counts."""
        config = SearchConfig(
            time_budget_ms=100,
            min_iterations=10,
            enable_public_card_sampling=True,
            num_future_boards_samples=150,  # Exceeds default threshold of 100
            max_samples_warning_threshold=100
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        with caplog.at_level(logging.WARNING):
            strategy = resolver.solve_with_sampling(
                subgame, "test_infoset", our_cards, street=Street.FLOP
            )
        
        # Check that warning was logged
        warning_found = any(
            "exceeds recommended threshold" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )
        assert warning_found, "Expected warning for excessive samples not found"
    
    def test_no_warning_for_reasonable_samples(self, test_state, our_cards, caplog):
        """Test that no warning is logged for reasonable sample counts."""
        config = SearchConfig(
            time_budget_ms=500,
            min_iterations=25,
            enable_public_card_sampling=True,
            num_future_boards_samples=20,  # Below threshold
            max_samples_warning_threshold=100
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        with caplog.at_level(logging.WARNING):
            strategy = resolver.solve_with_sampling(
                subgame, "test_infoset", our_cards, street=Street.FLOP
            )
        
        # Check that no excessive samples warning was logged
        warning_found = any(
            "exceeds recommended threshold" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )
        assert not warning_found, "Unexpected warning for reasonable sample count"
    
    def test_river_street_falls_back_to_single_solve(self, our_cards):
        """Test that river street falls back to single solve (no future cards to sample)."""
        state = TableState(
            street=Street.RIVER,
            pot=200.0,
            board=[
                Card('A', 'h'), Card('K', 's'), Card('Q', 'd'),
                Card('J', 'h'), Card('T', 's')
            ]
        )
        
        config = SearchConfig(
            time_budget_ms=200,
            min_iterations=50,
            enable_public_card_sampling=True,
            num_future_boards_samples=10
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        subgame = SubgameTree([Street.RIVER], state, our_cards)
        
        # On river, should fall back to single solve even with sampling enabled
        strategy = resolver.solve_with_sampling(
            subgame, "test_infoset", our_cards, street=Street.RIVER
        )
        
        # Should return a valid strategy (no crash, no NaN)
        assert len(strategy) > 0
        total_prob = sum(strategy.values())
        assert abs(total_prob - 1.0) < 0.01
        assert all(0.0 <= prob <= 1.0 for prob in strategy.values())

    
    def test_sampling_statistics_logged(self, test_state, our_cards, caplog):
        """Test that sampling statistics are logged."""
        config = SearchConfig(
            time_budget_ms=300,
            min_iterations=20,
            enable_public_card_sampling=True,
            num_future_boards_samples=6
        )
        
        blueprint = PolicyStore()
        resolver = SubgameResolver(config, blueprint)
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        
        with caplog.at_level(logging.INFO):
            strategy = resolver.solve_with_sampling(
                subgame, "test_infoset", our_cards, street=Street.FLOP
            )
        
        # Check for sampling enabled log
        enabled_log = any(
            "Public card sampling enabled" in record.message
            for record in caplog.records
            if record.levelname == "INFO"
        )
        assert enabled_log, "Expected 'sampling enabled' log not found"
        
        # Check for sampling complete log with statistics
        complete_log = any(
            "Public card sampling complete" in record.message and "boards sampled" in record.message
            for record in caplog.records
            if record.levelname == "INFO"
        )
        assert complete_log, "Expected 'sampling complete' log not found"
        
        # Check for timing information
        timing_log = any(
            "total_time" in record.message and "solving" in record.message
            for record in caplog.records
            if record.levelname == "INFO"
        )
        assert timing_log, "Expected timing information in log not found"


class TestPublicCardSamplingAblation:
    """Ablation tests comparing sampling ON vs OFF."""
    
    @pytest.fixture
    def test_state(self):
        """Create a test game state."""
        return TableState(
            street=Street.FLOP,
            pot=100.0,
            board=[Card('A', 'h'), Card('K', 's'), Card('Q', 'd')]
        )
    
    @pytest.fixture
    def our_cards(self):
        """Create test hole cards."""
        return [Card('J', 'c'), Card('T', 'c')]
    
    def test_ablation_comparison(self, test_state, our_cards):
        """Test that both sampling ON and OFF modes produce valid strategies."""
        # Configuration with sampling OFF
        config_off = SearchConfig(
            time_budget_ms=200,
            min_iterations=100,
            enable_public_card_sampling=False
        )
        
        # Configuration with sampling ON
        config_on = SearchConfig(
            time_budget_ms=200,
            min_iterations=100,
            enable_public_card_sampling=True,
            num_future_boards_samples=5
        )
        
        blueprint = PolicyStore()
        
        # Solve with sampling OFF
        resolver_off = SubgameResolver(config_off, blueprint)
        subgame = SubgameTree([Street.FLOP], test_state, our_cards)
        strategy_off = resolver_off.solve_with_sampling(
            subgame, "test_infoset", our_cards, street=Street.FLOP
        )
        
        # Solve with sampling ON
        resolver_on = SubgameResolver(config_on, blueprint)
        subgame2 = SubgameTree([Street.FLOP], test_state, our_cards)
        strategy_on = resolver_on.solve_with_sampling(
            subgame2, "test_infoset", our_cards, street=Street.FLOP
        )
        
        # Both should produce valid strategies
        assert len(strategy_off) > 0
        assert abs(sum(strategy_off.values()) - 1.0) < 0.01
        
        assert len(strategy_on) > 0
        assert abs(sum(strategy_on.values()) - 1.0) < 0.01
        
        # Strategies may differ (that's expected due to sampling variance)
        # but both should be valid probability distributions
    
    def test_consistency_with_num_samples_1(self, test_state, our_cards):
        """Test that num_samples=1 with sampling enabled behaves like disabled."""
        # Explicitly disabled
        config_disabled = SearchConfig(
            time_budget_ms=100,
            min_iterations=50,
            enable_public_card_sampling=False
        )
        
        # Enabled but with num_samples=1
        config_one_sample = SearchConfig(
            time_budget_ms=100,
            min_iterations=50,
            enable_public_card_sampling=True,
            num_future_boards_samples=1
        )
        
        blueprint = PolicyStore()
        
        resolver_disabled = SubgameResolver(config_disabled, blueprint)
        subgame1 = SubgameTree([Street.FLOP], test_state, our_cards)
        strategy_disabled = resolver_disabled.solve_with_sampling(
            subgame1, "test_infoset", our_cards, street=Street.FLOP
        )
        
        resolver_one = SubgameResolver(config_one_sample, blueprint)
        subgame2 = SubgameTree([Street.FLOP], test_state, our_cards)
        strategy_one = resolver_one.solve_with_sampling(
            subgame2, "test_infoset", our_cards, street=Street.FLOP
        )
        
        # Both should produce valid strategies
        assert len(strategy_disabled) > 0
        assert len(strategy_one) > 0
        
        # Note: Strategies may differ due to randomness, but both should be valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
