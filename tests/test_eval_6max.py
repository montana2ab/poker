"""Tests for tools/eval_6max.py."""

import json
import pickle
import tempfile
from pathlib import Path
import subprocess
import sys


def test_eval_6max_help():
    """Test that eval_6max.py --help runs without error."""
    result = subprocess.run(
        [sys.executable, "tools/eval_6max.py", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "6-max poker policy" in result.stdout.lower()


def test_eval_6max_json_policy():
    """Test evaluation with JSON policy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create test policy
        policy_path = tmpdir / "test_policy.json"
        policy = {
            "policy": {
                "test_infoset_1": {"fold": 0.3, "check_call": 0.5, "bet_0.5p": 0.2}
            },
            "metadata": {
                "bucket_hash": "test",
                "num_players": 6
            }
        }
        with open(policy_path, 'w') as f:
            json.dump(policy, f)
        
        # Run evaluation
        output_dir = tmpdir / "output"
        result = subprocess.run(
            [
                sys.executable, "tools/eval_6max.py",
                "--policy", str(policy_path),
                "--hands", "10",
                "--seed", "42",
                "--output", str(output_dir),
                "--workers", "1",
                "--quiet"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"stderr: {result.stderr}"
        
        # Check outputs exist
        assert (output_dir / "summary.json").exists()
        assert (output_dir / "eval_6max_runs.csv").exists()
        assert (output_dir / "eval_6max_positions.csv").exists()
        
        # Check JSON structure
        with open(output_dir / "summary.json") as f:
            summary = json.load(f)
        
        assert summary["num_players"] == 6
        assert summary["hands"] == 10
        assert "results" in summary
        assert "global" in summary["results"]
        assert "bb_per_100" in summary["results"]["global"]
        assert "ci95" in summary["results"]["global"]


def test_eval_6max_pickle_policy():
    """Test evaluation with pickle policy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create test checkpoint
        checkpoint_path = tmpdir / "checkpoint.pkl"
        data = {
            "strategy_sum": {
                "infoset_1": {"fold": 100, "check_call": 200, "bet_0.5p": 50}
            },
            "metadata": {"num_players": 6}
        }
        with open(checkpoint_path, 'wb') as f:
            pickle.dump(data, f)
        
        # Run evaluation
        output_dir = tmpdir / "output"
        result = subprocess.run(
            [
                sys.executable, "tools/eval_6max.py",
                "--policy", str(checkpoint_path),
                "--hands", "10",
                "--output", str(output_dir),
                "--workers", "1",
                "--quiet"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"stderr: {result.stderr}"
        
        # Check output
        with open(output_dir / "summary.json") as f:
            summary = json.load(f)
        
        assert summary["policy"]["type"] == "checkpoint"


def test_eval_6max_bucket_mismatch():
    """Test bucket mismatch detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create policy with 6 players
        policy_path = tmpdir / "test_policy.json"
        policy = {
            "policy": {"test": {"fold": 0.5, "check_call": 0.5}},
            "metadata": {"num_players": 6}
        }
        with open(policy_path, 'w') as f:
            json.dump(policy, f)
        
        # Try to run with 2 players (should fail)
        result = subprocess.run(
            [
                sys.executable, "tools/eval_6max.py",
                "--policy", str(policy_path),
                "--hands", "5",
                "--num-players", "2",
                "--fail-on-bucket-mismatch",
                "--quiet"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Should exit with code 2
        assert result.returncode == 2
        assert "num_players" in result.stderr.lower()


def test_eval_6max_head_up():
    """Test head-up (2 player) mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create policy
        policy_path = tmpdir / "test_policy.json"
        policy = {"policy": {"test": {"fold": 0.5, "check_call": 0.5}}}
        with open(policy_path, 'w') as f:
            json.dump(policy, f)
        
        # Run HU evaluation
        output_dir = tmpdir / "output"
        result = subprocess.run(
            [
                sys.executable, "tools/eval_6max.py",
                "--policy", str(policy_path),
                "--hands", "10",
                "--num-players", "2",
                "--no-fail-on-bucket-mismatch",
                "--output", str(output_dir),
                "--workers", "1",
                "--quiet"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        
        # Check JSON
        with open(output_dir / "summary.json") as f:
            summary = json.load(f)
        
        assert summary["num_players"] == 2
        
        # Check positions (BTN and BB for HU)
        positions = summary["results"]["by_position"]
        assert "BTN" in positions
        assert "BB" in positions


def test_eval_6max_no_rotate_seats():
    """Test without seat rotation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create policy
        policy_path = tmpdir / "test_policy.json"
        policy = {"policy": {"test": {"fold": 0.5, "check_call": 0.5}}}
        with open(policy_path, 'w') as f:
            json.dump(policy, f)
        
        # Run without rotation
        output_dir = tmpdir / "output"
        result = subprocess.run(
            [
                sys.executable, "tools/eval_6max.py",
                "--policy", str(policy_path),
                "--hands", "20",
                "--no-rotate-seats",
                "--output", str(output_dir),
                "--workers", "1",
                "--quiet"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        
        # Check that we have fewer total hands (no rotation)
        with open(output_dir / "summary.json") as f:
            summary = json.load(f)
        
        # With duplicate=2, no rotation: 20 * 2 = 40 hands
        # With rotation (6 positions): 20 * 2 * 6 = 240 hands
        assert summary["results"]["global"]["n"] == 40


def test_eval_6max_csv_output():
    """Test CSV output format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create policy
        policy_path = tmpdir / "test_policy.json"
        policy = {"policy": {"test": {"fold": 0.5, "check_call": 0.5}}}
        with open(policy_path, 'w') as f:
            json.dump(policy, f)
        
        # Run evaluation
        output_dir = tmpdir / "output"
        result = subprocess.run(
            [
                sys.executable, "tools/eval_6max.py",
                "--policy", str(policy_path),
                "--hands", "10",
                "--output", str(output_dir),
                "--workers", "1",
                "--quiet"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        
        # Check CSV files
        runs_csv = output_dir / "eval_6max_runs.csv"
        positions_csv = output_dir / "eval_6max_positions.csv"
        
        assert runs_csv.exists()
        assert positions_csv.exists()
        
        # Read runs CSV
        with open(runs_csv) as f:
            lines = f.readlines()
        
        assert len(lines) >= 2  # Header + at least one data row
        assert "bb_per_100" in lines[0]
        assert "ci95" in lines[0]
        
        # Read positions CSV
        with open(positions_csv) as f:
            lines = f.readlines()
        
        assert len(lines) >= 7  # Header + 6 positions for 6-max
        assert "position" in lines[0]


def test_eval_6max_no_output_flags():
    """Test --no-csv and --no-json flags."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create policy
        policy_path = tmpdir / "test_policy.json"
        policy = {"policy": {"test": {"fold": 0.5, "check_call": 0.5}}}
        with open(policy_path, 'w') as f:
            json.dump(policy, f)
        
        # Run with --no-csv
        output_dir = tmpdir / "output"
        result = subprocess.run(
            [
                sys.executable, "tools/eval_6max.py",
                "--policy", str(policy_path),
                "--hands", "10",
                "--output", str(output_dir),
                "--no-csv",
                "--workers", "1",
                "--quiet"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0
        assert (output_dir / "summary.json").exists()
        assert not (output_dir / "eval_6max_runs.csv").exists()


if __name__ == "__main__":
    # Run tests manually
    import pytest
    pytest.main([__file__, "-v"])
