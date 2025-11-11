"""
Infoset encoding utilities for compact storage of regrets and strategies.

This module provides utilities for encoding infoset data in a memory-efficient format,
including support for int32 storage with Pluribus-style regret floors.

Phase 2.3: Compact storage of regrets/strategies
- Option A: int32 with floor at -310M (Pluribus parity)
- Provides memory benchmarking and latency testing utilities
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional
import struct

# Pluribus-style regret floor: -310,000,000
# This prevents regret values from going too negative while maintaining precision
REGRET_FLOOR = -310_000_000

# Storage type constants
DTYPE_FLOAT64 = np.float64  # Standard Python float (8 bytes)
DTYPE_INT32 = np.int32      # Compact storage (4 bytes, 50% memory reduction)


class CompactRegretEncoder:
    """
    Encoder for compact regret/strategy storage using int32 format.
    
    This implementation follows the Pluribus approach:
    - Regrets are stored as int32 with a floor at -310,000,000
    - Provides 50% memory reduction compared to float64
    - Maintains sufficient precision for CFR convergence
    
    Memory savings:
    - float64: 8 bytes per value
    - int32: 4 bytes per value
    - Reduction: 50%
    
    Example:
        >>> encoder = CompactRegretEncoder()
        >>> regrets = {'action1': 1500.5, 'action2': -400000000.0}
        >>> encoded = encoder.encode_regrets(regrets)
        >>> decoded = encoder.decode_regrets(encoded)
        >>> print(decoded['action2'])  # Will be floored to -310,000,000
    """
    
    def __init__(self, regret_floor: int = REGRET_FLOOR):
        """
        Initialize the compact regret encoder.
        
        Args:
            regret_floor: Minimum allowed regret value (default: -310,000,000)
        """
        self.regret_floor = regret_floor
    
    def encode_regrets(self, regrets: Dict[str, float]) -> Dict[str, int]:
        """
        Encode regret values to int32 format with floor.
        
        Args:
            regrets: Dictionary mapping action names to float regret values
            
        Returns:
            Dictionary mapping action names to int32 regret values
        """
        encoded = {}
        for action, value in regrets.items():
            # Apply floor and convert to int32
            floored_value = max(value, self.regret_floor)
            # Round to nearest integer
            encoded[action] = int(np.clip(floored_value, self.regret_floor, np.iinfo(np.int32).max))
        return encoded
    
    def decode_regrets(self, encoded_regrets: Dict[str, int]) -> Dict[str, float]:
        """
        Decode int32 regret values back to float format.
        
        Args:
            encoded_regrets: Dictionary mapping action names to int32 regret values
            
        Returns:
            Dictionary mapping action names to float regret values
        """
        decoded = {}
        for action, value in encoded_regrets.items():
            # Convert back to float
            decoded[action] = float(value)
        return decoded
    
    def encode_regret_table(self, regret_table: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, int]]:
        """
        Encode an entire regret table (infoset -> action -> regret).
        
        Args:
            regret_table: Nested dict {infoset: {action: regret_value}}
            
        Returns:
            Encoded table with int32 regret values
        """
        encoded_table = {}
        for infoset, action_regrets in regret_table.items():
            encoded_table[infoset] = self.encode_regrets(action_regrets)
        return encoded_table
    
    def decode_regret_table(self, encoded_table: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, float]]:
        """
        Decode an entire regret table back to float format.
        
        Args:
            encoded_table: Encoded table with int32 regret values
            
        Returns:
            Decoded table with float regret values
        """
        decoded_table = {}
        for infoset, action_regrets in encoded_table.items():
            decoded_table[infoset] = self.decode_regrets(action_regrets)
        return decoded_table
    
    def encode_strategy_table(self, strategy_table: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, int]]:
        """
        Encode strategy sums using int32 format.
        
        Strategy sums can be large (accumulated over many iterations) but don't
        need the same floor as regrets since they're always non-negative.
        
        Args:
            strategy_table: Nested dict {infoset: {action: strategy_sum}}
            
        Returns:
            Encoded table with int32 values
        """
        encoded_table = {}
        for infoset, action_strategies in strategy_table.items():
            encoded = {}
            for action, value in action_strategies.items():
                # Strategy sums are non-negative, no floor needed
                # Just clip to int32 range
                encoded[action] = int(np.clip(value, 0, np.iinfo(np.int32).max))
            encoded_table[infoset] = encoded
        return encoded_table
    
    def decode_strategy_table(self, encoded_table: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, float]]:
        """
        Decode strategy sums back to float format.
        
        Args:
            encoded_table: Encoded table with int32 values
            
        Returns:
            Decoded table with float values
        """
        decoded_table = {}
        for infoset, action_strategies in encoded_table.items():
            decoded = {}
            for action, value in action_strategies.items():
                decoded[action] = float(value)
            decoded_table[infoset] = decoded
        return decoded_table
    
    def get_memory_stats(self, regret_table: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """
        Calculate memory usage statistics for a regret table.
        
        Args:
            regret_table: Regret table to analyze
            
        Returns:
            Dictionary with memory usage statistics
        """
        # Count total values
        total_values = sum(len(actions) for actions in regret_table.values())
        num_infosets = len(regret_table)
        
        # Calculate memory usage
        # Assuming string keys are approximately 50 bytes each (infoset key)
        # and 20 bytes each for action keys
        key_memory_bytes = num_infosets * 50  # Infoset keys
        for actions in regret_table.values():
            key_memory_bytes += len(actions) * 20  # Action keys
        
        # Value memory
        float64_memory = total_values * 8  # 8 bytes per float64
        int32_memory = total_values * 4    # 4 bytes per int32
        
        # Total memory (keys + values)
        float64_total = key_memory_bytes + float64_memory
        int32_total = key_memory_bytes + int32_memory
        
        # Savings
        bytes_saved = float64_total - int32_total
        percent_saved = (bytes_saved / float64_total) * 100 if float64_total > 0 else 0
        
        return {
            'num_infosets': num_infosets,
            'total_values': total_values,
            'float64_bytes': float64_total,
            'int32_bytes': int32_total,
            'bytes_saved': bytes_saved,
            'percent_saved': percent_saved,
            'float64_mb': float64_total / (1024 * 1024),
            'int32_mb': int32_total / (1024 * 1024),
            'mb_saved': bytes_saved / (1024 * 1024)
        }


class CompactCheckpointWriter:
    """
    Writer for compact checkpoint format.
    
    Handles serialization of regret/strategy data using compact int32 encoding.
    """
    
    def __init__(self, encoder: Optional[CompactRegretEncoder] = None):
        """
        Initialize checkpoint writer.
        
        Args:
            encoder: Compact encoder to use (default: create new one)
        """
        self.encoder = encoder or CompactRegretEncoder()
    
    def prepare_checkpoint_data(
        self,
        regrets: Dict[str, Dict[str, float]],
        strategy_sum: Dict[str, Dict[str, float]],
        use_compact: bool = True
    ) -> Tuple[Dict, Dict[str, Any]]:
        """
        Prepare regret and strategy data for checkpointing.
        
        Args:
            regrets: Regret table
            strategy_sum: Strategy sum table
            use_compact: Whether to use compact int32 encoding
            
        Returns:
            Tuple of (checkpoint_data, metadata)
        """
        metadata = {
            'storage_format': 'int32_compact' if use_compact else 'float64',
            'regret_floor': self.encoder.regret_floor if use_compact else None,
        }
        
        if use_compact:
            # Encode to int32
            encoded_regrets = self.encoder.encode_regret_table(regrets)
            encoded_strategies = self.encoder.encode_strategy_table(strategy_sum)
            
            # Add memory stats to metadata
            mem_stats = self.encoder.get_memory_stats(regrets)
            metadata['memory_stats'] = mem_stats
            
            checkpoint_data = {
                'regrets': encoded_regrets,
                'strategy_sum': encoded_strategies
            }
        else:
            # Keep as float64
            checkpoint_data = {
                'regrets': regrets,
                'strategy_sum': strategy_sum
            }
        
        return checkpoint_data, metadata
    
    def load_checkpoint_data(
        self,
        checkpoint_data: Dict,
        metadata: Dict[str, Any]
    ) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
        """
        Load regret and strategy data from checkpoint.
        
        Args:
            checkpoint_data: Raw checkpoint data
            metadata: Checkpoint metadata
            
        Returns:
            Tuple of (regrets, strategy_sum) as float tables
        """
        storage_format = metadata.get('storage_format', 'float64')
        
        if storage_format == 'int32_compact':
            # Decode from int32
            regrets = self.encoder.decode_regret_table(checkpoint_data['regrets'])
            strategy_sum = self.encoder.decode_strategy_table(checkpoint_data['strategy_sum'])
        else:
            # Already float64
            regrets = checkpoint_data['regrets']
            strategy_sum = checkpoint_data['strategy_sum']
        
        return regrets, strategy_sum


def benchmark_encoding_latency(
    regret_table: Dict[str, Dict[str, float]],
    num_iterations: int = 100
) -> Dict[str, float]:
    """
    Benchmark encoding/decoding latency for compact storage.
    
    Args:
        regret_table: Sample regret table to benchmark
        num_iterations: Number of iterations for timing
        
    Returns:
        Dictionary with latency statistics in milliseconds
    """
    import time
    
    encoder = CompactRegretEncoder()
    
    # Benchmark encoding
    start_time = time.perf_counter()
    for _ in range(num_iterations):
        encoded = encoder.encode_regret_table(regret_table)
    encode_time = (time.perf_counter() - start_time) / num_iterations * 1000  # ms
    
    # Benchmark decoding
    encoded = encoder.encode_regret_table(regret_table)
    start_time = time.perf_counter()
    for _ in range(num_iterations):
        decoded = encoder.decode_regret_table(encoded)
    decode_time = (time.perf_counter() - start_time) / num_iterations * 1000  # ms
    
    return {
        'encode_ms': encode_time,
        'decode_ms': decode_time,
        'total_ms': encode_time + decode_time,
        'num_infosets': len(regret_table),
        'total_values': sum(len(actions) for actions in regret_table.values())
    }


def format_memory_report(stats: Dict[str, Any]) -> str:
    """
    Format memory statistics as a human-readable report.
    
    Args:
        stats: Memory statistics from get_memory_stats
        
    Returns:
        Formatted report string
    """
    lines = [
        "=" * 70,
        "COMPACT STORAGE MEMORY REPORT",
        "=" * 70,
        f"Infosets: {stats['num_infosets']:,}",
        f"Total values: {stats['total_values']:,}",
        "",
        "Memory Usage:",
        f"  float64 (standard): {stats['float64_mb']:.2f} MB",
        f"  int32 (compact):    {stats['int32_mb']:.2f} MB",
        f"  Savings:            {stats['mb_saved']:.2f} MB ({stats['percent_saved']:.1f}%)",
        "=" * 70
    ]
    return "\n".join(lines)
