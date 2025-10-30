"""Main MCCFR solver."""

from pathlib import Path
from holdem.types import MCCFRConfig
from holdem.abstraction.bucketing import HandBucketing
from holdem.mccfr.mccfr_os import OutcomeSampler
from holdem.mccfr.policy_store import PolicyStore
from holdem.utils.logging import get_logger
from holdem.utils.timers import Timer

logger = get_logger("mccfr.solver")


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
    
    def train(self, logdir: Path = None):
        """Run MCCFR training."""
        logger.info(f"Starting MCCFR training for {self.config.num_iterations} iterations")
        
        timer = Timer()
        timer.start()
        
        for i in range(self.config.num_iterations):
            self.iteration = i + 1
            
            # Run one iteration
            utility = self.sampler.sample_iteration(self.iteration)
            
            # CFR+ discount
            if self.iteration % 1000 == 0 and self.config.discount_factor < 1.0:
                self.sampler.regret_tracker.discount(self.config.discount_factor)
            
            # Logging
            if (i + 1) % 10000 == 0:
                elapsed = timer.stop()
                timer.start()
                
                iter_per_sec = 10000 / elapsed if elapsed > 0 else 0
                logger.info(
                    f"Iteration {i+1}/{self.config.num_iterations} "
                    f"({iter_per_sec:.1f} iter/s) - Utility: {utility:.6f}"
                )
            
            # Checkpointing
            if logdir and (i + 1) % self.config.checkpoint_interval == 0:
                self.save_checkpoint(logdir, i + 1)
        
        logger.info("Training complete")
        
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
