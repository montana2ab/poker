"""Main MCCFR solver."""

import time
from pathlib import Path
from typing import Optional, Dict
from holdem.types import MCCFRConfig, Street
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.mccfr_os import OutcomeSampler
from holdem.mccfr.policy_store import PolicyStore
from holdem.utils.logging import get_logger
from holdem.utils.timers import Timer

logger = get_logger("mccfr.solver")

# Optional TensorBoard support
try:
    from torch.utils.tensorboard import SummaryWriter
    TENSORBOARD_AVAILABLE = True
except ImportError:
    TENSORBOARD_AVAILABLE = False
    logger.warning("TensorBoard not available. Install tensorboard for training visualization: pip install tensorboard")


class MCCFRSolver:
    """Main MCCFR solver."""
    
    def __init__(
        self,
        config: MCCFRConfig,
        bucketing: HandBucketing,
        num_players: int = 2
    ):
        self.config = config
        self.bucketing = bucketing
        self.num_players = num_players
        
        # Note: We pass the preflop_equity_samples to bucketing during construction
        # to avoid mutating it here. The bucketing object should be initialized
        # with the correct equity_samples value based on use case (training vs runtime)
        
        self.sampler = OutcomeSampler(
            bucketing=bucketing,
            num_players=num_players,
            epsilon=config.exploration_epsilon,
            use_linear_weighting=config.use_linear_weighting,
            enable_pruning=config.enable_pruning,
            pruning_threshold=config.pruning_threshold,
            pruning_probability=config.pruning_probability
        )
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
        
        # Track timing for adaptive IPS calculation
        self._last_batch_time = None
        self._last_iteration = 0
        
        # Track regret history for validation metrics (L2 norm slope)
        # Store history as list of (iteration, regret_norms_by_street)
        self._regret_history = []
        self._regret_history_window = 10000  # Keep last 10k iterations
    
    def train(self, logdir: Path = None, use_tensorboard: bool = True):
        """Run MCCFR training.
        
        Args:
            logdir: Directory for logs and checkpoints
            use_tensorboard: Enable TensorBoard logging (requires tensorboard package)
        """
        # Determine training mode
        use_time_budget = self.config.time_budget_seconds is not None
        
        if use_time_budget:
            logger.info(f"Starting MCCFR training with time budget: {self.config.time_budget_seconds:.0f} seconds "
                       f"({self.config.time_budget_seconds / 86400:.2f} days)")
        else:
            logger.info(f"Starting MCCFR training for {self.config.num_iterations} iterations")
        
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
        last_log_iteration = 0  # Track iteration number at last log
        timer = Timer()
        timer.start()
        
        # Track metrics for moving averages
        utility_history = []
        
        # Main training loop
        while True:
            self.iteration += 1
            current_time = time.time()
            
            # Check if time budget exceeded (if using time budget)
            if use_time_budget:
                elapsed_total = current_time - start_time
                if elapsed_total >= self.config.time_budget_seconds:
                    logger.info(f"Time budget reached: {elapsed_total:.1f}s")
                    break
            # Check if iteration limit reached (if using iteration count)
            elif self.iteration > self.config.num_iterations:
                break
            
            # Run one iteration
            utility = self.sampler.sample_iteration(self.iteration)
            utility_history.append(utility)
            
            # Update epsilon based on schedule (if configured)
            self._update_epsilon_schedule()
            
            # Linear MCCFR discount at regular intervals
            if self.iteration % self.config.discount_interval == 0:
                # Calculate discount factors based on mode
                if self.config.discount_mode == "dcfr":
                    # DCFR/CFR+ adaptive discounting
                    t = float(self.iteration)
                    d = float(self.config.discount_interval)
                    
                    # α = (t + d) / (t + 2d) for regrets
                    alpha = (t + d) / (t + 2 * d)
                    
                    # β = t / (t + d) for strategy
                    beta = t / (t + d) if t > 0 else 0.0
                    
                    # Apply discounting
                    self.sampler.regret_tracker.discount(
                        regret_factor=alpha,
                        strategy_factor=beta
                    )
                    
                    # CFR+: Reset negative regrets to 0
                    if self.config.dcfr_reset_negative_regrets:
                        self.sampler.regret_tracker.reset_regrets()
                    
                    logger.debug(f"DCFR discount at iteration {self.iteration}: α={alpha:.4f}, β={beta:.4f}")
                    
                elif self.config.discount_mode == "static":
                    # Static discount factors
                    if (self.config.regret_discount_alpha < 1.0 or 
                        self.config.strategy_discount_beta < 1.0):
                        self.sampler.regret_tracker.discount(
                            regret_factor=self.config.regret_discount_alpha,
                            strategy_factor=self.config.strategy_discount_beta
                        )
                # else: discount_mode == "none", no discounting
            
            # Snapshot saving (time-based)
            if logdir and use_time_budget:
                time_since_snapshot = current_time - last_snapshot_time
                if time_since_snapshot >= self.config.snapshot_interval_seconds:
                    self.save_snapshot(logdir, self.iteration, current_time - start_time)
                    last_snapshot_time = current_time
            
            # TensorBoard logging (configurable interval to reduce I/O overhead)
            if self.writer and self.iteration % self.config.tensorboard_log_interval == 0:
                self.writer.add_scalar('Training/Utility', utility, self.iteration)
                
                # Log moving average over last 1000 iterations
                if len(utility_history) >= 1000:
                    avg_utility = sum(utility_history[-1000:]) / 1000
                    self.writer.add_scalar('Training/UtilityMovingAvg', avg_utility, self.iteration)
                
                # Log exploration epsilon
                self.writer.add_scalar('Training/Epsilon', self._current_epsilon, self.iteration)
                
                # Log policy entropy per street
                entropy_metrics = self._calculate_policy_entropy_metrics()
                for metric_name, value in entropy_metrics.items():
                    self.writer.add_scalar(metric_name, value, self.iteration)
                
                # Log normalized regret per street
                regret_metrics = self._calculate_regret_norm_metrics()
                for metric_name, value in regret_metrics.items():
                    self.writer.add_scalar(metric_name, value, self.iteration)
                
                # Log adaptive epsilon metrics if enabled
                if self._adaptive_scheduler is not None:
                    adaptive_metrics = self._adaptive_scheduler.get_metrics()
                    for metric_name, value in adaptive_metrics.items():
                        self.writer.add_scalar(metric_name, value, self.iteration)
            
            # Console logging (every 10000 iterations or every 60 seconds in time-budget mode)
            time_since_log = current_time - last_log_time
            should_log = (self.iteration % 10000 == 0) or (use_time_budget and time_since_log >= 60)
            
            if should_log:
                elapsed = timer.stop()
                timer.start()
                
                # Calculate iterations since last log
                iter_count = self.iteration - last_log_iteration
                if iter_count <= 0:
                    iter_count = 1  # Safeguard against division by zero
                
                iter_per_sec = iter_count / elapsed if elapsed > 0 else 0
                
                # Record performance metrics for adaptive scheduler
                if self._adaptive_scheduler is not None:
                    num_infosets = len(self.sampler.regret_tracker.regrets)
                    self._adaptive_scheduler.record_merge(
                        self.iteration, num_infosets, elapsed, iter_count
                    )
                
                if use_time_budget:
                    elapsed_total = current_time - start_time
                    remaining = self.config.time_budget_seconds - elapsed_total
                    logger.info(
                        f"Iteration {self.iteration} "
                        f"({iter_per_sec:.1f} iter/s) - Utility: {utility:.6f} - "
                        f"Elapsed: {elapsed_total:.1f}s, Remaining: {remaining:.1f}s"
                    )
                else:
                    logger.info(
                        f"Iteration {self.iteration}/{self.config.num_iterations} "
                        f"({iter_per_sec:.1f} iter/s) - Utility: {utility:.6f}"
                    )
                
                last_log_time = current_time
                last_log_iteration = self.iteration
                
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
                    self.save_checkpoint(logdir, self.iteration, current_time - start_time)
                    last_checkpoint_time = current_time
        
        logger.info("Training complete")
        
        # Close TensorBoard writer
        if self.writer:
            self.writer.close()
            logger.info("TensorBoard logs saved")
        
        # Save final policy
        if logdir:
            self.save_policy(logdir)
    
    def _extract_street_from_infoset(self, infoset: str) -> str:
        """Extract street name from infoset encoding.
        
        Uses proper parsing instead of string matching heuristics.
        
        Args:
            infoset: Information set identifier
            
        Returns:
            Street name: 'preflop', 'flop', 'turn', or 'river'
        """
        from holdem.abstraction.state_encode import parse_infoset_key
        
        try:
            street_name, _, _ = parse_infoset_key(infoset)
            return street_name.lower()
        except (ValueError, IndexError):
            # Fallback for malformed infosets
            logger.warning(f"Could not parse infoset: {infoset}, defaulting to preflop")
            return 'preflop'
    
    def save_snapshot(self, logdir: Path, iteration: int, elapsed_seconds: float):
        """Save training snapshot with per-street policies.
        
        Args:
            logdir: Directory for logs and snapshots
            iteration: Current iteration number
            elapsed_seconds: Time elapsed since training start
        """
        snapshot_dir = logdir / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamp-based snapshot name
        snapshot_name = f"snapshot_iter{iteration}_t{int(elapsed_seconds)}s"
        snapshot_path = snapshot_dir / snapshot_name
        snapshot_path.mkdir(exist_ok=True)
        
        # Save overall policy
        policy_store = PolicyStore(self.sampler.regret_tracker)
        policy_store.save(snapshot_path / "avg_policy.pkl")
        policy_store.save_json(snapshot_path / "avg_policy.json")
        
        # Save per-street policies
        self._save_per_street_policies(snapshot_path)
        
        # Save snapshot metadata
        self._save_snapshot_metadata(snapshot_path, iteration, elapsed_seconds)
        
        logger.info(f"Saved snapshot at iteration {iteration} (elapsed: {elapsed_seconds:.1f}s)")
    
    def _save_per_street_policies(self, snapshot_path: Path):
        """Save policies separated by street with gzip compression.
        
        Args:
            snapshot_path: Path to snapshot directory
        """
        from holdem.utils.serialization import save_json
        
        # Group infosets by street
        policies_by_street = {
            'preflop': {},
            'flop': {},
            'turn': {},
            'river': {}
        }
        
        for infoset in self.sampler.regret_tracker.strategy_sum:
            actions_dict = self.sampler.regret_tracker.strategy_sum[infoset]
            actions = list(actions_dict.keys())
            avg_strategy = self.sampler.regret_tracker.get_average_strategy(infoset, actions)
            
            # Convert to JSON-serializable format
            policy_entry = {
                action.value: prob for action, prob in avg_strategy.items()
            }
            
            # Determine street using proper parsing
            street = self._extract_street_from_infoset(infoset)
            policies_by_street[street][infoset] = policy_entry
        
        # Save each street's policy with gzip compression
        for street, policy in policies_by_street.items():
            if policy:  # Only save if there are policies for this street
                street_path = snapshot_path / f"avg_policy_{street}.json.gz"
                save_json(policy, street_path, use_gzip=True)
    
    def _save_snapshot_metadata(self, snapshot_path: Path, iteration: int, elapsed_seconds: float):
        """Save snapshot metadata with enhanced metrics and RNG state.
        
        Args:
            snapshot_path: Path to snapshot directory
            iteration: Current iteration number
            elapsed_seconds: Time elapsed since training start
        """
        from holdem.utils.serialization import save_json
        import hashlib
        
        # Calculate metrics
        metrics = self._calculate_metrics(iteration, elapsed_seconds)
        
        # Get RNG state
        rng_state = self.sampler.rng.get_state()
        
        # Calculate bucket file hash for validation
        bucket_sha = self._calculate_bucket_hash()
        
        # Save metadata
        metadata = {
            'iteration': iteration,
            'elapsed_seconds': elapsed_seconds,
            'elapsed_hours': elapsed_seconds / 3600,
            'elapsed_days': elapsed_seconds / 86400,
            'metrics': metrics,
            'rng_state': rng_state,
            'bucket_metadata': {
                'bucket_file_sha': bucket_sha,
                'k_preflop': self.bucketing.config.k_preflop,
                'k_flop': self.bucketing.config.k_flop,
                'k_turn': self.bucketing.config.k_turn,
                'k_river': self.bucketing.config.k_river,
                'num_samples': self.bucketing.config.num_samples,
                'seed': self.bucketing.config.seed
            }
        }
        
        metadata_path = snapshot_path / "metadata.json"
        save_json(metadata, metadata_path)
    
    def _calculate_metrics(self, iteration: int, elapsed_seconds: float) -> Dict:
        """Calculate training metrics.
        
        Args:
            iteration: Current iteration number
            elapsed_seconds: Time elapsed since training start
            
        Returns:
            Dictionary of metrics
        """
        # Calculate average regret per street
        avg_regret_by_street = self._calculate_avg_regret_by_street()
        
        # Calculate states per second
        states_per_sec = iteration / elapsed_seconds if elapsed_seconds > 0 else 0
        
        # Note: Pruning statistics would require modifying OutcomeSampler
        # to track and report pruning events. For now, we set to 0.
        # To implement properly, OutcomeSampler.sample_iteration would need
        # to return a tuple (utility, was_pruned) and solver would track it.
        
        metrics = {
            'avg_regret_preflop': avg_regret_by_street.get('preflop', 0.0),
            'avg_regret_flop': avg_regret_by_street.get('flop', 0.0),
            'avg_regret_turn': avg_regret_by_street.get('turn', 0.0),
            'avg_regret_river': avg_regret_by_street.get('river', 0.0),
            'pruned_iterations_pct': 0.0,  # Placeholder - requires OutcomeSampler modification
            'iterations_per_second': states_per_sec,
            'total_iterations': iteration,
            'num_infosets': len(self.sampler.regret_tracker.regrets)
        }
        
        return metrics
    
    def _calculate_avg_regret_by_street(self) -> Dict[str, float]:
        """Calculate average regret grouped by street.
        
        Returns:
            Dictionary mapping street name to average regret
        """
        regrets_by_street = {
            'preflop': [],
            'flop': [],
            'turn': [],
            'river': []
        }
        
        for infoset, action_regrets in self.sampler.regret_tracker.regrets.items():
            # Determine street using helper method
            street = self._extract_street_from_infoset(infoset)
            
            # Add all regrets for this infoset
            regrets_by_street[street].extend(action_regrets.values())
        
        # Calculate averages
        avg_regrets = {}
        for street, regrets in regrets_by_street.items():
            if regrets:
                avg_regrets[street] = sum(regrets) / len(regrets)
            else:
                avg_regrets[street] = 0.0
        
        return avg_regrets
    
    def _calculate_bucket_hash(self) -> str:
        """Calculate hash of bucket configuration for validation.
        
        Returns:
            SHA256 hash of bucket configuration
        """
        import hashlib
        import json
        
        # Create a deterministic representation of the bucket configuration
        bucket_data = {
            'k_preflop': self.bucketing.config.k_preflop,
            'k_flop': self.bucketing.config.k_flop,
            'k_turn': self.bucketing.config.k_turn,
            'k_river': self.bucketing.config.k_river,
            'num_samples': self.bucketing.config.num_samples,
            'seed': self.bucketing.config.seed,
        }
        
        # Include cluster centers if available (most critical part)
        # Use tolist() for deterministic cross-platform hashing
        if self.bucketing.fitted and self.bucketing.models:
            for street, model in self.bucketing.models.items():
                if hasattr(model, 'cluster_centers_'):
                    # Convert to list for deterministic serialization
                    bucket_data[f'{street.name}_centers'] = model.cluster_centers_.tolist()
        
        # Calculate hash using JSON for deterministic serialization
        data_str = json.dumps(bucket_data, sort_keys=True)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()
    
    def save_checkpoint(self, logdir: Path, iteration: int, elapsed_seconds: float = 0):
        """Save training checkpoint with enhanced metrics, RNG state, and full regret state.
        
        Args:
            logdir: Directory for checkpoints
            iteration: Current iteration number
            elapsed_seconds: Time elapsed since training start (for time-budget mode)
        """
        from holdem.utils.serialization import save_json, save_pickle
        
        checkpoint_dir = logdir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Save policy
        policy_store = PolicyStore(self.sampler.regret_tracker)
        checkpoint_name = f"checkpoint_iter{iteration}"
        if elapsed_seconds > 0:
            checkpoint_name += f"_t{int(elapsed_seconds)}s"
        policy_store.save(checkpoint_dir / f"{checkpoint_name}.pkl")
        
        # Get RNG state
        rng_state = self.sampler.rng.get_state()
        
        # Get full regret tracker state for warm-start
        regret_state = self.sampler.regret_tracker.get_state()
        
        # Calculate bucket file hash for validation
        bucket_sha = self._calculate_bucket_hash()
        
        # Save checkpoint metadata with metrics, RNG state, epsilon, discount params, and bucket metadata
        metrics = self._calculate_metrics(iteration, elapsed_seconds)
        metadata = {
            'iteration': iteration,
            'elapsed_seconds': elapsed_seconds,
            'metrics': metrics,
            'rng_state': rng_state,
            'epsilon': self._current_epsilon,
            'regret_discount_alpha': self.config.regret_discount_alpha,
            'strategy_discount_beta': self.config.strategy_discount_beta,
            'bucket_metadata': {
                'bucket_file_sha': bucket_sha,
                'k_preflop': self.bucketing.config.k_preflop,
                'k_flop': self.bucketing.config.k_flop,
                'k_turn': self.bucketing.config.k_turn,
                'k_river': self.bucketing.config.k_river,
                'num_samples': self.bucketing.config.num_samples,
                'seed': self.bucketing.config.seed
            }
        }
        
        metadata_path = checkpoint_dir / f"{checkpoint_name}_metadata.json"
        save_json(metadata, metadata_path)
        
        # Save full regret state for warm-start (separate file for better organization)
        regret_state_path = checkpoint_dir / f"{checkpoint_name}_regrets.pkl"
        save_pickle(regret_state, regret_state_path)
        
        logger.info(f"Saved checkpoint at iteration {iteration} with complete metadata, RNG state, and regret state")
    
    def load_checkpoint(self, checkpoint_path: Path, validate_buckets: bool = True, warm_start: bool = True) -> int:
        """Load checkpoint and restore training state with optional warm-start.
        
        Args:
            checkpoint_path: Path to checkpoint .pkl file
            validate_buckets: If True, validate bucket configuration matches
            warm_start: If True, fully restore regret tracker state for warm-start
            
        Returns:
            Iteration number from checkpoint (0 if metadata not found)
            
        Raises:
            ValueError: If bucket validation fails
        """
        from holdem.utils.serialization import load_json, load_pickle
        
        # Load metadata
        metadata_path = checkpoint_path.parent / f"{checkpoint_path.stem}_metadata.json"
        if not metadata_path.exists():
            logger.warning(f"Metadata file not found: {metadata_path}")
            logger.warning("Cannot restore training state without metadata")
            return 0
        
        metadata = load_json(metadata_path)
        
        # Validate bucket configuration
        if validate_buckets and 'bucket_metadata' in metadata:
            current_sha = self._calculate_bucket_hash()
            checkpoint_sha = metadata['bucket_metadata'].get('bucket_file_sha', '')
            
            if current_sha != checkpoint_sha:
                raise ValueError(
                    f"Bucket configuration mismatch!\n"
                    f"Current SHA: {current_sha}\n"
                    f"Checkpoint SHA: {checkpoint_sha}\n"
                    f"Cannot safely resume training with different bucket configuration."
                )
            
            logger.info("Bucket configuration validated successfully")
        
        # Restore RNG state
        if 'rng_state' in metadata:
            self.sampler.rng.set_state(metadata['rng_state'])
            logger.info("RNG state restored")
        else:
            logger.warning("No RNG state found in checkpoint, randomness will not be exactly reproducible")
        
        # Restore epsilon if available
        if 'epsilon' in metadata:
            self._current_epsilon = metadata['epsilon']
            # Update sampler epsilon
            if hasattr(self.sampler, 'set_epsilon'):
                self.sampler.set_epsilon(self._current_epsilon)
            else:
                self.sampler.epsilon = self._current_epsilon
            logger.info(f"Restored epsilon: {self._current_epsilon:.3f}")
        else:
            logger.warning("No epsilon found in checkpoint metadata")
        
        # Restore full regret state for warm-start
        if warm_start:
            regret_state_path = checkpoint_path.parent / f"{checkpoint_path.stem}_regrets.pkl"
            if regret_state_path.exists():
                try:
                    regret_state = load_pickle(regret_state_path)
                    self.sampler.regret_tracker.set_state(regret_state)
                    logger.info("✓ Warm-start: Full regret tracker state restored")
                    logger.info(f"  - Restored {len(self.sampler.regret_tracker.regrets)} infosets with regrets")
                    logger.info(f"  - Restored {len(self.sampler.regret_tracker.strategy_sum)} infosets with strategy")
                except Exception as e:
                    logger.error(f"Failed to restore regret state: {e}")
                    logger.warning("Training will continue with fresh regret state")
            else:
                logger.warning(f"Regret state file not found: {regret_state_path}")
                logger.warning("Training will continue with fresh regret state (not a warm-start)")
        else:
            logger.info("Warm-start disabled, training will continue with fresh regret state")
        
        # Get iteration number
        iteration = metadata.get('iteration', 0)
        self.iteration = iteration
        
        logger.info(f"Loaded checkpoint from iteration {iteration}")
        
        return iteration
    
    def _update_epsilon_schedule(self):
        """Update epsilon based on schedule if configured."""
        if self.config.epsilon_schedule is None:
            return
        
        # Use adaptive scheduler if enabled
        if self._adaptive_scheduler is not None:
            new_epsilon = self._adaptive_scheduler.get_epsilon(self.iteration)
            if new_epsilon != self._current_epsilon:
                self._current_epsilon = new_epsilon
                # Update sampler epsilon
                if hasattr(self.sampler, 'set_epsilon'):
                    self.sampler.set_epsilon(new_epsilon)
                else:
                    self.sampler.epsilon = new_epsilon
                logger.info(f"Epsilon updated to {new_epsilon:.3f} at iteration {self.iteration}")
            return
        
        # Fall back to standard schedule-based update
        schedule = self.config.epsilon_schedule
        
        # Find the current epsilon value
        for i in range(len(schedule) - 1, -1, -1):
            if self.iteration >= schedule[i][0]:
                new_epsilon = schedule[i][1]
                if new_epsilon != self._current_epsilon:
                    self._current_epsilon = new_epsilon
                    # Update sampler epsilon (defensive check for interface)
                    if hasattr(self.sampler, 'set_epsilon'):
                        self.sampler.set_epsilon(new_epsilon)
                    else:
                        # Fallback: directly set epsilon attribute
                        self.sampler.epsilon = new_epsilon
                    logger.info(f"Epsilon updated to {new_epsilon:.3f} at iteration {self.iteration}")
                break
    
    def _calculate_policy_entropy_metrics(self) -> Dict[str, float]:
        """Calculate policy entropy metrics per street and position.
        
        Tracks entropy over time to validate that policy entropy decreases post-river,
        indicating convergence to a more deterministic strategy.
        
        Returns:
            Dictionary of metric names to values
        """
        import math
        
        # Group infosets by street and position (IP/OOP)
        entropy_by_street = {
            'preflop': [],
            'flop': [],
            'turn': [],
            'river': []
        }
        entropy_by_position = {
            'IP': [],  # In Position
            'OOP': []  # Out of Position
        }
        
        for infoset in self.sampler.regret_tracker.strategy_sum:
            actions_dict = self.sampler.regret_tracker.strategy_sum[infoset]
            if not actions_dict:
                continue
                
            actions = list(actions_dict.keys())
            avg_strategy = self.sampler.regret_tracker.get_average_strategy(infoset, actions)
            
            # Calculate entropy: H(p) = -Σ p(a) * log(p(a))
            entropy = 0.0
            for action, prob in avg_strategy.items():
                if prob > 0:
                    entropy -= prob * math.log2(prob)
            
            # Determine street
            street = self._extract_street_from_infoset(infoset)
            entropy_by_street[street].append(entropy)
            
            # Determine position (simplified: based on infoset encoding)
            # IP if acting last, OOP if acting first
            # This is a simplification - proper position depends on game state
            position = self._extract_position_from_infoset(infoset)
            if position:
                entropy_by_position[position].append(entropy)
        
        # Calculate averages
        metrics = {}
        for street, entropies in entropy_by_street.items():
            if entropies:
                avg_entropy = sum(entropies) / len(entropies)
                metrics[f'policy_entropy/{street}'] = avg_entropy
                
                # Track max entropy (most uncertain) for comparison
                metrics[f'policy_entropy_max/{street}'] = max(entropies)
        
        for position, entropies in entropy_by_position.items():
            if entropies:
                metrics[f'policy_entropy/{position}'] = sum(entropies) / len(entropies)
        
        # Validation metric: River entropy should decrease over training
        # This is checked implicitly by logging river entropy over time
        # User can verify monotonic decrease in TensorBoard
        
        return metrics
    
    def _extract_position_from_infoset(self, infoset: str) -> Optional[str]:
        """Extract position (IP/OOP) from infoset.
        
        Simplified heuristic: if history ends with 'c' (call), player is IP,
        if ends with 'b' or 'r' (bet/raise), player is OOP.
        
        Args:
            infoset: Information set identifier
            
        Returns:
            'IP' for in position, 'OOP' for out of position, or None
        """
        try:
            # Parse infoset to get action history
            parts = infoset.split('|')
            if len(parts) >= 2:
                history = parts[1] if len(parts) > 1 else ''
                if history:
                    last_action = history[-1]
                    # Simple heuristic
                    if last_action in ['c', 'k']:  # call or check
                        return 'IP'
                    elif last_action in ['b', 'r']:  # bet or raise
                        return 'OOP'
        except (IndexError, ValueError):
            pass
        return None
    
    def _calculate_regret_norm_metrics(self) -> Dict[str, float]:
        """Calculate normalized regret metrics per street with L2 slope validation.
        
        Returns:
            Dictionary of metric names to values, including L2 norms and slopes
        """
        import numpy as np
        
        # Group regrets by street
        regrets_by_street = {
            'preflop': [],
            'flop': [],
            'turn': [],
            'river': []
        }
        
        for infoset, action_regrets in self.sampler.regret_tracker.regrets.items():
            if not action_regrets:
                continue
                
            # Determine street
            street = self._extract_street_from_infoset(infoset)
            
            # Calculate regret norm (L2 norm)
            regret_values = list(action_regrets.values())
            regret_norm = np.linalg.norm(regret_values)
            regrets_by_street[street].append(regret_norm)
        
        # Calculate average L2 norms
        metrics = {}
        current_norms = {}
        for street, regret_norms in regrets_by_street.items():
            if regret_norms:
                avg_norm = sum(regret_norms) / len(regret_norms)
                metrics[f'avg_regret_norm/{street}'] = avg_norm
                current_norms[street] = avg_norm
        
        # Store current regret norms in history
        if current_norms:
            self._regret_history.append((self.iteration, current_norms))
            # Keep only recent history
            if len(self._regret_history) > self._regret_history_window:
                self._regret_history = self._regret_history[-self._regret_history_window:]
        
        # Calculate L2 regret slope (should be monotonically decreasing)
        # Use linear regression on recent history
        if len(self._regret_history) >= 2:
            for street in ['preflop', 'flop', 'turn', 'river']:
                # Extract data for this street
                iterations = []
                norms = []
                for iter_num, norms_dict in self._regret_history:
                    if street in norms_dict:
                        iterations.append(iter_num)
                        norms.append(norms_dict[street])
                
                if len(iterations) >= 2:
                    # Fit linear regression: norm = slope * iteration + intercept
                    iterations_arr = np.array(iterations)
                    norms_arr = np.array(norms)
                    
                    # Normalize iterations to avoid numerical issues
                    iter_mean = iterations_arr.mean()
                    iter_std = iterations_arr.std()
                    if iter_std > 0:
                        iterations_normalized = (iterations_arr - iter_mean) / iter_std
                        
                        # Fit line
                        slope_normalized, intercept = np.polyfit(iterations_normalized, norms_arr, 1)
                        
                        # Convert slope back to original scale
                        slope = slope_normalized / iter_std
                        
                        metrics[f'regret_slope/{street}'] = slope
                        
                        # Validation: slope should be negative (decreasing regrets)
                        # We expect monotonically decreasing L2 norm
                        metrics[f'regret_slope_ok/{street}'] = 1.0 if slope < 0 else 0.0
        
        return metrics
    
    def save_policy(self, logdir: Path):
        """Save final average policy."""
        logdir.mkdir(parents=True, exist_ok=True)
        
        policy_store = PolicyStore(self.sampler.regret_tracker)
        
        # Save as pickle
        policy_store.save(logdir / "avg_policy.pkl")
        
        # Save as JSON
        policy_store.save_json(logdir / "avg_policy.json")
        
        logger.info(f"Saved final policy to {logdir}")
    
    def get_policy(self) -> PolicyStore:
        """Get current policy store."""
        return PolicyStore(self.sampler.regret_tracker)
