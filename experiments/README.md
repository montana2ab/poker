# Public Card Sampling Experiments

This directory contains experiment scripts for testing and validating the public card sampling implementation.

## compare_public_card_sampling.py

Script to compare different public card sampling configurations (ablation tests).

### Usage

```bash
# Quick test with default settings
python experiments/compare_public_card_sampling.py

# Custom configuration
python experiments/compare_public_card_sampling.py \
    --num-hands 500 \
    --sample-counts 1,5,10,20,50 \
    --time-budget 200 \
    --min-iterations 100 \
    --street flop

# Test on different streets
python experiments/compare_public_card_sampling.py --street turn --num-hands 200
```

### Options

- `--num-hands`: Number of hands to test per configuration (default: 100)
- `--sample-counts`: Comma-separated list of sample counts (default: 1,5,10,20)
- `--time-budget`: Time budget per solve in milliseconds (default: 100)
- `--min-iterations`: Minimum CFR iterations per solve (default: 50)
- `--street`: Game street to test on - preflop/flop/turn/river (default: flop)
- `--output`: Output JSON file for results (default: experiments/results/sampling_comparison.json)

### What It Tests

The script compares multiple configurations:
- **Baseline**: Sampling OFF (num_samples=1)
- **Variants**: Different sample counts (5, 10, 20, 50, etc.)

For each configuration, it measures:
- Average/min/max/std solve time
- Throughput (hands per second)
- Time overhead vs baseline
- Strategy variance (when sampling enabled)

### Example Output

```
====================================================================================================
EXPERIMENT RESULTS - Public Card Sampling Comparison
====================================================================================================

Configuration                  Avg Time (ms)   Min (ms)     Max (ms)     Std (ms)     Hands/s   
----------------------------------------------------------------------------------------------------
sampling_OFF                   2.73            2.31         9.70         1.60         361.96    
sampling_ON_samples_5          14.78           14.65        15.23        0.11         67.46     
sampling_ON_samples_10         27.26           27.08        27.48        0.12         36.63     

----------------------------------------------------------------------------------------------------
Comparison vs Baseline (sampling OFF):
----------------------------------------------------------------------------------------------------
sampling_ON_samples_5          Time overhead: +442.4% | Throughput: 0.19x baseline
sampling_ON_samples_10         Time overhead: +900.0% | Throughput: 0.10x baseline
====================================================================================================
```

### Results Directory

Results are saved to `experiments/results/` in JSON format with:
- Timestamp
- Configuration parameters
- Per-config statistics (solve times, throughput)
- Full experiment metadata

## See Also

- [PUBLIC_CARD_SAMPLING_GUIDE.md](../PUBLIC_CARD_SAMPLING_GUIDE.md) - Full implementation guide
- [tests/test_public_card_sampling_config.py](../tests/test_public_card_sampling_config.py) - Unit tests
