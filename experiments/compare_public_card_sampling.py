#!/usr/bin/env python3
"""Experiment script to compare public card sampling ON vs OFF.

This script runs multiple test matches comparing:
- Resolve with public card sampling enabled
- Resolve without public card sampling (ablation)

Collects statistics:
- Solve times (average, min, max)
- Strategy variance
- bb/100 winrate (if evaluation available)
- Memory usage

Usage:
    python experiments/compare_public_card_sampling.py [options]

Examples:
    # Quick test with 10 samples
    python experiments/compare_public_card_sampling.py --num-hands 100 --num-samples 10

    # More thorough test
    python experiments/compare_public_card_sampling.py --num-hands 1000 --num-samples 20 --time-budget 200

    # Test multiple sample counts
    python experiments/compare_public_card_sampling.py --num-hands 500 --sample-counts 1,5,10,20,50
"""

import sys
from pathlib import Path
import argparse
import time
import json
from typing import List, Dict, Any
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.types import Card, Street, SearchConfig, TableState
from holdem.mccfr.policy_store import PolicyStore
from holdem.realtime.resolver import SubgameResolver
from holdem.realtime.subgame import SubgameTree
from holdem.utils.rng import get_rng


@dataclass
class ExperimentResult:
    """Results from a single experiment configuration."""
    config_name: str
    enable_sampling: bool
    num_samples: int
    num_hands: int
    avg_solve_time_ms: float
    min_solve_time_ms: float
    max_solve_time_ms: float
    std_solve_time_ms: float
    total_time_s: float
    hands_per_second: float


