# Enhanced RT vs Blueprint Evaluation - Complete Guide

## Overview

This document describes the enhanced RT vs Blueprint evaluation system that implements comprehensive statistical analysis, paired bootstrap, stratification, and telemetry tracking for poker AI evaluation.

## Key Features

### 1. Paired Bootstrap with Stratification

**Paired Bootstrap**: Uses identical deals (hands and boards) for both RT search and blueprint strategy evaluation. This reduces variance by eliminating deal-to-deal variation.

**Stratification**: Distributes hands across:
- **6 Positions**: BTN, SB, BB, UTG, MP, CO
- **3 Streets**: FLOP, TURN, RIVER

This ensures balanced representation across all strategic situations.

### 2. Multi-Seed Evaluation

Supports running evaluation with multiple random seeds and aggregating results:
- Recommended: ≥3 seeds × 5,000 hands = 15,000+ total hands
- Validates stability of results across different random samples
- Aggregates statistics across all seeds

### 3. KL Divergence Tracking

Monitors how much RT search deviates from blueprint strategy:
- **Per-position KL statistics** (BTN/SB/BB/UTG/MP/CO)
- **Per-street KL statistics** (FLOP/TURN/RIVER)
- **Expected range**: p50 KL ∈ [0.05, 0.25]
- Lower KL indicates closer adherence to blueprint
- Higher KL indicates more exploration/improvement

### 4. Comprehensive Telemetry

Tracks detailed metrics for each hand:
- **Latency**: RT decision time (mean, p50, p95, p99)
- **Fallback rate**: How often RT falls back to blueprint
- **Iterations per decision**: MCCFR iterations completed
- **Nodes expanded**: Search tree size

### 5. Adaptive Time Budget

**Strict Budget Mode** (`--strict-budget`):
- Enforces p95 latency ≤ 110ms
- Dynamically reduces samples when budget exceeded
- Per-street sample configuration (e.g., flop=16, turn=32, river=64)

### 6. Anti-Bias Controls

- **Frozen blueprint policy**: No learning during evaluation
- **Paired RNG**: Deterministic random number generation per seed
- **Placebo test capability**: Shuffle labels to verify EVΔ ≈ 0

### 7. AIVAT Variance Reduction

Optional AIVAT (Actor-Independent Variance-reduced Advantage Technique):
- Learns baseline value functions during warm-up
- Reduces evaluation variance by 30-95%
- Maintains unbiased estimates
- Enables faster convergence to confidence intervals

### 8. Enriched Output

**JSON Output** includes:
```json
{
  "commit_hash": "abcd1234",
  "config_hash": "config123",
  "blueprint_hash": "bp456",
  "seeds": [42, 1337, 2025],
  "total_hands": 15000,
  "bootstrap_reps": 2000,
  
  "ev_delta_bb100": 3.45,
  "ci_lower": 1.23,
  "ci_upper": 5.67,
  "is_significant": true,
  "p_value": 0.0012,
  
  "by_position": {
    "BTN": {"ev_delta_bb100": 4.2, "ci_lower": 2.1, ...},
    "SB": {"ev_delta_bb100": 2.8, ...},
    ...
  },
  
  "by_street": {
    "FLOP": {"ev_delta_bb100": 3.5, "p95_latency_ms": 95.2, ...},
    "TURN": {"ev_delta_bb100": 3.3, ...},
    ...
  },
  
  "latency": {
    "mean": 85.2,
    "p50": 78.5,
    "p95": 105.3,
    "p99": 142.1,
    "fallback_rate": 0.023
  },
  
  "kl_stats": {
    "mean": 0.142,
    "p50": 0.125,
    "p95": 0.245,
    "BTN_p50": 0.118,
    "FLOP_p50": 0.132,
    ...
  },
  
  "sampling": {
    "16": {"hands": 5000, "ev_delta_bb100": 3.2, "variance": 12.5, ...},
    "32": {"hands": 5000, ...},
    ...
  },
  
  "aivat_stats": {
    "vanilla_variance": 125.3,
    "aivat_variance": 45.2,
    "variance_reduction_pct": 63.9
  }
}
```

**CSV Export** (`--export-csv`):
- Tabular format for easy analysis
- Categories: global, position, street, latency, kl
- Compatible with spreadsheets and data analysis tools

## Usage

### Basic Evaluation

```bash
python tools/eval_rt_vs_blueprint_enhanced.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 10000 \
    --paired \
    --output results/comparison.json
```

### Multi-Seed with Stratification

