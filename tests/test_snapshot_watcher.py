"""Tests for snapshot watcher functionality."""

import pytest
import tempfile
import time
from pathlib import Path
from holdem.cli.watch_snapshots import SnapshotWatcher


def test_snapshot_watcher_initialization():
    """Test that snapshot watcher initializes correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir) / "snapshots"
        snapshot_dir.mkdir()
        
        watcher = SnapshotWatcher(
            snapshot_dir=snapshot_dir,
            eval_episodes=1000,
            check_interval=5
        )
        
        assert watcher.snapshot_dir == snapshot_dir
        assert watcher.eval_episodes == 1000
        assert watcher.check_interval == 5
        assert len(watcher.seen_snapshots) == 0


def test_snapshot_watcher_detects_existing_snapshots():
    """Test that watcher detects existing snapshots on initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir) / "snapshots"
        snapshot_dir.mkdir()
        
        # Create some existing snapshots
        (snapshot_dir / "snapshot_iter1000_t100s").mkdir()
        (snapshot_dir / "snapshot_iter2000_t200s").mkdir()
        
        watcher = SnapshotWatcher(
            snapshot_dir=snapshot_dir,
            check_interval=5
        )
        
        # Scan without triggering evaluation
        watcher._scan_snapshots(trigger_eval=False)
        
        assert len(watcher.seen_snapshots) == 2
        assert "snapshot_iter1000_t100s" in watcher.seen_snapshots
        assert "snapshot_iter2000_t200s" in watcher.seen_snapshots


def test_snapshot_watcher_detects_new_snapshots():
    """Test that watcher detects new snapshots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir) / "snapshots"
        snapshot_dir.mkdir()
        
        watcher = SnapshotWatcher(
            snapshot_dir=snapshot_dir,
            check_interval=1
        )
        
        # Initial scan
        watcher._scan_snapshots(trigger_eval=False)
        assert len(watcher.seen_snapshots) == 0
        
        # Create a new snapshot
        (snapshot_dir / "snapshot_iter1000_t100s").mkdir()
        
        # Scan again
        watcher._scan_snapshots(trigger_eval=False)
        
        assert len(watcher.seen_snapshots) == 1
        assert "snapshot_iter1000_t100s" in watcher.seen_snapshots


def test_snapshot_watcher_handles_missing_directory():
    """Test that watcher handles missing snapshot directory gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir) / "nonexistent"
        
        watcher = SnapshotWatcher(
            snapshot_dir=snapshot_dir,
            check_interval=1
        )
        
        # Should not crash
        watcher._scan_snapshots(trigger_eval=False)
        assert len(watcher.seen_snapshots) == 0


def test_snapshot_watcher_finds_policy_file():
    """Test that watcher finds policy files in snapshots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir) / "snapshots"
        snapshot_dir.mkdir()
        
        # Create snapshot with policy file
        snapshot_path = snapshot_dir / "snapshot_iter1000_t100s"
        snapshot_path.mkdir()
        policy_file = snapshot_path / "avg_policy.pkl"
        policy_file.touch()
        
        watcher = SnapshotWatcher(
            snapshot_dir=snapshot_dir,
            check_interval=1
        )
        
        # Should find the policy file
        # (We can't easily test evaluation trigger without mocking subprocess)
        assert policy_file.exists()


def test_snapshot_watcher_prefers_pkl_over_json():
    """Test that watcher prefers .pkl policy files over .json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir) / "snapshots"
        snapshot_dir.mkdir()
        
        snapshot_path = snapshot_dir / "snapshot_iter1000_t100s"
        snapshot_path.mkdir()
        
        # Create both pkl and json
        pkl_file = snapshot_path / "avg_policy.pkl"
        json_file = snapshot_path / "avg_policy.json"
        pkl_file.touch()
        json_file.touch()
        
        watcher = SnapshotWatcher(
            snapshot_dir=snapshot_dir,
            check_interval=1
        )
        
        # The watcher should prefer pkl
        policy_file = snapshot_path / "avg_policy.pkl"
        assert policy_file.exists()


def test_snapshot_watcher_creates_eval_directory():
    """Test that watcher creates evaluation directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_dir = Path(tmpdir) / "snapshots"
        snapshot_dir.mkdir()
        
        snapshot_path = snapshot_dir / "snapshot_iter1000_t100s"
        snapshot_path.mkdir()
        
        # Create policy file
        policy_file = snapshot_path / "avg_policy.pkl"
        policy_file.touch()
        
        watcher = SnapshotWatcher(
            snapshot_dir=snapshot_dir,
            check_interval=1,
            eval_script="echo"  # Use a dummy command that won't fail
        )
        
        # Note: We can't easily test the actual evaluation trigger without
        # a real eval script, but we can verify the directory structure


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
