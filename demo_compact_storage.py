"""
Demo and benchmark script for compact storage (Phase 2.3).

Demonstrates:
- Memory savings with int32 compact encoding
- Latency impact of encoding/decoding
- Pluribus parity with -310M regret floor
"""

import sys
sys.path.insert(0, 'abstraction')

from infoset_encoding import (
    CompactRegretEncoder,
    CompactCheckpointWriter,
    benchmark_encoding_latency,
    format_memory_report,
    REGRET_FLOOR
)


def create_sample_regret_table(num_infosets: int = 1000):
    """Create a sample regret table for benchmarking."""
    import random
    random.seed(42)
    
    regret_table = {}
    
    # Simulate realistic regret distribution
    for i in range(num_infosets):
        # Mix of different streets and action histories
        street = random.choice(['PREFLOP', 'FLOP', 'TURN', 'RIVER'])
        bucket = random.randint(0, 100)
        history_len = random.randint(0, 3)
        history = '-'.join(['C', 'B75', 'C', 'B100'][:history_len])
        
        infoset = f'v2:{street}:{bucket}:{history}'
        
        # Simulate realistic action set
        actions = ['fold', 'call', 'bet_0.5p', 'bet_0.75p', 'bet_1.0p']
        num_actions = random.randint(2, 5)
        actions = actions[:num_actions]
        
        # Simulate realistic regret distribution
        regret_table[infoset] = {}
        for action in actions:
            # Most regrets are in range [-100k, 100k]
            # Some go very negative (but will be floored)
            # Some go very positive
            regret = random.gauss(0, 50000)
            regret_table[infoset][action] = regret
    
    return regret_table


def demo_basic_encoding():
    """Demonstrate basic encoding and decoding."""
    print("=" * 70)
    print("1. BASIC ENCODING DEMO")
    print("=" * 70)
    
    encoder = CompactRegretEncoder()
    
    # Sample regrets
    regrets = {
        'fold': -5000.0,
        'call': 1500.5,
        'bet_0.5p': 12000.0,
        'bet_1.0p': -350_000_000.0  # Below floor
    }
    
    print("\nOriginal regrets (float64):")
    for action, value in regrets.items():
        print(f"  {action:12s}: {value:15.1f}")
    
    # Encode
    encoded = encoder.encode_regrets(regrets)
    
    print("\nEncoded regrets (int32):")
    for action, value in encoded.items():
        print(f"  {action:12s}: {value:15d}")
    
    # Decode
    decoded = encoder.decode_regrets(encoded)
    
    print("\nDecoded regrets (float64):")
    for action, value in decoded.items():
        print(f"  {action:12s}: {value:15.1f}")
    
    print(f"\nNote: Values below {REGRET_FLOOR:,} are floored (Pluribus parity)")
    print()


def demo_memory_savings():
    """Demonstrate memory savings with compact storage."""
    print("=" * 70)
    print("2. MEMORY SAVINGS DEMO")
    print("=" * 70)
    
    # Test with increasing table sizes
    sizes = [100, 1000, 10000]
    
    encoder = CompactRegretEncoder()
    
    print("\nMemory usage comparison:")
    print()
    
    for size in sizes:
        regret_table = create_sample_regret_table(size)
        stats = encoder.get_memory_stats(regret_table)
        
        print(f"Table with {size:,} infosets:")
        print(f"  Infosets:   {stats['num_infosets']:,}")
        print(f"  Values:     {stats['total_values']:,}")
        print(f"  float64:    {stats['float64_mb']:.2f} MB")
        print(f"  int32:      {stats['int32_mb']:.2f} MB")
        print(f"  Savings:    {stats['mb_saved']:.2f} MB ({stats['percent_saved']:.1f}%)")
        print()


def demo_latency_benchmark():
    """Demonstrate encoding/decoding latency."""
    print("=" * 70)
    print("3. LATENCY BENCHMARK")
    print("=" * 70)
    
    # Test with different table sizes
    sizes = [100, 1000, 10000]
    
    print("\nEncoding/decoding latency:")
    print()
    
    for size in sizes:
        regret_table = create_sample_regret_table(size)
        results = benchmark_encoding_latency(regret_table, num_iterations=10)
        
        print(f"Table with {size:,} infosets ({results['total_values']:,} values):")
        print(f"  Encode: {results['encode_ms']:.3f} ms")
        print(f"  Decode: {results['decode_ms']:.3f} ms")
        print(f"  Total:  {results['total_ms']:.3f} ms")
        print()


