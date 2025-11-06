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
        self.pruned_iterations = 0  # Track number of pruned iterations
        self.total_states_visited = 0  # Track total states visited
    
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
            
            # Linear MCCFR discount at regular intervals
            if (self.iteration % self.config.discount_interval == 0 and 
                (self.config.regret_discount_alpha < 1.0 or self.config.strategy_discount_beta < 1.0)):
                self.sampler.regret_tracker.discount(
                    regret_factor=self.config.regret_discount_alpha,
                    strategy_factor=self.config.strategy_discount_beta
                )
            
            # Snapshot saving (time-based)
            if logdir and use_time_budget:
                time_since_snapshot = current_time - last_snapshot_time
                if time_since_snapshot >= self.config.snapshot_interval_seconds:
                    self.save_snapshot(logdir, self.iteration, current_time - start_time)
                    last_snapshot_time = current_time
            
            # TensorBoard logging (every 100 iterations for smoother curves)
            if self.writer and self.iteration % 100 == 0:
                self.writer.add_scalar('Training/Utility', utility, self.iteration)
                
                # Log moving average over last 1000 iterations
                if len(utility_history) >= 1000:
                    avg_utility = sum(utility_history[-1000:]) / 1000
                    self.writer.add_scalar('Training/UtilityMovingAvg', avg_utility, self.iteration)
                
                # Log exploration epsilon
                self.writer.add_scalar('Training/Epsilon', self.config.exploration_epsilon, self.iteration)
                
                # Log pruning statistics
                if self.config.enable_pruning:
                    pruning_rate = self.pruned_iterations / self.iteration if self.iteration > 0 else 0
                    self.writer.add_scalar('Training/PruningRate', pruning_rate * 100, self.iteration)
            
            # Console logging (every 10000 iterations or every 60 seconds in time-budget mode)
            time_since_log = current_time - last_log_time
            should_log = (self.iteration % 10000 == 0) or (use_time_budget and time_since_log >= 60)
            
            if should_log:
                elapsed = timer.stop()
                timer.start()
                
                iter_count = 10000 if self.iteration % 10000 == 0 else self.iteration - (self.iteration // 10000) * 10000
                iter_per_sec = iter_count / elapsed if elapsed > 0 else 0
                
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
        """Save policies separated by street.
        
        Args:
            snapshot_path: Path to snapshot directory
        """
        import json
        
        # Group infosets by street
        policies_by_street = {
            'preflop': {},
            'flop': {},
            'turn': {},
            'river': {}
        }
        
        for infoset in self.sampler.regret_tracker.strategy_sum:
            # Infosets are encoded with street information
            # Extract street from infoset encoding (simplified - assumes street is encoded in infoset)
            # In practice, the StateEncoder includes street information
            actions_dict = self.sampler.regret_tracker.strategy_sum[infoset]
            actions = list(actions_dict.keys())
            avg_strategy = self.sampler.regret_tracker.get_average_strategy(infoset, actions)
            
            # Convert to JSON-serializable format
            policy_entry = {
                action.value: prob for action, prob in avg_strategy.items()
            }
            
            # Determine street from infoset (this is a simplified heuristic)
            # In production, you'd parse the infoset encoding properly
            if 'preflop' in infoset.lower() or len(infoset.split('_')) <= 2:
                policies_by_street['preflop'][infoset] = policy_entry
            elif 'flop' in infoset.lower():
                policies_by_street['flop'][infoset] = policy_entry
            elif 'turn' in infoset.lower():
                policies_by_street['turn'][infoset] = policy_entry
            elif 'river' in infoset.lower():
                policies_by_street['river'][infoset] = policy_entry
            else:
                # Default to preflop if can't determine
                policies_by_street['preflop'][infoset] = policy_entry
        
        # Save each street's policy
        for street, policy in policies_by_street.items():
            if policy:  # Only save if there are policies for this street
                street_path = snapshot_path / f"avg_policy_{street}.json"
                with open(street_path, 'w') as f:
                    json.dump(policy, f, indent=2)
    
    def _save_snapshot_metadata(self, snapshot_path: Path, iteration: int, elapsed_seconds: float):
        """Save snapshot metadata with enhanced metrics.
        
        Args:
            snapshot_path: Path to snapshot directory
            iteration: Current iteration number
            elapsed_seconds: Time elapsed since training start
        """
        import json
        
        # Calculate metrics
        metrics = self._calculate_metrics(iteration, elapsed_seconds)
        
        # Save metadata
        metadata = {
            'iteration': iteration,
            'elapsed_seconds': elapsed_seconds,
            'elapsed_hours': elapsed_seconds / 3600,
            'elapsed_days': elapsed_seconds / 86400,
            'metrics': metrics
        }
        
        metadata_path = snapshot_path / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
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
        
        # Calculate pruning statistics
        pruning_rate = self.pruned_iterations / iteration if iteration > 0 else 0
        
        # Calculate states per second
        states_per_sec = iteration / elapsed_seconds if elapsed_seconds > 0 else 0
        
        metrics = {
            'avg_regret_preflop': avg_regret_by_street.get('preflop', 0.0),
            'avg_regret_flop': avg_regret_by_street.get('flop', 0.0),
            'avg_regret_turn': avg_regret_by_street.get('turn', 0.0),
            'avg_regret_river': avg_regret_by_street.get('river', 0.0),
            'pruned_iterations_pct': pruning_rate * 100,
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
            # Determine street (simplified heuristic)
            if 'preflop' in infoset.lower() or len(infoset.split('_')) <= 2:
                street = 'preflop'
            elif 'flop' in infoset.lower():
                street = 'flop'
            elif 'turn' in infoset.lower():
                street = 'turn'
            elif 'river' in infoset.lower():
                street = 'river'
            else:
                street = 'preflop'
            
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
    
    def save_checkpoint(self, logdir: Path, iteration: int, elapsed_seconds: float = 0):
        """Save training checkpoint with enhanced metrics.
        
        Args:
            logdir: Directory for checkpoints
            iteration: Current iteration number
            elapsed_seconds: Time elapsed since training start (for time-budget mode)
        """
        checkpoint_dir = logdir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Save policy
        policy_store = PolicyStore(self.sampler.regret_tracker)
        checkpoint_name = f"checkpoint_iter{iteration}"
        if elapsed_seconds > 0:
            checkpoint_name += f"_t{int(elapsed_seconds)}s"
        policy_store.save(checkpoint_dir / f"{checkpoint_name}.pkl")
        
        # Save checkpoint metadata with metrics
        import json
        metrics = self._calculate_metrics(iteration, elapsed_seconds)
        metadata = {
            'iteration': iteration,
            'elapsed_seconds': elapsed_seconds,
            'metrics': metrics
        }
        
        metadata_path = checkpoint_dir / f"{checkpoint_name}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Saved checkpoint at iteration {iteration} with metrics")
    
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
