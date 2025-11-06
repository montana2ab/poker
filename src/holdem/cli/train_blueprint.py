"""CLI: Train blueprint strategy."""

import argparse
import yaml
from pathlib import Path
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.utils.logging import setup_logger

logger = setup_logger("train_blueprint")


def load_config_from_yaml(yaml_path: Path) -> dict:
    """Load configuration from YAML file.
    
    Args:
        yaml_path: Path to YAML configuration file
        
    Returns:
        Dictionary of configuration parameters
    """
    with open(yaml_path, 'r') as f:
        config_dict = yaml.safe_load(f)
    return config_dict


def create_mccfr_config(args, yaml_config: dict = None) -> MCCFRConfig:
    """Create MCCFRConfig from arguments and YAML config.
    
    Command-line arguments override YAML configuration.
    
    Args:
        args: Parsed command-line arguments
        yaml_config: Dictionary from YAML file (optional)
        
    Returns:
        MCCFRConfig instance
    """
    config_dict = yaml_config.copy() if yaml_config else {}
    
    # Override with command-line arguments (if provided)
    if args.iters is not None:
        config_dict['num_iterations'] = args.iters
        # If iterations specified, clear time budget
        config_dict.pop('time_budget_seconds', None)
    
    if args.time_budget is not None:
        config_dict['time_budget_seconds'] = args.time_budget
        # If time budget specified, iterations will be ignored
    
    if args.checkpoint_interval is not None:
        config_dict['checkpoint_interval'] = args.checkpoint_interval
    
    if args.snapshot_interval is not None:
        config_dict['snapshot_interval_seconds'] = args.snapshot_interval
    
    if args.epsilon is not None:
        config_dict['exploration_epsilon'] = args.epsilon
    
    if args.discount_interval is not None:
        config_dict['discount_interval'] = args.discount_interval
    
    return MCCFRConfig(**config_dict)


def main():
    parser = argparse.ArgumentParser(description="Train blueprint strategy using MCCFR")
    
    # Configuration file
    parser.add_argument("--config", type=Path,
                       help="Path to YAML configuration file")
    
    # Training mode (iteration-based or time-based)
    parser.add_argument("--iters", type=int,
                       help="Number of MCCFR iterations (overrides config)")
    parser.add_argument("--time-budget", type=float,
                       help="Time budget in seconds (e.g., 691200 for 8 days). Overrides --iters and config.")
    
    # Required arguments
    parser.add_argument("--buckets", type=Path, required=True,
                       help="Path to precomputed buckets file")
    parser.add_argument("--logdir", type=Path, required=True,
                       help="Directory for logs and checkpoints")
    
    # Optional parameters
    parser.add_argument("--checkpoint-interval", type=int,
                       help="Checkpoint interval (iterations)")
    parser.add_argument("--snapshot-interval", type=float,
                       help="Snapshot interval in seconds (for time-budget mode)")
    parser.add_argument("--discount-interval", type=int,
                       help="Discount interval in iterations")
    parser.add_argument("--num-players", type=int, default=2,
                       help="Number of players")
    parser.add_argument("--epsilon", type=float,
                       help="Exploration epsilon for outcome sampling")
    parser.add_argument("--tensorboard", action="store_true", default=True,
                       help="Enable TensorBoard logging (default: True)")
    parser.add_argument("--no-tensorboard", action="store_false", dest="tensorboard",
                       help="Disable TensorBoard logging")
    
    args = parser.parse_args()
    
    # Load YAML config if provided
    yaml_config = None
    if args.config:
        logger.info(f"Loading configuration from {args.config}")
        yaml_config = load_config_from_yaml(args.config)
    
    # Create config (merge YAML and CLI args)
    config = create_mccfr_config(args, yaml_config)
    
    # Validate configuration
    if config.time_budget_seconds is None and config.num_iterations is None:
        parser.error("Either --iters, --time-budget, or a config file with one of these must be provided")
    
    # Load buckets
    logger.info(f"Loading buckets from {args.buckets}")
    bucketing = HandBucketing.load(args.buckets)
    
    # Log training mode
    if config.time_budget_seconds is not None:
        days = config.time_budget_seconds / 86400
        hours = config.time_budget_seconds / 3600
        logger.info(f"Training mode: Time-budget ({config.time_budget_seconds:.0f}s = {hours:.1f}h = {days:.2f} days)")
        logger.info(f"Snapshots will be saved every {config.snapshot_interval_seconds:.0f}s")
    else:
        logger.info(f"Training mode: Iteration-based ({config.num_iterations} iterations)")
        logger.info(f"Checkpoints will be saved every {config.checkpoint_interval} iterations")
    
    logger.info(f"Discount interval: {config.discount_interval} iterations")
    logger.info(f"Exploration epsilon: {config.exploration_epsilon}")
    
    # Create solver
    logger.info("Initializing MCCFR solver...")
    solver = MCCFRSolver(
        config=config,
        bucketing=bucketing,
        num_players=args.num_players
    )
    
    # Train
    logger.info("Starting training...")
    if args.tensorboard:
        logger.info(f"TensorBoard logs will be saved to {args.logdir / 'tensorboard'}")
        logger.info(f"Monitor training with: tensorboard --logdir {args.logdir / 'tensorboard'}")
    solver.train(logdir=args.logdir, use_tensorboard=args.tensorboard)
    
    logger.info("Training complete!")


if __name__ == "__main__":
    main()
