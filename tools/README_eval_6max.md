# tools/eval_6max.py

A standalone 6-max poker policy evaluation tool (Pluribus-style).

## Overview

Evaluates a trained poker policy against baseline agents with:
- Duplicate deals + seat rotation for variance reduction
- bb/100 statistics globally and per position with 95% confidence intervals
- Support for 2-6 players (focus on 6-max)
- Multiprocessing for performance
- Atomic JSON and CSV output
- No external dependencies beyond numpy and stdlib

## Installation

No installation required beyond Python 3.12+ and numpy:

```bash
pip install numpy
```

## Usage

### Basic Usage

```bash
python tools/eval_6max.py --policy path/to/policy.json --hands 200000
```

### Advanced Options

```bash
python tools/eval_6max.py \
  --policy runs/training/avg_policy.json \
  --hands 500000 \
  --seed 42 \
  --output runs/eval_6max \
  --num-players 6 \
  --duplicate 3 \
  --rotate-seats \
  --workers 8
```

### Key Arguments

**Required:**
- `--policy PATH`: Path to policy file (`.json` or `.pkl`)

**Optional:**
- `--hands INT`: Number of deals (default: 200000)
- `--seed INT`: Random seed for deterministic results (default: 42)
- `--output DIR`: Output directory (default: runs/eval_6max)
- `--num-players {2,3,4,5,6}`: Number of players (default: 6)
- `--baselines preset|paths`: Baseline opponents (default: preset pool)
- `--duplicate INT`: Duplications per deal (default: 2)
- `--rotate-seats` / `--no-rotate-seats`: Rotate policy through positions
- `--workers INT`: Parallel workers (default: cpu_count - 1)
- `--quiet`: Minimal logging
- `--no-csv` / `--no-json`: Disable specific outputs

## Policy Format

### JSON Format

```json
{
  "policy": {
    "infoset_1": {
      "fold": 0.3,
      "check_call": 0.5,
      "bet_0.5p": 0.2
    }
  },
  "metadata": {
    "bucket_hash": "...",
    "num_players": 6,
    "config_digest": "..."
  }
}
```

### Pickle Format

Checkpoint files (`.pkl`) with:
- `strategy_sum`: Dict mapping infosets to action counts
- `avg_strategy`: Pre-normalized average strategy
- `policy`: Direct policy dictionary
- `metadata`: Optional metadata

## Baseline Agents

The tool includes 5 preset baseline agents:

1. **random**: Plays randomly among legal actions
2. **tight**: Folds 70% when facing bets, otherwise calls
3. **loose**: Rarely folds (20%), bets/raises frequently (40%)
4. **balanced**: Folds 40%, bets 30%, otherwise calls
5. **callish**: Calls frequently, rarely folds (15%) or raises (10%)

## Output

### JSON Output

`summary.json` contains:
- Configuration (num_players, hands, seed, etc.)
- Policy metadata
- Global statistics (bb/100, CI95, stdev, n, significance)
- Per-position statistics (BTN, SB, BB, UTG, MP, CO)
- Performance metrics (elapsed_seconds, hands_per_second)

Example:
```json
{
  "results": {
    "global": {
      "bb_per_100": 3.85,
      "ci95": 0.90,
      "stdev": 0.62,
      "n": 1200000,
      "significant": true
    },
    "by_position": {
      "BTN": {"bb_per_100": 7.1, "ci95": 1.8, "n": 200000},
      "SB": {"bb_per_100": -14.2, "ci95": 2.3, "n": 200000}
    }
  }
}
```

### CSV Output

Two CSV files are generated:

1. **eval_6max_runs.csv**: One row per evaluation run
   - Columns: timestamp, policy, num_players, hands, bb_per_100, ci95, etc.

2. **eval_6max_positions.csv**: Per-position statistics
   - Columns: timestamp, policy, position, bb_per_100, ci95, stdev, n

## Features

### Duplicate Deals

Specify `--duplicate N` to play each deal N times with different random seeds. This reduces variance while keeping the same board/hole cards structure.

### Seat Rotation

With `--rotate-seats` (default), the policy is rotated through all positions (BTN, SB, BB, UTG, MP, CO) for each deal. This provides balanced statistics across positions.

### Multiprocessing

Use `--workers N` to parallelize simulation across N processes. The tool automatically sets single-threaded BLAS environment variables to avoid thread contention.

### Atomic Writes

All output files are written atomically (temp file + rename) to prevent corruption if interrupted.

### Bucket Mismatch Detection

If the policy metadata indicates a different `num_players` than specified with `--num-players`, the tool exits with code 2 (unless `--no-fail-on-bucket-mismatch` is used).

## Self-Tests

Run integrated self-tests:

```bash
python tools/eval_6max.py --self-test
```

Tests include:
1. Deterministic evaluation (same seed → same results)
2. Duplicate variance reduction
3. Seat rotation produces all positions

## Performance

On M2 MacBook Pro:
- ~30,000-50,000 hands/second (single worker)
- Scales well with multiprocessing
- 200,000 deals (1.2M hands) in ~30-60 seconds

## Exit Codes

- `0`: Success
- `2`: Bucket mismatch (num_players)
- `3`: I/O error (file not found, read/write failed)
- `4`: Invalid arguments

## Limitations

This is a simplified evaluation framework:
- Uses basic hand evaluation (not full poker hand ranking)
- Baseline agents don't query the policy (use hardcoded strategies)
- No real-time resolving (RT) - placeholder only
- No action translator - uses default mapping

For production use with trained policies, integrate with the full poker evaluation framework.

## Examples

### Quick Test (100 hands)

```bash
python tools/eval_6max.py \
  --policy test_policy.json \
  --hands 100 \
  --workers 1 \
  --output /tmp/quick_test
```

### Full Evaluation (500k hands, 8 workers)

```bash
python tools/eval_6max.py \
  --policy runs/training/checkpoint_final.pkl \
  --hands 500000 \
  --seed 42 \
  --workers 8 \
  --output runs/eval_production
```

### Head-Up Evaluation

```bash
python tools/eval_6max.py \
  --policy hu_policy.json \
  --num-players 2 \
  --hands 200000 \
  --no-fail-on-bucket-mismatch
```

### Custom Baselines

```bash
python tools/eval_6max.py \
  --policy my_policy.json \
  --baselines baseline1.json,baseline2.json,baseline3.json \
  --hands 200000
```

## License

Same as parent project.
