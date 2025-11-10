# Poker AI Evaluation Tools

This directory contains standalone tools for evaluating and analyzing poker AI policies.

## Available Tools

### eval_h2h.py - Head-to-Head Policy Evaluation

Evaluates the relative strength of two poker policies in heads-up matches using duplicate deals and position swapping.

#### Features

- **Duplicate deals**: Each deal is played twice with swapped positions for unbiased evaluation
- **Position swapping**: Ensures fair comparison by eliminating positional bias
- **Statistical rigor**: 95% confidence intervals using bootstrap method
- **Multiple formats**: Console statistics, JSON, and CSV outputs
- **Policy flexibility**: Supports both JSON (avg_policy.json) and PKL checkpoint files
- **Auto-export**: Automatically converts .pkl checkpoints to JSON when needed
- **Pure Python**: Only requires numpy + stdlib (no eval7 or other game engine dependencies)

#### Usage

```bash
# Basic usage: evaluate two policies with default settings
python tools/eval_h2h.py policy_a.json policy_b.json --hands 1000

# Use pickle checkpoints with custom output directory
python tools/eval_h2h.py checkpoint_a.pkl checkpoint_b.pkl --hands 5000 --output results/

# Change blinds and random seed
python tools/eval_h2h.py policy_a.json policy_b.json --hands 2000 --sb 0.5 --bb 1.0 --seed 123

# Suppress progress output and skip CSV
python tools/eval_h2h.py policy_a.json policy_b.json --hands 1000 --quiet --no-csv
```

#### Arguments

- `policy_a`: Path to policy A (JSON or PKL file)
- `policy_b`: Path to policy B (JSON or PKL file)
- `--hands N`: Number of hand pairs to play (default: 1000, total hands = 2*N)
- `--sb AMOUNT`: Small blind amount (default: 1.0)
- `--bb AMOUNT`: Big blind amount (default: 2.0)
- `--seed SEED`: Random seed for reproducibility (default: 42)
- `--output DIR`: Output directory for results (default: current directory)
- `--no-json`: Do not save JSON results
- `--no-csv`: Do not save CSV results
- `--quiet`: Suppress progress output

#### Output

The script produces three output files (unless disabled):

1. **JSON file**: Complete evaluation results including all hand details
   - Configuration (blinds, seed, hands)
   - Individual hand results
   - Statistical summary

2. **CSV file**: Detailed hand-by-hand results
   - hand_id, position_a, chips_won_a, chips_won_b, deal_hash

3. **Summary CSV**: Statistical summary only
   - Winrate (bb/100)
   - 95% confidence intervals
   - Win rates
   - Chip statistics

#### Console Output Example

```
============================================================
Running heads-up evaluation: policy_a vs policy_b
============================================================
Hand pairs (duplicate deals): 1000
Total hands to play: 2000
Blinds: 1.0/2.0
Random seed: 42

Progress: 100/1000 hand pairs completed
Progress: 200/1000 hand pairs completed
...

Completed 2000 hands (1000 duplicate pairs)

============================================================
EVALUATION RESULTS
============================================================

Policy A: policy_a
Policy B: policy_b

Total hands played: 2000
Duplicate deal pairs: 1000

Winrate (Policy A):
  bb/100:     +3.25
  95% CI:     [+1.12, +5.38]
  Margin:     ±2.13 bb/100

Chip statistics:
  Mean chips: +0.0650
  Std dev:    1.3421

Win rates:
  Policy A:   52.3%
  Policy B:   47.7%

Conclusion: Policy A is statistically significantly better (95% CI)
============================================================
```

#### Interpretation

- **bb/100**: Big blinds won per 100 hands (positive = Policy A winning)
- **95% CI**: If this interval doesn't contain zero, the difference is statistically significant
- **Margin**: Half-width of confidence interval (smaller = more precise estimate)
- **Win rates**: Percentage of hands won by each policy

#### Technical Details

**Duplicate Deals**
Each hand is played twice:
1. Policy A as small blind vs Policy B as big blind
2. Policy B as small blind vs Policy A as big blind (same cards)

This eliminates luck variance from card distribution and provides a more accurate strength comparison.

**Simplified Poker Simulator**
The script uses a simplified heads-up poker simulator that doesn't require external libraries like eval7. While not a full poker engine with complete betting rounds, it's sufficient for comparing policy strength through hand evaluation.

For production-level evaluation, consider integrating with the full MCCFR game tree implementation in `src/holdem/mccfr/`.

**Bootstrap Confidence Intervals**
The 95% confidence intervals are computed using the bootstrap method with 10,000 resamples. This provides non-parametric estimates that don't assume normal distribution of results.

#### Compatibility

- Python 3.12+
- macOS M2 (also works on Linux and Windows)
- Dependencies: numpy only

#### Testing

Run the test suite:
```bash
python tests/test_eval_h2h.py
```

Or using pytest (if installed):
```bash
pytest tests/test_eval_h2h.py -v
```

## Future Tools

Additional evaluation and analysis tools may be added here, such as:
- Exploitability calculation
- Policy visualization
- Tournament-style multi-policy evaluation
- Hand history analysis