```bash
python tools/eval_rt_vs_blueprint_enhanced.py \
    --policy runs/blueprint/avg_policy.json \
    --seeds 42,1337,2025 \
    --hands-per-seed 5000 \
    --paired \
    --street-samples flop=16,turn=32,river=64 \
    --output results/multi_seed.json
```

### With Adaptive Time Budget

```bash
python tools/eval_rt_vs_blueprint_enhanced.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 10000 \
    --time-budget-ms 110 \
    --strict-budget \
    --paired \
    --output results/strict_budget.json
```

### With AIVAT and CSV Export

```bash
python tools/eval_rt_vs_blueprint_enhanced.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 10000 \
    --paired \
    --aivat \
    --bootstrap-reps 2000 \
    --output results/comparison.json \
    --export-csv results/comparison.csv
```

### Production Configuration

```bash
python tools/eval_rt_vs_blueprint_enhanced.py \
    --policy runs/blueprint/avg_policy.json \
    --seeds 42,1337,2025 \
    --hands-per-seed 5000 \
    --paired \
    --street-samples flop=16,turn=32,river=64 \
    --time-budget-ms 110 \
    --strict-budget \
    --aivat \
    --bootstrap-reps 2000 \
    --output results/production_eval.json \
    --export-csv results/production_eval.csv
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--policy PATH` | Blueprint policy file (JSON or PKL) | Required |
| `--hands N` | Number of hands to evaluate | 10000 |
| `--paired` | Use paired bootstrap (same deals) | Off |
| `--seeds SEEDS` | Comma-separated random seeds | "42" |
| `--hands-per-seed N` | Hands per seed (overrides --hands) | - |
| `--street-samples STR` | Per-street samples (e.g., "flop=16,turn=32") | Default |
| `--time-budget-ms N` | Time budget per solve (ms) | 80 |
| `--strict-budget` | Enforce strict time budget | Off |
| `--bootstrap-reps N` | Bootstrap replicates | 2000 |
| `--aivat` | Use AIVAT variance reduction | Off |
| `--output PATH` | JSON output file | - |
| `--export-csv PATH` | CSV output file | - |
| `--quiet` | Suppress progress output | Off |

## Definition of Done Validation

The tool automatically validates against 5 gates:

### Gate 1: Global EVΔ CI95 > 0
**Requirement**: EVΔ confidence interval excludes 0 and is positive

**Status**: ✅ if `ci_lower > 0` and `is_significant == true`

### Gate 2: Per-Position EVΔ
**Requirement**: ≥4/6 positions show positive EVΔ with significant CI

**Status**: ✅ if at least 4 positions have `ci_lower > 0`

### Gate 3: Latency p95 ≤ 110ms
**Requirement**: 95th percentile latency under 110ms

**Status**: ✅ if `latency['p95'] <= 110.0`

### Gate 4: Fallback ≤ 5%
**Requirement**: Fallback to blueprint happens ≤5% of the time

**Status**: ✅ if `latency['fallback_rate'] <= 0.05`

### Gate 5: KL p50 ∈ [0.05, 0.25]
**Requirement**: Median KL divergence in acceptable range

**Status**: ✅ if `0.05 <= kl_stats['p50'] <= 0.25`

## Interpretation

### EVΔ Values

| EVΔ (bb/100) | Interpretation |
|--------------|----------------|
| > +5.0 | Excellent improvement |
| +2.0 to +5.0 | Good improvement |
| +0.5 to +2.0 | Moderate improvement |
| -0.5 to +0.5 | No significant difference |
| < -0.5 | Regression (investigate) |

### KL Divergence

| KL p50 | Interpretation |
|--------|----------------|
| < 0.05 | Too conservative (under-exploring) |
| 0.05 - 0.15 | Balanced (recommended) |
| 0.15 - 0.25 | Moderate exploration |
| > 0.25 | High deviation (verify improvement) |

### Latency

| Metric | Target | Notes |
|--------|--------|-------|
| p50 | < 80ms | Median should be fast |
| p95 | ≤ 110ms | Required for DoD |
| p99 | < 150ms | Outliers acceptable |
| Fallback | ≤ 5% | Required for DoD |

## Best Practices

### Sample Size

**Minimum**: 10,000 hands for stable CI
**Recommended**: 15,000 hands (3 seeds × 5,000)
**Production**: 30,000+ hands (6 seeds × 5,000)

### Bootstrap Replicates

**Minimum**: 1,000 replicates
**Recommended**: 2,000 replicates
**High precision**: 5,000+ replicates

### Street Samples

**Default**: flop=16, turn=32, river=64
**Fast**: flop=8, turn=16, river=32
**Precision**: flop=32, turn=64, river=128

### Time Budget

**Development**: 200ms (focus on accuracy)
**Testing**: 110ms (balanced)
**Production**: 80-110ms (strict requirement)

