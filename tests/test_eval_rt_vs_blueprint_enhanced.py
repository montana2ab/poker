"""Tests for enhanced RT vs Blueprint evaluation."""

import pytest
import sys
from pathlib import Path
import json
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import numpy as np
from holdem.types import Street, Position
from holdem.mccfr.policy_store import PolicyStore

# Import from the tool
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
from eval_rt_vs_blueprint_enhanced import (
    HandResult,
    EnhancedPokerSim,
    parse_street_samples,
    compute_hash,
    _compute_statistics
)


class TestParseStreetSamples:
    """Test street sample parsing."""
    
    def test_parse_single_street(self):
        result = parse_street_samples("flop=16")
        assert result[Street.FLOP] == 16
    
    def test_parse_multiple_streets(self):
        result = parse_street_samples("flop=16,turn=32,river=64")
        assert result[Street.FLOP] == 16
        assert result[Street.TURN] == 32
        assert result[Street.RIVER] == 64
    
    def test_parse_with_spaces(self):
        result = parse_street_samples("flop = 16, turn = 32")
        assert result[Street.FLOP] == 16
        assert result[Street.TURN] == 32


class TestComputeHash:
    """Test hash computation."""
    
    def test_same_object_same_hash(self):
        obj = {'a': 1, 'b': 2}
        hash1 = compute_hash(obj)
        hash2 = compute_hash(obj)
        assert hash1 == hash2
    
    def test_different_objects_different_hash(self):
        obj1 = {'a': 1, 'b': 2}
        obj2 = {'a': 1, 'b': 3}
        hash1 = compute_hash(obj1)
        hash2 = compute_hash(obj2)
        assert hash1 != hash2
    
    def test_hash_length(self):
        obj = {'test': 'value'}
        hash_val = compute_hash(obj)
        assert len(hash_val) == 16


class TestEnhancedPokerSim:
    """Test enhanced poker simulator."""
    
    @pytest.fixture
    def blueprint(self):
        """Create a simple blueprint policy."""
        policy = PolicyStore()
        return policy
    
    @pytest.fixture
    def simulator(self, blueprint):
        """Create simulator instance."""
        return EnhancedPokerSim(blueprint, seed=42, paired=True)
    
    def test_initialization(self, simulator):
        assert simulator.seed == 42
        assert simulator.paired is True
        assert len(simulator.deals) == 0
    
    def test_generate_deal_unpaired(self, blueprint):
        sim = EnhancedPokerSim(blueprint, seed=42, paired=False)
        board1, cards1 = sim.generate_deal(1, Position.BTN, Street.FLOP)
        board2, cards2 = sim.generate_deal(1, Position.BTN, Street.FLOP)
        
        # With unpaired, deals are not stored
        assert len(sim.deals) == 0
    
    def test_generate_deal_paired(self, simulator):
        board1, cards1 = simulator.generate_deal(1, Position.BTN, Street.FLOP)
        board2, cards2 = simulator.generate_deal(1, Position.BTN, Street.FLOP)
        
        # With paired, same deal should be returned
        assert board1 == board2
        assert cards1 == cards2
        assert len(simulator.deals) == 1
    
    def test_generate_deal_street_lengths(self, simulator):
        # Flop
        board, _ = simulator.generate_deal(1, Position.BTN, Street.FLOP)
        assert len(board) == 3
        
        # Turn
        board, _ = simulator.generate_deal(2, Position.BTN, Street.TURN)
        assert len(board) == 4
        
        # River
        board, _ = simulator.generate_deal(3, Position.BTN, Street.RIVER)
        assert len(board) == 5
    
    def test_kl_divergence_same_distributions(self, simulator):
        p = {'fold': 0.2, 'call': 0.3, 'raise': 0.5}
        q = {'fold': 0.2, 'call': 0.3, 'raise': 0.5}
        kl = simulator._compute_kl_divergence(p, q)
        assert abs(kl) < 1e-6
    
    def test_kl_divergence_different_distributions(self, simulator):
        p = {'fold': 0.1, 'call': 0.4, 'raise': 0.5}
        q = {'fold': 0.5, 'call': 0.3, 'raise': 0.2}
        kl = simulator._compute_kl_divergence(p, q)
        assert kl > 0


class TestHandResult:
    """Test HandResult dataclass."""
    
    def test_creation(self):
        result = HandResult(
            hand_id=1,
            position=Position.BTN,
            street=Street.FLOP,
            rt_chips=5.0,
            blueprint_chips=0.0,
            deal_hash="hash123",
            samples_per_solve=16,
            rt_latency_ms=75.0
        )
        assert result.hand_id == 1
        assert result.position == Position.BTN
        assert result.street == Street.FLOP
        assert result.rt_chips == 5.0
        assert result.rt_latency_ms == 75.0
    
    def test_default_values(self):
        result = HandResult(
            hand_id=1,
            position=Position.BTN,
            street=Street.FLOP,
            rt_chips=5.0,
            blueprint_chips=0.0,
            deal_hash="hash123",
            samples_per_solve=16,
            rt_latency_ms=75.0
        )
        assert result.kl_divergence == 0.0
        assert result.fallback_used is False
        assert result.iterations == 0
        assert result.nodes_expanded == 0


