# Abstraction Experiments Guide

This document explains how to run experiments comparing different bucket configurations (information abstraction strategies) and measure their impact on playing strength.

## Overview

The experimentation infrastructure consists of:

1. **Predefined Configurations**: Named bucket configurations with different granularities
2. **Training Script**: Trains abbreviated blueprint strategies for each configuration
3. **Evaluation Script**: Compares strategies head-to-head with statistical analysis
4. **Results Analysis**: 95% confidence intervals and clear winner determination

## Available Configurations

The system provides three predefined configurations:

| Config | Specification | Description |
|--------|--------------|-------------|
| **A** | 24/80/80/64 | Base configuration (current default) |
| **B** | 48/160/160/128 | Fine-grained configuration (2x buckets) |
| **C** | 12/40/40/32 | Coarse configuration (0.5x buckets) |

The specification format is: `preflop/flop/turn/river` bucket counts.

### List Available Configurations

```bash
python scripts/compare_buckets_training.py --list-configs
```

## Running Experiments

### Step 1: Train Configurations

Train multiple bucket configurations with abbreviated training:

```bash
# Quick test (100k iterations, ~10-30 minutes per config)
python scripts/compare_buckets_training.py \
    --configs A B \
    --iters 100000 \
    --output experiments/quick_test/

# Medium test (500k iterations, ~1-2 hours per config)
python scripts/compare_buckets_training.py \
    --configs A B C \
    --iters 500000 \
    --samples 1000000 \
    --output experiments/medium_test/

# Full test (1M+ iterations, several hours per config)
python scripts/compare_buckets_training.py \
    --configs A B \
    --iters 1000000 \
    --samples 1000000 \
    --output experiments/full_test/
```

**Parameters:**
- `--configs`: List of configurations to train (A, B, C, or combinations)
- `--iters`: Number of MCCFR iterations (more = better convergence)
- `--samples`: Number of samples for bucket generation (default: 500000)
- `--output`: Directory for experiment outputs
- `--num-players`: Number of players (2-6, default: 2 for heads-up)
- `--seed`: Random seed for reproducibility (default: 42)

**Output Structure:**
```
experiments/quick_test/
├── training_metadata.json          # Experiment metadata
├── buckets_config_a.pkl           # Buckets for config A
├── buckets_config_b.pkl           # Buckets for config B
├── training_config_a/             # Training logs for A
│   ├── strategy_100000.pkl        # Final strategy
│   └── checkpoint_*.pkl           # Checkpoints
└── training_config_b/             # Training logs for B
    └── strategy_100000.pkl
```

### Step 2: Evaluate Configurations

Compare trained strategies head-to-head:

```bash
# Evaluate all configs from an experiment
python scripts/compare_buckets_eval.py \
    --experiment experiments/quick_test/ \
    --hands 10000

# Evaluate with more hands for tighter confidence intervals
python scripts/compare_buckets_eval.py \
    --experiment experiments/quick_test/ \
    --hands 50000 \
    --output results/

# Manual strategy comparison (if needed)
python scripts/compare_buckets_eval.py \
    --strategies \
        A experiments/quick_test/training_config_a/strategy_100000.pkl \
        B experiments/quick_test/training_config_b/strategy_100000.pkl \
    --hands 10000
```

**Parameters:**
- `--experiment`: Experiment directory from training script
- `--hands`: Number of hands to simulate (more = tighter confidence intervals)
- `--output`: Optional output directory for detailed results
- `--seed`: Random seed (default: 42)

### Step 3: Interpret Results

The evaluation script outputs:

```
======================================================================
Evaluating A vs B
======================================================================

Results (A vs B):
  A winrate: 2.35 ± 0.82 bb/100 (95% CI: [1.53, 3.17])
  ✓ A is favored

======================================================================
```

**Interpretation:**

1. **Winrate**: Mean chips won per 100 hands (bb/100)
   - Positive = Configuration A wins on average
   - Negative = Configuration B wins on average
   - Near zero = Configurations perform similarly

2. **Confidence Interval**: 95% CI bounds
   - If CI doesn't include zero → statistically significant difference
   - If CI includes zero → no statistically significant difference
   - Narrower CI = more confident estimate (run more hands)

3. **Favored Player**: Clear winner indication
   - ✓ Symbol indicates favored configuration
   - = Symbol indicates even match

**Example Scenarios:**

- `A: 2.35 ± 0.82 bb/100 (95% CI: [1.53, 3.17])` → **A wins significantly**
- `A: 0.15 ± 1.20 bb/100 (95% CI: [-1.05, 1.35])` → **No significant difference**
- `A: -3.50 ± 0.65 bb/100 (95% CI: [-4.15, -2.85])` → **B wins significantly**

