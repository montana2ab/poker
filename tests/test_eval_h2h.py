"""Tests for tools/eval_h2h.py head-to-head evaluation script."""

import sys
import json
import tempfile
from pathlib import Path

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.eval_h2h import (
    Policy, SimplePokerGame, HeadsUpEvaluator,
    HandResult, EvaluationStats, load_policy
)


def test_simple_poker_game_creation():
    """Test creating a poker game."""
    game = SimplePokerGame()
    assert game.sb_amount == 1.0
    assert game.bb_amount == 2.0
    assert game.starting_stack == 200.0
    assert len(game.deck) == 52


def test_simple_poker_game_deal():
    """Test dealing cards."""
    game = SimplePokerGame()
    sb_cards, bb_cards, board = game._deal_cards(seed=42)
    
    assert len(sb_cards) == 2
    assert len(bb_cards) == 2
    assert len(board) == 5
    
    # Check all cards are unique
    all_cards = sb_cards + bb_cards + board
    assert len(all_cards) == len(set(all_cards))


def test_simple_poker_game_hand_strength():
    """Test hand strength calculation."""
    game = SimplePokerGame()
    
    # High card
    strength1 = game._hand_strength(['Ah', 'Kd'], ['2c', '3d', '5h', '7s', '9c'])
    assert strength1 > 1000
    assert strength1 < 2000
    
    # Pair
    strength2 = game._hand_strength(['Ah', 'Ad'], ['2c', '3d', '5h', '7s', '9c'])
    assert strength2 > 2000
    assert strength2 < 3000
    
    # Pair should be stronger than high card
    assert strength2 > strength1


def test_policy_creation():
    """Test creating a policy."""
    policy_data = {
        "infoset1": {"fold": 0.1, "call": 0.5, "bet": 0.4}
    }
    policy = Policy(policy_data, name="test_policy")
    
    assert policy.name == "test_policy"
    assert len(policy.policy_data) == 1


