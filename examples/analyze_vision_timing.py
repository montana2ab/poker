"""Example script demonstrating vision timing profiling analysis.

This script shows how to load and analyze vision timing logs to identify
performance bottlenecks.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def load_timing_logs(log_file: Path) -> list:
    """Load timing records from a JSONL file.
    
    Args:
        log_file: Path to the JSONL log file
        
    Returns:
        List of timing records (dicts)
    """
    records = []
    with open(log_file) as f:
        for line in f:
            record = json.loads(line)
            # Skip header
            if record.get('type') != 'header':
                records.append(record)
    return records


def analyze_timing_breakdown(records: list):
    """Analyze and display timing breakdown by component.
    
    Args:
        records: List of timing records
    """
    print("\n" + "="*80)
    print("TIMING BREAKDOWN ANALYSIS")
    print("="*80)
    
    # Collect all timing fields
    timing_fields = [k for k in records[0].keys() 
                     if k.startswith('t_') and k != 't_total_parse_ms']
    
    # Calculate statistics for each component
    stats = {}
    for field in timing_fields:
        values = [r[field] for r in records if field in r]
        if values:
            stats[field] = {
                'mean': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'total': sum(values),
                'count': len(values)
            }
    
    # Sort by mean time (descending)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['mean'], reverse=True)
    
    # Display results
    print(f"\nTotal parses analyzed: {len(records)}")
    print(f"\nComponents sorted by average time:\n")
    print(f"{'Component':<30} {'Mean (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12} {'Total (ms)':<12}")
    print("-" * 80)
    
    for field, data in sorted_stats:
        # Clean field name for display
        display_name = field.replace('t_', '').replace('_ms', '').replace('_', ' ').title()
        print(f"{display_name:<30} {data['mean']:>10.2f}   {data['min']:>10.2f}   "
              f"{data['max']:>10.2f}   {data['total']:>10.2f}")
    
    # Calculate percentage breakdown
    total_time = sum(data['total'] for data in stats.values())
    print(f"\n{'Component':<30} {'% of Total Time':<20}")
    print("-" * 50)
    for field, data in sorted_stats:
        display_name = field.replace('t_', '').replace('_ms', '').replace('_', ' ').title()
        percentage = (data['total'] / total_time * 100) if total_time > 0 else 0
        print(f"{display_name:<30} {percentage:>18.1f}%")


def analyze_by_mode(records: list):
    """Analyze timing differences between full and light parse modes.
    
    Args:
        records: List of timing records
    """
    print("\n" + "="*80)
    print("FULL vs LIGHT PARSE COMPARISON")
    print("="*80)
    
    # Group by mode
    by_mode = defaultdict(list)
    for record in records:
        mode = record.get('mode', 'unknown')
        by_mode[mode].append(record['t_total_parse_ms'])
    
    print(f"\n{'Mode':<15} {'Count':<10} {'Mean (ms)':<15} {'Min (ms)':<15} {'Max (ms)':<15}")
    print("-" * 70)
    
    for mode, times in sorted(by_mode.items()):
        count = len(times)
        mean = sum(times) / count
        min_time = min(times)
        max_time = max(times)
        print(f"{mode:<15} {count:<10} {mean:>13.2f}   {min_time:>13.2f}   {max_time:>13.2f}")


def analyze_by_street(records: list):
    """Analyze timing by poker street.
    
    Args:
        records: List of timing records
    """
    print("\n" + "="*80)
    print("TIMING BY STREET")
    print("="*80)
    
    # Group by street
    by_street = defaultdict(list)
    for record in records:
        street = record.get('street', 'UNKNOWN')
        by_street[street].append(record['t_total_parse_ms'])
    
    print(f"\n{'Street':<15} {'Count':<10} {'Mean (ms)':<15} {'Min (ms)':<15} {'Max (ms)':<15}")
    print("-" * 70)
    
    # Display in poker order
    street_order = ['PREFLOP', 'FLOP', 'TURN', 'RIVER', 'UNKNOWN']
    for street in street_order:
        if street in by_street:
            times = by_street[street]
            count = len(times)
            mean = sum(times) / count
            min_time = min(times)
            max_time = max(times)
            print(f"{street:<15} {count:<10} {mean:>13.2f}   {min_time:>13.2f}   {max_time:>13.2f}")


def find_slow_parses(records: list, top_n: int = 10):
    """Find and display the slowest parses.
    
    Args:
        records: List of timing records
        top_n: Number of slowest parses to show
    """
    print("\n" + "="*80)
    print(f"TOP {top_n} SLOWEST PARSES")
    print("="*80)
    
    # Sort by total time
    sorted_records = sorted(records, key=lambda r: r['t_total_parse_ms'], reverse=True)
    
    print(f"\n{'Parse ID':<10} {'Total (ms)':<15} {'Mode':<10} {'Street':<15} {'Players':<10}")
    print("-" * 60)
    
    for record in sorted_records[:top_n]:
        parse_id = record.get('parse_id', 'N/A')
        total = record.get('t_total_parse_ms', 0)
        mode = record.get('mode', 'unknown')
        street = record.get('street', 'UNKNOWN')
        players = record.get('num_players', 0)
        print(f"{parse_id:<10} {total:>13.2f}   {mode:<10} {street:<15} {players:<10}")


def main():
    """Main analysis function."""
    if len(sys.argv) < 2:
        print("Usage: python examples/analyze_vision_timing.py <log_file.jsonl>")
        print("\nExample:")
        print("  python examples/analyze_vision_timing.py logs/vision_timing/vision_timing_20251115_172721.jsonl")
        sys.exit(1)
    
    log_file = Path(sys.argv[1])
    
    if not log_file.exists():
        print(f"Error: Log file not found: {log_file}")
        sys.exit(1)
    
    print(f"Loading timing logs from: {log_file}")
    records = load_timing_logs(log_file)
    
    if not records:
        print("No timing records found in log file!")
        sys.exit(1)
    
    print(f"Loaded {len(records)} timing records")
    
    # Run analyses
    analyze_timing_breakdown(records)
    analyze_by_mode(records)
    analyze_by_street(records)
    find_slow_parses(records)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print("\nRecommendations:")
    print("1. Focus optimization on components with highest % of total time")
    print("2. Investigate slowest individual parses for anomalies")
    print("3. Compare full vs light parse performance to tune parse interval")
    print("4. Check if specific streets are consistently slower\n")


if __name__ == "__main__":
    main()
