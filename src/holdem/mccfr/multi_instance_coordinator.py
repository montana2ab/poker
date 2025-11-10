"""Multi-instance coordinator for parallel solver execution.

This module enables launching multiple independent solver instances in parallel,
each running with a single worker. The coordinator manages:
- Work distribution (iteration ranges) to avoid overlap
- Separate output directories per instance
- Progress monitoring across all instances
- Result aggregation from multiple instances
"""

import multiprocessing as mp
import signal
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import json

from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.solver import MCCFRSolver
from holdem.utils.logging import get_logger, setup_logger

logger = get_logger("mccfr.multi_instance")


class InstanceProgress:
    """Track progress of a single solver instance."""
    
    def __init__(self, instance_id: int, start_iter: int, end_iter: int):
        self.instance_id = instance_id
        self.start_iter = start_iter
        self.end_iter = end_iter
        self.current_iter = start_iter
        self.status = "starting"  # starting, running, completed, failed
        self.error_msg = None
        self.last_update = time.time()
    
    def update(self, current_iter: int, status: str = "running"):
        """Update progress."""
        self.current_iter = current_iter
        self.status = status
        self.last_update = time.time()
    
    def progress_pct(self) -> float:
        """Calculate progress percentage."""
        if self.end_iter <= self.start_iter:
            return 0.0
        return 100.0 * (self.current_iter - self.start_iter) / (self.end_iter - self.start_iter)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'instance_id': self.instance_id,
            'start_iter': self.start_iter,
            'end_iter': self.end_iter,
            'current_iter': self.current_iter,
            'status': self.status,
            'error_msg': self.error_msg,
            'progress_pct': self.progress_pct(),
            'last_update': self.last_update
        }