class TestComputeStatistics:
    """Test statistics computation."""
    
    @pytest.fixture
    def sample_results(self):
        """Create sample hand results."""
        results = []
        for i in range(100):
            result = HandResult(
                hand_id=i,
                position=Position.BTN if i % 2 == 0 else Position.BB,
                street=Street.FLOP if i % 3 == 0 else Street.TURN,
                rt_chips=np.random.randn() * 10 + 5,  # Mean ~5
                blueprint_chips=0.0,
                deal_hash=f"hash{i}",
                samples_per_solve=16,
                rt_latency_ms=np.random.uniform(50, 150),
                kl_divergence=np.random.uniform(0.05, 0.25),
                fallback_used=i % 20 == 0,  # 5% fallback
                iterations=np.random.randint(50, 200),
                nodes_expanded=np.random.randint(100, 1000)
            )
            results.append(result)
        return results
    
    def test_compute_statistics_basic(self, sample_results):
        result = _compute_statistics(
            sample_results,
            seeds=[42],
            commit_hash="abcd1234",
            config_hash="config123",
            blueprint_hash="bp123",
            bootstrap_reps=100,  # Use fewer reps for faster testing
            aivat_evaluator=None
        )
        
        assert result.commit_hash == "abcd1234"
        assert result.config_hash == "config123"
        assert result.blueprint_hash == "bp123"
        assert result.seeds == [42]
        assert result.total_hands == 100
        assert result.bootstrap_reps == 100
        
        # Check that statistics are computed
        assert isinstance(result.ev_delta_bb100, float)
        assert isinstance(result.ci_lower, float)
        assert isinstance(result.ci_upper, float)
        assert isinstance(result.p_value, float)
    
    def test_per_position_breakdown(self, sample_results):
        result = _compute_statistics(
            sample_results,
            seeds=[42],
            commit_hash="test",
            config_hash="test",
            blueprint_hash="test",
            bootstrap_reps=100,
            aivat_evaluator=None
        )
        
        # Should have BTN and BB positions
        assert 'BTN' in result.by_position
        assert 'BB' in result.by_position
        
        # Check BTN stats
        btn_stats = result.by_position['BTN']
        assert 'hands' in btn_stats
        assert 'ev_delta_bb100' in btn_stats
        assert 'ci_lower' in btn_stats
        assert 'ci_upper' in btn_stats
        assert 'mean_kl' in btn_stats
        assert btn_stats['hands'] > 0
    
    def test_per_street_breakdown(self, sample_results):
        result = _compute_statistics(
            sample_results,
            seeds=[42],
            commit_hash="test",
            config_hash="test",
            blueprint_hash="test",
            bootstrap_reps=100,
            aivat_evaluator=None
        )
        
        # Should have FLOP and TURN streets
        assert 'FLOP' in result.by_street
        assert 'TURN' in result.by_street
        
        # Check FLOP stats
        flop_stats = result.by_street['FLOP']
        assert 'hands' in flop_stats
        assert 'ev_delta_bb100' in flop_stats
        assert 'mean_latency_ms' in flop_stats
        assert 'p95_latency_ms' in flop_stats
        assert 'fallback_rate' in flop_stats
        assert 'mean_iterations' in flop_stats
        assert flop_stats['hands'] > 0
    
    def test_latency_metrics(self, sample_results):
        result = _compute_statistics(
            sample_results,
            seeds=[42],
            commit_hash="test",
            config_hash="test",
            blueprint_hash="test",
            bootstrap_reps=100,
            aivat_evaluator=None
        )
        
        assert 'mean' in result.latency
        assert 'p50' in result.latency
        assert 'p95' in result.latency
        assert 'p99' in result.latency
        assert 'fallback_rate' in result.latency
        
        # Check reasonable values
        assert 50 <= result.latency['mean'] <= 150
        assert 0 <= result.latency['fallback_rate'] <= 1
    
    def test_kl_statistics(self, sample_results):
        result = _compute_statistics(
            sample_results,
            seeds=[42],
            commit_hash="test",
            config_hash="test",
            blueprint_hash="test",
            bootstrap_reps=100,
            aivat_evaluator=None
        )
        
        assert 'mean' in result.kl_stats
        assert 'p50' in result.kl_stats
        assert 'p95' in result.kl_stats
        assert 'p99' in result.kl_stats
        
        # Check reasonable values (we generated between 0.05 and 0.25)
        assert 0.03 <= result.kl_stats['p50'] <= 0.27
    
    def test_sampling_analysis(self, sample_results):
        result = _compute_statistics(
            sample_results,
            seeds=[42],
            commit_hash="test",
            config_hash="test",
            blueprint_hash="test",
            bootstrap_reps=100,
            aivat_evaluator=None
        )
        
        # All samples use 16
        assert '16' in result.sampling
        sample_stats = result.sampling['16']
        
        assert 'hands' in sample_stats
        assert 'ev_delta_bb100' in sample_stats
        assert 'variance' in sample_stats
        assert 'latency_p95' in sample_stats
        assert sample_stats['hands'] == 100


