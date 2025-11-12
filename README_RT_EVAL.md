# RT Search vs Blueprint Evaluation - Quick Start

## Overview

This implementation measures the Expected Value difference (EVΔ) between RT (real-time) search and blueprint strategy, with support for public card sampling (16-64 samples).

## Requirements Addressed

✅ **1. Mesurer EVΔ du RT search vs blueprint avec bootstrap CI95 (doit être > 0)**
   - Measures EV difference with 95% confidence intervals
   - Uses bootstrap method (10,000 resamples)
   - Tests statistical significance
   - Validates EVΔ > 0

✅ **2. Activer public-card sampling (16–64 samples) + mesurer variance/latence**
   - Supports 16, 32, 64 samples
   - Measures variance reduction
   - Measures latency impact

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Validation

```bash
python validate_implementation.py
```

Expected output:
```
✅ PASS - search_config
✅ PASS - file_structure
✅ PASS - eval_tool
✅ PASS - bootstrap_ci
```

### 3. Run Tests

```bash
# Unit tests
pytest tests/test_eval_rt_vs_blueprint.py -v

# Extended sampling tests (with detailed output)
pytest tests/test_public_card_sampling_extended.py -v -s
```

### 4. Run Evaluation

#### Single Sample Count

```bash
python tools/eval_rt_vs_blueprint.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 1000 \
    --samples-per-solve 16 \
    --output results/16samples.json
```

#### Multiple Sample Counts

```bash
python tools/eval_rt_vs_blueprint.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 500 \
    --test-sample-counts 1,16,32,64 \
    --output results/comparison.json
```

## Expected Output

```
======================================================================
RT SEARCH vs BLUEPRINT EVALUATION RESULTS
======================================================================

Configuration:
  Total hands:       2000
  Samples per solve: 16

Expected Value Difference (RT - Blueprint):
  EVΔ:              +3.25 bb/100
  95% CI:           [+1.12, +5.38]
  Margin:           ±2.13 bb/100
  p-value:          0.0023

  ✅ SIGNIFICANT: RT search is statistically better than blueprint (p < 0.05)

Latency Statistics:
  Mean:             85.32 ms
  Median (p50):     78.15 ms
  p95:              145.78 ms
  p99:              210.43 ms
======================================================================
```

## Files Created

### Tools
- `tools/eval_rt_vs_blueprint.py` - Main evaluation script

### Tests
- `tests/test_eval_rt_vs_blueprint.py` - Unit/integration tests
- `tests/test_public_card_sampling_extended.py` - Extended sampling tests

### Documentation
- `docs/RT_VS_BLUEPRINT_EVALUATION.md` - Complete guide (English)
- `docs/RT_VS_BLUEPRINT_EVALUATION_FR.md` - Guide complet (French)
- `IMPLEMENTATION_SUMMARY_RT_EVAL.md` - Technical details

### Validation
- `validate_implementation.py` - Implementation validator

## Key Features

### Bootstrap Confidence Intervals
- Non-parametric method (no distribution assumptions)
- 10,000 bootstrap resamples
- 95% confidence level
- Two-tailed p-value calculation

### Public Card Sampling
- Leverages existing `SearchConfig.samples_per_solve`
- Tests 16, 32, 64 samples
- Measures variance reduction
- Tracks latency scaling

### Statistical Testing
- Tests if EVΔ ≠ 0
- Requires p-value < 0.05 for significance
- Validates EVΔ > 0 (RT better than blueprint)

## Command-Line Options

```
--policy PATH           Blueprint policy (JSON or PKL)
--hands N              Number of hand pairs (default: 1000)
--samples-per-solve N  Public card samples (default: 1)
--test-sample-counts   Test multiple counts (e.g., "1,16,32,64")
--time-budget MS       Time budget per solve (default: 80)
--seed N               Random seed (default: 42)
--output PATH          Output JSON file
--quiet                Suppress progress output
```

## Interpretation

### EVΔ Values

| EVΔ (bb/100) | Interpretation |
|--------------|----------------|
| > +5.0 | Excellent |
| +2.0 to +5.0 | Good |
| +0.5 to +2.0 | Moderate |
| -0.5 to +0.5 | No difference |
| < -0.5 | Regression |

### Statistical Significance

- **Significant**: 95% CI excludes 0, p < 0.05
- **Not significant**: 95% CI contains 0, p ≥ 0.05

### Latency

| Samples | Expected Latency |
|---------|------------------|
| 1 | ~80ms |
| 16 | ~800ms |
| 32 | ~1.6s |
| 64 | ~3.2s |

## Troubleshooting

### EVΔ is negative
- Check blueprint quality
- Verify time budget is sufficient
- Check RT resolver configuration

### Latency too high
- Reduce `samples_per_solve`
- Increase `time_budget_ms` per sample
- Reduce `min_iterations`

### Not statistically significant
- Increase `--hands` (more samples)
- Improve EVΔ magnitude
- Reduce noise in evaluation

## References

- **EVAL_PROTOCOL.md** - Evaluation methodology
- **PUBLIC_CARD_SAMPLING_GUIDE.md** - Sampling guide
- **docs/RT_VS_BLUEPRINT_EVALUATION.md** - Complete documentation

## Support

For detailed information:
- English: `docs/RT_VS_BLUEPRINT_EVALUATION.md`
- French: `docs/RT_VS_BLUEPRINT_EVALUATION_FR.md`
- Technical: `IMPLEMENTATION_SUMMARY_RT_EVAL.md`