def _run_solver_instance(
    instance_id: int,
    config: MCCFRConfig,
    bucketing: HandBucketing,
    num_players: int,
    logdir: Path,
    use_tensorboard: bool,
    progress_file: Path,
    use_time_budget: bool,
    start_iter: int = 0,
    end_iter: int = None,
    resume_checkpoint: Path = None
):
    """Run a single solver instance in a separate process.
    
    This function runs in its own process and trains the solver either for
    a specific time budget or a specific range of iterations.
    
    Args:
        instance_id: Unique ID for this instance
        config: MCCFR configuration
        bucketing: Hand bucketing
        num_players: Number of players
        logdir: Directory for this instance's logs
        use_tensorboard: Enable TensorBoard
        progress_file: File to write progress updates
        use_time_budget: Whether to use time-budget mode (True) or iteration mode (False)
        start_iter: Starting iteration (inclusive) - only used in iteration mode
        end_iter: Ending iteration (exclusive) - only used in iteration mode
        resume_checkpoint: Path to checkpoint file to resume from (optional)
    """
    # Setup instance-specific logger
    instance_logger = setup_logger(f"instance_{instance_id}", log_file=logdir / f"instance_{instance_id}.log")
    
    try:
        if use_time_budget:
            instance_logger.info(f"Instance {instance_id} starting: time budget {config.time_budget_seconds:.0f}s")
            
            # Create config for time-budget mode
            instance_config = MCCFRConfig(
                time_budget_seconds=config.time_budget_seconds,
                snapshot_interval_seconds=config.snapshot_interval_seconds,
                discount_interval=config.discount_interval,
                regret_discount_alpha=config.regret_discount_alpha,
                strategy_discount_beta=config.strategy_discount_beta,
                exploration_epsilon=config.exploration_epsilon,
                enable_pruning=config.enable_pruning,
                pruning_threshold=config.pruning_threshold,
                pruning_probability=config.pruning_probability,
                use_linear_weighting=config.use_linear_weighting,
                num_workers=1,  # Force single worker per instance
                batch_size=config.batch_size,
                num_iterations=None,  # No iteration limit in time-budget mode
                checkpoint_interval=None,
                epsilon_schedule=config.epsilon_schedule,
                adaptive_epsilon_enabled=config.adaptive_epsilon_enabled,
                adaptive_target_ips=config.adaptive_target_ips
            )
            
            # Create initial progress tracking (time-based)
            progress = InstanceProgress(instance_id, 0, -1)  # -1 indicates time-based mode
            progress.update(0, "running")
            _write_progress(progress_file, progress)
            
        else:
            # Iteration-based mode
            instance_logger.info(f"Instance {instance_id} starting: iterations {start_iter} to {end_iter-1}")
            
            # Create a modified config for this instance's iteration range
            instance_config = MCCFRConfig(
                num_iterations=end_iter - start_iter,
                checkpoint_interval=config.checkpoint_interval,
                discount_interval=config.discount_interval,
                regret_discount_alpha=config.regret_discount_alpha,
                strategy_discount_beta=config.strategy_discount_beta,
                exploration_epsilon=config.exploration_epsilon,
                enable_pruning=config.enable_pruning,
                pruning_threshold=config.pruning_threshold,
                pruning_probability=config.pruning_probability,
                use_linear_weighting=config.use_linear_weighting,
                num_workers=1,  # Force single worker per instance
                batch_size=config.batch_size,
                time_budget_seconds=None,  # Use iteration-based for instances
                snapshot_interval_seconds=None,
                epsilon_schedule=config.epsilon_schedule,
                adaptive_epsilon_enabled=config.adaptive_epsilon_enabled,
                adaptive_target_ips=config.adaptive_target_ips
            )
            
            # Create initial progress tracking (iteration-based)
            progress = InstanceProgress(instance_id, start_iter, end_iter)
            progress.update(start_iter, "running")
            _write_progress(progress_file, progress)
        
        # Create solver
        solver = MCCFRSolver(
            config=instance_config,
            bucketing=bucketing,
            num_players=num_players
        )
        
        # Create instance-specific logdir
        instance_logdir = logdir / f"instance_{instance_id}"
        instance_logdir.mkdir(parents=True, exist_ok=True)
        
        # Resume from checkpoint if provided
        resumed_iteration = 0
        if resume_checkpoint and resume_checkpoint.exists():
            instance_logger.info(f"Resuming instance {instance_id} from checkpoint: {resume_checkpoint}")
            try:
                resumed_iteration = solver.load_checkpoint(resume_checkpoint, validate_buckets=True)
                instance_logger.info(f"Successfully loaded checkpoint at iteration {resumed_iteration}")
                
                # Update start iteration if resuming in iteration mode
                if not use_time_budget:
                    start_iter = resumed_iteration
                    progress.start_iter = start_iter
                    progress.update(start_iter, "running")
                    _write_progress(progress_file, progress)
                    instance_logger.info(f"Resuming from iteration {start_iter} to {end_iter-1}")
            except Exception as e:
                instance_logger.error(f"Failed to load checkpoint: {e}")
                instance_logger.warning("Starting from scratch instead")
                resumed_iteration = 0
        
        # Override iteration counter to reflect actual iteration numbers (iteration mode only)
        if not use_time_budget:
            solver.iteration = start_iter
        
        # Hook into solver's iteration loop to report progress
        original_train = solver.train
        
        def train_with_progress(*args, **kwargs):
            """Wrapper to report progress during training."""
            # Patch the sampler to report progress
            original_sample = solver.sampler.sample_iteration
            
            if use_time_budget:
                # Time-budget mode: report progress based on time elapsed
                import time
                start_training_time = time.time()
                
                def sample_with_progress_time(iteration):
                    result = original_sample(iteration)
                    # Update progress every 100 iterations
                    if iteration % 100 == 0:
                        elapsed = time.time() - start_training_time
                        progress.current_iter = iteration
                        progress.update(iteration, "running")
                        # Add elapsed time info for time-budget mode
                        progress_data = progress.to_dict()
                        progress_data['elapsed_seconds'] = elapsed
                        progress_data['time_budget_seconds'] = config.time_budget_seconds
                        progress_data['time_progress_pct'] = 100.0 * elapsed / config.time_budget_seconds if config.time_budget_seconds else 0
                        _write_progress_dict(progress_file, progress_data)
                    return result
                
                solver.sampler.sample_iteration = sample_with_progress_time
            else:
                # Iteration-based mode: report progress based on iterations
                def sample_with_progress_iter(iteration):
                    result = original_sample(iteration)
                    # Update progress every 100 iterations
                    if iteration % 100 == 0:
                        progress.update(iteration, "running")
                        _write_progress(progress_file, progress)
                    return result
                
                solver.sampler.sample_iteration = sample_with_progress_iter
            
            # Run training
            return original_train(*args, **kwargs)
        
        solver.train = train_with_progress
        
        # Train
        instance_logger.info(f"Starting training for instance {instance_id}")
        solver.train(logdir=instance_logdir, use_tensorboard=use_tensorboard)
        
        # Mark as completed
        if use_time_budget:
            # For time-budget mode, mark with final iteration count
            progress.update(solver.iteration, "completed")
            progress_data = progress.to_dict()
            progress_data['final_iteration'] = solver.iteration
            _write_progress_dict(progress_file, progress_data)
        else:
            progress.update(end_iter - 1, "completed")
            _write_progress(progress_file, progress)
        
        instance_logger.info(f"Instance {instance_id} completed successfully")
        
    except KeyboardInterrupt:
        instance_logger.info(f"Instance {instance_id} interrupted by user")
        progress = InstanceProgress(instance_id, start_iter if not use_time_budget else 0, end_iter if not use_time_budget else -1)
        progress.status = "interrupted"
        _write_progress(progress_file, progress)
        
    except Exception as e:
        import traceback
        error_msg = f"Instance {instance_id} failed: {str(e)}\n{traceback.format_exc()}"
        instance_logger.error(error_msg)
        
        progress = InstanceProgress(instance_id, start_iter if not use_time_budget else 0, end_iter if not use_time_budget else -1)
        progress.status = "failed"
        progress.error_msg = str(e)
        _write_progress(progress_file, progress)
        
        raise


