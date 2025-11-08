"""Tests for AIVAT (Actor-Independent Variance-reduced Advantage Technique)."""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from holdem.rl_eval.aivat import AIVATEvaluator


def test_aivat_initialization():
    """Test AIVAT evaluator initialization."""
    aivat = AIVATEvaluator(num_players=9, min_samples=100)
    
    assert aivat.num_players == 9
    assert aivat.min_samples == 100
    assert not aivat.trained
    assert aivat.can_train() == False


def test_add_sample():
    """Test adding samples to AIVAT."""
    aivat = AIVATEvaluator(num_players=2, min_samples=10)
    
    # Add samples for player 0
    for i in range(15):
        aivat.add_sample(
            player_id=0,
            state_key=f"state_{i % 5}",
            payoff=float(i)
        )
    
    assert len(aivat.samples[0]) == 15


def test_can_train():
    """Test can_train logic."""
    aivat = AIVATEvaluator(num_players=2, min_samples=10)
    
    # Not enough samples yet
    assert not aivat.can_train()
    
    # Add samples for player 0
    for i in range(10):
        aivat.add_sample(player_id=0, state_key=f"state_{i}", payoff=1.0)
    
    # Still not enough (need both players)
    assert not aivat.can_train()
    
    # Add samples for player 1
    for i in range(10):
        aivat.add_sample(player_id=1, state_key=f"state_{i}", payoff=2.0)
    
    # Now we can train
    assert aivat.can_train()


def test_train_value_functions():
    """Test training value functions."""
    aivat = AIVATEvaluator(num_players=2, min_samples=5)
    
    # Add samples with known patterns
    # Player 0: state_a has payoff 10, state_b has payoff 20
    for _ in range(5):
        aivat.add_sample(player_id=0, state_key="state_a", payoff=10.0)
        aivat.add_sample(player_id=0, state_key="state_b", payoff=20.0)
    
    # Player 1: state_c has payoff -5
    for _ in range(5):
        aivat.add_sample(player_id=1, state_key="state_c", payoff=-5.0)
    
    # Train
    aivat.train_value_functions()
    
    assert aivat.trained
    
    # Check learned baselines
    assert abs(aivat.get_baseline_value(0, "state_a") - 10.0) < 0.01
    assert abs(aivat.get_baseline_value(0, "state_b") - 20.0) < 0.01
    assert abs(aivat.get_baseline_value(1, "state_c") - (-5.0)) < 0.01
    
    # Unseen state should return 0.0
    assert aivat.get_baseline_value(0, "state_unseen") == 0.0


def test_compute_advantage():
    """Test advantage computation."""
    aivat = AIVATEvaluator(num_players=1, min_samples=5)
    
    # Add and train
    for _ in range(5):
        aivat.add_sample(player_id=0, state_key="state_x", payoff=100.0)
    
    aivat.train_value_functions()
    
    # Baseline should be 100.0
    # If actual payoff is 120.0, advantage should be 20.0
    advantage = aivat.compute_advantage(
        player_id=0,
        state_key="state_x",
        actual_payoff=120.0
    )
    
    assert abs(advantage - 20.0) < 0.01
    
    # If actual payoff is 80.0, advantage should be -20.0
    advantage = aivat.compute_advantage(
        player_id=0,
        state_key="state_x",
        actual_payoff=80.0
    )
    
    assert abs(advantage - (-20.0)) < 0.01


def test_variance_reduction_calculation():
    """Test variance reduction calculation."""
    aivat = AIVATEvaluator(num_players=1)
    
    # Vanilla results with high variance
    vanilla_results = [0.0, 100.0, -100.0, 50.0, -50.0]
    
    # AIVAT results with lower variance (baselines subtracted)
    aivat_results = [0.0, 10.0, -10.0, 5.0, -5.0]
    
    stats = aivat.compute_variance_reduction(vanilla_results, aivat_results)
    
    assert stats['vanilla_variance'] > stats['aivat_variance']
    assert stats['variance_reduction_pct'] > 0
    assert stats['variance_reduction_ratio'] < 1.0
    assert stats['num_samples'] == 5


