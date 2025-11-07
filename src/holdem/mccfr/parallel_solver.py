"""Parallel MCCFR solver using multiprocessing."""

import time
import multiprocessing as mp
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from holdem.types import MCCFRConfig, Street
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.mccfr_os import OutcomeSampler
from holdem.mccfr.policy_store import PolicyStore
from holdem.mccfr.regrets import RegretTracker
from holdem.utils.logging import get_logger
from holdem.utils.timers import Timer

logger = get_logger("mccfr.parallel_solver")

# Optional TensorBoard support
try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_AVAILABLE = True
except ImportError:
    TENSORBOARD_AVAILABLE = False
    logger.warning("TensorBoard not available. Install tensorboard for training visualization: pip install tensorboard")


def worker_process(
    worker_id: int,
    bucketing: HandBucketing,
    num_players: int,
    epsilon: float,
    use_linear_weighting: bool,
    enable_pruning: bool,
    pruning_threshold: float,
    pruning_probability: float,
    iteration_start: int,
    num_iterations: int,
    result_queue: mp.Queue
):
    """Worker process that runs MCCFR iterations.
    
    Args:
        worker_id: ID of this worker
        bucketing: Hand bucketing configuration
        num_players: Number of players
        epsilon: Exploration epsilon
        use_linear_weighting: Use linear weighting
        enable_pruning: Enable pruning
        pruning_threshold: Pruning threshold
        pruning_probability: Pruning probability
        iteration_start: Starting iteration number
        num_iterations: Number of iterations to run
        result_queue: Queue to put results
    """
    # Create sampler for this worker
    sampler = OutcomeSampler(
        bucketing=bucketing,
        num_players=num_players,
        epsilon=epsilon,
        use_linear_weighting=use_linear_weighting,
        enable_pruning=enable_pruning,
        pruning_threshold=pruning_threshold,
        pruning_probability=pruning_probability
    )
    
    # Run iterations
    utilities = []
    regret_updates = {}  # Track regret updates: {infoset: {action: regret}}
    strategy_updates = {}  # Track strategy updates: {infoset: {action: weight}}
    
    for i in range(num_iterations):
        iteration = iteration_start + i
        utility = sampler.sample_iteration(iteration)
        utilities.append(utility)
    
    # Collect regret and strategy updates from this worker
    for infoset in sampler.regret_tracker.regrets:
        regret_updates[infoset] = dict(sampler.regret_tracker.regrets[infoset])
    
    for infoset in sampler.regret_tracker.strategy_sum:
        strategy_updates[infoset] = dict(sampler.regret_tracker.strategy_sum[infoset])
    
    # Put results in queue
    result = {
        'worker_id': worker_id,
        'utilities': utilities,
        'regret_updates': regret_updates,
        'strategy_updates': strategy_updates
    }
    result_queue.put(result)


