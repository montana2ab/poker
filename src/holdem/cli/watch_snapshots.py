"""CLI: Watch for new snapshots and trigger evaluation."""

import argparse
import sys
import time
from pathlib import Path
from typing import Set, Optional
import subprocess
from holdem.utils.logging import setup_logger

logger = setup_logger("watch_snapshots")


class SnapshotWatcher:
    """Watch for new training snapshots and trigger evaluation."""
    
    def __init__(
        self,
        snapshot_dir: Path,
        eval_script: Optional[Path] = None,
        eval_episodes: int = 10000,
        check_interval: int = 60
    ):
        """Initialize snapshot watcher.
        
        Args:
            snapshot_dir: Directory to watch for snapshots
            eval_script: [DEPRECATED] Path to evaluation script (ignored, kept for compatibility)
            eval_episodes: Number of episodes for evaluation
            check_interval: Check interval in seconds
        """
        self.snapshot_dir = snapshot_dir
        self.eval_script = eval_script  # Kept for backward compatibility but not used
        self.eval_episodes = eval_episodes
        self.check_interval = check_interval
        self.seen_snapshots: Set[str] = set()
    
    def watch(self):
        """Start watching for new snapshots."""
        logger.info(f"Starting snapshot watcher on {self.snapshot_dir}")
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info(f"Evaluation episodes: {self.eval_episodes}")
        
        # Initial scan to populate seen snapshots
        self._scan_snapshots(trigger_eval=False)
        logger.info(f"Found {len(self.seen_snapshots)} existing snapshots")
        
        # Main watch loop
        while True:
            try:
                time.sleep(self.check_interval)
                self._scan_snapshots(trigger_eval=True)
            except KeyboardInterrupt:
                logger.info("Watcher stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in watch loop: {e}")
                time.sleep(self.check_interval)
    
    def _scan_snapshots(self, trigger_eval: bool = True):
        """Scan for new snapshots and trigger evaluation.
        
        Args:
            trigger_eval: Whether to trigger evaluation for new snapshots
        """
        if not self.snapshot_dir.exists():
            logger.warning(f"Snapshot directory does not exist: {self.snapshot_dir}")
            return
        
        # Find all snapshot directories
        snapshot_pattern = "snapshot_*"
        current_snapshots = set()
        
        for snapshot_path in self.snapshot_dir.glob(snapshot_pattern):
            if snapshot_path.is_dir():
                current_snapshots.add(snapshot_path.name)
        
        # Find new snapshots
        new_snapshots = current_snapshots - self.seen_snapshots
        
        if new_snapshots:
            for snapshot_name in sorted(new_snapshots):
                logger.info(f"New snapshot detected: {snapshot_name}")
                
                if trigger_eval:
                    snapshot_path = self.snapshot_dir / snapshot_name
                    self._trigger_evaluation(snapshot_path)
                
                self.seen_snapshots.add(snapshot_name)
    
    def _trigger_evaluation(self, snapshot_path: Path):
        """Trigger evaluation for a snapshot.
        
        Args:
            snapshot_path: Path to snapshot directory
        """
        # Find policy file in snapshot
        policy_file = snapshot_path / "avg_policy.pkl"
        if not policy_file.exists():
            policy_file = snapshot_path / "avg_policy.json"
        
        if not policy_file.exists():
            logger.warning(f"No policy file found in {snapshot_path}")
            return
        
        # Create output directory for evaluation results
        eval_dir = snapshot_path / "evaluation"
        eval_dir.mkdir(exist_ok=True)
        
        results_file = eval_dir / "results.json"
        
        logger.info(f"Triggering evaluation for {snapshot_path.name}")
        logger.info(f"Policy: {policy_file}")
        logger.info(f"Results will be saved to: {results_file}")
        
        # Build evaluation command
        # Use sys.executable to ensure subprocess uses same Python environment
        cmd = [
            sys.executable,
            "-m", "holdem.cli.eval_blueprint",
            "--policy", str(policy_file),
            "--episodes", str(self.eval_episodes),
            "--out", str(results_file)
        ]
        
        try:
            # Run evaluation in background
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Evaluation completed successfully for {snapshot_path.name}")
                if result.stdout:
                    logger.info(f"Output:\n{result.stdout}")
            else:
                logger.error(f"Evaluation failed for {snapshot_path.name}")
                logger.error(f"Error: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            logger.error(f"Evaluation timed out for {snapshot_path.name}")
        except Exception as e:
            logger.error(f"Failed to run evaluation: {e}")


def main():
    parser = argparse.ArgumentParser(description="Watch for new snapshots and trigger evaluation")
    
    parser.add_argument("--snapshot-dir", type=Path, required=True,
                       help="Directory containing snapshots to watch")
    parser.add_argument("--eval-script", type=Path,
                       help="Path to evaluation script (default: holdem-eval-blueprint)")
    parser.add_argument("--episodes", type=int, default=10000,
                       help="Number of evaluation episodes (default: 10000)")
    parser.add_argument("--check-interval", type=int, default=60,
                       help="Check interval in seconds (default: 60)")
    
    args = parser.parse_args()
    
    watcher = SnapshotWatcher(
        snapshot_dir=args.snapshot_dir,
        eval_script=args.eval_script,
        eval_episodes=args.episodes,
        check_interval=args.check_interval
    )
    
    watcher.watch()


if __name__ == "__main__":
    main()
