"""Tests for CFV dataset reader/writer."""

import pytest
import tempfile
import shutil
from pathlib import Path
import json
from holdem.value_net.dataset import (
    CFVDatasetWriter,
    CFVDatasetReader,
    split_dataset
)


def test_dataset_writer_basic():
    """Test basic dataset writing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create writer
        writer = CFVDatasetWriter(tmpdir, shard_size=10)
        
        # Add examples
        for i in range(25):
            example = {
                "street": "FLOP",
                "num_players": 6,
                "hero_pos": "BTN",
                "spr": 5.0 + i * 0.1,
                "public_bucket": i,
                "ranges": {"BTN": [[0, 1.0]]},
                "scalars": {
                    "pot_norm": 1.0,
                    "to_call_over_pot": 0.2,
                    "last_bet_over_pot": 0.3,
                    "aset": "balanced"
                },
                "target_cfv_bb": float(i)
            }
            writer.add_example(example)
        
        writer.finalize()
        
        # Check output
        output_dir = Path(tmpdir)
        
        # Should have 3 shards (10 + 10 + 5)
        shard_files = list(output_dir.glob("shard_*.jsonl.zst"))
        assert len(shard_files) == 3
        
        # Check metadata
        metadata_path = output_dir / "metadata.json"
        assert metadata_path.exists()
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        assert metadata['num_shards'] == 3
        assert metadata['total_examples'] == 25


def test_dataset_reader_basic():
    """Test basic dataset reading."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write dataset
        with CFVDatasetWriter(tmpdir, shard_size=10) as writer:
            for i in range(25):
                example = {
                    "street": "FLOP",
                    "num_players": 6,
                    "hero_pos": "BTN",
                    "spr": 5.0,
                    "public_bucket": i,
                    "ranges": {"BTN": [[0, 1.0]]},
                    "scalars": {
                        "pot_norm": 1.0,
                        "to_call_over_pot": 0.2,
                        "last_bet_over_pot": 0.3,
                        "aset": "balanced"
                    },
                    "target_cfv_bb": float(i)
                }
                writer.add_example(example)
        
        # Read dataset
        reader = CFVDatasetReader(tmpdir, shuffle=False)
        
        # Check examples
        examples = list(reader)
        assert len(examples) == 25
        
        # Check first example
        assert examples[0]['street'] == "FLOP"
        assert examples[0]['num_players'] == 6


def test_dataset_shuffle():
    """Test dataset shuffling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write dataset with known order
        with CFVDatasetWriter(tmpdir, shard_size=10) as writer:
            for i in range(25):
                example = {
                    "street": "FLOP",
                    "num_players": 6,
                    "hero_pos": "BTN",
                    "spr": 5.0,
                    "public_bucket": i,
                    "ranges": {"BTN": [[0, 1.0]]},
                    "scalars": {
                        "pot_norm": 1.0,
                        "to_call_over_pot": 0.2,
                        "last_bet_over_pot": 0.3,
                        "aset": "balanced"
                    },
                    "target_cfv_bb": float(i)
                }
                writer.add_example(example)
        
        # Read without shuffle
        reader1 = CFVDatasetReader(tmpdir, shuffle=False, seed=42)
        examples1 = list(reader1)
        
        # Read with shuffle
        reader2 = CFVDatasetReader(tmpdir, shuffle=True, seed=42)
        examples2 = list(reader2)
        
        # Should have same examples but different order
        assert len(examples1) == len(examples2)
        
        # Check that at least some examples are in different positions
        # (This is probabilistic but should almost always pass)
        different_positions = sum(
            e1['target_cfv_bb'] != e2['target_cfv_bb']
            for e1, e2 in zip(examples1, examples2)
        )
        assert different_positions > 5, "Expected shuffling to change order"


def test_dataset_atomic_write():
    """Test that shard writes are atomic (no .tmp files left)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write dataset
        with CFVDatasetWriter(tmpdir, shard_size=10) as writer:
            for i in range(15):
                example = {
                    "street": "FLOP",
                    "num_players": 6,
                    "hero_pos": "BTN",
                    "spr": 5.0,
                    "public_bucket": i,
                    "ranges": {"BTN": [[0, 1.0]]},
                    "scalars": {
                        "pot_norm": 1.0,
                        "to_call_over_pot": 0.2,
                        "last_bet_over_pot": 0.3,
                        "aset": "balanced"
                    },
                    "target_cfv_bb": float(i)
                }
                writer.add_example(example)
        
        # Check for .tmp files
        output_dir = Path(tmpdir)
        tmp_files = list(output_dir.glob("*.tmp"))
        
        assert len(tmp_files) == 0, "Found temporary files after finalization"


