"""CLI: Train blueprint strategy."""

import argparse
from pathlib import Path
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.utils.logging import setup_logger

logger = setup_logger("train_blueprint")


def main():
    parser = argparse.ArgumentParser(description="Train blueprint strategy using MCCFR")
    parser.add_argument("--iters", type=int, required=True,
                       help="Number of MCCFR iterations")
    parser.add_argument("--buckets", type=Path, required=True,
                       help="Path to precomputed buckets file")
    parser.add_argument("--logdir", type=Path, required=True,
                       help="Directory for logs and checkpoints")
    parser.add_argument("--checkpoint-interval", type=int, default=100000,
                       help="Checkpoint interval")
    parser.add_argument("--num-players", type=int, default=2,
                       help="Number of players")
    parser.add_argument("--epsilon", type=float, default=0.6,
                       help="Exploration epsilon for outcome sampling")
    
    args = parser.parse_args()
    
    # Load buckets
    logger.info(f"Loading buckets from {args.buckets}")
    bucketing = HandBucketing.load(args.buckets)
    
    # Create config
    config = MCCFRConfig(
        num_iterations=args.iters,
        checkpoint_interval=args.checkpoint_interval,
        exploration_epsilon=args.epsilon
    )
    
    # Create solver
    logger.info("Initializing MCCFR solver...")
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=args.num_players
    )
    
    # Train
    logger.info(f"Training blueprint for {args.iters} iterations...")
    solver.train(logdir=args.logdir)
    
    logger.info("Training complete!")


if __name__ == "__main__":
    main()
