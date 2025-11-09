"""Test for new argparse arguments in eval_blueprint.py"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from holdem.rl_eval.eval_loop import Evaluator
from holdem.mccfr.policy_store import PolicyStore


def test_evaluator_with_new_params():
    """Test that Evaluator accepts the new parameters."""
    # Create a mock policy
    policy = PolicyStore()
    
    # Create evaluator with new parameters
    evaluator = Evaluator(
        policy, 
        duplicate=5, 
        translator="aggressive", 
        seed=123
    )
    
    # Verify parameters are stored
    assert evaluator.duplicate == 5
    assert evaluator.translator == "aggressive"
    assert evaluator.seed == 123


def test_evaluator_default_params():
    """Test that Evaluator uses default values when parameters not provided."""
    policy = PolicyStore()
    
    # Create evaluator without specifying new parameters
    evaluator = Evaluator(policy)
    
    # Verify default values
    assert evaluator.duplicate == 0
    assert evaluator.translator == "balanced"
    assert evaluator.seed == 42


def test_evaluator_backwards_compatibility():
    """Test that existing code still works (backwards compatibility)."""
    policy = PolicyStore()
    
    # Test with existing parameters only
    evaluator = Evaluator(
        policy, 
        use_aivat=True, 
        num_players=9,
        confidence_level=0.99
    )
    
    # Old parameters should work
    assert evaluator.use_aivat == True
    assert evaluator.num_players == 9
    assert evaluator.confidence_level == 0.99
    
    # New parameters should have defaults
    assert evaluator.duplicate == 0
    assert evaluator.translator == "balanced"
    assert evaluator.seed == 42


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, "-v"])