class ParallelMCCFRSolver:
    """Parallel MCCFR solver using multiprocessing."""
    
    def __init__(
        self,
        config: MCCFRConfig,
        bucketing: HandBucketing,
        num_players: int = 2
    ):
        self.config = config
        self.bucketing = bucketing
        self.num_players = num_players
        
        # Determine number of workers
        if self.config.num_workers == 0:
            # Use all available CPU cores
            self.num_workers = mp.cpu_count()
        else:
            self.num_workers = max(1, self.config.num_workers)
        
        logger.info(f"Initialized parallel solver with {self.num_workers} worker(s)")
        
        # Main regret tracker (will aggregate results from workers)
        self.regret_tracker = RegretTracker()
        self.iteration = 0
        self.writer: Optional[SummaryWriter] = None
        
        # Initialize epsilon schedule tracking
        self._epsilon_schedule_index = 0
        self._current_epsilon = config.exploration_epsilon
    
    def _merge_worker_results(self, results: List[Dict]):
        """Merge regret and strategy updates from workers.
        
        Workers compute independent samples of the game tree. We sum (not average)
        their cumulative regrets and strategy sums, as each worker's contribution
        represents additional iterations of the algorithm. All values are stored
        as Python floats (float64) for numerical precision.
        
        Args:
            results: List of worker results containing regret_updates and strategy_updates
        """
        for result in results:
            regret_updates = result['regret_updates']
            strategy_updates = result['strategy_updates']
            
            # Merge regret updates by summing cumulative regrets
            for infoset, actions_dict in regret_updates.items():
                if infoset not in self.regret_tracker.regrets:
                    self.regret_tracker.regrets[infoset] = {}
                
                for action, regret in actions_dict.items():
                    if action not in self.regret_tracker.regrets[infoset]:
                        self.regret_tracker.regrets[infoset][action] = 0.0
                    # Sum cumulative regrets (not averages) - each worker ran independent iterations
                    # Python float is float64 by default, ensuring numerical precision
                    self.regret_tracker.regrets[infoset][action] += float(regret)
            
            # Merge strategy updates by summing cumulative strategy sums
            for infoset, actions_dict in strategy_updates.items():
                if infoset not in self.regret_tracker.strategy_sum:
                    self.regret_tracker.strategy_sum[infoset] = {}
                
                for action, weight in actions_dict.items():
                    if action not in self.regret_tracker.strategy_sum[infoset]:
                        self.regret_tracker.strategy_sum[infoset][action] = 0.0
                    # Sum cumulative strategy weights (not averages)
                    # Python float is float64 by default, ensuring numerical precision
                    self.regret_tracker.strategy_sum[infoset][action] += float(weight)
    
    def train(self, logdir: Path = None, use_tensorboard: bool = True):
        """Run parallel MCCFR training.
        
        Args:
            logdir: Directory for logs and checkpoints
            use_tensorboard: Enable TensorBoard logging (requires tensorboard package)
        """
        # Force 'spawn' start method for cross-platform compatibility (Mac/Linux)
        # This ensures consistent behavior across platforms
        try:
            mp.set_start_method('spawn', force=True)
            logger.info("Set multiprocessing start method to 'spawn' for cross-platform compatibility")
        except RuntimeError:
            # Already set, which is fine
            logger.info(f"Multiprocessing start method already set to '{mp.get_start_method()}'")
        
        # Import solver for non-parallel metrics and save methods
        from holdem.mccfr.solver import MCCFRSolver
        
        # Determine training mode
        use_time_budget = self.config.time_budget_seconds is not None
        
        if use_time_budget:
            logger.info(f"Starting parallel MCCFR training with time budget: {self.config.time_budget_seconds:.0f} seconds "
                       f"({self.config.time_budget_seconds / 86400:.2f} days)")
        else:
            logger.info(f"Starting parallel MCCFR training for {self.config.num_iterations} iterations")
        
        logger.info(f"Using {self.num_workers} worker process(es)")
        logger.info(f"Batch size: {self.config.batch_size} iterations (merge period between workers)")
        
        # Initialize TensorBoard writer if requested and available
        if logdir and use_tensorboard and TENSORBOARD_AVAILABLE:
            tensorboard_dir = logdir / "tensorboard"
            tensorboard_dir.mkdir(parents=True, exist_ok=True)
            self.writer = SummaryWriter(log_dir=str(tensorboard_dir))
            logger.info(f"TensorBoard logging enabled. Run: tensorboard --logdir {tensorboard_dir}")
        elif use_tensorboard and not TENSORBOARD_AVAILABLE:
            logger.warning("TensorBoard requested but not available. Install with: pip install tensorboard")
        
        # Initialize timers and tracking
        start_time = time.time()
        last_snapshot_time = start_time
        last_checkpoint_time = start_time
        last_log_time = start_time
        timer = Timer()
        timer.start()
        
        # Track metrics for moving averages
        utility_history = []
        
        # Main training loop
        while True:
            current_time = time.time()
            
            # Check if time budget exceeded (if using time budget)
            if use_time_budget:
                elapsed_total = current_time - start_time
                if elapsed_total >= self.config.time_budget_seconds:
                    logger.info(f"Time budget reached: {elapsed_total:.1f}s")
                    break
            # Check if iteration limit reached (if using iteration count)
            elif self.iteration >= self.config.num_iterations:
                break
            
            # Run batch of iterations in parallel
            batch_size = self.config.batch_size
            iterations_per_worker = batch_size // self.num_workers
            
            # Create result queue
            result_queue = mp.Queue()
            
            # Start workers
            workers = []
            for worker_id in range(self.num_workers):
                worker_start_iter = self.iteration + worker_id * iterations_per_worker
                
                p = mp.Process(
                    target=worker_process,
                    args=(
                        worker_id,
                        self.bucketing,
                        self.num_players,
                        self._current_epsilon,
                        self.config.use_linear_weighting,
                        self.config.enable_pruning,
                        self.config.pruning_threshold,
                        self.config.pruning_probability,
                        worker_start_iter,
                        iterations_per_worker,
                        result_queue
                    )
                )
                p.start()
                workers.append(p)
            
            # Wait for all workers to complete
            for p in workers:
                p.join()
            
            # Collect results from all workers
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())
            
            # Merge worker results
            self._merge_worker_results(results)
            
            # Update iteration count
            self.iteration += batch_size
            
            # Collect utilities for logging
            for result in results:
                utility_history.extend(result['utilities'])
            
            # Update epsilon based on schedule (if configured)
            self._update_epsilon_schedule()
            
            # Linear MCCFR discount at regular intervals
            if (self.iteration % self.config.discount_interval == 0 and 
                (self.config.regret_discount_alpha < 1.0 or self.config.strategy_discount_beta < 1.0)):
                self.regret_tracker.discount(
                    regret_factor=self.config.regret_discount_alpha,
                    strategy_factor=self.config.strategy_discount_beta
                )
            
            # Snapshot saving (time-based)
            if logdir and use_time_budget:
                time_since_snapshot = current_time - last_snapshot_time
                if time_since_snapshot >= self.config.snapshot_interval_seconds:
                    # Use MCCFRSolver methods for saving
                    self._save_snapshot(logdir, self.iteration, current_time - start_time)
                    last_snapshot_time = current_time
            
            # TensorBoard logging
            if self.writer and self.iteration % self.config.tensorboard_log_interval == 0:
                if utility_history:
                    recent_utility = sum(utility_history[-100:]) / min(100, len(utility_history))
                    self.writer.add_scalar('Training/Utility', recent_utility, self.iteration)
                    
                    # Log moving average over last 1000 iterations
                    if len(utility_history) >= 1000:
                        avg_utility = sum(utility_history[-1000:]) / 1000
                        self.writer.add_scalar('Training/UtilityMovingAvg', avg_utility, self.iteration)
                
                # Log exploration epsilon
                self.writer.add_scalar('Training/Epsilon', self._current_epsilon, self.iteration)
                
                # Log number of infosets
                self.writer.add_scalar('Training/NumInfosets', len(self.regret_tracker.regrets), self.iteration)
            
            # Console logging
            time_since_log = current_time - last_log_time
            should_log = (self.iteration % 10000 == 0) or (use_time_budget and time_since_log >= 60)
            
            if should_log:
                elapsed = timer.stop()
                timer.start()
                
                iter_count = batch_size
                iter_per_sec = iter_count / elapsed if elapsed > 0 else 0
                
                recent_utility = sum(utility_history[-100:]) / min(100, len(utility_history)) if utility_history else 0.0
                
                if use_time_budget:
                    elapsed_total = current_time - start_time
                    remaining = self.config.time_budget_seconds - elapsed_total
                    logger.info(
                        f"Iteration {self.iteration} ({iter_per_sec:.1f} iter/s) - "
                        f"Utility: {recent_utility:.6f} - "
                        f"Elapsed: {elapsed_total:.1f}s, Remaining: {remaining:.1f}s - "
                        f"Workers: {self.num_workers}"
                    )
                else:
                    logger.info(
                        f"Iteration {self.iteration}/{self.config.num_iterations} "
                        f"({iter_per_sec:.1f} iter/s) - "
                        f"Utility: {recent_utility:.6f} - "
                        f"Workers: {self.num_workers}"
                    )
                
                last_log_time = current_time
                
                # Log performance metrics to TensorBoard
                if self.writer:
                    self.writer.add_scalar('Performance/IterationsPerSecond', iter_per_sec, self.iteration)
            
            # Checkpointing (iteration-based or time-based)
            if logdir:
                should_checkpoint = False
                if use_time_budget:
                    time_since_checkpoint = current_time - last_checkpoint_time
                    # Checkpoint every hour in time-budget mode
                    should_checkpoint = time_since_checkpoint >= 3600
                else:
                    should_checkpoint = self.iteration % self.config.checkpoint_interval == 0
                
                if should_checkpoint:
                    self._save_checkpoint(logdir, self.iteration, current_time - start_time)
                    last_checkpoint_time = current_time
        
        logger.info("Training complete")
        
        # Close TensorBoard writer
        if self.writer:
            self.writer.close()
            logger.info("TensorBoard logs saved")
        
        # Save final policy
        if logdir:
            self.save_policy(logdir)
    
    def _update_epsilon_schedule(self):
        """Update epsilon based on schedule if configured."""
        if self.config.epsilon_schedule is None:
            return
        
        schedule = self.config.epsilon_schedule
        
        for i in range(len(schedule) - 1, -1, -1):
            if self.iteration >= schedule[i][0]:
                new_epsilon = schedule[i][1]
                if new_epsilon != self._current_epsilon:
                    self._current_epsilon = new_epsilon
                    logger.info(f"Epsilon updated to {new_epsilon:.3f} at iteration {self.iteration}")
                break
    
    def _save_snapshot(self, logdir: Path, iteration: int, elapsed_seconds: float):
        """Save training snapshot."""
        from holdem.utils.serialization import save_json
        
        snapshot_dir = logdir / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        snapshot_name = f"snapshot_iter{iteration}_t{int(elapsed_seconds)}s"
        snapshot_path = snapshot_dir / snapshot_name
        snapshot_path.mkdir(exist_ok=True)
        
        # Save overall policy
        policy_store = PolicyStore(self.regret_tracker)
        policy_store.save(snapshot_path / "avg_policy.pkl")
        policy_store.save_json(snapshot_path / "avg_policy.json")
        
        # Save metadata
        metadata = {
            'iteration': iteration,
            'elapsed_seconds': elapsed_seconds,
            'num_workers': self.num_workers,
            'batch_size': self.config.batch_size
        }
        save_json(metadata, snapshot_path / "metadata.json")
        
        logger.info(f"Saved snapshot at iteration {iteration} (elapsed: {elapsed_seconds:.1f}s)")
    
    def _save_checkpoint(self, logdir: Path, iteration: int, elapsed_seconds: float):
        """Save training checkpoint with complete metadata.
        
        Args:
            logdir: Directory for checkpoints
            iteration: Current iteration number
            elapsed_seconds: Time elapsed since training start
        """
        from holdem.utils.serialization import save_json
        
        checkpoint_dir = logdir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        policy_store = PolicyStore(self.regret_tracker)
        checkpoint_name = f"checkpoint_iter{iteration}"
        if elapsed_seconds > 0:
            checkpoint_name += f"_t{int(elapsed_seconds)}s"
        policy_store.save(checkpoint_dir / f"{checkpoint_name}.pkl")
        
        # Save complete metadata including epsilon, discount params, and bucket info
        metadata = {
            'iteration': iteration,
            'elapsed_seconds': elapsed_seconds,
            'num_workers': self.num_workers,
            'batch_size': self.config.batch_size,
            'epsilon': self._current_epsilon,
            'regret_discount_alpha': self.config.regret_discount_alpha,
            'strategy_discount_beta': self.config.strategy_discount_beta,
            'bucket_metadata': {
                'k_preflop': self.bucketing.config.k_preflop,
                'k_flop': self.bucketing.config.k_flop,
                'k_turn': self.bucketing.config.k_turn,
                'k_river': self.bucketing.config.k_river,
                'num_samples': self.bucketing.config.num_samples,
                'seed': self.bucketing.config.seed
            }
        }
        save_json(metadata, checkpoint_dir / f"{checkpoint_name}_metadata.json")
        
        logger.info(f"Saved checkpoint at iteration {iteration} with complete metadata")
    
    def save_policy(self, logdir: Path):
        """Save final average policy."""
        logdir.mkdir(parents=True, exist_ok=True)
        
        policy_store = PolicyStore(self.regret_tracker)
        policy_store.save(logdir / "avg_policy.pkl")
        policy_store.save_json(logdir / "avg_policy.json")
        
        logger.info(f"Saved final policy to {logdir}")
    
    def get_policy(self) -> PolicyStore:
        """Get current policy store."""
        return PolicyStore(self.regret_tracker)
    
    def load_checkpoint(self, checkpoint_path: Path, validate_buckets: bool = True) -> int:
        """Load checkpoint and restore training state.
        
        For parallel solver, this loads the checkpoint created by either single-process
        or parallel training and restores the regret tracker state.
        
        Args:
            checkpoint_path: Path to checkpoint .pkl file
            validate_buckets: If True, validate bucket configuration matches
            
        Returns:
            Iteration number from checkpoint (0 if metadata not found)
            
        Raises:
            ValueError: If bucket validation fails or checkpoint incompatible
        """
        from holdem.utils.serialization import load_json, load_pickle
        
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_path}")
        
        # Load metadata
        metadata_path = checkpoint_path.parent / f"{checkpoint_path.stem}_metadata.json"
        if not metadata_path.exists():
            logger.warning(f"Metadata file not found: {metadata_path}")
            logger.warning("Cannot restore training state without metadata")
            return 0
        
        metadata = load_json(metadata_path)
        
        # Validate bucket configuration
        if validate_buckets and 'bucket_metadata' in metadata:
            bucket_meta = metadata['bucket_metadata']
            
            # Compare bucket parameters
            if (bucket_meta.get('k_preflop') != self.bucketing.config.k_preflop or
                bucket_meta.get('k_flop') != self.bucketing.config.k_flop or
                bucket_meta.get('k_turn') != self.bucketing.config.k_turn or
                bucket_meta.get('k_river') != self.bucketing.config.k_river):
                raise ValueError(
                    f"Bucket configuration mismatch!\n"
                    f"Checkpoint: preflop={bucket_meta.get('k_preflop')}, "
                    f"flop={bucket_meta.get('k_flop')}, "
                    f"turn={bucket_meta.get('k_turn')}, "
                    f"river={bucket_meta.get('k_river')}\n"
                    f"Current: preflop={self.bucketing.config.k_preflop}, "
                    f"flop={self.bucketing.config.k_flop}, "
                    f"turn={self.bucketing.config.k_turn}, "
                    f"river={self.bucketing.config.k_river}\n"
                    f"Cannot safely resume training with different bucket configuration."
                )
            
            logger.info("Bucket configuration validated successfully")
        
        # Restore epsilon if available
        if 'epsilon' in metadata:
            self._current_epsilon = metadata['epsilon']
            logger.info(f"Restored epsilon: {self._current_epsilon:.3f}")
        
        # Load regret tracker state from checkpoint
        # Note: PolicyStore contains the regret tracker data
        policy_data = load_pickle(checkpoint_path)
        
        # The checkpoint contains a dictionary with 'regrets' and 'strategy_sum'
        if isinstance(policy_data, dict):
            if 'regrets' in policy_data:
                self.regret_tracker.regrets = policy_data['regrets']
                logger.info(f"Loaded {len(self.regret_tracker.regrets)} infosets (regrets)")
            
            if 'strategy_sum' in policy_data:
                self.regret_tracker.strategy_sum = policy_data['strategy_sum']
                logger.info(f"Loaded {len(self.regret_tracker.strategy_sum)} infosets (strategy_sum)")
        
        # Get iteration number
        iteration = metadata.get('iteration', 0)
        self.iteration = iteration
        
        logger.info(f"Successfully loaded checkpoint from iteration {iteration}")
        logger.info("Parallel training will continue from this state")
        
        return iteration
