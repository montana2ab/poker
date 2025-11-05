"""CLI: Build abstraction buckets."""

import argparse
from pathlib import Path
import yaml
from holdem.types import BucketConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.utils.logging import setup_logger

logger = setup_logger("build_buckets")


def main():
    parser = argparse.ArgumentParser(description="Build hand abstraction buckets")
    parser.add_argument("--hands", type=int, default=500000,
                       help="Number of hands to sample per street")
    parser.add_argument("--k-preflop", type=int, default=24,
                       help="Number of preflop buckets")
    parser.add_argument("--k-flop", type=int, default=80,
                       help="Number of flop buckets")
    parser.add_argument("--k-turn", type=int, default=80,
                       help="Number of turn buckets")
    parser.add_argument("--k-river", type=int, default=64,
                       help="Number of river buckets")
    parser.add_argument("--config", type=Path,
                       help="Output config file path")
    parser.add_argument("--out", type=Path, required=True,
                       help="Output pickle file path")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")
    
    args = parser.parse_args()
    
    # Create config
    config = BucketConfig(
        k_preflop=args.k_preflop,
        k_flop=args.k_flop,
        k_turn=args.k_turn,
        k_river=args.k_river,
        num_samples=args.hands,
        seed=args.seed
    )
    
    # Save config if requested
    if args.config:
        args.config.parent.mkdir(parents=True, exist_ok=True)
        with open(args.config, 'w') as f:
            yaml.dump(vars(config), f, default_flow_style=False)
        logger.info(f"Saved config to {args.config}")
    
    # Build buckets
    logger.info("Building hand buckets...")
    logger.info(f"  Preflop: {config.k_preflop} buckets")
    logger.info(f"  Flop: {config.k_flop} buckets")
    logger.info(f"  Turn: {config.k_turn} buckets")
    logger.info(f"  River: {config.k_river} buckets")
    logger.info(f"  Samples per street: {config.num_samples}")
    
    bucketing = HandBucketing(config)
    bucketing.build(num_samples=args.hands)
    
    # Save buckets
    bucketing.save(args.out)
    logger.info(f"Saved buckets to {args.out}")
    
    logger.info("Complete!")


if __name__ == "__main__":
    main()
