"""Main MCCFR solver."""

from pathlib import Path
from typing import Optional
from holdem.types import MCCFRConfig
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
            epsilon=config.exploration_epsilon
        )
        self.iteration = 0
        self.writer: Optional[SummaryWriter] = None
    
    def train(self, logdir: Path = None, use_tensorboard: bool = True):
        """Run MCCFR training.
        
        Args:
            logdir: Directory for logs and checkpoints
            use_tensorboard: Enable TensorBoard logging (requires tensorboard package)
        """
        logger.info(f"Starting MCCFR training for {self.config.num_iterations} iterations")
        
        # Initialize TensorBoard writer if requested and available
        if logdir and use_tensorboard and TENSORBOARD_AVAILABLE:
            tensorboard_dir = logdir / "tensorboard"
            tensorboard_dir.mkdir(parents=True, exist_ok=True)
            self.writer = SummaryWriter(log_dir=str(tensorboard_dir))
            logger.info(f"TensorBoard logging enabled. Run: tensorboard --logdir {tensorboard_dir}")
        elif use_tensorboard and not TENSORBOARD_AVAILABLE:
            logger.warning("TensorBoard requested but not available. Install with: pip install tensorboard")
        
        timer = Timer()
        timer.start()
        
        # Track metrics for moving averages
        utility_history = []
        
        for i in range(self.config.num_iterations):
            self.iteration = i + 1
            
            # Run one iteration
            utility = self.sampler.sample_iteration(self.iteration)
            utility_history.append(utility)
            
            # CFR+ discount
            if self.iteration % 1000 == 0 and self.config.discount_factor < 1.0:
                self.sampler.regret_tracker.discount(self.config.discount_factor)
            
            # TensorBoard logging (every 100 iterations for smoother curves)
            if self.writer and (i + 1) % 100 == 0:
                self.writer.add_scalar('Training/Utility', utility, i + 1)
                
                # Log moving average over last 1000 iterations
                if len(utility_history) >= 1000:
                    avg_utility = sum(utility_history[-1000:]) / 1000
                    self.writer.add_scalar('Training/UtilityMovingAvg', avg_utility, i + 1)
                
                # Log iteration number and exploration epsilon
                self.writer.add_scalar('Training/Iteration', i + 1, i + 1)
                self.writer.add_scalar('Training/Epsilon', self.config.exploration_epsilon, i + 1)
            
            # Console logging
            if (i + 1) % 10000 == 0:
                elapsed = timer.stop()
                timer.start()
                
                iter_per_sec = 10000 / elapsed if elapsed > 0 else 0
                logger.info(
                    f"Iteration {i+1}/{self.config.num_iterations} "
                    f"({iter_per_sec:.1f} iter/s) - Utility: {utility:.6f}"
                )
                
                # Log performance metrics to TensorBoard
                if self.writer:
                    self.writer.add_scalar('Performance/IterationsPerSecond', iter_per_sec, i + 1)
            
            # Checkpointing
            if logdir and (i + 1) % self.config.checkpoint_interval == 0:
                self.save_checkpoint(logdir, i + 1)
        
        logger.info("Training complete")
        
        # Close TensorBoard writer
        if self.writer:
            self.writer.close()
            logger.info("TensorBoard logs saved")
        
        # Save final policy
        if logdir:
            self.save_policy(logdir)
    
    def save_checkpoint(self, logdir: Path, iteration: int):
        """Save training checkpoint."""
        checkpoint_dir = logdir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        policy_store = PolicyStore(self.sampler.regret_tracker)
        policy_store.save(checkpoint_dir / f"checkpoint_{iteration}.pkl")
        
        logger.info(f"Saved checkpoint at iteration {iteration}")
    
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