def test_policy_load_json():
    """Test loading policy from JSON."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        policy_data = {
            "infoset1": {"fold": 0.1, "call": 0.5, "bet": 0.4}
        }
        json.dump(policy_data, f)
        json_path = Path(f.name)
    
    try:
        policy = Policy.load_from_json(json_path)
        assert policy.name == json_path.stem
        assert len(policy.policy_data) == 1
    finally:
        json_path.unlink()


def test_policy_export_json():
    """Test exporting policy to JSON."""
    policy_data = {
        "infoset1": {"fold": 0.1, "call": 0.5, "bet": 0.4}
    }
    policy = Policy(policy_data, name="test")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json_path = Path(f.name)
    
    try:
        policy.export_to_json(json_path)
        assert json_path.exists()
        
        # Load and verify
        with open(json_path) as f:
            loaded_data = json.load(f)
        assert loaded_data == policy_data
    finally:
        if json_path.exists():
            json_path.unlink()


def test_evaluator_creation():
    """Test creating an evaluator."""
    policy_a = Policy({}, name="A")
    policy_b = Policy({}, name="B")
    
    evaluator = HeadsUpEvaluator(policy_a, policy_b, seed=42)
    
    assert evaluator.policy_a.name == "A"
    assert evaluator.policy_b.name == "B"
    assert evaluator.seed == 42
    assert len(evaluator.results) == 0


def test_evaluator_run_small():
    """Test running a small evaluation."""
    policy_a = Policy({}, name="A")
    policy_b = Policy({}, name="B")
    
    evaluator = HeadsUpEvaluator(policy_a, policy_b, seed=42)
    stats = evaluator.run_evaluation(num_hands=5, verbose=False)
    
    assert stats.total_hands == 10  # 5 pairs * 2
    assert stats.duplicate_pairs == 5
    assert len(evaluator.results) == 10


def test_evaluator_duplicate_deals():
    """Test that duplicate deals are used correctly."""
    policy_a = Policy({}, name="A")
    policy_b = Policy({}, name="B")
    
    evaluator = HeadsUpEvaluator(policy_a, policy_b, seed=42)
    evaluator.run_evaluation(num_hands=3, verbose=False)
    
    # Check that we have pairs of hands with same deal_hash
    deal_hashes = [r.deal_hash for r in evaluator.results]
    
    # Each deal should appear exactly twice
    from collections import Counter
    hash_counts = Counter(deal_hashes)
    for count in hash_counts.values():
        assert count == 2


def test_evaluator_position_swapping():
    """Test that positions are swapped in duplicate deals."""
    policy_a = Policy({}, name="A")
    policy_b = Policy({}, name="B")
    
    evaluator = HeadsUpEvaluator(policy_a, policy_b, seed=42)
    evaluator.run_evaluation(num_hands=3, verbose=False)
    
    # Check position swapping
    for i in range(0, len(evaluator.results), 2):
        hand1 = evaluator.results[i]
        hand2 = evaluator.results[i + 1]
        
        # Same deal hash
        assert hand1.deal_hash == hand2.deal_hash
        
        # Opposite positions
        assert hand1.position_a != hand2.position_a
        assert (hand1.position_a == 'SB' and hand2.position_a == 'BB') or \
               (hand1.position_a == 'BB' and hand2.position_a == 'SB')


def test_bootstrap_ci():
    """Test bootstrap confidence interval calculation."""
    import numpy as np
    
    policy_a = Policy({}, name="A")
    policy_b = Policy({}, name="B")
    evaluator = HeadsUpEvaluator(policy_a, policy_b, seed=42)
    
    # Test data
    data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    ci_lower, ci_upper = evaluator._bootstrap_ci(data, confidence=0.95, n_bootstrap=1000)
    
    # CI should contain the mean
    mean = np.mean(data)
    assert ci_lower <= mean <= ci_upper
    
    # CI bounds should be reasonable
    assert ci_lower < ci_upper


def test_evaluator_save_json():
    """Test saving results to JSON."""
    policy_a = Policy({}, name="A")
    policy_b = Policy({}, name="B")
    
    evaluator = HeadsUpEvaluator(policy_a, policy_b, seed=42)
    evaluator.run_evaluation(num_hands=2, verbose=False)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json_path = Path(f.name)
    
    try:
        evaluator.save_json(json_path)
        assert json_path.exists()
        
        # Load and verify structure
        with open(json_path) as f:
            data = json.load(f)
        
        assert 'policy_a' in data
        assert 'policy_b' in data
        assert 'configuration' in data
        assert 'results' in data
        assert 'statistics' in data
        assert len(data['results']) == 4  # 2 pairs * 2
    finally:
        if json_path.exists():
            json_path.unlink()


def test_evaluator_save_csv():
    """Test saving results to CSV."""
    import csv
    
    policy_a = Policy({}, name="A")
    policy_b = Policy({}, name="B")
    
    evaluator = HeadsUpEvaluator(policy_a, policy_b, seed=42)
    evaluator.run_evaluation(num_hands=2, verbose=False)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = Path(f.name)
    
    try:
        evaluator.save_csv(csv_path)
        assert csv_path.exists()
        
        # Load and verify
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 4  # 2 pairs * 2
        assert 'hand_id' in rows[0]
        assert 'position_a' in rows[0]
        assert 'chips_won_a' in rows[0]
        
        # Check summary CSV
        summary_path = csv_path.parent / f"{csv_path.stem}_summary.csv"
        assert summary_path.exists()
    finally:
        if csv_path.exists():
            csv_path.unlink()
        summary_path = csv_path.parent / f"{csv_path.stem}_summary.csv"
        if summary_path.exists():
            summary_path.unlink()


def test_load_policy_json():
    """Test load_policy function with JSON."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        policy_data = {"infoset1": {"fold": 0.1, "call": 0.9}}
        json.dump(policy_data, f)
        json_path = Path(f.name)
    
    try:
        policy = load_policy(json_path)
        assert policy.name == json_path.stem
        assert len(policy.policy_data) == 1
    finally:
        json_path.unlink()


def test_statistics_dataclass():
    """Test EvaluationStats dataclass."""
    stats = EvaluationStats(
        total_hands=100,
        winrate_bb100=5.0,
        ci_lower=2.0,
        ci_upper=8.0,
        mean_chips=0.1,
        std_chips=0.5,
        policy_a_winrate=55.0,
        policy_b_winrate=45.0,
        duplicate_pairs=50
    )
    
    assert stats.total_hands == 100
    assert stats.winrate_bb100 == 5.0
    assert stats.duplicate_pairs == 50


def test_hand_result_dataclass():
    """Test HandResult dataclass."""
    result = HandResult(
        hand_id=0,
        position_a='SB',
        chips_won_a=1.5,
        chips_won_b=-1.5,
        deal_hash='deal_42'
    )
    
    assert result.hand_id == 0
    assert result.position_a == 'SB'
    assert result.chips_won_a == 1.5
    assert result.deal_hash == 'deal_42'


if __name__ == '__main__':
    # Run all tests
    test_functions = [
        test_simple_poker_game_creation,
        test_simple_poker_game_deal,
        test_simple_poker_game_hand_strength,
        test_policy_creation,
        test_policy_load_json,
        test_policy_export_json,
        test_evaluator_creation,
        test_evaluator_run_small,
        test_evaluator_duplicate_deals,
        test_evaluator_position_swapping,
        test_bootstrap_ci,
        test_evaluator_save_json,
        test_evaluator_save_csv,
        test_load_policy_json,
        test_statistics_dataclass,
        test_hand_result_dataclass,
    ]
    
    print("Running tests for eval_h2h.py...")
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            print(f"✓ {test_func.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__}: {e}")
            failed += 1
    
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
