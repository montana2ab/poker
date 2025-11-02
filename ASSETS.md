# Assets and Training Artifacts Guide

This document explains the assets required by the poker AI system and how to generate them.

## Directory Structure

```
assets/
  templates/              # Card recognition templates (52 files)
  samples/                # Sample images for testing
  abstraction/            # Hand abstraction files
    buckets_config.yaml   # Bucket configuration
    precomputed_buckets.pkl  # Pre-computed hand clusters
  table_profiles/         # Table calibration profiles
    default_profile.json  # Example table profile
```

## Required Assets

### 1. Card Templates (`assets/templates/`)

**Purpose**: Used for computer vision card recognition

**How to Generate**:
```bash
# Automatically created by setup_assets.py
python setup_assets.py
```

**Manual Creation** (if opencv-python is not installed):
```python
from holdem.vision.cards import create_mock_templates
from pathlib import Path
create_mock_templates(Path("assets/templates"))
```

**What's Created**: 52 template images (one per card: 2h, 3h, ..., Ah, 2d, ...)

### 2. Abstraction Buckets (`assets/abstraction/precomputed_buckets.pkl`)

**Purpose**: Hand clustering for game tree abstraction

**Status**: ⚠️ **Must be generated before training**

**How to Generate**:
```bash
# Quick test (fast, small buckets)
holdem-build-buckets \
  --hands 10000 \
  --k-preflop 8 --k-flop 20 --k-turn 15 --k-river 10 \
  --out assets/abstraction/test_buckets.pkl

# Production (slower, better abstraction)
holdem-build-buckets \
  --hands 500000 \
  --k-preflop 12 --k-flop 60 --k-turn 40 --k-river 24 \
  --config assets/abstraction/buckets_config.yaml \
  --out assets/abstraction/precomputed_buckets.pkl
```

**Time Required**:
- Test (10k hands): ~30 seconds
- Production (500k hands): 10-30 minutes

### 3. Blueprint Policy (`runs/blueprint/avg_policy.json`)

**Purpose**: The trained MCCFR strategy used for decision-making

**Status**: ⚠️ **Must be trained before using dry-run or auto-play**

**How to Generate**:
```bash
# Prerequisites: Must have precomputed_buckets.pkl first!

# Quick test (fast, weak strategy)
holdem-train-blueprint \
  --iters 10000 \
  --buckets assets/abstraction/test_buckets.pkl \
  --logdir runs/test_blueprint

# Medium training (decent strategy)
holdem-train-blueprint \
  --iters 100000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/medium_blueprint

# Production (strong strategy)
holdem-train-blueprint \
  --iters 2500000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint
```

**Time Required**:
- Test (10k iters): ~2-5 minutes
- Medium (100k iters): ~20-40 minutes
- Production (2.5M iters): 8-12 hours

**Output Files**:
- `avg_policy.json` - The average strategy (what you use)
- `regrets.pkl` - Regret values (for continuing training)
- Tensorboard logs in the logdir

### 4. Table Profile (`assets/table_profiles/*.json`)

**Purpose**: Calibration data for detecting and parsing poker table UI

**Status**: ⚠️ **Must be created for your specific poker client**

**How to Generate**:
```bash
# Interactive wizard
holdem-profile-wizard \
  --window-title "PokerStars" \
  --out assets/table_profiles/pokerstars.json

# Or specify screen region manually
holdem-profile-wizard \
  --screen-region 100,100,800,600 \
  --out assets/table_profiles/custom.json
```

**What It Contains**:
- Window title or screen region coordinates
- Feature descriptors for table detection
- Region coordinates for cards, buttons, pot, stacks
- Reference images for matching

## Complete Setup Workflow

Here's the recommended order for setting up all assets:

```bash
# Step 1: Create directory structure and card templates
python setup_assets.py

# Step 2: Build abstraction buckets (required for training)
holdem-build-buckets \
  --hands 100000 \
  --k-preflop 12 --k-flop 60 --k-turn 40 --k-river 24 \
  --out assets/abstraction/precomputed_buckets.pkl

# Step 3: Train blueprint strategy
holdem-train-blueprint \
  --iters 100000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint

# Step 4: (Optional) Create table profile for vision
holdem-profile-wizard \
  --window-title "YourPokerClient" \
  --out assets/table_profiles/my_table.json

# Step 5: Test with dry-run
holdem-dry-run \
  --profile assets/table_profiles/my_table.json \
  --policy runs/blueprint/avg_policy.json
```

## Asset Files Summary

| File | Required? | How to Generate | Time |
|------|-----------|----------------|------|
| `assets/templates/*.png` | Yes (for vision) | `python setup_assets.py` | <1 min |
| `assets/abstraction/precomputed_buckets.pkl` | Yes (for training) | `holdem-build-buckets` | 10-30 min |
| `runs/blueprint/avg_policy.json` | Yes (for play) | `holdem-train-blueprint` | 20 min - 12 hrs |
| `assets/table_profiles/*.json` | Yes (for vision) | `holdem-profile-wizard` | 5-10 min |
| `assets/abstraction/buckets_config.yaml` | Optional | `--config` flag in build-buckets | N/A |

## Troubleshooting

### "FileNotFoundError: avg_policy.json"
**Problem**: Blueprint hasn't been trained yet  
**Solution**: Run `holdem-train-blueprint` first (see above)

### "FileNotFoundError: precomputed_buckets.pkl"
**Problem**: Buckets haven't been built yet  
**Solution**: Run `holdem-build-buckets` first (see above)

### "No card templates found"
**Problem**: Vision assets not created  
**Solution**: Run `python setup_assets.py`

### Training is too slow
**Problem**: Using too many iterations or samples  
**Solution**: Use smaller parameters for testing:
```bash
# Fast test parameters
holdem-build-buckets --hands 10000 --out test_buckets.pkl
holdem-train-blueprint --iters 10000 --buckets test_buckets.pkl --logdir test_run
```

### Not enough disk space
**Problem**: Training generates large files  
**Solution**: 
- Use smaller bucket configurations (fewer k values)
- Use fewer training iterations
- Clean old runs with `make clean`

## Continuing Training

You can continue training from a previous run:

```bash
# Resume training from checkpoint
holdem-train-blueprint \
  --iters 1000000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint \
  --resume  # Loads existing regrets.pkl and continues
```

## Pre-trained Assets (Not Available)

Currently, there are no pre-trained assets available. All assets must be generated on your machine. This is intentional because:

1. **Bucket quality**: Better to generate fresh buckets with your chosen parameters
2. **Strategy customization**: Train for your specific opponent pool and stakes
3. **Table profiles**: Every poker client UI is different
4. **Reproducibility**: Ensures you understand the full pipeline

However, the quick test parameters above (~30 min total) will give you a working system.