## Troubleshooting

### EVΔ is not significant

**Possible causes**:
1. Insufficient sample size → Increase `--hands`
2. High variance → Enable `--aivat`
3. Blueprint is already strong → Expected
4. RT configuration suboptimal → Check time budget and samples

**Solutions**:
- Increase hands to 20,000+
- Use paired bootstrap (`--paired`)
- Enable AIVAT (`--aivat`)
- Review KL statistics to verify RT is actually exploring

### Latency exceeds budget

**Possible causes**:
1. Too many samples → Reduce `--street-samples`
2. Time budget too aggressive → Increase `--time-budget-ms`
3. Hardware limitations → Use faster CPU

**Solutions**:
- Enable `--strict-budget` for adaptive reduction
- Reduce samples: flop=8, turn=16, river=32
- Increase time budget to 150ms

### KL outside acceptable range

**KL too low (< 0.05)**:
- RT is barely deviating from blueprint
- Increase exploration or reduce KL weight
- May indicate under-solving

**KL too high (> 0.25)**:
- RT is deviating significantly
- Verify EVΔ is actually positive
- May indicate over-exploration or bugs

### High fallback rate (> 5%)

**Possible causes**:
1. Time budget too strict
2. Solver failing to converge
3. Configuration issues

**Solutions**:
- Increase time budget
- Reduce samples per solve
- Check RT resolver configuration

## Technical Details

### Paired Bootstrap Algorithm

1. Generate N unique deals (board + hole cards)
2. For each deal:
   - Evaluate with RT search → `ev_rt`
   - Evaluate with blueprint → `ev_bp`
   - Store delta: `ev_delta = ev_rt - ev_bp`
3. Bootstrap resample deltas with replacement (2000 times)
4. Compute percentile CI from bootstrap distribution

**Benefits**:
- Reduces variance by 30-50%
- Eliminates deal quality variation
- More stable CI estimates

### Stratification Algorithm

1. Create strata: 6 positions × 3 streets = 18 strata
2. Allocate hands: `hands_per_stratum = total_hands / 18`
3. For each stratum:
   - Generate `hands_per_stratum` deals
   - Evaluate with fixed position and street
4. Aggregate results with proper weighting

**Benefits**:
- Ensures balanced representation
- Prevents position/street bias
- More representative results

### AIVAT Algorithm

**Training Phase** (warmup):
1. Collect samples: `(state_key, payoff)` for each position/street
2. Learn baselines: `V(state_key) = mean(payoffs)`

**Evaluation Phase**:
1. For each hand:
   - Get actual payoff: `payoff`
   - Get baseline: `baseline = V(state_key)`
   - Compute advantage: `advantage = payoff - baseline`
2. Report mean advantage (unbiased, lower variance)

**Benefits**:
- Reduces variance by 30-95%
- Maintains unbiased estimates
- Enables smaller sample sizes

## Examples

### Example 1: Quick Test

```bash
# Fast evaluation with 1000 hands
python tools/eval_rt_vs_blueprint_enhanced.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 1000 \
    --paired \
    --output results/quick_test.json
```

### Example 2: Production Evaluation

```bash
# Comprehensive evaluation with all features
python tools/eval_rt_vs_blueprint_enhanced.py \
    --policy runs/blueprint/avg_policy.json \
    --seeds 42,1337,2025,9999,12345,67890 \
    --hands-per-seed 5000 \
    --paired \
    --street-samples flop=16,turn=32,river=64 \
    --time-budget-ms 110 \
    --strict-budget \
    --aivat \
    --bootstrap-reps 5000 \
    --output results/production_eval.json \
    --export-csv results/production_eval.csv
```

### Example 3: Latency Optimization

```bash
# Focus on meeting latency requirements
python tools/eval_rt_vs_blueprint_enhanced.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 10000 \
    --paired \
    --street-samples flop=8,turn=16,river=32 \
    --time-budget-ms 110 \
    --strict-budget \
    --output results/latency_optimized.json
```

## References

- **Bootstrap Methods**: Efron & Tibshirani (1994). "An Introduction to the Bootstrap"
- **AIVAT**: Brown & Sandholm (2019). "Superhuman AI for multiplayer poker"
- **Paired Bootstrap**: Noreen (1989). "Computer-Intensive Methods for Testing Hypotheses"
- **Stratified Sampling**: Cochran (1977). "Sampling Techniques"

## Support

For issues or questions:
1. Check this documentation
2. Review test cases in `tests/test_eval_rt_vs_blueprint_enhanced.py`
3. Examine example runs in the tool docstring
4. Check output JSON for diagnostic information
