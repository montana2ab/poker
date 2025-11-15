#!/usr/bin/env python3
"""Compare bucket configurations by training abbreviated blueprint strategies.

This script trains multiple bucket configurations with reduced iterations
and saves the resulting strategies with config-encoded names for later comparison.

Usage:
    python scripts/compare_buckets_training.py --configs A B --iters 100000 --output experiments/
    python scripts/compare_buckets_training.py --configs A B C --iters 50000 --output experiments/quick_test/
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from holdem.bucket_configs import BucketConfigFactory
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.utils.logging import setup_logger, get_logger

logger = get_logger("compare_buckets_training")


def train_config(
    config_name: str,
    output_dir: Path,
    num_iterations: int,
    num_samples: int,
    num_players: int,
    seed: int
) -> dict:
    """Train a single bucket configuration.
    
    Args:
        config_name: Name of the bucket configuration (e.g., 'A', 'B')
        output_dir: Directory to save outputs
        num_iterations: Number of MCCFR iterations
        num_samples: Number of samples for bucket generation
        num_players: Number of players
        seed: Random seed
        
    Returns:
        Dictionary with training metadata
    """
    logger.info("=" * 70)
    logger.info(f"Training Configuration {config_name}")
    logger.info("=" * 70)
    
    # Create bucket config
    bucket_config, metadata = BucketConfigFactory.create(
        config_name=config_name,
        num_samples=num_samples,
        seed=seed,
        num_players=num_players
    )
    
    logger.info(f"Configuration: {metadata['description']}")
    logger.info(f"Bucket spec: {metadata['spec']}")
    
    # Create output paths
    config_id = metadata['internal_name']
    bucket_path = output_dir / f"buckets_{config_id}.pkl"
    logdir = output_dir / f"training_{config_id}"
    logdir.mkdir(parents=True, exist_ok=True)
    
    # Build buckets
    logger.info(f"Building buckets with {num_samples} samples...")
    bucketing = HandBucketing(bucket_config)
    bucketing.build(num_samples=num_samples)
    bucketing.save(bucket_path)
    logger.info(f"Buckets saved to {bucket_path}")
    
    # Create MCCFR config
    mccfr_config = MCCFRConfig(
        num_iterations=num_iterations,
        checkpoint_interval=max(10000, num_iterations // 10),
        num_players=num_players,
        exploration_epsilon=0.6,
        use_linear_weighting=True,
        discount_interval=1000,
        discount_mode="dcfr",
        enable_pruning=True,
        pruning_threshold=-300_000_000.0,
        pruning_probability=0.95,
    )
    
    # Create solver
    logger.info(f"Initializing MCCFR solver for {num_iterations} iterations...")
    solver = MCCFRSolver(config=mccfr_config, bucketing=bucketing)
    
    # Train
    start_time = datetime.now()
    logger.info("Starting training...")
    solver.train(logdir=logdir, use_tensorboard=False)
    end_time = datetime.now()
    
    training_time = (end_time - start_time).total_seconds()
    
    logger.info(f"Training completed in {training_time:.1f} seconds")
    
    # Find final strategy file
    strategy_files = sorted(logdir.glob("strategy_*.pkl"))
    if strategy_files:
        strategy_path = strategy_files[-1]
        logger.info(f"Strategy saved to {strategy_path}")
    else:
        logger.warning("No strategy file found")
        strategy_path = None
    
    result = {
        'config_name': config_name,
        'config_id': config_id,
        'spec': metadata['spec'],
        'description': metadata['description'],
        'bucket_path': str(bucket_path),
        'strategy_path': str(strategy_path) if strategy_path else None,
        'logdir': str(logdir),
        'num_iterations': num_iterations,
        'training_time_seconds': training_time,
        'num_samples': num_samples,
        'num_players': num_players,
        'seed': seed,
    }
    
    logger.info("=" * 70)
    logger.info(f"Configuration {config_name} training complete")
    logger.info("=" * 70)
    logger.info("")
    
    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Train multiple bucket configurations for comparison",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train configs A and B with 100k iterations
  python scripts/compare_buckets_training.py --configs A B --iters 100000 --output experiments/

  # Quick test with 3 configs and 50k iterations
  python scripts/compare_buckets_training.py --configs A B C --iters 50000 --output experiments/quick/

  # Full training with 500k iterations
  python scripts/compare_buckets_training.py --configs A B --iters 500000 --samples 1000000 --output experiments/full/
        """
    )
    
    parser.add_argument(
        '--configs',
        nargs='+',
        help='Bucket configurations to train (e.g., A B C)'
    )
    parser.add_argument(
        '--iters',
        type=int,
        default=100000,
        help='Number of MCCFR iterations (default: 100000)'
    )
    parser.add_argument(
        '--samples',
        type=int,
        default=500000,
        help='Number of samples for bucket generation (default: 500000)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('experiments'),
        help='Output directory for results (default: experiments/)'
    )
    parser.add_argument(
        '--num-players',
        type=int,
        default=2,
        choices=[2, 3, 4, 5, 6],
        help='Number of players (default: 2)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed (default: 42)'
    )
    parser.add_argument(
        '--list-configs',
        action='store_true',
        help='List available configurations and exit'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logger("compare_buckets_training")
    
    # List configs if requested
    if args.list_configs:
        if args.configs:
            logger.warning("--configs ignored when --list-configs is specified")
        logger.info("Available bucket configurations:")
        logger.info("")
        for config in BucketConfigFactory.list_configs():
            logger.info(f"  {config['name']}: {config['description']}")
            logger.info(f"      Spec: {config['spec']}")
            logger.info("")
        return 0
    
    # Validate that configs is provided for training
    if not args.configs:
        parser.error("--configs is required for training (use --list-configs to see available configurations)")
    
    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)
    
    # Log experiment setup
    logger.info("=" * 70)
    logger.info("BUCKET CONFIGURATION TRAINING EXPERIMENT")
    logger.info("=" * 70)
    logger.info(f"Configurations to train: {', '.join(args.configs)}")
    logger.info(f"MCCFR iterations: {args.iters:,}")
    logger.info(f"Bucket samples: {args.samples:,}")
    logger.info(f"Number of players: {args.num_players}")
    logger.info(f"Random seed: {args.seed}")
    logger.info(f"Output directory: {args.output}")
    logger.info("=" * 70)
    logger.info("")
    
    # Train each configuration
    results = []
    for config_name in args.configs:
        try:
            result = train_config(
                config_name=config_name.upper(),
                output_dir=args.output,
                num_iterations=args.iters,
                num_samples=args.samples,
                num_players=args.num_players,
                seed=args.seed
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to train configuration {config_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Save experiment metadata
    import json
    metadata_path = args.output / 'training_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'num_iterations': args.iters,
            'num_samples': args.samples,
            'num_players': args.num_players,
            'seed': args.seed,
            'results': results,
        }, f, indent=2)
    
    logger.info("=" * 70)
    logger.info("EXPERIMENT COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Trained {len(results)} configurations")
    logger.info(f"Metadata saved to {metadata_path}")
    logger.info("")
    logger.info("To evaluate these configurations, run:")
    logger.info(f"  python scripts/compare_buckets_eval.py --experiment {args.output}")
    logger.info("=" * 70)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