class TestIntegration:
    """Integration tests."""
    
    def test_full_evaluation_workflow(self):
        """Test a minimal evaluation workflow."""
        # Create a simple policy
        policy = PolicyStore()
        
        # Create simulator
        simulator = EnhancedPokerSim(policy, seed=42, paired=True)
        
        # Generate a few hands
        results = []
        for i in range(10):
            # Generate deal (will be stored for paired bootstrap)
            board, cards = simulator.generate_deal(i, Position.BTN, Street.FLOP)
            
            # Verify paired behavior
            board2, cards2 = simulator.generate_deal(i, Position.BTN, Street.FLOP)
            assert board == board2
            assert cards == cards2
        
        assert len(simulator.deals) == 10
    
    def test_json_serialization(self):
        """Test that results can be serialized to JSON."""
        results = []
        for i in range(10):
            result = HandResult(
                hand_id=i,
                position=Position.BTN,
                street=Street.FLOP,
                rt_chips=5.0,
                blueprint_chips=0.0,
                deal_hash=f"hash{i}",
                samples_per_solve=16,
                rt_latency_ms=75.0
            )
            results.append(result)
        
        eval_result = _compute_statistics(
            results,
            seeds=[42],
            commit_hash="test",
            config_hash="test",
            blueprint_hash="test",
            bootstrap_reps=100,
            aivat_evaluator=None
        )
        
        # Convert to dict and serialize
        from dataclasses import asdict
        result_dict = asdict(eval_result)
        json_str = json.dumps(result_dict, indent=2)
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed['commit_hash'] == "test"
        assert parsed['total_hands'] == 10


class TestDefinitionOfDone:
    """Test Definition of Done gates."""
    
    def test_positive_ev_delta_gate(self):
        """Test that positive EVΔ with significant CI passes gate."""
        results = []
        for i in range(100):
            # Generate positive EV results
            result = HandResult(
                hand_id=i,
                position=Position.BTN,
                street=Street.FLOP,
                rt_chips=10.0,  # Consistently positive
                blueprint_chips=0.0,
                deal_hash=f"hash{i}",
                samples_per_solve=16,
                rt_latency_ms=75.0,
                kl_divergence=0.15
            )
            results.append(result)
        
        eval_result = _compute_statistics(
            results,
            seeds=[42],
            commit_hash="test",
            config_hash="test",
            blueprint_hash="test",
            bootstrap_reps=100,
            aivat_evaluator=None
        )
        
        # Should be significant and positive
        assert eval_result.is_significant
        assert eval_result.ci_lower > 0
    
    def test_latency_gate(self):
        """Test latency metrics."""
        results = []
        for i in range(100):
            # Keep latency under 110ms
            result = HandResult(
                hand_id=i,
                position=Position.BTN,
                street=Street.FLOP,
                rt_chips=5.0,
                blueprint_chips=0.0,
                deal_hash=f"hash{i}",
                samples_per_solve=16,
                rt_latency_ms=np.random.uniform(50, 100),  # Under budget
                kl_divergence=0.15
            )
            results.append(result)
        
        eval_result = _compute_statistics(
            results,
            seeds=[42],
            commit_hash="test",
            config_hash="test",
            blueprint_hash="test",
            bootstrap_reps=100,
            aivat_evaluator=None
        )
        
        # p95 should be under 110ms
        assert eval_result.latency['p95'] <= 110.0
    
    def test_kl_range_gate(self):
        """Test KL divergence in acceptable range."""
        results = []
        for i in range(100):
            # KL in [0.05, 0.25] range
            result = HandResult(
                hand_id=i,
                position=Position.BTN,
                street=Street.FLOP,
                rt_chips=5.0,
                blueprint_chips=0.0,
                deal_hash=f"hash{i}",
                samples_per_solve=16,
                rt_latency_ms=75.0,
                kl_divergence=np.random.uniform(0.10, 0.20)  # In range
            )
            results.append(result)
        
        eval_result = _compute_statistics(
            results,
            seeds=[42],
            commit_hash="test",
            config_hash="test",
            blueprint_hash="test",
            bootstrap_reps=100,
            aivat_evaluator=None
        )
        
        # p50 should be in acceptable range
        assert 0.05 <= eval_result.kl_stats['p50'] <= 0.25


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
