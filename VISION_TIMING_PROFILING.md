# Vision Timing Profiling Guide

This document explains how to use the detailed vision timing profiling system to measure and analyze performance bottlenecks in the poker vision system.

## Overview

The vision timing profiling system provides detailed breakdowns of parsing times for all vision subsystems:

- **Pot OCR**: Time spent extracting pot amounts
- **Stacks OCR**: Time spent extracting player stack amounts (accumulated across all seats)
- **Bets OCR**: Time spent extracting player bet amounts (accumulated across all seats)
- **Names OCR**: Time spent extracting player names (accumulated across all seats)
- **Hero Cards**: Time spent recognizing hero's hole cards
- **Board Vision**: Time spent recognizing community cards
- **Parse State Building**: Time spent constructing the final TableState object

## Enabling Detailed Profiling

### Method 1: Command Line Flag

When running `run_dry_run.py` or `run_autoplay.py`, add the `--enable-detailed-vision-logs` flag:

```bash
# For dry run mode
python src/holdem/cli/run_dry_run.py \
    --profile configs/profiles/my_table.json \
    --policy data/strategies/my_strategy.dat \
    --buckets data/buckets/my_buckets.dat \
    --enable-detailed-vision-logs

# For auto-play mode
python src/holdem/cli/run_autoplay.py \
    --profile configs/profiles/my_table.json \
    --policy data/strategies/my_strategy.dat \
    --buckets data/buckets/my_buckets.dat \
    --enable-detailed-vision-logs \
    --i-understand-the-tos
```

### Method 2: Custom Log Directory

You can specify a custom directory for timing logs:

```bash
python src/holdem/cli/run_dry_run.py \
    --profile configs/profiles/my_table.json \
    --policy data/strategies/my_strategy.dat \
    --buckets data/buckets/my_buckets.dat \
    --enable-detailed-vision-logs \
    --vision-timing-log-dir /path/to/custom/log/dir
```

### Method 3: Configuration File

Edit `configs/vision_metrics_config.yaml`:

```yaml
vision_timing:
  enabled: true
  log_dir: "logs/vision_timing"
  log_filename: null  # Auto-generate timestamped filename
```

Then load and use the configuration in your code:

```python
import yaml
from holdem.vision.vision_timing import create_profiler

with open('configs/vision_metrics_config.yaml') as f:
    config = yaml.safe_load(f)

timing_config = config.get('vision_timing', {})
profiler = create_profiler(
    enabled=timing_config.get('enabled', False),
    log_dir=timing_config.get('log_dir'),
    log_filename=timing_config.get('log_filename')
)
```

## Log File Format

Timing logs are written in JSONL (JSON Lines) format to `logs/vision_timing/vision_timing_{timestamp}.jsonl`.

Each line in the log file is a JSON object representing one parse operation.

### Header Line

The first line is a header describing the log format:

```json
{
  "type": "header",
  "timestamp": "2025-11-15T17:27:21.123Z",
  "description": "Vision timing profiling log",
  "format": "JSONL (one JSON object per line)"
}
```

### Timing Record Lines

Subsequent lines are timing records for each parse:

```json
{
  "parse_id": 123,
  "timestamp": "2025-11-15T17:27:21.456Z",
  "mode": "full",
  "street": "FLOP",
  "hero_pos": 2,
  "button": 0,
  "t_total_parse_ms": 1998.0,
  "t_detect_table_ms": 5.2,
  "t_ocr_pot_ms": 3.1,
  "t_ocr_stacks_ms": 350.7,
  "t_ocr_bets_ms": 220.4,
  "t_ocr_names_ms": 15.2,
  "t_hero_cards_ms": 10.2,
  "t_board_vision_ms": 80.5,
  "t_chat_ocr_ms": 45.6,
  "t_chat_parse_ms": 8.3,
  "t_chat_validation_ms": 2.1,
  "t_event_fusion_ms": 2.7,
  "t_chat_enrichment_ms": 5.4,
  "t_build_parsed_state_ms": 1.5,
  "cache_hits": 12,
  "cache_misses": 3,
  "num_players": 6,
  "board_cards": 3
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `parse_id` | int | Unique sequential ID for this parse |
| `timestamp` | string | ISO 8601 timestamp when parse occurred |
| `mode` | string | Parse mode: "full" or "light" |
| `street` | string | Current poker street: "PREFLOP", "FLOP", "TURN", "RIVER" |
| `hero_pos` | int | Hero's position (0-5 for 6-max) |
| `button` | int | Button position (0-5 for 6-max) |
| `t_total_parse_ms` | float | Total parse time in milliseconds |
| `t_detect_table_ms` | float | Time for table detection / homography |
| `t_ocr_pot_ms` | float | Time for pot OCR |
| `t_ocr_stacks_ms` | float | Total time for all stacks OCR |
| `t_ocr_bets_ms` | float | Total time for all bets OCR |
| `t_ocr_names_ms` | float | Total time for all names OCR |
| `t_hero_cards_ms` | float | Time for hero card recognition |
| `t_board_vision_ms` | float | Time for board card recognition |
| `t_chat_ocr_ms` | float | Time for chat OCR |
| `t_chat_parse_ms` | float | Time for parsing chat lines |
| `t_chat_validation_ms` | float | Time for chat event validation |
| `t_event_fusion_ms` | float | Time for fusing vision + chat events |
| `t_chat_enrichment_ms` | float | Time for enriching state with chat |
| `t_build_parsed_state_ms` | float | Time for building TableState object |
| `cache_hits` | int | Number of cache hits during parse |
| `cache_misses` | int | Number of cache misses during parse |
| `num_players` | int | Number of players detected |
| `board_cards` | int | Number of community cards detected |

## Analyzing the Logs

### Using Python

Load and analyze the logs with Python:

```python
import json
import pandas as pd

