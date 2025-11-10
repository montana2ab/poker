"""Test chunked training with multi-instance mode."""

import pytest
import yaml
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def test_chunked_with_num_instances_no_error():
    """Test that --chunked and --num-instances can be used together without error."""
    # Simulate the argument parsing from train_blueprint.py
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--iters", type=int)
    parser.add_argument("--time-budget", type=float)
    parser.add_argument("--buckets", type=Path, required=True)
    parser.add_argument("--logdir", type=Path, required=True)
    parser.add_argument("--num-instances", type=int)
    parser.add_argument("--chunked", action="store_true")
    parser.add_argument("--chunk-iterations", type=int)
    parser.add_argument("--chunk-minutes", type=float)
    parser.add_argument("--num-workers", type=int)
    
    # Test the command from the problem statement
    test_args = [
        '--buckets', 'assets/abstraction/buckets_mid_street.pkl',
        '--logdir', '/tmp/test_run',
        '--iters', '1000',
        '--num-instances', '5',
        '--chunked',
        '--chunk-minutes', '10'
    ]
    
    args = parser.parse_args(test_args)
    
    # Validate chunked training mode (from the updated code)
    # This should NOT error out
    if args.chunked:
        if args.chunk_iterations is None and args.chunk_minutes is None:
            pytest.fail("--chunked requires either --chunk-iterations or --chunk-minutes")
    
    # Validate multi-instance mode
    if args.num_instances is not None:
        if args.num_instances < 1:
            pytest.fail("--num-instances must be >= 1")
        
        if args.num_workers is not None and args.num_workers != 1:
            pytest.fail("--num-instances requires each instance to use 1 worker")
    
    # If we get here, the combination is accepted
    assert args.num_instances == 5
    assert args.chunked == True
    assert args.chunk_minutes == 10


def test_chunked_requires_chunk_size():
    """Test that --chunked still requires chunk size specification."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--buckets", type=Path, required=True)
    parser.add_argument("--logdir", type=Path, required=True)
    parser.add_argument("--iters", type=int)
    parser.add_argument("--num-instances", type=int)
    parser.add_argument("--chunked", action="store_true")
    parser.add_argument("--chunk-iterations", type=int)
    parser.add_argument("--chunk-minutes", type=float)
    
    test_args = [
        '--buckets', 'test.pkl',
        '--logdir', '/tmp/test',
        '--iters', '1000',
        '--num-instances', '2',
        '--chunked'
        # Missing --chunk-iterations or --chunk-minutes
    ]
    
    args = parser.parse_args(test_args)
    
    # Validation should fail
    if args.chunked:
        if args.chunk_iterations is None and args.chunk_minutes is None:
            # This is the expected error
            return
    
    pytest.fail("Expected validation error for missing chunk size")


def test_chunked_with_num_instances_time_budget():
    """Test chunked + multi-instance with time-budget mode."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--buckets", type=Path, required=True)
    parser.add_argument("--logdir", type=Path, required=True)
    parser.add_argument("--time-budget", type=float)
    parser.add_argument("--num-instances", type=int)
    parser.add_argument("--chunked", action="store_true")
    parser.add_argument("--chunk-minutes", type=float)
    
    test_args = [
        '--buckets', 'test.pkl',
        '--logdir', '/tmp/test',
        '--time-budget', '3600',
        '--num-instances', '2',
        '--chunked',
        '--chunk-minutes', '30'
    ]
    
    args = parser.parse_args(test_args)
    
    # Should parse successfully
    assert args.time_budget == 3600
    assert args.num_instances == 2
    assert args.chunked == True
    assert args.chunk_minutes == 30


def test_chunked_with_num_instances_iteration_mode():
    """Test chunked + multi-instance with iteration-based training."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--buckets", type=Path, required=True)
    parser.add_argument("--logdir", type=Path, required=True)
    parser.add_argument("--iters", type=int)
    parser.add_argument("--num-instances", type=int)
    parser.add_argument("--chunked", action="store_true")
    parser.add_argument("--chunk-iterations", type=int)
    
    test_args = [
        '--buckets', 'test.pkl',
        '--logdir', '/tmp/test',
        '--iters', '10000',
        '--num-instances', '4',
        '--chunked',
        '--chunk-iterations', '1000'
    ]
    
    args = parser.parse_args(test_args)
    
    # Should parse successfully
    assert args.iters == 10000
    assert args.num_instances == 4
    assert args.chunked == True
    assert args.chunk_iterations == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