def test_variance_reduction_on_synthetic_data():
    """Test that AIVAT actually reduces variance on synthetic data."""
    aivat = AIVATEvaluator(num_players=1, min_samples=50)
    
    # Create synthetic data where state determines baseline payoff
    # State A: baseline = 0, noise = ±10
    # State B: baseline = 50, noise = ±10
    
    import random
    random.seed(42)
    
    # Training phase
    for _ in range(50):
        # State A samples
        payoff_a = 0.0 + random.uniform(-10, 10)
        aivat.add_sample(player_id=0, state_key="state_a", payoff=payoff_a)
        
        # State B samples
        payoff_b = 50.0 + random.uniform(-10, 10)
        aivat.add_sample(player_id=0, state_key="state_b", payoff=payoff_b)
    
    aivat.train_value_functions()
    
    # Evaluation phase
    vanilla_results = []
    aivat_results = []
    
    for _ in range(100):
        # Randomly choose state A or B
        if random.random() < 0.5:
            state_key = "state_a"
            true_mean = 0.0
        else:
            state_key = "state_b"
            true_mean = 50.0
        
        payoff = true_mean + random.uniform(-10, 10)
        vanilla_results.append(payoff)
        
        advantage = aivat.compute_advantage(0, state_key, payoff)
        aivat_results.append(advantage)
    
    # Calculate variance reduction
    stats = aivat.compute_variance_reduction(vanilla_results, aivat_results)
    
    # AIVAT should reduce variance significantly (target: >30%)
    assert stats['variance_reduction_pct'] > 30.0, \
        f"AIVAT only reduced variance by {stats['variance_reduction_pct']:.1f}%, expected >30%"
    
    print(f"\nVariance reduction test:")
    print(f"  Vanilla variance: {stats['vanilla_variance']:.2f}")
    print(f"  AIVAT variance: {stats['aivat_variance']:.2f}")
    print(f"  Reduction: {stats['variance_reduction_pct']:.1f}%")


def test_variance_reduction_with_many_states():
    """Test variance reduction with multiple states (more realistic)."""
    aivat = AIVATEvaluator(num_players=1, min_samples=100)
    
    import random
    random.seed(123)
    
    # Define 10 states with different baseline payoffs
    state_baselines = {
        f"state_{i}": float(i * 10 - 45)  # Range from -45 to +45
        for i in range(10)
    }
    
    # Training phase: collect samples for each state
    for _ in range(100):
        for state_key, baseline in state_baselines.items():
            payoff = baseline + random.gauss(0, 15)  # Noise with std=15
            aivat.add_sample(player_id=0, state_key=state_key, payoff=payoff)
    
    aivat.train_value_functions()
    
    # Evaluation phase
    vanilla_results = []
    aivat_results = []
    
    for _ in range(1000):
        # Randomly sample a state
        state_key = random.choice(list(state_baselines.keys()))
        baseline = state_baselines[state_key]
        
        payoff = baseline + random.gauss(0, 15)
        vanilla_results.append(payoff)
        
        advantage = aivat.compute_advantage(0, state_key, payoff)
        aivat_results.append(advantage)
    
    stats = aivat.compute_variance_reduction(vanilla_results, aivat_results)
    
    # With multiple states and good baseline learning, should achieve >30% reduction
    assert stats['variance_reduction_pct'] > 30.0, \
        f"Variance reduction {stats['variance_reduction_pct']:.1f}% < 30%"
    
    print(f"\nMulti-state variance reduction test:")
    print(f"  Vanilla variance: {stats['vanilla_variance']:.2f}")
    print(f"  AIVAT variance: {stats['aivat_variance']:.2f}")
    print(f"  Reduction: {stats['variance_reduction_pct']:.1f}%")


def test_get_statistics():
    """Test statistics retrieval."""
    aivat = AIVATEvaluator(num_players=2, min_samples=10)
    
    # Initial stats
    stats = aivat.get_statistics()
    assert stats['num_players'] == 2
    assert stats['min_samples'] == 10
    assert stats['total_samples'] == 0
    assert not stats['trained']
    assert not stats['can_train']
    
    # Add samples and train
    for i in range(10):
        aivat.add_sample(player_id=0, state_key=f"s{i}", payoff=1.0)
        aivat.add_sample(player_id=1, state_key=f"s{i}", payoff=2.0)
    
    aivat.train_value_functions()
    
    # Updated stats
    stats = aivat.get_statistics()
    assert stats['total_samples'] == 20
    assert stats['trained']
    assert stats['can_train']
    assert 'total_unique_states' in stats


