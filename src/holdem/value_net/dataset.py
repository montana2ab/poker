"""Dataset reader/writer for CFV training data.

Handles .jsonl.zst sharded format with 100k examples per shard.
Supports atomic writes and efficient streaming reads.
"""

import json
import os
import zstandard as zstd
from pathlib import Path
from typing import Dict, Iterator, List, Optional
import tempfile
import shutil
import numpy as np


class CFVDatasetWriter:
    """Write CFV training examples to sharded .jsonl.zst files."""
    
    def __init__(
        self,
        output_dir: str,
        shard_size: int = 100000,
        compression_level: int = 3
    ):
        """Initialize writer.
        
        Args:
            output_dir: Output directory for shards
            shard_size: Number of examples per shard
            compression_level: zstd compression level (1-22)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.shard_size = shard_size
        self.compression_level = compression_level
        
        self.current_shard: List[Dict] = []
        self.shard_index = 0
        self.total_examples = 0
        
    def add_example(self, example: Dict):
        """Add a training example.
        
        Args:
            example: Dictionary with keys:
                - street: str ("PREFLOP", "FLOP", "TURN", "RIVER")
                - num_players: int (2-6)
                - hero_pos: str (position name)
                - spr: float
                - public_bucket: int
                - ranges: Dict[str, List[List]] - position -> [[bucket_id, weight], ...]
                - scalars: Dict with pot_norm, to_call_over_pot, last_bet_over_pot, aset
                - target_cfv_bb: float (target value in big blinds)
        """
        self.current_shard.append(example)
        self.total_examples += 1
        
        # Write shard if full
        if len(self.current_shard) >= self.shard_size:
            self._write_shard()
    
    def _write_shard(self):
        """Write current shard to disk atomically."""
        if not self.current_shard:
            return
        
        shard_filename = f"shard_{self.shard_index:06d}.jsonl.zst"
        shard_path = self.output_dir / shard_filename
        temp_path = self.output_dir / f".{shard_filename}.tmp"
        
        try:
            # Write to temporary file
            with open(temp_path, 'wb') as f:
                cctx = zstd.ZstdCompressor(level=self.compression_level)
                with cctx.stream_writer(f) as writer:
                    for example in self.current_shard:
                        line = json.dumps(example) + '\n'
                        writer.write(line.encode('utf-8'))
            
            # Atomic rename
            shutil.move(str(temp_path), str(shard_path))
            
            print(f"Wrote shard {self.shard_index}: {len(self.current_shard)} examples -> {shard_path}")
            
            # Clear current shard
            self.current_shard.clear()
            self.shard_index += 1
            
        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise e
    
    def finalize(self):
        """Write remaining examples and finalize dataset."""
        if self.current_shard:
            self._write_shard()
        
        # Write metadata
        metadata = {
            'num_shards': self.shard_index,
            'total_examples': self.total_examples,
            'shard_size': self.shard_size
        }
        
        metadata_path = self.output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Dataset finalized: {self.total_examples} examples in {self.shard_index} shards")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finalize()


class CFVDatasetReader:
    """Read CFV training examples from sharded .jsonl.zst files."""
    
    def __init__(self, data_dir: str, shuffle: bool = True, seed: int = 42):
        """Initialize reader.
        
        Args:
            data_dir: Directory containing shards
            shuffle: Whether to shuffle examples
            seed: Random seed for shuffling
        """
        self.data_dir = Path(data_dir)
        self.shuffle = shuffle
        self.seed = seed
        
        # Load metadata
        metadata_path = self.data_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
        else:
            # Infer from files
            self.metadata = self._infer_metadata()
        
        # List all shards
        self.shard_files = sorted(self.data_dir.glob("shard_*.jsonl.zst"))
        
        if not self.shard_files:
            raise ValueError(f"No shard files found in {self.data_dir}")
        
        print(f"Dataset loaded: {len(self.shard_files)} shards, "
              f"~{self.metadata.get('total_examples', 'unknown')} examples")
    
    def _infer_metadata(self) -> Dict:
        """Infer metadata from shard files."""
        shard_files = list(self.data_dir.glob("shard_*.jsonl.zst"))
        return {
            'num_shards': len(shard_files),
            'total_examples': None  # Unknown
        }
    
    def __iter__(self) -> Iterator[Dict]:
        """Iterate over all examples."""
        # Optionally shuffle shard order
        shard_files = list(self.shard_files)
        if self.shuffle:
            rng = np.random.RandomState(self.seed)
            rng.shuffle(shard_files)
        
        for shard_file in shard_files:
            yield from self._read_shard(shard_file)
    
    def _read_shard(self, shard_path: Path) -> Iterator[Dict]:
        """Read examples from a single shard.
        
        Args:
            shard_path: Path to shard file
            
        Yields:
            Example dictionaries
        """
        examples = []
        
        with open(shard_path, 'rb') as f:
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(f) as reader:
                text_stream = reader.read().decode('utf-8')
                for line in text_stream.split('\n'):
                    if line.strip():
                        examples.append(json.loads(line))
        
        # Optionally shuffle examples within shard
        if self.shuffle:
            # Ensure seed is in valid range [0, 2^32 - 1] by taking absolute value and modulo
            seed_value = (self.seed + hash(str(shard_path))) % (2**32)
            rng = np.random.RandomState(seed_value)
            rng.shuffle(examples)
        
        yield from examples
    
    def get_num_examples(self) -> Optional[int]:
        """Get total number of examples if known."""
        return self.metadata.get('total_examples')
    
    def get_num_shards(self) -> int:
        """Get number of shards."""
        return len(self.shard_files)


def split_dataset(
    data_dir: str,
    train_frac: float = 0.96,
    val_frac: float = 0.02,
    test_frac: float = 0.02,
    seed: int = 42
) -> Dict[str, List[Path]]:
    """Split dataset into train/val/test by shards.
    
    Args:
        data_dir: Dataset directory
        train_frac: Training fraction
        val_frac: Validation fraction
        test_frac: Test fraction
        seed: Random seed
        
    Returns:
        Dictionary with 'train', 'val', 'test' keys mapping to shard file lists
    """
    data_path = Path(data_dir)
    shard_files = sorted(data_path.glob("shard_*.jsonl.zst"))
    
    if not shard_files:
        raise ValueError(f"No shard files found in {data_dir}")
    
    # Shuffle shards
    rng = np.random.RandomState(seed)
    indices = np.arange(len(shard_files))
    rng.shuffle(indices)
    
    # Calculate split points
    num_train = int(len(shard_files) * train_frac)
    num_val = int(len(shard_files) * val_frac)
    
    train_indices = indices[:num_train]
    val_indices = indices[num_train:num_train + num_val]
    test_indices = indices[num_train + num_val:]
    
    return {
        'train': [shard_files[i] for i in train_indices],
        'val': [shard_files[i] for i in val_indices],
        'test': [shard_files[i] for i in test_indices]
    }