## Recommendations

### Quick Validation (30 min - 1 hour)
```bash
python scripts/compare_buckets_training.py --configs A B --iters 50000 --output exp/quick/
python scripts/compare_buckets_eval.py --experiment exp/quick/ --hands 5000
```
Use for: Initial testing, debugging, parameter exploration

### Medium Test (2-4 hours)
```bash
python scripts/compare_buckets_training.py --configs A B --iters 250000 --output exp/medium/
python scripts/compare_buckets_eval.py --experiment exp/medium/ --hands 20000
```
Use for: Preliminary results, configuration screening

### Thorough Analysis (8+ hours)
```bash
python scripts/compare_buckets_training.py --configs A B C --iters 1000000 --samples 1000000 --output exp/full/
python scripts/compare_buckets_eval.py --experiment exp/full/ --hands 100000
```
Use for: Final validation, publication-quality results

## Understanding Bucket Configurations

### Trade-offs

**Fine-grained (more buckets, e.g., Config B):**
- ✓ More precise hand abstraction
- ✓ Can distinguish subtle differences in hand strength
- ✗ Larger state space → slower convergence
- ✗ More memory required
- ✗ Needs more training iterations

**Coarse-grained (fewer buckets, e.g., Config C):**
- ✓ Faster convergence
- ✓ Lower memory requirements
- ✓ More robust with limited training
- ✗ Less precise hand abstraction
- ✗ May miss important strategic nuances

**Hypothesis to Test:**
- Does doubling bucket count (A → B) improve playing strength?
- Is the improvement worth 2x memory/training cost?
- Does halving bucket count (A → C) significantly hurt performance?

## Expected Results Pattern

Based on poker AI research:

1. **Under-trained regime** (<100k iterations):
   - Coarse configs may perform better (faster convergence)
   
2. **Well-trained regime** (>500k iterations):
   - Fine configs should perform better (more accurate)
   
3. **Optimal point**:
   - Balance between granularity and convergence
   - May vary by number of players and game complexity

## Advanced Usage

### Custom Configurations

To add a new configuration, edit `src/holdem/bucket_configs.py`:

```python
'D': {
    'name': 'config_d',
    'description': 'Custom ultra-fine configuration',
    'k_preflop': 96,
    'k_flop': 320,
    'k_turn': 320,
    'k_river': 256,
},
```

### Multi-player Experiments

Test with 6-max configurations:

```bash
python scripts/compare_buckets_training.py \
    --configs A B \
    --iters 500000 \
    --num-players 6 \
    --output experiments/6max_test/
```

### Parallel Training

For faster experiments, use multiple CPU cores:

```bash
python src/holdem/cli/train_blueprint.py \
    --config configs/blueprint_training.yaml \
    --buckets experiments/quick_test/buckets_config_a.pkl \
    --logdir experiments/parallel_test/ \
    --iters 500000 \
    --num-workers 4
```

## Troubleshooting

### Training Takes Too Long
- Reduce `--iters` for quicker tests
- Reduce `--samples` to 100000 for bucket generation
- Use fewer configurations initially

### Evaluation Shows No Difference
- Increase `--hands` for tighter confidence intervals
- Ensure training converged (check logs)
- Try more extreme configurations (A vs C)

### Out of Memory
- Reduce bucket counts
- Reduce `--samples`
- Close other applications

## Results Log

Document your experiment results here:

### Experiment 1: [Date]
**Setup:**
- Configurations: A vs B
- Training iterations: 
- Evaluation hands: 
- Number of players: 

**Results:**
```
[Paste evaluation output here]
```

**Conclusions:**
- 
- 

---

### Experiment 2: [Date]
**Setup:**
- Configurations: 
- Training iterations: 
- Evaluation hands: 
- Number of players: 

**Results:**
```
[Paste evaluation output here]
```

**Conclusions:**
- 
- 

---

## Further Reading

- [Pluribus: Superhuman AI for multiplayer poker](https://science.sciencemag.org/content/365/6456/885)
- [DeepStack: Expert-level artificial intelligence in heads-up no-limit poker](https://science.sciencemag.org/content/356/6337/508)
- Information abstraction in poker AI: balancing granularity and convergence

## Contributing

To add new configurations or improve the infrastructure:

1. Add configurations to `src/holdem/bucket_configs.py`
2. Enhance evaluation metrics in `scripts/compare_buckets_eval.py`
3. Document findings in this file
4. Submit experiments results with PR

---

*Last updated: [Date]*
