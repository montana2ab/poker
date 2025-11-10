#!/usr/bin/env python3
"""
Example script demonstrating chunked training mode.

Chunked training splits long training runs into segments (chunks). At the end of
each chunk, the solver:
1. Saves a complete checkpoint (with all metadata including RNG state)
2. Flushes TensorBoard/logs
3. Terminates the process (releases 100% of RAM)
4. The coordinator automatically restarts from the last checkpoint

No loss of continuity: t_global, RNG state, ε/discount/DCFR parameters, and 
bucket_hash are all restored between chunks.

This is useful for:
- Memory-constrained environments
- Long training runs that may need to be interrupted
- Environments with limited continuous uptime
"""

from pathlib import Path
from holdem.types import MCCFRConfig, BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.chunked_coordinator import ChunkedTrainingCoordinator


def example_chunked_by_iterations():
    """Example: Chunked training with iteration-based chunks.
    
    Train for 1M iterations total, in chunks of 100k iterations each.
    After every 100k iterations, the process restarts to free memory.
    """
    print("\n" + "=" * 80)
    print("Example 1: Chunked Training by Iterations")
    print("=" * 80)
    
    config = MCCFRConfig(
        # Total training: 1 million iterations
        num_iterations=1_000_000,
        
        # Chunked mode: 100k iterations per chunk
        enable_chunked_training=True,
        chunk_size_iterations=100_000,
        
        # Save checkpoints every 25k iterations within each chunk
        checkpoint_interval=25_000,
        
        # DCFR discounting
        discount_mode="dcfr",
        discount_interval=1000,
        
        # Exploration
        exploration_epsilon=0.6,
        enable_pruning=True
    )
    
    print(f"Total iterations: {config.num_iterations:,}")
    print(f"Chunk size: {config.chunk_size_iterations:,} iterations")
    print(f"Number of chunks: {config.num_iterations // config.chunk_size_iterations}")
    print(f"Checkpoint interval: {config.checkpoint_interval:,} iterations")
    print()
    
    return config


def example_chunked_by_time():
    """Example: Chunked training with time-based chunks.
    
    Train for 8 days total, in chunks of 1 hour each.
    After every hour, the process restarts to free memory.
    """
    print("\n" + "=" * 80)
    print("Example 2: Chunked Training by Time")
    print("=" * 80)
    
    config = MCCFRConfig(
        # Total training: 8 days
        time_budget_seconds=8 * 24 * 3600,  # 691200 seconds
        
        # Chunked mode: 1 hour per chunk
        enable_chunked_training=True,
        chunk_size_minutes=60.0,  # 1 hour
        
        # Save checkpoints every 15 minutes within each chunk
        checkpoint_interval=None,  # Not used in time-budget mode
        snapshot_interval_seconds=900,  # 15 minutes
        
        # DCFR discounting
        discount_mode="dcfr",
        discount_interval=5000,
        
        # Exploration
        exploration_epsilon=0.6,
        enable_pruning=True
    )
    
    hours = config.time_budget_seconds / 3600
    days = config.time_budget_seconds / 86400
    num_chunks = int(hours / (config.chunk_size_minutes / 60))
    
    print(f"Total time budget: {hours:.1f} hours ({days:.2f} days)")
    print(f"Chunk duration: {config.chunk_size_minutes:.1f} minutes")
    print(f"Number of chunks: {num_chunks}")
    print(f"Snapshot interval: {config.snapshot_interval_seconds:.0f}s")
    print()
    
    return config


def example_chunked_hybrid():
    """Example: Chunked training with hybrid chunks.
    
    Train for 2M iterations OR 48 hours (whichever comes first),
    in chunks of 50k iterations OR 30 minutes (whichever comes first).
    """
    print("\n" + "=" * 80)
    print("Example 3: Chunked Training with Hybrid Boundaries")
    print("=" * 80)
    
    config = MCCFRConfig(
        # Total training: 2M iterations OR 48 hours
        num_iterations=2_000_000,
        time_budget_seconds=48 * 3600,  # 48 hours
        
        # Chunked mode: 50k iterations OR 30 minutes (whichever comes first)
        enable_chunked_training=True,
        chunk_size_iterations=50_000,
        chunk_size_minutes=30.0,
        
        # Checkpointing
        checkpoint_interval=10_000,
        
        # DCFR discounting
        discount_mode="dcfr",
        discount_interval=1000,
        
        # Exploration
        exploration_epsilon=0.6,
        enable_pruning=True
    )
    
    print(f"Total iterations: {config.num_iterations:,}")
    print(f"Total time budget: {config.time_budget_seconds / 3600:.1f} hours")
    print(f"Chunk size: {config.chunk_size_iterations:,} iterations OR {config.chunk_size_minutes:.1f} minutes")
    print(f"Checkpoint interval: {config.checkpoint_interval:,} iterations")
    print()
    
    return config