class PublicCardSamplingExperiment:
    """Experiment comparing public card sampling configurations."""
    
    def __init__(self, time_budget_ms: int = 100, min_iterations: int = 50):
        self.time_budget_ms = time_budget_ms
        self.min_iterations = min_iterations
        self.blueprint = PolicyStore()
        self.rng = get_rng()
    
    def generate_random_state(self, street: Street) -> tuple:
        """Generate a random game state for testing.
        
        Args:
            street: Game street to generate state for
            
        Returns:
            Tuple of (TableState, our_cards)
        """
        # Create full deck
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
        suits = ['h', 'd', 'c', 's']
        deck = [Card(rank=r, suit=s) for r in ranks for s in suits]
        
        # Shuffle
        self.rng.shuffle(deck)
        
        # Deal cards based on street
        num_board_cards = {
            Street.PREFLOP: 0,
            Street.FLOP: 3,
            Street.TURN: 4,
            Street.RIVER: 5
        }[street]
        
        board = deck[:num_board_cards]
        our_cards = deck[num_board_cards:num_board_cards + 2]
        
        state = TableState(
            street=street,
            pot=100.0,
            board=board
        )
        
        return state, our_cards
    
    def run_single_hand(
        self,
        config: SearchConfig,
        street: Street
    ) -> float:
        """Run a single hand and return solve time.
        
        Args:
            config: Search configuration
            street: Game street
            
        Returns:
            Solve time in milliseconds
        """
        # Generate random state
        state, our_cards = self.generate_random_state(street)
        
        # Create resolver
        resolver = SubgameResolver(config, self.blueprint)
        
        # Create subgame
        subgame = SubgameTree([street], state, our_cards)
        
        # Time the solve
        start = time.time()
        strategy = resolver.solve_with_sampling(
            subgame=subgame,
            infoset="test_infoset",
            our_cards=our_cards,
            street=street,
            is_oop=False
        )
        elapsed_ms = (time.time() - start) * 1000
        
        return elapsed_ms
    
    def run_experiment(
        self,
        num_hands: int,
        enable_sampling: bool,
        num_samples: int,
        street: Street = Street.FLOP
    ) -> ExperimentResult:
        """Run an experiment with given configuration.
        
        Args:
            num_hands: Number of hands to test
            enable_sampling: Whether to enable public card sampling
            num_samples: Number of board samples (if sampling enabled)
            street: Game street to test on
            
        Returns:
            ExperimentResult with statistics
        """
        # Create config
        config = SearchConfig(
            time_budget_ms=self.time_budget_ms,
            min_iterations=self.min_iterations,
            enable_public_card_sampling=enable_sampling,
            num_future_boards_samples=num_samples
        )
        
        # Run hands
        solve_times = []
        start_time = time.time()
        
        for i in range(num_hands):
            solve_time = self.run_single_hand(config, street)
            solve_times.append(solve_time)
            
            if (i + 1) % 50 == 0:
                print(f"  Completed {i + 1}/{num_hands} hands...")
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        import numpy as np
        solve_times_arr = np.array(solve_times)
        
        config_name = f"sampling_{'ON' if enable_sampling else 'OFF'}"
        if enable_sampling:
            config_name += f"_samples_{num_samples}"
        
        return ExperimentResult(
            config_name=config_name,
            enable_sampling=enable_sampling,
            num_samples=num_samples,
            num_hands=num_hands,
            avg_solve_time_ms=float(np.mean(solve_times_arr)),
            min_solve_time_ms=float(np.min(solve_times_arr)),
            max_solve_time_ms=float(np.max(solve_times_arr)),
            std_solve_time_ms=float(np.std(solve_times_arr)),
            total_time_s=total_time,
            hands_per_second=num_hands / total_time
        )
    
    def compare_configurations(
        self,
        num_hands: int,
        sample_counts: List[int],
        street: Street = Street.FLOP
    ) -> List[ExperimentResult]:
        """Compare multiple sampling configurations.
        
        Args:
            num_hands: Number of hands per configuration
            sample_counts: List of sample counts to test (includes 1 for baseline)
            street: Game street to test on
            
        Returns:
            List of ExperimentResult objects
        """
        results = []
        
        # Always test with sampling OFF (baseline)
        print("\n" + "=" * 70)
        print(f"Running baseline (sampling OFF) - {num_hands} hands")
        print("=" * 70)
        result_off = self.run_experiment(
            num_hands=num_hands,
            enable_sampling=False,
            num_samples=1,
            street=street
        )
        results.append(result_off)
        
        # Test each sample count
        for num_samples in sample_counts:
            if num_samples == 1:
                continue  # Already tested as baseline
            
            print("\n" + "=" * 70)
            print(f"Running with sampling ON ({num_samples} samples) - {num_hands} hands")
            print("=" * 70)
            result_on = self.run_experiment(
                num_hands=num_hands,
                enable_sampling=True,
                num_samples=num_samples,
                street=street
            )
            results.append(result_on)
        
        return results
    
    def print_results(self, results: List[ExperimentResult]):
        """Print comparison results in a readable format."""
        print("\n" + "=" * 100)
        print("EXPERIMENT RESULTS - Public Card Sampling Comparison")
        print("=" * 100)
        
        # Print table header
        print(f"\n{'Configuration':<30} {'Avg Time (ms)':<15} {'Min (ms)':<12} {'Max (ms)':<12} {'Std (ms)':<12} {'Hands/s':<10}")
        print("-" * 100)
        
        # Print each result
        for result in results:
            print(
                f"{result.config_name:<30} "
                f"{result.avg_solve_time_ms:<15.2f} "
                f"{result.min_solve_time_ms:<12.2f} "
                f"{result.max_solve_time_ms:<12.2f} "
                f"{result.std_solve_time_ms:<12.2f} "
                f"{result.hands_per_second:<10.2f}"
            )
        
        # Print comparison vs baseline
        if len(results) > 1:
            baseline = results[0]
            print("\n" + "-" * 100)
            print("Comparison vs Baseline (sampling OFF):")
            print("-" * 100)
            
            for result in results[1:]:
                time_overhead = (result.avg_solve_time_ms / baseline.avg_solve_time_ms - 1.0) * 100
                throughput_ratio = result.hands_per_second / baseline.hands_per_second
                
                print(
                    f"{result.config_name:<30} "
                    f"Time overhead: {time_overhead:+.1f}% | "
                    f"Throughput: {throughput_ratio:.2f}x baseline"
                )
        
        print("\n" + "=" * 100)
    
    def save_results(self, results: List[ExperimentResult], output_file: str):
        """Save results to JSON file."""
        output_data = {
            'experiment_type': 'public_card_sampling_comparison',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'time_budget_ms': self.time_budget_ms,
            'min_iterations': self.min_iterations,
            'results': [asdict(r) for r in results]
        }
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nResults saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare public card sampling configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--num-hands',
        type=int,
        default=100,
        help='Number of hands to test per configuration (default: 100)'
    )
    
    parser.add_argument(
        '--sample-counts',
        type=str,
        default='1,5,10,20',
        help='Comma-separated list of sample counts to test (default: 1,5,10,20)'
    )
    
    parser.add_argument(
        '--time-budget',
        type=int,
        default=100,
        help='Time budget per solve in milliseconds (default: 100)'
    )
    
    parser.add_argument(
        '--min-iterations',
        type=int,
        default=50,
        help='Minimum CFR iterations per solve (default: 50)'
    )
    
    parser.add_argument(
        '--street',
        choices=['preflop', 'flop', 'turn', 'river'],
        default='flop',
        help='Game street to test on (default: flop)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='experiments/results/sampling_comparison.json',
        help='Output file for results (default: experiments/results/sampling_comparison.json)'
    )
    
    args = parser.parse_args()
    
    # Parse sample counts
    sample_counts = [int(x.strip()) for x in args.sample_counts.split(',')]
    
    # Parse street
    street_map = {
        'preflop': Street.PREFLOP,
        'flop': Street.FLOP,
        'turn': Street.TURN,
        'river': Street.RIVER
    }
    street = street_map[args.street]
    
    # Print experiment configuration
    print("\n" + "=" * 100)
    print("PUBLIC CARD SAMPLING EXPERIMENT")
    print("=" * 100)
    print(f"Number of hands per config: {args.num_hands}")
    print(f"Sample counts to test: {sample_counts}")
    print(f"Time budget per solve: {args.time_budget}ms")
    print(f"Min iterations per solve: {args.min_iterations}")
    print(f"Street: {args.street}")
    print("=" * 100)
    
    # Run experiment
    experiment = PublicCardSamplingExperiment(
        time_budget_ms=args.time_budget,
        min_iterations=args.min_iterations
    )
    
    results = experiment.compare_configurations(
        num_hands=args.num_hands,
        sample_counts=sample_counts,
        street=street
    )
    
    # Print and save results
    experiment.print_results(results)
    experiment.save_results(results, args.output)


if __name__ == '__main__':
    main()
