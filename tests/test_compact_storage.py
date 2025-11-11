"""
Tests for compact infoset encoding (int32 storage with Pluribus parity).

Tests Phase 2.3: Compact storage of regrets/strategies
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

import numpy as np
from abstraction.infoset_encoding import (
    CompactRegretEncoder,
    CompactCheckpointWriter,
    benchmark_encoding_latency,
    format_memory_report,
    REGRET_FLOOR
)


def test_encode_decode_basic():
    """Test basic encoding and decoding of regret values."""
    encoder = CompactRegretEncoder()
    
    # Test basic values
    regrets = {
        'fold': 0.0,
        'call': 1500.5,
        'bet_0.5p': -5000.0,
        'bet_1.0p': 100000.0
    }
    
    # Encode
    encoded = encoder.encode_regrets(regrets)
    assert all(isinstance(v, (int, np.integer)) for v in encoded.values())
    
    # Decode
    decoded = encoder.decode_regrets(encoded)
    
    # Check values are close (may have rounding)
    assert abs(decoded['fold'] - 0.0) < 1.0
    assert abs(decoded['call'] - 1500.5) < 1.0
    assert abs(decoded['bet_0.5p'] - (-5000.0)) < 1.0
    assert abs(decoded['bet_1.0p'] - 100000.0) < 1.0


def test_regret_floor():
    """Test that regret floor is applied correctly."""
    encoder = CompactRegretEncoder()
    
    # Test values below floor
    regrets = {
        'action1': -400_000_000.0,  # Below floor
        'action2': -310_000_000.0,  # At floor
        'action3': -300_000_000.0,  # Above floor
    }
    
    encoded = encoder.encode_regrets(regrets)
    decoded = encoder.decode_regrets(encoded)
    
    # Values below floor should be floored
    assert decoded['action1'] == REGRET_FLOOR
    assert decoded['action2'] == REGRET_FLOOR
    assert decoded['action3'] == -300_000_000.0


def test_large_positive_regrets():
    """Test handling of large positive regret values."""
    encoder = CompactRegretEncoder()
    
    regrets = {
        'action1': 1_000_000.0,
        'action2': 50_000_000.0,
        'action3': 2_000_000_000.0,  # 2 billion (within int32 range)
    }
    
    encoded = encoder.encode_regrets(regrets)
    decoded = encoder.decode_regrets(encoded)
    
    # Check values are preserved
    assert abs(decoded['action1'] - 1_000_000.0) < 1.0
    assert abs(decoded['action2'] - 50_000_000.0) < 1.0
    assert abs(decoded['action3'] - 2_000_000_000.0) < 1.0


def test_encode_decode_table():
    """Test encoding/decoding full regret tables."""
    encoder = CompactRegretEncoder()
    
    # Create sample regret table
    regret_table = {
        'v2:PREFLOP:5:': {
            'fold': -1000.0,
            'call': 500.0,
            'bet_0.5p': 2000.0
        },
        'v2:FLOP:12:C': {
            'fold': 0.0,
            'call': 1500.0,
            'bet_0.75p': -3000.0
        },
        'v2:TURN:42:C-B75': {
            'fold': -5000.0,
            'call': 0.0,
            'bet_1.0p': 10000.0,
            'all_in': 50000.0
        }
    }
    
    # Encode table
    encoded_table = encoder.encode_regret_table(regret_table)
    
    # Check structure is preserved
    assert len(encoded_table) == len(regret_table)
    assert set(encoded_table.keys()) == set(regret_table.keys())
    
    # Decode table
    decoded_table = encoder.decode_regret_table(encoded_table)
    
    # Check values are close
    for infoset in regret_table:
        for action in regret_table[infoset]:
            original = regret_table[infoset][action]
            decoded = decoded_table[infoset][action]
            assert abs(decoded - original) < 1.0, f"Mismatch for {infoset}:{action}"


def test_strategy_table_encoding():
    """Test encoding/decoding strategy sum tables."""
    encoder = CompactRegretEncoder()
    
    # Strategy sums are always non-negative
    strategy_table = {
        'v2:PREFLOP:5:': {
            'fold': 100.0,
            'call': 500.0,
            'bet_0.5p': 2000.0
        },
        'v2:FLOP:12:C': {
            'fold': 50.0,
            'call': 1500.0,
            'bet_0.75p': 3000.0
        }
    }
    
    # Encode
    encoded = encoder.encode_strategy_table(strategy_table)
    
    # Decode
    decoded = encoder.decode_strategy_table(encoded)
    
    # Check values
    for infoset in strategy_table:
        for action in strategy_table[infoset]:
            original = strategy_table[infoset][action]
            decoded_val = decoded[infoset][action]
            assert abs(decoded_val - original) < 1.0


def test_memory_stats():
    """Test memory usage statistics calculation."""
    encoder = CompactRegretEncoder()
    
    # Create sample regret table
    regret_table = {
        f'v2:FLOP:{i}:C-B75': {
            'fold': -1000.0 * i,
            'call': 500.0 * i,
            'bet_0.5p': 2000.0 * i,
            'bet_1.0p': 5000.0 * i
        }
        for i in range(100)  # 100 infosets
    }
    
    # Get stats
    stats = encoder.get_memory_stats(regret_table)
    
    # Check stats are reasonable
    assert stats['num_infosets'] == 100
    assert stats['total_values'] == 400  # 100 infosets * 4 actions
    assert stats['float64_bytes'] > stats['int32_bytes']
    assert stats['percent_saved'] > 0
    assert stats['percent_saved'] < 100
    
    # Memory reduction depends on key overhead vs value storage
    # For small tables with many short keys, savings will be less
    # For large tables with many values, savings approach 50%
    assert 5 < stats['percent_saved'] < 60  # Reasonable range including key overhead


def test_checkpoint_writer():
    """Test compact checkpoint writer."""
    writer = CompactCheckpointWriter()
    
    regrets = {
        'v2:PREFLOP:5:': {
            'fold': -1000.0,
            'call': 500.0
        },
        'v2:FLOP:12:C': {
            'fold': 0.0,
            'call': 1500.0
        }
    }
    
    strategy_sum = {
        'v2:PREFLOP:5:': {
            'fold': 100.0,
            'call': 500.0
        },
        'v2:FLOP:12:C': {
            'fold': 50.0,
            'call': 1500.0
        }
    }
    
    # Test compact format
    checkpoint_data, metadata = writer.prepare_checkpoint_data(
        regrets, strategy_sum, use_compact=True
    )
    
    assert metadata['storage_format'] == 'int32_compact'
    assert metadata['regret_floor'] == REGRET_FLOOR
    assert 'memory_stats' in metadata
    
    # Load back
    loaded_regrets, loaded_strategy = writer.load_checkpoint_data(
        checkpoint_data, metadata
    )
    
    # Check values are preserved
    for infoset in regrets:
        for action in regrets[infoset]:
            assert abs(loaded_regrets[infoset][action] - regrets[infoset][action]) < 1.0


def test_checkpoint_writer_float64():
    """Test checkpoint writer with float64 format (no compression)."""
    writer = CompactCheckpointWriter()
    
    regrets = {
        'v2:PREFLOP:5:': {'fold': -1000.0, 'call': 500.0}
    }
    strategy_sum = {
        'v2:PREFLOP:5:': {'fold': 100.0, 'call': 500.0}
    }
    
    # Test float64 format
    checkpoint_data, metadata = writer.prepare_checkpoint_data(
        regrets, strategy_sum, use_compact=False
    )
    
    assert metadata['storage_format'] == 'float64'
    assert metadata['regret_floor'] is None
    
    # Load back
    loaded_regrets, loaded_strategy = writer.load_checkpoint_data(
        checkpoint_data, metadata
    )
    
    # Check exact preservation
    assert loaded_regrets == regrets
    assert loaded_strategy == strategy_sum


def test_encoding_latency_benchmark():
    """Test latency benchmarking for encoding/decoding."""
    # Create sample data
    regret_table = {
        f'v2:FLOP:{i}:C': {
            'fold': -1000.0,
            'call': 500.0,
            'bet_0.5p': 2000.0
        }
        for i in range(50)  # Small table for fast test
    }
    
    # Run benchmark
    results = benchmark_encoding_latency(regret_table, num_iterations=10)
    
    # Check results structure
    assert 'encode_ms' in results
    assert 'decode_ms' in results
    assert 'total_ms' in results
    assert 'num_infosets' in results
    assert 'total_values' in results
    
    # Check reasonable values
    assert results['num_infosets'] == 50
    assert results['total_values'] == 150  # 50 * 3
    assert results['encode_ms'] > 0
    assert results['decode_ms'] > 0
    assert results['total_ms'] == results['encode_ms'] + results['decode_ms']


def test_format_memory_report():
    """Test memory report formatting."""
    stats = {
        'num_infosets': 1000,
        'total_values': 4000,
        'float64_mb': 10.5,
        'int32_mb': 5.2,
        'mb_saved': 5.3,
        'percent_saved': 50.5
    }
    
    report = format_memory_report(stats)
    
    # Check report contains key information
    assert '1,000' in report
    assert '4,000' in report
    assert '10.5' in report or '10.50' in report
    assert '5.2' in report or '5.20' in report
    assert '50.5%' in report or '50.5 %' in report
    assert 'MEMORY REPORT' in report


def test_zero_regrets():
    """Test handling of zero regret values."""
    encoder = CompactRegretEncoder()
    
    regrets = {
        'action1': 0.0,
        'action2': 0.0,
        'action3': 0.0
    }
    
    encoded = encoder.encode_regrets(regrets)
    decoded = encoder.decode_regrets(encoded)
    
    for action in regrets:
        assert decoded[action] == 0.0


def test_fractional_regrets():
    """Test handling of fractional regret values."""
    encoder = CompactRegretEncoder()
    
    regrets = {
        'action1': 123.456,
        'action2': -789.123,
        'action3': 0.999
    }
    
    encoded = encoder.encode_regrets(regrets)
    decoded = encoder.decode_regrets(encoded)
    
    # Should have rounding to nearest integer
    assert abs(decoded['action1'] - 123.0) <= 1.0
    assert abs(decoded['action2'] - (-789.0)) <= 1.0
    assert abs(decoded['action3'] - 1.0) <= 1.0  # 0.999 rounds to 1


def test_pluribus_parity():
    """Test that regret floor matches Pluribus implementation."""
    encoder = CompactRegretEncoder()
    
    # Pluribus uses -310,000,000 as the floor
    assert encoder.regret_floor == -310_000_000
    
    # Test that extremely negative regrets are floored
    regrets = {
        'action1': -1_000_000_000.0,  # Way below floor
    }
    
    encoded = encoder.encode_regrets(regrets)
    decoded = encoder.decode_regrets(encoded)
    
    assert decoded['action1'] == -310_000_000.0


def test_int32_range_limits():
    """Test behavior at int32 range limits."""
    encoder = CompactRegretEncoder()
    
    # int32 max is 2,147,483,647
    regrets = {
        'action1': 2_147_483_647.0,  # Max int32
        'action2': 2_147_483_648.0,  # Above max int32 (should be clipped)
    }
    
    encoded = encoder.encode_regrets(regrets)
    decoded = encoder.decode_regrets(encoded)
    
    # Both should be at or near int32 max
    assert decoded['action1'] >= 2_147_483_000.0  # Close to max
    assert decoded['action2'] >= 2_147_483_000.0  # Clipped to max


if __name__ == "__main__":
    print("Running compact storage tests...")
    
    test_encode_decode_basic()
    print("✓ test_encode_decode_basic")
    
    test_regret_floor()
    print("✓ test_regret_floor")
    
    test_large_positive_regrets()
    print("✓ test_large_positive_regrets")
    
    test_encode_decode_table()
    print("✓ test_encode_decode_table")
    
    test_strategy_table_encoding()
    print("✓ test_strategy_table_encoding")
    
    test_memory_stats()
    print("✓ test_memory_stats")
    
    test_checkpoint_writer()
    print("✓ test_checkpoint_writer")
    
    test_checkpoint_writer_float64()
    print("✓ test_checkpoint_writer_float64")
    
    test_encoding_latency_benchmark()
    print("✓ test_encoding_latency_benchmark")
    
    test_format_memory_report()
    print("✓ test_format_memory_report")
    
    test_zero_regrets()
    print("✓ test_zero_regrets")
    
    test_fractional_regrets()
    print("✓ test_fractional_regrets")
    
    test_pluribus_parity()
    print("✓ test_pluribus_parity")
    
    test_int32_range_limits()
    print("✓ test_int32_range_limits")
    
    print("\n" + "=" * 70)
    print("All compact storage tests passed! ✨")
    print("=" * 70)
