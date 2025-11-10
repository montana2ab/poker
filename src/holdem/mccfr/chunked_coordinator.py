"""Chunked training coordinator for memory-constrained environments.

This module implements a chunked training mode that splits long training runs into
segments (chunks). At the end of each chunk, the solver:
1. Saves a complete checkpoint (with all metadata including RNG state)
2. Flushes TensorBoard/logs
3. Terminates the process (releases 100% of RAM)
4. The coordinator automatically restarts from the last checkpoint

No loss of continuity: t_global, RNG state, ε/discount/DCFR parameters, and 
bucket_hash are all restored between chunks.
"""

import time
import sys
from pathlib import Path
from typing import Optional
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.utils.logging import get_logger

logger = get_logger("mccfr.chunked_coordinator")


class ChunkedTrainingCoordinator:
    """Coordinator for chunked training mode.
    
    Manages the lifecycle of training chunks, automatically restarting the
    solver process after each chunk to free memory completely.
    """
    
    def __init__(
        self,
        config: MCCFRConfig,
        bucketing: HandBucketing,
        logdir: Path,
        num_players: int = 2,
        use_tensorboard: bool = True
    ):
        """Initialize the chunked training coordinator.
        
        Args:
            config: MCCFR configuration (must have enable_chunked_training=True)
            bucketing: Hand bucketing abstraction
            logdir: Directory for logs and checkpoints
            num_players: Number of players (default: 2)
            use_tensorboard: Enable TensorBoard logging
        """
        if not config.enable_chunked_training:
            raise ValueError("Chunked training not enabled in config. Set enable_chunked_training=True")
        
        if config.chunk_size_iterations is None and config.chunk_size_minutes is None:
            raise ValueError("Must specify either chunk_size_iterations or chunk_size_minutes")
        
        self.config = config
        self.bucketing = bucketing
        self.logdir = logdir
        self.num_players = num_players
        self.use_tensorboard = use_tensorboard
        
        # Ensure logdir exists
        self.logdir.mkdir(parents=True, exist_ok=True)
        
        logger.info("=" * 80)
        logger.info("Chunked Training Mode Initialized")
        logger.info("=" * 80)
        if config.chunk_size_iterations:
            logger.info(f"Chunk size: {config.chunk_size_iterations:,} iterations")
        if config.chunk_size_minutes:
            logger.info(f"Chunk duration: {config.chunk_size_minutes:.1f} minutes")
        logger.info(f"Logdir: {logdir}")
        logger.info("=" * 80)
    
    def run(self) -> None:
        """Run training in chunked mode.
        
        This method orchestrates the chunked training process:
        1. Find the latest checkpoint (if any)
        2. Create a solver and load the checkpoint
        3. Run one chunk of training
        4. Save checkpoint and flush logs
        5. Exit (coordinator will be called again to start next chunk)
        """
        # Find latest checkpoint to resume from
        latest_checkpoint = self._find_latest_checkpoint()
        
        if latest_checkpoint:
            logger.info(f"Resuming from checkpoint: {latest_checkpoint}")
        else:
            logger.info("Starting fresh training (no checkpoint found)")
        
        # Create solver
        solver = MCCFRSolver(
            config=self.config,
            bucketing=self.bucketing,
            num_players=self.num_players
        )
        
        # Load checkpoint if available
        start_iteration = 0
        if latest_checkpoint:
            try:
                start_iteration = solver.load_checkpoint(
                    latest_checkpoint,
                    validate_buckets=True,
                    warm_start=True
                )
                logger.info(f"Successfully resumed from iteration {start_iteration}")
            except Exception as e:
                logger.error(f"Failed to load checkpoint: {e}")
                logger.warning("Starting fresh training")
                start_iteration = 0
        
        # Calculate chunk boundaries
        chunk_start_iter = start_iteration
        chunk_end_iter = None
        chunk_end_time = None
        
        if self.config.chunk_size_iterations:
            # Calculate next chunk boundary based on iterations
            chunk_end_iter = chunk_start_iter + self.config.chunk_size_iterations
            logger.info(f"Chunk: iterations {chunk_start_iter} -> {chunk_end_iter}")
            
            # If using time budget, also respect that
            if self.config.time_budget_seconds:
                # Check if we'd exceed time budget
                # We'll let the solver's normal time budget check handle this
                pass
        
        if self.config.chunk_size_minutes:
            chunk_end_time = time.time() + (self.config.chunk_size_minutes * 60)
            logger.info(f"Chunk duration: {self.config.chunk_size_minutes:.1f} minutes")
        
        # Run one chunk of training
        logger.info("Starting chunk training...")
        chunk_start_time = time.time()
        
        try:
            self._run_chunk(
                solver=solver,
                chunk_start_iter=chunk_start_iter,
                chunk_end_iter=chunk_end_iter,
                chunk_end_time=chunk_end_time,
                chunk_start_time=chunk_start_time
            )
        except KeyboardInterrupt:
            logger.info("Training interrupted by user")
            # Still save checkpoint before exiting
            self._save_chunk_checkpoint(solver, chunk_start_time)
            raise
        except Exception as e:
            logger.error(f"Error during chunk training: {e}")
            # Save checkpoint on error
            self._save_chunk_checkpoint(solver, chunk_start_time)
            raise
        
        # Save final checkpoint for this chunk
        self._save_chunk_checkpoint(solver, chunk_start_time)
        
        # Flush TensorBoard if enabled
        if solver.writer:
            logger.info("Flushing TensorBoard logs...")
            solver.writer.flush()
            solver.writer.close()
        
        # Check if training is complete
        training_complete = self._is_training_complete(solver)
        
        if training_complete:
            logger.info("=" * 80)
            logger.info("Training Complete!")
            logger.info(f"Final iteration: {solver.iteration}")
            logger.info("=" * 80)
        else:
            logger.info("=" * 80)
            logger.info("Chunk Complete - Process will now exit to free memory")
            logger.info(f"Progress: iteration {solver.iteration}")
            logger.info("Restart this command to continue training from checkpoint")
            logger.info("=" * 80)
    
    def _run_chunk(
        self,
        solver: MCCFRSolver,
        chunk_start_iter: int,
        chunk_end_iter: Optional[int],
        chunk_end_time: Optional[float],
        chunk_start_time: float
    ) -> None:
        """Run one chunk of training.
        
        This is a modified version of the solver's train() method that exits
        when the chunk limit is reached.
        
        Args:
            solver: The MCCFR solver instance
            chunk_start_iter: Starting iteration for this chunk
            chunk_end_iter: Ending iteration for this chunk (if using iteration-based chunks)
            chunk_end_time: End time for this chunk (if using time-based chunks)
            chunk_start_time: Start time of this chunk (for elapsed time calculation)
        """
        # Initialize TensorBoard writer if requested
        if self.use_tensorboard:
            try:
                from torch.utils.tensorboard import SummaryWriter
                tensorboard_dir = self.logdir / "tensorboard"
                tensorboard_dir.mkdir(parents=True, exist_ok=True)
                solver.writer = SummaryWriter(log_dir=str(tensorboard_dir))
                logger.info(f"TensorBoard logging enabled. Run: tensorboard --logdir {tensorboard_dir}")
            except ImportError:
                logger.warning("TensorBoard not available. Install with: pip install tensorboard")
        
        # Determine training mode from config
        use_time_budget = self.config.time_budget_seconds is not None
        
        # Main training loop adapted from MCCFRSolver.train()
        last_checkpoint_time = chunk_start_time
        last_log_time = chunk_start_time
        last_log_iteration = solver.iteration
        
        from holdem.utils.timers import Timer
        timer = Timer()
        timer.start()
        
        # Track metrics
        utility_history = []
        
        logger.info(f"Starting training loop from iteration {solver.iteration}")
        
        while True:
            solver.iteration += 1
            current_time = time.time()
            
            # Check chunk boundaries
            if chunk_end_iter and solver.iteration >= chunk_end_iter:
                logger.info(f"Chunk iteration limit reached: {solver.iteration} >= {chunk_end_iter}")
                break
            
            if chunk_end_time and current_time >= chunk_end_time:
                elapsed_chunk = (current_time - chunk_start_time) / 60
                logger.info(f"Chunk time limit reached: {elapsed_chunk:.1f} >= {self.config.chunk_size_minutes:.1f} minutes")
                break
            
            # Check global time budget (if configured)
            if use_time_budget:
                # Calculate total elapsed time across all chunks
                chunk_elapsed = current_time - chunk_start_time
                total_elapsed = solver._cumulative_elapsed_seconds + chunk_elapsed
                if total_elapsed >= self.config.time_budget_seconds:
                    logger.info(f"Global time budget reached: {total_elapsed:.1f}s >= {self.config.time_budget_seconds:.1f}s")
                    break
            # Check iteration limit (if not using time budget)
            elif not use_time_budget and solver.iteration > self.config.num_iterations:
                logger.info(f"Global iteration limit reached: {solver.iteration} > {self.config.num_iterations}")
                break
            
            # Run one iteration
            utility = solver.sampler.sample_iteration(solver.iteration)
            utility_history.append(utility)
            
            # Update epsilon based on schedule (if configured)
            solver._update_epsilon_schedule()
            
            # Linear MCCFR discount at regular intervals
            if solver.iteration % self.config.discount_interval == 0:
                if self.config.discount_mode == "dcfr":
                    # DCFR/CFR+ adaptive discounting
                    t = float(solver.iteration)
                    d = float(self.config.discount_interval)
                    alpha = (t + d) / (t + 2 * d)
                    beta = t / (t + d) if t > 0 else 0.0
                    
                    solver.sampler.regret_tracker.discount(
                        regret_factor=alpha,
                        strategy_factor=beta
                    )
                    
                    if self.config.dcfr_reset_negative_regrets:
                        solver.sampler.regret_tracker.reset_regrets()
                    
                    logger.debug(f"DCFR discount at iteration {solver.iteration}: α={alpha:.4f}, β={beta:.4f}")
                    
                elif self.config.discount_mode == "static":
                    if (self.config.regret_discount_alpha < 1.0 or 
                        self.config.strategy_discount_beta < 1.0):
                        solver.sampler.regret_tracker.discount(
                            regret_factor=self.config.regret_discount_alpha,
                            strategy_factor=self.config.strategy_discount_beta
                        )
            
            # Regular checkpoint saving (if configured)
            if self.config.checkpoint_interval and solver.iteration % self.config.checkpoint_interval == 0:
                elapsed_seconds = current_time - chunk_start_time
                solver.save_checkpoint(self.logdir, solver.iteration, elapsed_seconds)
                last_checkpoint_time = current_time
            
            # TensorBoard logging
            if solver.writer and solver.iteration % self.config.tensorboard_log_interval == 0:
                solver.writer.add_scalar('Training/Utility', utility, solver.iteration)
                
                if len(utility_history) >= 1000:
                    avg_utility = sum(utility_history[-1000:]) / 1000
                    solver.writer.add_scalar('Training/UtilityMovingAvg', avg_utility, solver.iteration)
                
                solver.writer.add_scalar('Training/Epsilon', solver._current_epsilon, solver.iteration)
                
                # Log policy entropy per street
                entropy_metrics = solver._calculate_policy_entropy_metrics()
                for metric_name, value in entropy_metrics.items():
                    solver.writer.add_scalar(metric_name, value, solver.iteration)
                
                # Log normalized regret per street
                regret_metrics = solver._calculate_regret_norm_metrics()
                for metric_name, value in regret_metrics.items():
                    solver.writer.add_scalar(metric_name, value, solver.iteration)
            
            # Console logging
            time_since_log = current_time - last_log_time
            should_log = (solver.iteration % 10000 == 0) or (use_time_budget and time_since_log >= 60)
            
            if should_log:
                elapsed = timer.stop()
                timer.start()
                
                iter_count = solver.iteration - last_log_iteration
                if iter_count <= 0:
                    iter_count = 1
                
                iter_per_sec = iter_count / elapsed if elapsed > 0 else 0
                
                if len(utility_history) > 0:
                    recent_utility = sum(utility_history[-min(1000, len(utility_history)):]) / min(1000, len(utility_history))
                    logger.info(f"Iter {solver.iteration:,} | {iter_per_sec:.1f} it/s | "
                              f"Avg Utility: {recent_utility:.3f} | "
                              f"ε: {solver._current_epsilon:.3f}")
                
                last_log_time = current_time
                last_log_iteration = solver.iteration
        
        logger.info(f"Chunk training complete at iteration {solver.iteration}")
    
    def _save_chunk_checkpoint(self, solver: MCCFRSolver, chunk_start_time: float) -> None:
        """Save a checkpoint at the end of a chunk.
        
        Args:
            solver: The MCCFR solver instance
            chunk_start_time: Start time of the chunk (for elapsed time)
        """
        elapsed_seconds = time.time() - chunk_start_time
        logger.info(f"Saving checkpoint at iteration {solver.iteration}...")
        solver.save_checkpoint(self.logdir, solver.iteration, elapsed_seconds)
        logger.info("Checkpoint saved successfully")
    
    def _find_latest_checkpoint(self) -> Optional[Path]:
        """Find the most recent complete checkpoint in the logdir.
        
        Returns:
            Path to the latest checkpoint .pkl file, or None if no checkpoint found
        """
        checkpoint_dir = self.logdir / "checkpoints"
        if not checkpoint_dir.exists():
            return None
        
        # Find all checkpoint files
        checkpoint_files = list(checkpoint_dir.glob("checkpoint_*.pkl"))
        
        if not checkpoint_files:
            return None
        
        # Filter to only complete checkpoints
        complete_checkpoints = [
            ckpt for ckpt in checkpoint_files
            if MCCFRSolver.is_checkpoint_complete(ckpt)
        ]
        
        if not complete_checkpoints:
            logger.warning("Found checkpoint files but none are complete")
            return None
        
        # Sort by modification time and return the latest
        complete_checkpoints.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return complete_checkpoints[0]
    
    def _is_training_complete(self, solver: MCCFRSolver) -> bool:
        """Check if training has reached its completion criteria.
        
        Args:
            solver: The MCCFR solver instance
            
        Returns:
            True if training is complete, False otherwise
        """
        # Check iteration-based completion
        if self.config.time_budget_seconds is None:
            if solver.iteration >= self.config.num_iterations:
                return True
        else:
            # Check time-budget completion using cumulative elapsed time
            if solver._cumulative_elapsed_seconds >= self.config.time_budget_seconds:
                return True
        
        return False