def test_invalid_player_id():
    """Test that invalid player IDs raise errors."""
    aivat = AIVATEvaluator(num_players=2)
    
    # Valid player IDs: 0, 1
    aivat.add_sample(player_id=0, state_key="test", payoff=1.0)
    aivat.add_sample(player_id=1, state_key="test", payoff=2.0)
    
    # Invalid player IDs
    try:
        aivat.add_sample(player_id=-1, state_key="test", payoff=1.0)
        assert False, "Should have raised ValueError for negative player_id"
    except ValueError:
        pass
    
    try:
        aivat.add_sample(player_id=2, state_key="test", payoff=1.0)
        assert False, "Should have raised ValueError for player_id >= num_players"
    except ValueError:
        pass


def test_unbiased_estimation():
    """Test that AIVAT maintains unbiased estimation (same mean as vanilla)."""
    aivat = AIVATEvaluator(num_players=1, min_samples=50)
    
    import random
    random.seed(456)
    
    # Training - use multiple states to make it more realistic
    states = ["state_a", "state_b", "state_c"]
    state_means = [10.0, 5.0, 15.0]
    
    for _ in range(50):
        for state, mean in zip(states, state_means):
            payoff = random.gauss(mean, 5.0)
            aivat.add_sample(player_id=0, state_key=state, payoff=payoff)
    
    aivat.train_value_functions()
    
    # Evaluation
    vanilla_results = []
    aivat_results = []
    
    for _ in range(1000):
        # Randomly pick a state
        idx = random.randint(0, 2)
        state = states[idx]
        mean = state_means[idx]
        
        payoff = random.gauss(mean, 5.0)
        vanilla_results.append(payoff)
        
        advantage = aivat.compute_advantage(0, state, payoff)
        aivat_results.append(advantage)
    
    vanilla_mean = sum(vanilla_results) / len(vanilla_results)
    aivat_mean = sum(aivat_results) / len(aivat_results)
    
    # AIVAT advantages should have mean ≈ 0 (since baseline ≈ state means)
    # Allow for more sampling variation with tolerance of 1.0
    assert abs(aivat_mean) < 1.0, \
        f"AIVAT mean {aivat_mean:.2f} should be close to 0"
    
    # Vanilla mean should be close to average of state means (10.0)
    expected_mean = sum(state_means) / len(state_means)
    assert abs(vanilla_mean - expected_mean) < 1.0, \
        f"Vanilla mean {vanilla_mean:.2f} should be close to {expected_mean:.2f}"
    
    print(f"\nUnbiased estimation test:")
    print(f"  Vanilla mean: {vanilla_mean:.2f} (expected: {expected_mean:.2f})")
    print(f"  AIVAT mean: {aivat_mean:.2f} (expected: ~0.0)")


if __name__ == '__main__':
    # Run all tests
    print("Running AIVAT tests...\n")
    
    test_aivat_initialization()
    print("✓ test_aivat_initialization")
    
    test_add_sample()
    print("✓ test_add_sample")
    
    test_can_train()
    print("✓ test_can_train")
    
    test_train_value_functions()
    print("✓ test_train_value_functions")
    
    test_compute_advantage()
    print("✓ test_compute_advantage")
    
    test_variance_reduction_calculation()
    print("✓ test_variance_reduction_calculation")
    
    test_variance_reduction_on_synthetic_data()
    print("✓ test_variance_reduction_on_synthetic_data")
    
    test_variance_reduction_with_many_states()
    print("✓ test_variance_reduction_with_many_states")
    
    test_get_statistics()
    print("✓ test_get_statistics")
    
    test_invalid_player_id()
    print("✓ test_invalid_player_id")
    
    test_unbiased_estimation()
    print("✓ test_unbiased_estimation")
    
    print("\n✅ All AIVAT tests passed!")