# Load JSONL file
records = []
with open('logs/vision_timing/vision_timing_20251115_172721.jsonl') as f:
    for line in f:
        record = json.loads(line)
        if record.get('type') != 'header':
            records.append(record)

# Convert to DataFrame
df = pd.DataFrame(records)

# Analyze timing breakdowns
print("Average timing breakdown (ms):")
timing_cols = [col for col in df.columns if col.startswith('t_') and col != 't_total_parse_ms']
print(df[timing_cols].mean().sort_values(ascending=False))

# Find slowest parses
print("\nSlowest 10 parses:")
print(df.nlargest(10, 't_total_parse_ms')[['parse_id', 'street', 'mode', 't_total_parse_ms']])

# Compare full vs light parse
print("\nFull vs Light parse comparison:")
print(df.groupby('mode')['t_total_parse_ms'].agg(['mean', 'median', 'std']))

# Breakdown by street
print("\nTiming by street:")
print(df.groupby('street')['t_total_parse_ms'].agg(['mean', 'median']))
```

### Using Command Line Tools

Quick analysis with `jq`:

```bash
# Count total parses
cat logs/vision_timing/vision_timing_*.jsonl | grep -v '"type"' | wc -l

# Average total parse time
cat logs/vision_timing/vision_timing_*.jsonl | \
  jq -s 'map(select(.t_total_parse_ms)) | map(.t_total_parse_ms) | add/length'

# Average OCR stacks time
cat logs/vision_timing/vision_timing_*.jsonl | \
  jq -s 'map(select(.t_ocr_stacks_ms)) | map(.t_ocr_stacks_ms) | add/length'

# Find hotspots (top 5 time consumers on average)
cat logs/vision_timing/vision_timing_*.jsonl | \
  jq -s 'map(select(.parse_id)) | 
    [.[0] | to_entries | map(select(.key | startswith("t_") and . != "t_total_parse_ms")) | 
    .[] | {key, avg: ([.[].value] | add/length)}] | 
    sort_by(.avg) | reverse | .[0:5]'
```

## Performance Optimization Workflow

1. **Enable detailed profiling**: Run with `--enable-detailed-vision-logs`

2. **Collect data**: Let it run for at least 100-200 parses to get representative data

3. **Identify hotspots**: Analyze the logs to find which subsystems take the most time:
   ```python
   timing_cols = [col for col in df.columns if col.startswith('t_') and col != 't_total_parse_ms']
   print(df[timing_cols].mean().sort_values(ascending=False))
   ```

4. **Focus optimization**: Based on the analysis, optimize the slowest subsystems:
   - If `t_ocr_stacks_ms` is high: Consider better caching or ROI downscaling
   - If `t_board_vision_ms` is high: Optimize card recognition or use better templates
   - If `t_chat_ocr_ms` is high: Consider reducing chat parse frequency

5. **Measure improvement**: Re-run with profiling to verify optimizations worked

## Performance Impact

### When Disabled (Default)

The profiling system has **minimal overhead** when disabled:
- < 50ms for 1000 iterations
- Just a few boolean checks and null pointer checks
- No file I/O or timing measurements

### When Enabled

With profiling enabled, there is a small overhead:
- ~2-5% additional latency from `time.perf_counter()` calls
- Periodic file writes (buffered, minimal impact)
- Slightly increased memory usage for timing data

The overhead is acceptable for profiling sessions and should not significantly impact bot performance.

## Tips and Best Practices

1. **Run profiling sessions separately**: Don't leave profiling enabled during normal play

2. **Profile different scenarios**: Collect data for different game states (preflop, postflop, full table, heads-up)

3. **Compare configurations**: Profile with different cache settings, OCR backends, or performance configs

4. **Archive logs**: Keep timing logs from different versions to track performance improvements over time

5. **Automate analysis**: Create scripts to automatically analyze new log files and alert on regressions

## Troubleshooting

### Profiling not working

If timing logs are not being created:

1. Check that the flag is set: `--enable-detailed-vision-logs`
2. Verify the log directory exists and is writable
3. Check for import errors in the logs
4. Ensure `holdem.vision.vision_timing` module is available

### Log file not found

If you can't find the log file:

- Default location: `logs/vision_timing/`
- Check the console output for the actual path
- Use `--vision-timing-log-dir` to specify a custom path

### High overhead

If profiling causes significant slowdown:

- This is expected when profiling is enabled
- Reduce the profiling frequency by only enabling it periodically
- Use a faster disk for log writes (SSD recommended)

## See Also

- [VISION_METRICS_GUIDE.md](VISION_METRICS_GUIDE.md) - Aggregate metrics tracking
- [RUNTIME_CHECKLIST.md](RUNTIME_CHECKLIST.md) - Runtime requirements and checklist
- [VISION_OPTIMIZATION_GUIDE.md](VISION_OPTIMIZATION_GUIDE.md) - Performance optimization strategies
