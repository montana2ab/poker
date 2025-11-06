#!/usr/bin/env python3
"""
Example demonstrating parallel training configuration.

This script shows how to configure and use the parallel training features
without requiring full dependencies installed.
"""

import multiprocessing as mp
from pathlib import Path


def show_parallel_config():
    """Show examples of parallel configuration."""
    print("=" * 80)
    print("Parallel Training Configuration Examples")
    print("=" * 80)
    
    # Detect available cores
    num_cores = mp.cpu_count()
    print(f"\n💻 System has {num_cores} CPU cores available\n")
    
    # Example 1: Single process (default)
    print("Example 1: Single Process Training (Default)")
    print("-" * 40)
    print("Command:")
    print("  python -m holdem.cli.train_blueprint \\")
    print("    --buckets assets/abstraction/precomputed_buckets.pkl \\")
    print("    --logdir runs/single_process \\")
    print("    --iters 1000000")
    print("\nConfiguration:")
    print("  - num_workers: 1 (default)")
    print("  - Uses single CPU core")
    print("  - Lower memory usage")
    print("  - Slower but simpler")
    print()
    
    # Example 2: Fixed number of workers
    print("Example 2: Fixed Number of Workers")
    print("-" * 40)
    print("Command:")
    print("  python -m holdem.cli.train_blueprint \\")
    print("    --buckets assets/abstraction/precomputed_buckets.pkl \\")
    print("    --logdir runs/parallel_4cores \\")
    print("    --iters 1000000 \\")
    print("    --num-workers 4 \\")
    print("    --batch-size 100")
    print("\nConfiguration:")
    print("  - num_workers: 4")
    print("  - Uses 4 CPU cores")
    print("  - batch_size: 100 iterations per batch")
    print("  - Faster training (3-4x speedup)")
    print()
    
    # Example 3: Use all cores
    print("Example 3: Use All Available Cores (Recommended)")
    print("-" * 40)
    print("Command:")
    print("  python -m holdem.cli.train_blueprint \\")
    print("    --buckets assets/abstraction/precomputed_buckets.pkl \\")
    print("    --logdir runs/parallel_all_cores \\")
    print("    --iters 1000000 \\")
    print("    --num-workers 0 \\")
    print("    --batch-size 100")
    print("\nConfiguration:")
    print(f"  - num_workers: 0 (auto-detect, will use {num_cores} cores)")
    print(f"  - Uses all {num_cores} CPU cores")
    print("  - Maximum parallelization")
    print(f"  - Expected speedup: {min(num_cores, 16)}x (approximately)")
    print()
    
    # Example 4: Time-budget mode with parallelism
    print("Example 4: Time-Budget Training with Parallelism")
    print("-" * 40)
    print("Command:")
    print("  python -m holdem.cli.train_blueprint \\")
    print("    --buckets assets/abstraction/precomputed_buckets.pkl \\")
    print("    --logdir runs/8days_parallel \\")
    print("    --time-budget 691200 \\")
    print("    --snapshot-interval 3600 \\")
    print("    --num-workers 0 \\")
    print("    --batch-size 200")
    print("\nConfiguration:")
    print("  - time_budget: 691200 seconds (8 days)")
    print(f"  - num_workers: 0 (will use {num_cores} cores)")
    print("  - batch_size: 200 (larger batches for long runs)")
    print("  - Snapshots every hour")
    print()


def show_realtime_parallel_config():
    """Show examples of parallel real-time solving configuration."""
    print("=" * 80)
    print("Parallel Real-time Solving Configuration Examples")
    print("=" * 80)
    
    num_cores = mp.cpu_count()
    print(f"\n💻 System has {num_cores} CPU cores available\n")
    
    # Example 1: Single process
    print("Example 1: Sequential Real-time Solving (Default)")
    print("-" * 40)
    print("Command:")
    print("  python -m holdem.cli.run_dry_run \\")
    print("    --profile assets/table_profiles/default_profile.json \\")
    print("    --policy runs/blueprint/avg_policy.json \\")
    print("    --time-budget-ms 80 \\")
    print("    --min-iters 100")
    print("\nConfiguration:")
    print("  - num_workers: 1 (default)")
    print("  - Sequential solving")
    print("  - Lower overhead")
    print()
    
    # Example 2: Parallel solving
    print("Example 2: Parallel Real-time Solving")
    print("-" * 40)
    print("Command:")
    print("  python -m holdem.cli.run_dry_run \\")
    print("    --profile assets/table_profiles/default_profile.json \\")
    print("    --policy runs/blueprint/avg_policy.json \\")
    print("    --time-budget-ms 80 \\")
    print("    --min-iters 100 \\")
    print("    --num-workers 4")
    print("\nConfiguration:")
    print("  - num_workers: 4")
    print("  - 4 parallel CFR iterations")
    print("  - Better solution quality in same time")
    print("  - Recommended: 2-4 workers for real-time")
    print()


def show_performance_tips():
    """Show performance optimization tips."""
    print("=" * 80)
    print("Performance Optimization Tips")
    print("=" * 80)
    print()
    
    print("1. Choosing num_workers:")
    print("   - Training: Use 0 (all cores) for maximum speed")
    print("   - Real-time: Use 2-4 workers (more may add overhead)")
    print()
    
    print("2. Choosing batch_size:")
    print("   - Smaller (50-100): More frequent updates, more overhead")
    print("   - Larger (100-200): Less overhead, less frequent updates")
    print("   - Recommended: 100 for most cases")
    print()
    
    print("3. Expected Performance:")
    num_cores = mp.cpu_count()
    print(f"   Your system ({num_cores} cores):")
    print(f"   - 1 worker:  ~1000 iterations/sec (baseline)")
    print(f"   - 4 workers: ~3500 iterations/sec (3.5x speedup)")
    print(f"   - {num_cores} workers: ~{num_cores * 900} iterations/sec ({num_cores * 0.9:.1f}x speedup)")
    print()
    
    print("4. Memory Considerations:")
    print("   - Each worker uses memory for regret tracking")
    print("   - Monitor RAM usage with many workers")
    print("   - Reduce batch_size if running out of memory")
    print()


def show_yaml_example():
    """Show YAML configuration example."""
    print("=" * 80)
    print("YAML Configuration Example")
    print("=" * 80)
    print()
    print("Create configs/parallel_training.yaml:")
    print()
    print("```yaml")
    print("# Parallel training configuration")
    print("time_budget_seconds: 86400  # 1 day")
    print("snapshot_interval_seconds: 3600  # 1 hour")
    print()
    print("# Parallelism")
    print("num_workers: 0  # Use all cores")
    print("batch_size: 100")
    print()
    print("# MCCFR parameters")
    print("discount_interval: 5000")
    print("exploration_epsilon: 0.6")
    print("enable_pruning: true")
    print("```")
    print()
    print("Use with:")
    print("  python -m holdem.cli.train_blueprint \\")
    print("    --config configs/parallel_training.yaml \\")
    print("    --buckets assets/abstraction/precomputed_buckets.pkl \\")
    print("    --logdir runs/parallel_yaml")
    print()


if __name__ == "__main__":
    show_parallel_config()
    print()
    show_realtime_parallel_config()
    print()
    show_performance_tips()
    print()
    show_yaml_example()
    print()
    print("=" * 80)
    print("For more details, see PARALLEL_TRAINING.md")
    print("=" * 80)