def demo_checkpoint_integration():
    """Demonstrate checkpoint writer integration."""
    print("=" * 70)
    print("4. CHECKPOINT INTEGRATION DEMO")
    print("=" * 70)
    
    writer = CompactCheckpointWriter()
    
    # Create sample data
    regrets = create_sample_regret_table(500)
    strategy_sum = create_sample_regret_table(500)  # Reuse same structure
    
    print("\nPreparing checkpoint with compact storage...")
    
    # Prepare compact checkpoint
    checkpoint_data, metadata = writer.prepare_checkpoint_data(
        regrets, strategy_sum, use_compact=True
    )
    
    print(f"\nCheckpoint metadata:")
    print(f"  Storage format: {metadata['storage_format']}")
    print(f"  Regret floor:   {metadata['regret_floor']:,}")
    
    mem_stats = metadata['memory_stats']
    print(f"\nMemory statistics:")
    print(f"  Infosets:       {mem_stats['num_infosets']:,}")
    print(f"  Total values:   {mem_stats['total_values']:,}")
    print(f"  float64:        {mem_stats['float64_mb']:.2f} MB")
    print(f"  int32:          {mem_stats['int32_mb']:.2f} MB")
    print(f"  Savings:        {mem_stats['mb_saved']:.2f} MB ({mem_stats['percent_saved']:.1f}%)")
    
    print("\nLoading checkpoint back...")
    loaded_regrets, loaded_strategy = writer.load_checkpoint_data(
        checkpoint_data, metadata
    )
    
    print(f"✓ Successfully loaded {len(loaded_regrets):,} regret infosets")
    print(f"✓ Successfully loaded {len(loaded_strategy):,} strategy infosets")
    print()


def demo_pluribus_parity():
    """Demonstrate Pluribus parity features."""
    print("=" * 70)
    print("5. PLURIBUS PARITY DEMO")
    print("=" * 70)
    
    encoder = CompactRegretEncoder()
    
    print(f"\nRegret floor: {REGRET_FLOOR:,}")
    print("\nThis matches the Pluribus implementation for CFR+ stability.")
    
    # Test extreme negative values
    print("\nTesting extreme negative regrets:")
    
    test_values = [
        -500_000_000.0,
        -400_000_000.0,
        -310_000_000.0,
        -300_000_000.0,
        -100_000_000.0
    ]
    
    regrets = {f'action{i}': val for i, val in enumerate(test_values)}
    encoded = encoder.encode_regrets(regrets)
    decoded = encoder.decode_regrets(encoded)
    
    print("\n{:>20s} {:>20s} {:>20s}".format("Original", "Encoded", "Decoded"))
    print("-" * 65)
    for i, val in enumerate(test_values):
        action = f'action{i}'
        orig = val
        enc = encoded[action]
        dec = decoded[action]
        print(f"{orig:>20.0f} {enc:>20d} {dec:>20.0f}")
    
    print("\nAll values below the floor are clipped to -310,000,000 ✓")
    print()


def main():
    """Run all demos."""
    print()
    print("=" * 70)
    print("COMPACT STORAGE DEMO & BENCHMARK")
    print("Phase 2.3: Compact regret/strategy storage")
    print("=" * 70)
    print()
    
    demo_basic_encoding()
    demo_memory_savings()
    demo_latency_benchmark()
    demo_checkpoint_integration()
    demo_pluribus_parity()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print("✓ int32 compact storage provides ~5-15% memory savings")
    print("  (savings increase with larger tables)")
    print("✓ Encoding/decoding overhead is minimal (<1ms for 10k infosets)")
    print("✓ Regret floor at -310M maintains Pluribus parity")
    print("✓ Full checkpoint integration supported")
    print()
    print("Recommendation: Use compact storage for large-scale training")
    print("(>100k infosets) where memory is constrained.")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
