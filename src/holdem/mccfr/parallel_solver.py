"""Parallel MCCFR solver using multiprocessing."""

import multiprocessing as mp
import platform
import queue
import time
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

# Platform detection for Apple Silicon optimization
def _is_apple_silicon() -> bool:
    """Detect if running on Apple Silicon (M1, M2, M3, etc.)."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"

def _is_macos() -> bool:
    """Detect if running on macOS."""
    return platform.system() == "Darwin"

# Worker timeout configuration
# Adaptive timeout is calculated as max(WORKER_TIMEOUT_MIN_SECONDS, iterations_per_worker * WORKER_TIMEOUT_MULTIPLIER)
# Each MCCFR iteration can take several seconds depending on game tree complexity,
# so we need generous timeouts to avoid false positives
WORKER_TIMEOUT_MIN_SECONDS = 300  # Minimum timeout in seconds (5 minutes)
WORKER_TIMEOUT_MULTIPLIER = 10  # Multiplier for adaptive timeout based on batch size (seconds per iteration)

# Queue operation timeouts - platform specific
# Apple Silicon (M1/M2/M3) requires longer timeouts to avoid excessive context switching
# and scheduler thrashing. The aggressive 0.01s timeout causes progressive CPU collapse
# on macOS due to the way the scheduler handles very short sleep/wake cycles.
if _is_apple_silicon():
    # Apple Silicon: Use longer timeouts to reduce context switching overhead
    QUEUE_GET_TIMEOUT_SECONDS = 0.1  # 100ms - reduces GIL contention and context switches
    QUEUE_GET_TIMEOUT_MIN = 0.05     # 50ms - minimum for backoff
    QUEUE_GET_TIMEOUT_MAX = 0.5      # 500ms - maximum for backoff
    logger.info("Detected Apple Silicon - using optimized queue timeouts for M1/M2/M3")
elif _is_macos():
    # Intel macOS: Slightly longer than Linux but not as much as Apple Silicon
    QUEUE_GET_TIMEOUT_SECONDS = 0.05  # 50ms
    QUEUE_GET_TIMEOUT_MIN = 0.02      # 20ms
    QUEUE_GET_TIMEOUT_MAX = 0.2       # 200ms
    logger.info("Detected Intel macOS - using optimized queue timeouts")
else:
    # Linux/Windows: More aggressive timeouts work well on x86
    QUEUE_GET_TIMEOUT_SECONDS = 0.01  # 10ms - keeps processes responsive
    QUEUE_GET_TIMEOUT_MIN = 0.01      # 10ms
    QUEUE_GET_TIMEOUT_MAX = 0.1       # 100ms

RESULT_PUT_TIMEOUT_SECONDS = 60  # Timeout for putting results in queue (60s - handles large payloads)
ERROR_PUT_TIMEOUT_SECONDS = 5  # Timeout for putting error results (5s - shorter since errors are small)

# Worker monitoring configuration
WORKER_STATUS_CHECK_INTERVAL = 10  # Check worker status every N results collected

# Backoff configuration for queue polling
BACKOFF_MULTIPLIER = 1.5  # Exponential backoff multiplier
MAX_EMPTY_POLLS = 5  # Maximum consecutive empty polls before increasing timeout

# Optional TensorBoard support
try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_AVAILABLE = True
except ImportError:
    TENSORBOARD_AVAILABLE = False
    logger.warning("TensorBoard not available. Install tensorboard for training visualization: pip install tensorboard")


def _diagnostic_test_worker(queue: mp.Queue):
    """Simple worker function for diagnostic multiprocessing test.
    
    This function must be at module level to be picklable with the 'spawn'
    multiprocessing start method.
    
    Args:
        queue: Queue to put test result
    """
    queue.put("test_success")


def persistent_worker_process(
    worker_id: int,
    bucketing: HandBucketing,
    num_players: int,
    use_linear_weighting: bool,
    enable_pruning: bool,
    pruning_threshold: float,
    pruning_probability: float,
    task_queue: mp.Queue,
    result_queue: mp.Queue
):
    """Persistent worker process that processes multiple batches.
    
    This worker stays alive and processes tasks from the task queue until
    it receives a shutdown signal. This eliminates the overhead of recreating
    worker processes for each batch.
    
    Args:
        worker_id: ID of this worker
        bucketing: Hand bucketing configuration
        num_players: Number of players
        use_linear_weighting: Use linear weighting
        enable_pruning: Enable pruning
        pruning_threshold: Pruning threshold
        pruning_probability: Pruning probability
        task_queue: Queue to receive tasks from main process
        result_queue: Queue to send results to main process
    """
    worker_logger = get_logger(f"mccfr.worker_{worker_id}")
    sampler = None
    
    try:
        worker_logger.info(f"Worker {worker_id} started and ready for tasks")
        
        while True:
            # Wait for task from main process
            # Block indefinitely to avoid busy-wait polling that causes CPU overhead
            # Workers should sleep until work arrives, not poll with timeouts
            task = task_queue.get()  # Blocking call - no timeout
            
            # Check for shutdown signal
            if task is None or task.get('shutdown', False):
                worker_logger.info(f"Worker {worker_id} received shutdown signal")
                break
            
            # Extract task parameters
            epsilon = task['epsilon']
            iteration_start = task['iteration_start']
            num_iterations = task['num_iterations']
            
            worker_logger.debug(f"Worker {worker_id} processing batch: iterations {iteration_start} to {iteration_start + num_iterations - 1}")
            
            # Create or update sampler if epsilon changed or first time
            if sampler is None or sampler.epsilon != epsilon:
                sampler = OutcomeSampler(
                    bucketing=bucketing,
                    num_players=num_players,
                    epsilon=epsilon,
                    use_linear_weighting=use_linear_weighting,
                    enable_pruning=enable_pruning,
                    pruning_threshold=pruning_threshold,
                    pruning_probability=pruning_probability
                )
                worker_logger.debug(f"Worker {worker_id} sampler initialized with epsilon={epsilon:.3f}")
            
            # Snapshot state before running batch to compute deltas
            # This allows us to send only incremental updates, not the entire accumulated state
            regrets_before = {}
            strategy_sum_before = {}
            
            for infoset in sampler.regret_tracker.regrets:
                regrets_before[infoset] = dict(sampler.regret_tracker.regrets[infoset])
            
            for infoset in sampler.regret_tracker.strategy_sum:
                strategy_sum_before[infoset] = dict(sampler.regret_tracker.strategy_sum[infoset])
            
            # Run iterations
            utilities = []
            
            for i in range(num_iterations):
                iteration = iteration_start + i
                utility = sampler.sample_iteration(iteration)
                utilities.append(utility)
            
            # Compute deltas: only send the incremental changes made during this batch
            # This prevents the data transfer size from growing unboundedly as training progresses
            regret_updates = {}  # Track regret deltas: {infoset: {action: delta_regret}}
            strategy_updates = {}  # Track strategy deltas: {infoset: {action: delta_weight}}
            
            # Calculate regret deltas
            for infoset in sampler.regret_tracker.regrets:
                regret_delta = {}
                for action, new_value in sampler.regret_tracker.regrets[infoset].items():
                    old_value = regrets_before.get(infoset, {}).get(action, 0.0)
                    delta = new_value - old_value
                    if delta != 0.0:  # Only include non-zero deltas
                        regret_delta[action] = delta
                
                if regret_delta:  # Only include infosets with changes
                    regret_updates[infoset] = regret_delta
            
            # Calculate strategy deltas
            for infoset in sampler.regret_tracker.strategy_sum:
                strategy_delta = {}
                for action, new_value in sampler.regret_tracker.strategy_sum[infoset].items():
                    old_value = strategy_sum_before.get(infoset, {}).get(action, 0.0)
                    delta = new_value - old_value
                    if delta != 0.0:  # Only include non-zero deltas
                        strategy_delta[action] = delta
                
                if strategy_delta:  # Only include infosets with changes
                    strategy_updates[infoset] = strategy_delta
            
            worker_logger.debug(f"Worker {worker_id} completed batch: {len(utilities)} iterations, "
                              f"{len(regret_updates)} infosets with regret changes, "
                              f"{len(strategy_updates)} infosets with strategy changes")
            
            # Put results in queue with timeout to avoid indefinite blocking
            # This prevents workers from getting stuck if the result queue is full
            result = {
                'worker_id': worker_id,
                'utilities': utilities,
                'regret_updates': regret_updates,
                'strategy_updates': strategy_updates,
                'success': True,
                'error': None
            }
            
            # Use a timeout to avoid indefinite blocking on large results
            # The main process should be actively consuming results, but this provides a safeguard
            try:
                result_queue.put(result, timeout=RESULT_PUT_TIMEOUT_SECONDS)
                worker_logger.debug(f"Worker {worker_id} successfully sent results to main process")
            except queue.Full:
                # This should rarely happen if main process is consuming results properly
                error_msg = f"Worker {worker_id}: Result queue full after {RESULT_PUT_TIMEOUT_SECONDS}s timeout!"
                worker_logger.error(error_msg)
                # Try to send error result with shorter timeout
                error_result = {
                    'worker_id': worker_id,
                    'utilities': [],
                    'regret_updates': {},
                    'strategy_updates': {},
                    'success': False,
                    'error': error_msg
                }
                try:
                    result_queue.put(error_result, timeout=ERROR_PUT_TIMEOUT_SECONDS)
                except queue.Full:
                    worker_logger.error(f"Worker {worker_id}: Failed to send error result - queue still full")
                    # At this point, worker will continue to next iteration or shutdown
                    # The main process should detect the missing result via timeout
        
        worker_logger.info(f"Worker {worker_id} shutting down gracefully")
        
    except Exception as e:
        # Capture and report any errors
        import sys
        import traceback
        error_msg = f"Worker {worker_id} failed: {str(e)}\n{traceback.format_exc()}"
        try:
            worker_logger.error(error_msg)
        except:
            print(f"ERROR in worker {worker_id}: {error_msg}", file=sys.stderr)
        
        # Send error result to main process
        result = {
            'worker_id': worker_id,
            'utilities': [],
            'regret_updates': {},
            'strategy_updates': {},
            'success': False,
            'error': error_msg
        }
        try:
            result_queue.put(result)
        except:
            print(f"ERROR: Worker {worker_id} failed to put error result in queue", file=sys.stderr)


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
        
        # Create multiprocessing context with 'spawn' for cross-platform compatibility
        # Use get_context() instead of set_start_method() to avoid conflicts
        self.mp_context = mp.get_context('spawn')
        
        # Determine number of workers
        if self.config.num_workers == 0:
            # Use all available CPU cores
            self.num_workers = self.mp_context.cpu_count()
        else:
            self.num_workers = max(1, self.config.num_workers)
        
        logger.info(f"Initialized parallel solver with {self.num_workers} worker(s)")
        
        # Validate batch size for parallel efficiency
        if self.num_workers > 1:
            if self.config.batch_size < self.num_workers:
                logger.warning(
                    f"Batch size ({self.config.batch_size}) is smaller than number of workers ({self.num_workers}). "
                    f"Only {self.config.batch_size} of {self.num_workers} workers will be utilized per batch. "
                    f"Consider increasing --batch-size to at least {self.num_workers} for better parallelization."
                )
            elif self.config.batch_size % self.num_workers != 0:
                # Batch size doesn't divide evenly - some workers will get +1 iteration
                base = self.config.batch_size // self.num_workers
                remainder = self.config.batch_size % self.num_workers
                logger.debug(
                    f"Batch size ({self.config.batch_size}) does not divide evenly by workers ({self.num_workers}). "
                    f"{remainder} workers will get {base+1} iterations, {self.num_workers-remainder} workers get {base}. "
                    f"Consider using batch_size={self.num_workers * base} or {self.num_workers * (base+1)} for even distribution."
                )
        
        # Main regret tracker (will aggregate results from workers)
        self.regret_tracker = RegretTracker()
        self.iteration = 0
        self.writer: Optional[SummaryWriter] = None
        
        # Initialize epsilon schedule tracking
        self._epsilon_schedule_index = 0
        self._current_epsilon = config.exploration_epsilon
        
        # Initialize adaptive epsilon scheduler if enabled
        self._adaptive_scheduler = None
        if config.adaptive_epsilon_enabled and config.epsilon_schedule is not None:
            from holdem.mccfr.adaptive_epsilon import AdaptiveEpsilonScheduler
            self._adaptive_scheduler = AdaptiveEpsilonScheduler(config)
            logger.info("Adaptive epsilon scheduling enabled")
        
        # Worker pool management
        self._workers: List[mp.Process] = []
        self._task_queue: Optional[mp.Queue] = None
        self._result_queue: Optional[mp.Queue] = None
        self._workers_started = False
    
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
                    # Python float is already float64, no explicit conversion needed
                    self.regret_tracker.regrets[infoset][action] += regret
            
            # Merge strategy updates by summing cumulative strategy sums
            for infoset, actions_dict in strategy_updates.items():
                if infoset not in self.regret_tracker.strategy_sum:
                    self.regret_tracker.strategy_sum[infoset] = {}
                
                for action, weight in actions_dict.items():
                    if action not in self.regret_tracker.strategy_sum[infoset]:
                        self.regret_tracker.strategy_sum[infoset][action] = 0.0
                    # Sum cumulative strategy weights (not averages)
                    # Python float is already float64, no explicit conversion needed
                    self.regret_tracker.strategy_sum[infoset][action] += weight
    
    def _start_worker_pool(self):
        """Start persistent worker processes."""
        if self._workers_started:
            logger.warning("Worker pool already started")
            return
        
        logger.info(f"Starting worker pool with {self.num_workers} persistent worker(s)...")
        
        # Create task and result queues
        self._task_queue = self.mp_context.Queue()
        self._result_queue = self.mp_context.Queue()
        
        # Start worker processes
        self._workers = []
        for worker_id in range(self.num_workers):
            p = self.mp_context.Process(
                target=persistent_worker_process,
                args=(
                    worker_id,
                    self.bucketing,
                    self.num_players,
                    self.config.use_linear_weighting,
                    self.config.enable_pruning,
                    self.config.pruning_threshold,
                    self.config.pruning_probability,
                    self._task_queue,
                    self._result_queue
                )
            )
            p.start()
            self._workers.append(p)
            logger.debug(f"Started persistent worker {worker_id} with PID {p.pid}")
        
        self._workers_started = True
        logger.info(f"Worker pool started successfully with {self.num_workers} worker(s)")
    
    def _stop_worker_pool(self):
        """Stop persistent worker processes gracefully."""
        if not self._workers_started:
            return
        
        logger.info("Stopping worker pool...")
        
        # Send shutdown signal to all workers
        for _ in range(self.num_workers):
            self._task_queue.put({'shutdown': True})
        
        # Wait for workers to finish gracefully
        for worker_id, p in enumerate(self._workers):
            p.join(timeout=10)
            if p.is_alive():
                logger.warning(f"Worker {worker_id} (PID {p.pid}) did not stop gracefully, terminating...")
                p.terminate()
                p.join(timeout=5)
                if p.is_alive():
                    logger.error(f"Worker {worker_id} (PID {p.pid}) did not terminate, killing...")
                    p.kill()
                    p.join()
        
        self._workers = []
        self._workers_started = False
        logger.info("Worker pool stopped")
    
    def train(self, logdir: Path = None, use_tensorboard: bool = True):
        """Run parallel MCCFR training.
        
        Args:
            logdir: Directory for logs and checkpoints
            use_tensorboard: Enable TensorBoard logging (requires tensorboard package)
        """
        # Using 'spawn' context for cross-platform compatibility (Mac/Linux)
        # This was initialized in __init__ to avoid conflicts with already-used context
        logger.info(f"Using multiprocessing context: 'spawn' for cross-platform compatibility")
        
        # Verify multiprocessing is working by running a simple test
        logger.info("Running multiprocessing diagnostic test...")
        try:
            test_queue = self.mp_context.Queue()
            test_proc = self.mp_context.Process(target=_diagnostic_test_worker, args=(test_queue,))
            test_proc.start()
            # Wait up to 30 seconds for process to complete (generous timeout for slow imports on spawn)
            test_proc.join(timeout=30)
            if test_proc.is_alive():
                logger.error("Multiprocessing test timed out!")
                logger.error("This usually means the child process is hanging during module import.")
                logger.error("Common causes on macOS:")
                logger.error("  - Heavy dependencies (torch, numpy, etc.) taking long to import")
                logger.error("  - Terminal/console initialization issues with 'rich' library")
                logger.error("  - Module path or sys.path issues")
                test_proc.terminate()
                test_proc.join(timeout=5)
                if test_proc.is_alive():
                    test_proc.kill()
                    test_proc.join()
                raise RuntimeError("Multiprocessing test failed: test worker timed out")
            # Check process exit code
            if test_proc.exitcode != 0:
                logger.error(f"Multiprocessing test process exited with code {test_proc.exitcode}")
                raise RuntimeError(f"Multiprocessing test failed: process exited with code {test_proc.exitcode}")
            # Try to get result from queue
            try:
                test_result = test_queue.get(timeout=2)
            except queue.Empty:
                logger.error("Multiprocessing test: process completed but no result in queue")
                raise RuntimeError("Multiprocessing test failed: no result received from worker")
            if test_result != "test_success":
                raise RuntimeError(f"Multiprocessing test failed: expected 'test_success', got {test_result}")
            logger.info("✓ Multiprocessing diagnostic test passed")
        except Exception as e:
            logger.error(f"Multiprocessing diagnostic test failed: {e}")
            logger.error("Your system may not support multiprocessing properly.")
            logger.error("Try running with --num-workers 1 for single-process mode.")
            raise
        
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
        last_logged_iteration = 0  # Track iterations at last log for accurate rate calculation
        timer = Timer()
        timer.start()
        
        # Track metrics for moving averages
        utility_history = []
        
        # Start persistent worker pool
        try:
            self._start_worker_pool()
            
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
                
                # Distribute work evenly across workers, ensuring all iterations are executed
                # Use floor division to get base iterations per worker
                base_iterations_per_worker = batch_size // self.num_workers
                # Calculate remainder to distribute among first workers
                remainder = batch_size % self.num_workers
                
                # Warn if batch size is too small for the number of workers
                if base_iterations_per_worker == 0:
                    logger.warning(f"Batch size ({batch_size}) is smaller than number of workers ({self.num_workers}). "
                                 f"Consider increasing --batch-size to at least {self.num_workers} for better performance.")
                
                logger.debug(f"Dispatching batch to workers: {self.num_workers} workers, "
                           f"{base_iterations_per_worker} base iterations each, "
                           f"{remainder} workers get +1 iteration")
                
                # Send tasks to workers via task queue
                # Distribute iterations ensuring total equals batch_size
                current_iteration = self.iteration
                for worker_id in range(self.num_workers):
                    # First 'remainder' workers get one extra iteration
                    iterations_for_this_worker = base_iterations_per_worker + (1 if worker_id < remainder else 0)
                    
                    # Skip workers with no work (only happens if batch_size < num_workers)
                    if iterations_for_this_worker == 0:
                        continue
                    
                    task = {
                        'epsilon': self._current_epsilon,
                        'iteration_start': current_iteration,
                        'num_iterations': iterations_for_this_worker
                    }
                    self._task_queue.put(task)
                    logger.debug(f"Dispatched task to worker {worker_id}: iterations {current_iteration} "
                               f"to {current_iteration + iterations_for_this_worker - 1} "
                               f"({iterations_for_this_worker} iterations)")
                    
                    current_iteration += iterations_for_this_worker
                
                # Calculate expected number of active workers (for result collection)
                active_workers = min(self.num_workers, batch_size)
                
                # Collect results from workers with adaptive backoff
                # Adaptive backoff reduces context switching and GIL contention on macOS/Apple Silicon
                # by progressively increasing the timeout when the queue is empty, then resetting
                # when results arrive. This prevents the progressive CPU collapse seen with multiple workers.
                results = []
                # Calculate timeout based on maximum iterations per worker
                max_iterations_per_worker = base_iterations_per_worker + (1 if remainder > 0 else 0)
                timeout_seconds = max(WORKER_TIMEOUT_MIN_SECONDS, max_iterations_per_worker * WORKER_TIMEOUT_MULTIPLIER)
                start_wait_time = time.time()
                
                # Adaptive timeout for queue polling
                current_timeout = QUEUE_GET_TIMEOUT_SECONDS
                consecutive_empty_polls = 0
                
                while len(results) < active_workers:
                    # Check if timeout exceeded
                    if time.time() - start_wait_time > timeout_seconds:
                        logger.error(f"Timeout waiting for worker results after {timeout_seconds}s")
                        break
                    
                    # Try to get result from queue with adaptive timeout
                    # The timeout increases with consecutive empty polls to reduce CPU thrashing,
                    # then resets when results are found to maintain responsiveness
                    try:
                        result = self._result_queue.get(timeout=current_timeout)
                        results.append(result)
                        logger.debug(f"Collected result from worker {result['worker_id']} ({len(results)}/{active_workers})")
                        
                        # Reset adaptive timeout when we successfully get a result
                        current_timeout = QUEUE_GET_TIMEOUT_SECONDS
                        consecutive_empty_polls = 0
                        
                        # Batch collection: When we get one result, drain any other immediately available
                        # results from the queue without waiting. This reduces synchronization overhead
                        # when multiple workers complete around the same time (common pattern).
                        while len(results) < active_workers:
                            try:
                                # Use very short timeout (non-blocking) to drain available results
                                extra_result = self._result_queue.get(timeout=0.001)
                                results.append(extra_result)
                                logger.debug(f"Batch collected result from worker {extra_result['worker_id']} "
                                           f"({len(results)}/{active_workers})")
                            except queue.Empty:
                                # No more results immediately available, break inner loop
                                break
                        
                    except queue.Empty:
                        # Queue empty - apply exponential backoff to reduce CPU overhead
                        consecutive_empty_polls += 1
                        
                        if consecutive_empty_polls >= MAX_EMPTY_POLLS:
                            # Increase timeout to reduce polling frequency
                            current_timeout = min(
                                current_timeout * BACKOFF_MULTIPLIER,
                                QUEUE_GET_TIMEOUT_MAX
                            )
                            # Log backoff on first occurrence to help diagnose performance issues
                            if consecutive_empty_polls == MAX_EMPTY_POLLS:
                                logger.debug(f"Queue empty after {consecutive_empty_polls} polls, "
                                           f"increasing timeout to {current_timeout:.3f}s")
                    
                    # Check if any worker has died unexpectedly
                    # Check on first result and then periodically to balance overhead vs responsiveness
                    # For small batches, check more frequently to ensure we catch worker failures
                    check_interval = min(WORKER_STATUS_CHECK_INTERVAL, self.num_workers)
                    if len(results) == 1 or len(results) % check_interval == 0:
                        for p in self._workers:
                            if not p.is_alive() and p.exitcode is not None and p.exitcode != 0:
                                logger.error(f"Worker process {p.pid} died with exit code {p.exitcode}")
                
                # Check for worker errors
                failed_workers = []
                for result in results:
                    if not result.get('success', True):
                        failed_workers.append(result['worker_id'])
                        logger.error(f"Worker {result['worker_id']} failed with error:\n{result.get('error', 'Unknown error')}")
                
                # Check if we got results from all active workers
                if len(results) < active_workers:
                    missing_workers = active_workers - len(results)
                    logger.error(f"Only received results from {len(results)}/{active_workers} workers ({missing_workers} missing)")
                    logger.error("Training cannot continue reliably. Please check:")
                    logger.error("  1. Worker logs above for specific errors")
                    logger.error("  2. System resources (RAM, CPU)")
                    logger.error("  3. Try reducing --num-workers or --batch-size")
                    raise RuntimeError(f"Parallel training failed: {missing_workers} workers did not complete")
                
                if failed_workers:
                    logger.error(f"Training failed due to {len(failed_workers)} worker failure(s)")
                    raise RuntimeError(f"Workers {failed_workers} failed during execution")
                
                # Merge worker results
                self._merge_worker_results(results)
                
                # Update iteration count
                self.iteration += batch_size
                
                # Collect utilities for logging
                for result in results:
                    utility_history.extend(result['utilities'])
                
                # Limit utility_history size to prevent unbounded memory growth
                # Keep only the most recent 10,000 utilities for moving averages
                if len(utility_history) > 10000:
                    utility_history = utility_history[-10000:]
                
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
                    
                    # Log adaptive epsilon metrics if enabled
                    if self._adaptive_scheduler is not None:
                        adaptive_metrics = self._adaptive_scheduler.get_metrics()
                        for metric_name, value in adaptive_metrics.items():
                            self.writer.add_scalar(metric_name, value, self.iteration)
                
                # Console logging
                time_since_log = current_time - last_log_time
                should_log = (self.iteration % 10000 == 0) or (use_time_budget and time_since_log >= 60)
                
                if should_log:
                    elapsed = timer.stop()
                    timer.start()
                    
                    # Calculate iterations since last log for accurate rate
                    iter_count = self.iteration - last_logged_iteration
                    iter_per_sec = iter_count / elapsed if elapsed > 0 else 0
                    last_logged_iteration = self.iteration
                    
                    # Record performance metrics for adaptive scheduler
                    if self._adaptive_scheduler is not None:
                        num_infosets = len(self.regret_tracker.regrets)
                        self._adaptive_scheduler.record_merge(
                            self.iteration, num_infosets, elapsed, iter_count
                        )
                    
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
        
        finally:
            # Always stop worker pool, even if training was interrupted
            self._stop_worker_pool()
        
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
        
        # Use adaptive scheduler if enabled
        if self._adaptive_scheduler is not None:
            new_epsilon = self._adaptive_scheduler.get_epsilon(self.iteration)
            if new_epsilon != self._current_epsilon:
                self._current_epsilon = new_epsilon
                logger.info(f"Epsilon updated to {new_epsilon:.3f} at iteration {self.iteration}")
            return
        
        # Fall back to standard schedule-based update
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