def run_chunked_training_example():
    """Run a minimal chunked training example.
    
    This demonstrates the actual usage of the ChunkedTrainingCoordinator.
    In practice, you would call this script multiple times to complete training.
    """
    print("\n" + "=" * 80)
    print("Running Chunked Training Example")
    print("=" * 80)
    
    # For this example, we'll use small numbers for quick testing
    config = MCCFRConfig(
        # Train for 10k iterations total
        num_iterations=10_000,
        
        # Chunks of 2k iterations
        enable_chunked_training=True,
        chunk_size_iterations=2_000,
        
        # Checkpoint every 1k iterations
        checkpoint_interval=1_000,
        
        # Basic DCFR
        discount_mode="dcfr",
        discount_interval=500,
        exploration_epsilon=0.6,
        enable_pruning=True
    )
    
    # You would need actual buckets for this to work
    # For the example, we'll just show the setup
    
    # Create simple bucket config (for demonstration)
    bucket_config = BucketConfig(
        k_preflop=8,
        k_flop=50,
        k_turn=50,
        k_river=50,
        num_samples=1000,
        seed=42
    )
    
    print("\nTo run this example:")
    print("1. Create buckets:")
    print("   ./bin/holdem-build-buckets --config configs/example_buckets.yaml")
    print()
    print("2. Run chunked training (will run one chunk and exit):")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/chunked_example \\")
    print("     --chunked \\")
    print("     --chunk-iterations 2000 \\")
    print("     --iters 10000")
    print()
    print("3. Run again to continue (will resume from checkpoint):")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/chunked_example \\")
    print("     --chunked \\")
    print("     --chunk-iterations 2000 \\")
    print("     --iters 10000")
    print()
    print("Repeat step 3 until training completes (5 chunks total in this example)")
    print()


def print_cli_examples():
    """Print CLI examples for chunked training."""
    print("\n" + "=" * 80)
    print("CLI Examples for Chunked Training")
    print("=" * 80)
    
    print("\n1. Iteration-based chunks (100k iterations per chunk):")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/chunked_iters \\")
    print("     --iters 1000000 \\")
    print("     --chunked \\")
    print("     --chunk-iterations 100000")
    
    print("\n2. Time-based chunks (1 hour per chunk):")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/chunked_time \\")
    print("     --time-budget 691200 \\")  # 8 days
    print("     --chunked \\")
    print("     --chunk-minutes 60")
    
    print("\n3. Hybrid chunks (50k iterations OR 30 minutes):")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/chunked_hybrid \\")
    print("     --iters 2000000 \\")
    print("     --time-budget 172800 \\")  # 48 hours
    print("     --chunked \\")
    print("     --chunk-iterations 50000 \\")
    print("     --chunk-minutes 30")
    
    print("\n4. With YAML config:")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --config configs/chunked_training.yaml \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/chunked_yaml")
    
    print("\n5. Continue from checkpoint (automatic resume):")
    print("   # Just run the same command again!")
    print("   ./bin/holdem-train-blueprint \\")
    print("     --buckets data/buckets.pkl \\")
    print("     --logdir runs/chunked_iters \\")
    print("     --iters 1000000 \\")
    print("     --chunked \\")
    print("     --chunk-iterations 100000")
    print("   # The coordinator will automatically find and resume from the latest checkpoint")
    print()


def print_monitoring_tips():
    """Print tips for monitoring chunked training."""
    print("\n" + "=" * 80)
    print("Monitoring Chunked Training")
    print("=" * 80)
    
    print("\n1. Check current progress:")
    print("   ls -lth runs/chunked_example/checkpoints/ | head -5")
    
    print("\n2. View latest checkpoint metadata:")
    print("   cat runs/chunked_example/checkpoints/checkpoint_iter*_metadata.json | jq")
    
    print("\n3. Monitor with TensorBoard (continuous across chunks):")
    print("   tensorboard --logdir runs/chunked_example/tensorboard")
    
    print("\n4. Track cumulative time:")
    print("   jq '.elapsed_seconds' runs/chunked_example/checkpoints/checkpoint_iter*_metadata.json")
    
    print("\n5. Automate chunk execution with a loop:")
    print("   #!/bin/bash")
    print("   while true; do")
    print("       ./bin/holdem-train-blueprint --buckets data/buckets.pkl \\")
    print("           --logdir runs/chunked --chunked --chunk-iterations 100000 \\")
    print("           --iters 1000000")
    print("       if [ $? -ne 0 ]; then break; fi")
    print("   done")
    print()


def print_benefits():
    """Print benefits of chunked training."""
    print("\n" + "=" * 80)
    print("Benefits of Chunked Training")
    print("=" * 80)
    
    print("\n1. Memory Management:")
    print("   - Process restart releases 100% of RAM")
    print("   - Prevents memory leaks from accumulating")
    print("   - Ideal for memory-constrained environments")
    
    print("\n2. Robustness:")
    print("   - Training can survive system restarts")
    print("   - Safe interruption points every chunk")
    print("   - Easy to pause and resume")
    
    print("\n3. No Loss of Progress:")
    print("   - Full checkpoint with all state (RNG, regrets, epsilon, etc.)")
    print("   - Seamless continuation across chunks")
    print("   - TensorBoard logs continuous across chunks")
    
    print("\n4. Flexibility:")
    print("   - Can change training parameters between chunks if needed")
    print("   - Easy to integrate with job schedulers (SLURM, etc.)")
    print("   - Works with both iteration and time-based training")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Chunked Training Mode - Examples")
    print("=" * 80)
    
    # Show different config examples
    config1 = example_chunked_by_iterations()
    config2 = example_chunked_by_time()
    config3 = example_chunked_hybrid()
    
    # Show how to run
    run_chunked_training_example()
    
    # Show CLI examples
    print_cli_examples()
    
    # Show monitoring tips
    print_monitoring_tips()
    
    # Show benefits
    print_benefits()
    
    print("=" * 80 + "\n")
