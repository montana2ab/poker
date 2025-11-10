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
        # Clear epsilon_schedule if static epsilon provided via CLI
        config_dict.pop('epsilon_schedule', None)
    
    if args.discount_interval is not None:
        config_dict['discount_interval'] = args.discount_interval
    
    if args.num_workers is not None:
        config_dict['num_workers'] = args.num_workers
    
    if args.batch_size is not None:
        config_dict['batch_size'] = args.batch_size
    
    # Convert epsilon_schedule from list of lists to list of tuples
    if 'epsilon_schedule' in config_dict and config_dict['epsilon_schedule'] is not None:
        config_dict['epsilon_schedule'] = [tuple(item) for item in config_dict['epsilon_schedule']]
    
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
    parser.add_argument("--resume-from", type=Path,
                       help="Resume training from checkpoint (will validate bucket compatibility)")
    parser.add_argument("--tensorboard", action="store_true", default=True,
                       help="Enable TensorBoard logging (default: True)")
    parser.add_argument("--no-tensorboard", action="store_false", dest="tensorboard",
                       help="Disable TensorBoard logging")
    parser.add_argument("--num-workers", type=int,
                       help="Number of parallel worker processes (1 = single process, 0 = use all CPU cores)")
    parser.add_argument("--batch-size", type=int,
                       help="Number of iterations per worker batch (only for parallel training)")
    
    # Multi-instance parallel training
    parser.add_argument("--num-instances", type=int,
                       help="Launch multiple independent solver instances in parallel (each with 1 worker). "
                            "In iteration mode (--iters), iterations are distributed among instances. "
                            "In time-budget mode (--time-budget), each instance runs independently for the full time budget. "
                            "Cannot be used with --num-workers. Supports --resume-from to continue previous multi-instance run.")
    
    args = parser.parse_args()
    
    # Validate multi-instance mode
    if args.num_instances is not None:
        if args.num_instances < 1:
            parser.error("--num-instances must be >= 1")
        
        if args.num_workers is not None and args.num_workers != 1:
            parser.error("--num-instances requires each instance to use 1 worker. "
                        "Do not specify --num-workers or set it to 1.")
        
        # Resume is now supported in multi-instance mode
        # No need to error out if resume_from is specified
        
        # Force num_workers to 1 for multi-instance mode
        args.num_workers = 1
    
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
    
    # Note: Multi-instance mode now supports both iteration-based and time-budget modes
    
    # Load buckets
    logger.info(f"Loading buckets from {args.buckets}")
    bucketing = HandBucketing.load(args.buckets)
    
    # Multi-instance mode: Launch multiple independent solver instances
    if args.num_instances is not None:
        logger.info("=" * 60)
        logger.info(f"MULTI-INSTANCE MODE: Launching {args.num_instances} independent solver instances")
        if args.resume_from:
            logger.info(f"RESUME MODE: Will attempt to resume from {args.resume_from}")
        logger.info("=" * 60)
        
        from holdem.mccfr.multi_instance_coordinator import MultiInstanceCoordinator
        
        coordinator = MultiInstanceCoordinator(
            num_instances=args.num_instances,
            config=config,
            bucketing=bucketing,
            num_players=args.num_players
        )
        
        result = coordinator.train(logdir=args.logdir, use_tensorboard=args.tensorboard, resume_from=args.resume_from)
        return result
    
    # Standard single-solver mode (with optional multi-worker parallelism)
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
    
    # Log multiprocessing configuration
    if config.num_workers > 1 or config.num_workers == 0:
        import multiprocessing as mp
        actual_workers = config.num_workers if config.num_workers > 0 else mp.cpu_count()
        logger.info(f"Parallel training enabled: {actual_workers} worker(s), batch size: {config.batch_size}")
    else:
        logger.info("Single-process training mode")
    
    # Log epsilon configuration
    if config.epsilon_schedule:
        logger.info("Epsilon schedule configured:")
        for iteration, epsilon in config.epsilon_schedule:
            logger.info(f"  Iteration {iteration:>10}: ε = {epsilon:.3f}")
    else:
        logger.info(f"Exploration epsilon (static): {config.exploration_epsilon}")
    
    # Create solver
    logger.info("Initializing MCCFR solver...")
    
    # Choose solver based on num_workers
    if config.num_workers > 1 or config.num_workers == 0:
        from holdem.mccfr.parallel_solver import ParallelMCCFRSolver
        solver = ParallelMCCFRSolver(
            config=config,
            bucketing=bucketing,
            num_players=args.num_players
        )
    else:
        solver = MCCFRSolver(
            config=config,
            bucketing=bucketing,
            num_players=args.num_players
        )
    
    # Resume from checkpoint if provided
    if args.resume_from:
        logger.info(f"Resuming training from checkpoint: {args.resume_from}")
        try:
            solver.load_checkpoint(args.resume_from, validate_buckets=True)
            logger.info("Checkpoint loaded and validated successfully")
        except ValueError as e:
            logger.error(f"BUCKET VALIDATION FAILED: {e}")
            logger.error("Cannot resume training with incompatible bucket configuration")
            logger.error("Please use the same bucket file that was used for the checkpoint")
            return 1
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return 1
    
    # Train
    logger.info("Starting training...")
    if args.tensorboard:
        logger.info(f"TensorBoard logs will be saved to {args.logdir / 'tensorboard'}")
        logger.info(f"Monitor training with: tensorboard --logdir {args.logdir / 'tensorboard'}")
    solver.train(logdir=args.logdir, use_tensorboard=args.tensorboard)
    
    logger.info("Training complete!")


if __name__ == "__main__":
    main()