def _write_progress(progress_file: Path, progress: InstanceProgress):
    """Write progress to a file (atomic operation)."""
    temp_file = progress_file.with_suffix('.tmp')
    with open(temp_file, 'w') as f:
        json.dump(progress.to_dict(), f, indent=2)
    temp_file.replace(progress_file)


def _write_progress_dict(progress_file: Path, progress_dict: Dict):
    """Write progress dictionary to a file (atomic operation)."""
    temp_file = progress_file.with_suffix('.tmp')
    with open(temp_file, 'w') as f:
        json.dump(progress_dict, f, indent=2)
    temp_file.replace(progress_file)


class MultiInstanceCoordinator:
    """Coordinates multiple independent solver instances running in parallel."""
    
    def __init__(
        self,
        num_instances: int,
        config: MCCFRConfig,
        bucketing: HandBucketing,
        num_players: int = 2
    ):
        """Initialize multi-instance coordinator.
        
        Args:
            num_instances: Number of parallel instances to launch
            config: MCCFR configuration (will be divided among instances)
            bucketing: Hand bucketing
            num_players: Number of players
        """
        if num_instances < 1:
            raise ValueError(f"num_instances must be >= 1, got {num_instances}")
        
        self.num_instances = num_instances
        self.config = config
        self.bucketing = bucketing
        self.num_players = num_players
        
        # Validate configuration: must have either time_budget or num_iterations
        if config.time_budget_seconds is None and config.num_iterations is None:
            raise ValueError(
                "Multi-instance mode requires either --iters or --time-budget to be specified"
            )
        
        # Force single worker per instance
        if config.num_workers != 1:
            logger.warning(
                f"Multi-instance mode requires num_workers=1 per instance. "
                f"Overriding num_workers={config.num_workers} to 1."
            )
            config.num_workers = 1
        
        logger.info(f"Initialized multi-instance coordinator with {num_instances} instances")
        
        # Determine training mode
        self.use_time_budget = config.time_budget_seconds is not None
        
        if self.use_time_budget:
            logger.info(f"Training mode: Time-budget ({config.time_budget_seconds:.0f}s = {config.time_budget_seconds / 86400:.2f} days)")
            logger.info(f"Each instance will run for the full time budget independently")
        else:
            logger.info(f"Training mode: Iteration-based ({config.num_iterations} total iterations)")
            logger.info(f"Iterations will be distributed across instances")
        
        logger.info(f"Each instance will run with 1 worker")
        
        # Calculate iteration ranges for each instance (only for iteration-based mode)
        self.iteration_ranges = self._calculate_iteration_ranges() if not self.use_time_budget else None
        
        # Process management
        self._processes: List[mp.Process] = []
        self._progress_files: List[Path] = []
        self._interrupted = False
    
    def _calculate_iteration_ranges(self) -> List[Tuple[int, int]]:
        """Calculate iteration ranges for each instance.
        
        Returns:
            List of (start_iter, end_iter) tuples for each instance
        """
        total_iters = self.config.num_iterations
        iters_per_instance = total_iters // self.num_instances
        remainder = total_iters % self.num_instances
        
        ranges = []
        current_start = 0
        
        for i in range(self.num_instances):
            # Distribute remainder evenly among first instances
            instance_iters = iters_per_instance + (1 if i < remainder else 0)
            end_iter = current_start + instance_iters
            
            ranges.append((current_start, end_iter))
            
            logger.info(f"Instance {i}: iterations {current_start} to {end_iter-1} ({instance_iters} total)")
            
            current_start = end_iter
        
        return ranges
    
    def _find_resume_checkpoints(self, resume_from: Path) -> List[Optional[Path]]:
        """Find the latest checkpoint for each instance in a previous run.
        
        Args:
            resume_from: Base directory of previous multi-instance run
            
        Returns:
            List of checkpoint paths (or None) for each instance
        """
        checkpoints = []
        for i in range(self.num_instances):
            instance_dir = resume_from / f"instance_{i}"
            checkpoint_dir = instance_dir / "checkpoints"
            
            if not checkpoint_dir.exists():
                logger.warning(f"No checkpoint directory found for instance {i}")
                checkpoints.append(None)
                continue
            
            # Find the latest checkpoint
            checkpoint_files = list(checkpoint_dir.glob("checkpoint_*.pkl"))
            if not checkpoint_files:
                logger.warning(f"No checkpoint files found for instance {i}")
                checkpoints.append(None)
                continue
            
            # Sort by modification time and get the latest
            latest_checkpoint = max(checkpoint_files, key=lambda p: p.stat().st_mtime)
            logger.info(f"Found checkpoint for instance {i}: {latest_checkpoint.name}")
            checkpoints.append(latest_checkpoint)
        
        return checkpoints
    
    def train(self, logdir: Path, use_tensorboard: bool = True, resume_from: Optional[Path] = None):
        """Launch and coordinate multiple solver instances.
        
        Args:
            logdir: Base directory for logs and checkpoints
            use_tensorboard: Enable TensorBoard for each instance
            resume_from: Base directory containing previous multi-instance run to resume from (optional)
        """
        logdir.mkdir(parents=True, exist_ok=True)
        
        # Create progress directory
        progress_dir = logdir / "progress"
        progress_dir.mkdir(exist_ok=True)
        
        # Check for resume capability
        resume_checkpoints = []
        if resume_from:
            logger.info(f"Attempting to resume from previous run in: {resume_from}")
            resume_checkpoints = self._find_resume_checkpoints(resume_from)
            if resume_checkpoints:
                logger.info(f"Found {len(resume_checkpoints)} instance checkpoint(s) to resume from")
            else:
                logger.warning(f"No checkpoints found in {resume_from}, starting fresh")
        
        logger.info(f"Launching {self.num_instances} solver instances...")
        logger.info(f"Logs will be written to: {logdir}")
        logger.info(f"Progress tracking: {progress_dir}")
        
        # Setup signal handler for graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Received interrupt signal, shutting down instances...")
            self._interrupted = True
            self._terminate_all()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Launch instances
        mp_context = mp.get_context('spawn')
        
        if self.use_time_budget:
            # Time-budget mode: all instances run for the same time budget
            for i in range(self.num_instances):
                progress_file = progress_dir / f"instance_{i}_progress.json"
                self._progress_files.append(progress_file)
                
                # Get resume checkpoint if available
                resume_checkpoint = resume_checkpoints[i] if resume_checkpoints and i < len(resume_checkpoints) else None
                
                # Create process
                p = mp_context.Process(
                    target=_run_solver_instance,
                    args=(
                        i,
                        self.config,
                        self.bucketing,
                        self.num_players,
                        logdir,
                        use_tensorboard,
                        progress_file,
                        True,  # use_time_budget
                    ),
                    kwargs={'resume_checkpoint': resume_checkpoint}
                )
                p.start()
                self._processes.append(p)
                
                if resume_checkpoint:
                    logger.info(f"Launched instance {i} (PID: {p.pid}) - resuming from checkpoint")
                else:
                    logger.info(f"Launched instance {i} (PID: {p.pid}) - time budget: {self.config.time_budget_seconds:.0f}s")
        else:
            # Iteration-based mode: distribute iterations among instances
            for i, (start_iter, end_iter) in enumerate(self.iteration_ranges):
                progress_file = progress_dir / f"instance_{i}_progress.json"
                self._progress_files.append(progress_file)
                
                # Get resume checkpoint if available
                resume_checkpoint = resume_checkpoints[i] if resume_checkpoints and i < len(resume_checkpoints) else None
                
                # Create process
                p = mp_context.Process(
                    target=_run_solver_instance,
                    args=(
                        i,
                        self.config,
                        self.bucketing,
                        self.num_players,
                        logdir,
                        use_tensorboard,
                        progress_file,
                        False,  # use_time_budget
                        start_iter,
                        end_iter
                    ),
                    kwargs={'resume_checkpoint': resume_checkpoint}
                )
                p.start()
                self._processes.append(p)
                
                if resume_checkpoint:
                    logger.info(f"Launched instance {i} (PID: {p.pid}) - resuming from checkpoint")
                else:
                    logger.info(f"Launched instance {i} (PID: {p.pid}) - iterations {start_iter} to {end_iter-1}")
        
        # Monitor progress
        self._monitor_progress(progress_dir)
        
        # Wait for all to complete
        logger.info("Waiting for all instances to complete...")
        for i, p in enumerate(self._processes):
            p.join()
            if p.exitcode == 0:
                logger.info(f"Instance {i} completed successfully")
            else:
                logger.error(f"Instance {i} failed with exit code {p.exitcode}")
        
        # Check if all completed successfully
        all_success = all(p.exitcode == 0 for p in self._processes)
        
        if all_success:
            logger.info("All instances completed successfully!")
            self._summarize_results(logdir)
        else:
            logger.error("Some instances failed. Check individual logs for details.")
            return 1
        
        return 0
    
    def _monitor_progress(self, progress_dir: Path):
        """Monitor and report progress of all instances."""
        logger.info("Monitoring instance progress (press Ctrl+C to stop)...")
        
        last_report = time.time()
        report_interval = 30  # Report every 30 seconds
        
        while any(p.is_alive() for p in self._processes):
            if self._interrupted:
                break
            
            # Check if it's time to report
            current_time = time.time()
            if current_time - last_report >= report_interval:
                self._report_progress(progress_dir)
                last_report = current_time
            
            time.sleep(5)
        
        # Final progress report
        if not self._interrupted:
            self._report_progress(progress_dir)
    
    def _report_progress(self, progress_dir: Path):
        """Read and report current progress of all instances."""
        progress_data = []
        
        for progress_file in self._progress_files:
            if progress_file.exists():
                try:
                    with open(progress_file, 'r') as f:
                        data = json.load(f)
                        progress_data.append(data)
                except:
                    pass
        
        if not progress_data:
            return
        
        # Calculate overall progress
        if self.use_time_budget:
            # For time-budget mode, use time_progress_pct if available
            total_progress = 0
            for p in progress_data:
                if 'time_progress_pct' in p:
                    total_progress += p['time_progress_pct']
                else:
                    # Fallback: estimate based on progress_pct
                    total_progress += p.get('progress_pct', 0)
            total_progress /= len(progress_data)
        else:
            # For iteration mode, use iteration-based progress
            total_progress = sum(p.get('progress_pct', 0) for p in progress_data) / len(progress_data)
        
        logger.info(f"=" * 60)
        logger.info(f"Overall Progress: {total_progress:.1f}%")
        logger.info(f"-" * 60)
        
        for p in progress_data:
            status_symbol = {
                'starting': '⏳',
                'running': '▶️',
                'completed': '✅',
                'failed': '❌',
                'interrupted': '⏸️'
            }.get(p['status'], '?')
            
            if self.use_time_budget:
                # Time-budget mode: show time elapsed and current iteration
                elapsed = p.get('elapsed_seconds', 0)
                time_budget = p.get('time_budget_seconds', self.config.time_budget_seconds)
                time_pct = p.get('time_progress_pct', 0)
                current_iter = p.get('current_iter', 0)
                logger.info(
                    f"Instance {p['instance_id']}: {status_symbol} {time_pct:.1f}% "
                    f"(elapsed {elapsed:.0f}s/{time_budget:.0f}s, iter {current_iter})"
                )
            else:
                # Iteration mode: show iteration progress
                logger.info(
                    f"Instance {p['instance_id']}: {status_symbol} {p.get('progress_pct', 0):.1f}% "
                    f"(iter {p.get('current_iter', 0)}/{p.get('end_iter', 0)})"
                )
        
        logger.info(f"=" * 60)
    
    def _terminate_all(self):
        """Terminate all running instances."""
        for i, p in enumerate(self._processes):
            if p.is_alive():
                logger.info(f"Terminating instance {i} (PID: {p.pid})")
                p.terminate()
        
        # Wait for termination
        time.sleep(2)
        
        # Force kill if still alive
        for i, p in enumerate(self._processes):
            if p.is_alive():
                logger.warning(f"Force killing instance {i} (PID: {p.pid})")
                p.kill()
    
    def _summarize_results(self, logdir: Path):
        """Summarize results from all instances."""
        logger.info("=" * 60)
        logger.info("Multi-Instance Training Complete!")
        logger.info("=" * 60)
        logger.info(f"Total instances: {self.num_instances}")
        logger.info(f"Total iterations: {self.config.num_iterations}")
        logger.info(f"Results directory: {logdir}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Each instance has its own checkpoint in instance_N/")
        logger.info("2. To use a specific instance's policy:")
        logger.info(f"   python -m holdem.cli.eval_blueprint --checkpoint {logdir}/instance_0/checkpoint_final.pkl")
        logger.info("3. View TensorBoard logs for each instance:")
        logger.info(f"   tensorboard --logdir {logdir}/instance_0/tensorboard")
        logger.info("=" * 60)
