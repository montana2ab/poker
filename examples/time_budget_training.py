#!/usr/bin/env python3
"""
Example script demonstrating time-budget based training.

This script shows how to use the new time-budget training mode
both programmatically and via CLI.
"""

from pathlib import Path
from holdem.types import MCCFRConfig

def example_config_time_budget():
    """Example: Create config for 8-day training run."""
    config = MCCFRConfig(
        # Time-budget mode: 8 days
        time_budget_seconds=8 * 24 * 3600,  # 691200 seconds
        
        # Save snapshots every hour
        snapshot_interval_seconds=3600,
        
        # Discount every 5000 iterations
        discount_interval=5000,
        regret_discount_alpha=1.0,  # No discount (Linear MCCFR)
        strategy_discount_beta=1.0,
        
        # Exploration and pruning
        exploration_epsilon=0.6,
        enable_pruning=True,
        pruning_threshold=-300_000_000.0,
        pruning_probability=0.95
    )
    
    print("8-Day Training Configuration:")
    print(f"  Time budget: {config.time_budget_seconds}s ({config.time_budget_seconds / 86400:.1f} days)")
    print(f"  Snapshot interval: {config.snapshot_interval_seconds}s ({config.snapshot_interval_seconds / 60:.0f} min)")
    print(f"  Discount interval: {config.discount_interval} iterations")
    print(f"  Exploration epsilon: {config.exploration_epsilon}")
    print()
    
    return config


def example_config_quick_test():
    """Example: Create config for quick 1-hour test."""
    config = MCCFRConfig(
        # Time-budget mode: 1 hour
        time_budget_seconds=3600,
        
        # Save snapshots every 5 minutes
        snapshot_interval_seconds=300,
        
        # Discount every 500 iterations
        discount_interval=500,
        
        # Same exploration/pruning settings
        exploration_epsilon=0.6,
        enable_pruning=True
    )
    
    print("1-Hour Test Configuration:")
    print(f"  Time budget: {config.time_budget_seconds}s ({config.time_budget_seconds / 60:.0f} minutes)")
    print(f"  Snapshot interval: {config.snapshot_interval_seconds}s ({config.snapshot_interval_seconds / 60:.0f} min)")
    print(f"  Discount interval: {config.discount_interval} iterations")
    print()
    
    return config


def example_config_iteration_mode():
    """Example: Create config for traditional iteration-based training."""
    config = MCCFRConfig(
        # Iteration mode (no time budget)
        num_iterations=2_500_000,
        
        # Checkpoint every 100k iterations
        checkpoint_interval=100_000,
        
        # Discount every 1000 iterations
        discount_interval=1000,
        
        exploration_epsilon=0.6,
        enable_pruning=True
    )
    
    print("Iteration-Based Configuration:")
    print(f"  Iterations: {config.num_iterations:,}")
    print(f"  Checkpoint interval: {config.checkpoint_interval:,} iterations")
    print(f"  Discount interval: {config.discount_interval} iterations")
    print()
    
    return config


def print_cli_examples():
    """Print example CLI commands."""
    print("CLI Examples:")
    print("=" * 80)
    
    print("\n1. Time-budget mode with YAML config:")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --config configs/blueprint_training.yaml \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/8days_run")
    
    print("\n2. Time-budget mode with CLI args (8 days):")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --time-budget 691200 \\")
    print("     --snapshot-interval 3600 \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/8days_cli")
    
    print("\n3. Quick test (1 hour):")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --time-budget 3600 \\")
    print("     --snapshot-interval 300 \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/test_1hour")
    
    print("\n4. Iteration mode (backwards compatible):")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --iters 2500000 \\")
    print("     --checkpoint-interval 100000 \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/2.5M_iters")
    
    print("\n5. Override YAML config with CLI args:")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --config configs/blueprint_training.yaml \\")
    print("     --time-budget 43200 \\")  # 12 hours instead of config value
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/custom_run")
    print()


def print_monitoring_commands():
    """Print commands for monitoring training."""
    print("Monitoring Training:")
    print("=" * 80)
    
    print("\n1. Monitor with TensorBoard:")
    print("   tensorboard --logdir runs/8days_run/tensorboard")
    
    print("\n2. Check latest snapshot:")
    print("   ls -lth runs/8days_run/snapshots/ | head -5")
    
    print("\n3. View snapshot metadata:")
    print("   cat runs/8days_run/snapshots/snapshot_iter10000_t3600s/metadata.json | jq")
    
    print("\n4. Check checkpoint metrics:")
    print("   cat runs/8days_run/checkpoints/checkpoint_iter100000_t7200s_metadata.json | jq .metrics")
    print()


def print_time_conversions():
    """Print useful time conversion reference."""
    print("Time Conversion Reference:")
    print("=" * 80)
    
    conversions = [
        ("1 hour", 1 * 3600),
        ("6 hours", 6 * 3600),
        ("12 hours", 12 * 3600),
        ("1 day", 1 * 86400),
        ("3 days", 3 * 86400),
        ("7 days", 7 * 86400),
        ("8 days", 8 * 86400),
        ("14 days", 14 * 86400),
        ("30 days", 30 * 86400),
    ]
    
    for name, seconds in conversions:
        hours = seconds / 3600
        days = seconds / 86400
        print(f"  {name:12s}: {seconds:9,d} seconds  ({hours:6.1f} hours, {days:5.2f} days)")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Time-Budget Training Mode - Examples")
    print("=" * 80 + "\n")
    
    # Show different config examples
    config1 = example_config_time_budget()
    config2 = example_config_quick_test()
    config3 = example_config_iteration_mode()
    
    # Show CLI examples
    print_cli_examples()
    
    # Show monitoring commands
    print_monitoring_commands()
    
    # Show time conversions
    print_time_conversions()
    
    print("For more information, see BLUEPRINT_TIME_BUDGET.md")
    print("=" * 80 + "\n")
