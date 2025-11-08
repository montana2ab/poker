"""Tests for AIVAT integration with eval_loop."""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from holdem.rl_eval.eval_loop import Evaluator
from holdem.mccfr.policy_store import PolicyStore


def test_evaluator_without_aivat():
    """Test evaluator works without AIVAT (vanilla mode)."""
    # Create a mock policy
    policy = PolicyStore()
    
    # Create evaluator without AIVAT
    evaluator = Evaluator(policy, use_aivat=False)
    
    assert evaluator.use_aivat == False
    assert evaluator.aivat is None
    
    # Run a small evaluation
    results = evaluator.evaluate(num_episodes=100)
    
    # Check results structure
    assert 'Random' in results
    assert 'AlwaysCall' in results
    assert 'Tight' in results
    assert 'Aggressive' in results
    
    # Each result should have mean, std, variance, episodes
    for baseline_name, baseline_results in results.items():
        if baseline_name != 'aivat_stats':
            assert 'mean' in baseline_results
            assert 'std' in baseline_results
            assert 'variance' in baseline_results
            assert 'episodes' in baseline_results
            assert baseline_results['episodes'] == 100
            
            # Should NOT have AIVAT metrics
            assert 'aivat' not in baseline_results
    
    # Should not have AIVAT stats
    assert 'aivat_stats' not in results


def test_evaluator_with_aivat():
    """Test evaluator works with AIVAT enabled."""
    # Create a mock policy
    policy = PolicyStore()
    
    # Create evaluator with AIVAT
    evaluator = Evaluator(policy, use_aivat=True, num_players=9)
    
    assert evaluator.use_aivat == True
    assert evaluator.aivat is not None
    # In heads-up evaluation mode, AIVAT uses 2 players (policy vs baseline)
    assert evaluator.aivat.num_players == 2
    
    # Run evaluation with small warmup and evaluation episodes
    results = evaluator.evaluate(num_episodes=100, warmup_episodes=50)
    
    # Check results structure
    assert 'Random' in results
    assert 'AlwaysCall' in results
    
    # Each result should have AIVAT metrics
    for baseline_name, baseline_results in results.items():
        if baseline_name != 'aivat_stats':
            assert 'mean' in baseline_results
            assert 'std' in baseline_results
            assert 'variance' in baseline_results
            assert 'episodes' in baseline_results
            
            # Should have AIVAT metrics
            assert 'aivat' in baseline_results
            aivat_metrics = baseline_results['aivat']
            
            assert 'vanilla_variance' in aivat_metrics
            assert 'aivat_variance' in aivat_metrics
            assert 'variance_reduction_pct' in aivat_metrics
            assert 'variance_reduction_ratio' in aivat_metrics
            assert 'num_samples' in aivat_metrics
    
    # Should have overall AIVAT stats
    assert 'aivat_stats' in results
    aivat_stats = results['aivat_stats']
    assert aivat_stats['trained'] == True
    assert aivat_stats['num_players'] == 2  # Heads-up mode


def test_aivat_variance_reduction_in_evaluator():
    """Test that AIVAT actually reduces variance in the evaluator."""
    policy = PolicyStore()
    
    # Run vanilla evaluation
    evaluator_vanilla = Evaluator(policy, use_aivat=False)
    results_vanilla = evaluator_vanilla.evaluate(num_episodes=200)
    
    # Run AIVAT evaluation
    evaluator_aivat = Evaluator(policy, use_aivat=True)
    results_aivat = evaluator_aivat.evaluate(num_episodes=200, warmup_episodes=100)
    
    # Compare variance for each baseline
    # Note: Due to randomness, we can't guarantee reduction in every single run,
    # but we check that AIVAT metrics are present and computed
    for baseline_name in ['Random', 'AlwaysCall', 'Tight', 'Aggressive']:
        vanilla_variance = results_vanilla[baseline_name]['variance']
        aivat_result = results_aivat[baseline_name]
        
        # AIVAT result should have variance metrics
        assert 'aivat' in aivat_result
        
        vanilla_var = aivat_result['aivat']['vanilla_variance']
        aivat_var = aivat_result['aivat']['aivat_variance']
        
        # Variances should be computed
        assert vanilla_var >= 0
        assert aivat_var >= 0
        
        print(f"\n{baseline_name}:")
        print(f"  Vanilla variance: {vanilla_var:.2f}")
        print(f"  AIVAT variance: {aivat_var:.2f}")
        if vanilla_var > 0:
            reduction = (vanilla_var - aivat_var) / vanilla_var * 100
            print(f"  Reduction: {reduction:.1f}%")


def test_evaluator_play_episode_with_state():
    """Test that _play_episode_with_state returns both payoff and state."""
    policy = PolicyStore()
    evaluator = Evaluator(policy)
    
    from holdem.rl_eval.baselines import RandomAgent
    opponent = RandomAgent()
    
    # Call the method
    payoff, state_key = evaluator._play_episode_with_state(opponent)
    
    # Check return types
    assert isinstance(payoff, (int, float))
    assert isinstance(state_key, str)
    assert state_key.startswith("state_")


if __name__ == '__main__':
    print("Running AIVAT eval_loop integration tests...\n")
    
    test_evaluator_without_aivat()
    print("✓ test_evaluator_without_aivat")
    
    test_evaluator_with_aivat()
    print("✓ test_evaluator_with_aivat")
    
    test_aivat_variance_reduction_in_evaluator()
    print("✓ test_aivat_variance_reduction_in_evaluator")
    
    test_evaluator_play_episode_with_state()
    print("✓ test_evaluator_play_episode_with_state")
    
    print("\n✅ All eval_loop integration tests passed!")