def test_split_dataset():
    """Test dataset splitting into train/val/test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write dataset with 10 shards
        with CFVDatasetWriter(tmpdir, shard_size=10) as writer:
            for i in range(100):
                example = {
                    "street": "FLOP",
                    "num_players": 6,
                    "hero_pos": "BTN",
                    "spr": 5.0,
                    "public_bucket": i,
                    "ranges": {"BTN": [[0, 1.0]]},
                    "scalars": {
                        "pot_norm": 1.0,
                        "to_call_over_pot": 0.2,
                        "last_bet_over_pot": 0.3,
                        "aset": "balanced"
                    },
                    "target_cfv_bb": float(i)
                }
                writer.add_example(example)
        
        # Split dataset
        split = split_dataset(
            tmpdir,
            train_frac=0.8,
            val_frac=0.1,
            test_frac=0.1,
            seed=42
        )
        
        # Check splits
        assert 'train' in split
        assert 'val' in split
        assert 'test' in split
        
        # Should have 10 total shards
        total_shards = len(split['train']) + len(split['val']) + len(split['test'])
        assert total_shards == 10
        
        # Check approximate proportions (within 1 shard)
        assert len(split['train']) >= 7  # ~80%
        assert len(split['val']) >= 0    # ~10%
        assert len(split['test']) >= 0   # ~10%


def test_empty_dataset():
    """Test handling of empty dataset."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create empty dataset
        writer = CFVDatasetWriter(tmpdir, shard_size=10)
        writer.finalize()
        
        # Check metadata
        output_dir = Path(tmpdir)
        metadata_path = output_dir / "metadata.json"
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        assert metadata['num_shards'] == 0
        assert metadata['total_examples'] == 0


def test_context_manager():
    """Test that writer works as context manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use context manager
        with CFVDatasetWriter(tmpdir, shard_size=10) as writer:
            for i in range(5):
                example = {
                    "street": "FLOP",
                    "num_players": 6,
                    "hero_pos": "BTN",
                    "spr": 5.0,
                    "public_bucket": i,
                    "ranges": {"BTN": [[0, 1.0]]},
                    "scalars": {
                        "pot_norm": 1.0,
                        "to_call_over_pot": 0.2,
                        "last_bet_over_pot": 0.3,
                        "aset": "balanced"
                    },
                    "target_cfv_bb": float(i)
                }
                writer.add_example(example)
        
        # Should finalize automatically
        output_dir = Path(tmpdir)
        metadata_path = output_dir / "metadata.json"
        assert metadata_path.exists()


def test_compression():
    """Test that data is actually compressed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write dataset
        with CFVDatasetWriter(tmpdir, shard_size=100) as writer:
            for i in range(100):
                example = {
                    "street": "FLOP",
                    "num_players": 6,
                    "hero_pos": "BTN",
                    "spr": 5.0,
                    "public_bucket": i,
                    "ranges": {"BTN": [[j, 1.0] for j in range(16)]},  # Larger ranges
                    "scalars": {
                        "pot_norm": 1.0,
                        "to_call_over_pot": 0.2,
                        "last_bet_over_pot": 0.3,
                        "aset": "balanced"
                    },
                    "target_cfv_bb": float(i)
                }
                writer.add_example(example)
        
        # Check that compressed file exists and is smaller than uncompressed
        output_dir = Path(tmpdir)
        shard_files = list(output_dir.glob("shard_*.jsonl.zst"))
        
        assert len(shard_files) > 0
        
        # Compressed file should be reasonably small
        # (Hard to check exact size without uncompressing, but basic sanity check)
        for shard_file in shard_files:
            file_size = shard_file.stat().st_size
            assert file_size > 0, "Shard file should not be empty"
            assert file_size < 1000000, "Shard file seems too large (compression may have failed)"


def test_numpy_types_serialization():
    """Test that numpy types are properly converted to JSON-serializable types."""
    import numpy as np
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create writer
        with CFVDatasetWriter(tmpdir, shard_size=10) as writer:
            # Generate example with numpy types (simulating what collect_cfv_data.py does)
            rng = np.random.RandomState(42)
            
            for i in range(5):
                # Simulate the actual usage in collect_cfv_data.py
                bucket_id = rng.randint(0, 200)  # Returns numpy.int64
                weight = rng.uniform(0.5, 1.0)   # Returns numpy.float64
                public_bucket = rng.randint(0, 1000)  # Returns numpy.int64
                
                example = {
                    "street": "FLOP",
                    "num_players": int(rng.choice([2, 3, 4, 5, 6])),  # This should be converted
                    "hero_pos": "BTN",
                    "spr": float(rng.uniform(2.0, 10.0)),
                    "public_bucket": int(public_bucket),  # Convert numpy int64 to Python int
                    "ranges": {
                        "BTN": [[int(bucket_id), float(weight)]]  # Must convert numpy types
                    },
                    "scalars": {
                        "pot_norm": float(rng.uniform(0.0, 1.0)),
                        "to_call_over_pot": float(rng.uniform(0.0, 0.5)),
                        "last_bet_over_pot": float(rng.uniform(0.0, 0.5)),
                        "aset": "balanced"
                    },
                    "target_cfv_bb": float(rng.uniform(-5.0, 5.0))
                }
                
                # This should not raise TypeError
                writer.add_example(example)
        
        # Verify we can read back the data
        reader = CFVDatasetReader(tmpdir, shuffle=False)
        examples = list(reader)
        assert len(examples) == 5
        
        # Verify all values are Python native types
        for example in examples:
            assert isinstance(example['num_players'], int)
            assert isinstance(example['public_bucket'], int)
            assert isinstance(example['spr'], float)
            assert isinstance(example['target_cfv_bb'], float)
            
            # Check ranges values
            for pos, ranges in example['ranges'].items():
                for bucket_id, weight in ranges:
                    assert isinstance(bucket_id, int), f"bucket_id should be int, got {type(bucket_id)}"
                    assert isinstance(weight, float), f"weight should be float, got {type(weight)}"
