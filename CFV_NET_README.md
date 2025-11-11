# Counterfactual Value Net (CFV Net)

## Overview

The CFV Net is a neural network-based leaf evaluator that replaces Monte Carlo rollouts during real-time poker solving. It maintains expected value (EV) while fitting within the 80-110ms decision time budget.

**Key Features:**
- ⚡ **Fast**: ≤1ms inference on M2 CPU (vs ~10-50ms for rollouts)
- 🎯 **Accurate**: MAE < 0.30 bb, PI90 coverage ≥ 85%
- 🛡️ **Safe**: Gating + fallback ensures no failures
- 📊 **Calibrated**: Prediction intervals with uncertainty estimation

## Architecture

### Model
- **Type**: MLP with quantile regression
- **Hidden layers**: [512, 512, 256] (M2) or [768, 768, 512] (Server)
- **Activation**: GELU
- **Regularization**: LayerNorm, Dropout 0.05
- **Outputs**: mean (Huber loss), q10/q90 (pinball loss)

### Features (~470 dimensions)
- **Public**: street, num_players, position, SPR, pot ratios, action_set
- **Buckets**: public card bucket embedding (64d)
- **Ranges**: top-16 buckets per player with embeddings (6 × 64d)

### Gating Logic
Predictions are accepted only if:
1. **PI width** < threshold (flop: 0.20, turn: 0.16, river: 0.12 bb)
2. **OOD check**: all normalized features within 4σ
3. **Value clamp**: |CFV| ≤ 25 bb
4. **Position adjustment**: OOP×0.9, IP×1.1

If rejected → fallback to rollouts or blueprint.

## Usage

### 1. Collect Training Data

```bash
# Collect 2M examples from blueprint snapshots
python tools/collect_cfv_data.py \
  --snapshots /Volumes/122/runs/blueprint_6max_m2_8h/instance_*/snapshots/snapshot_iter* \
  --buckets assets/abstraction/buckets_6max.pkl \
  --out data/cfv/6max_jsonlz \
  --max-examples 2000000 --seed 42
```

**Dataset format** (`.jsonl.zst` shards):
```json
{
  "street": "TURN",
  "num_players": 6,
  "hero_pos": "CO",
  "spr": 3.2,
  "public_bucket": 8123,
  "ranges": {"BTN": [[id, weight], ...], ...},
  "scalars": {
    "pot_norm": 1.4,
    "to_call_over_pot": 0.3,
    "last_bet_over_pot": 0.5,
    "aset": "balanced"
  },
  "target_cfv_bb": 1.23
}
```

### 2. Train Model

```bash
# Train M2 model
python tools/train_cfv_net.py \
  --data data/cfv/6max_jsonlz \
  --config configs/cfv_net_m2.yaml \
  --logdir runs/cfv_net_6max_m2

# Monitor with TensorBoard
tensorboard --logdir runs/cfv_net_6max_m2
```

**Training features:**
- AdamW optimizer (lr=1e-3, weight_decay=1e-4)
- Cosine decay with 5% warmup
- Gradient accumulation (effective batch: 8k)
- Early stopping on validation MAE (patience=3)

### 3. Evaluate Model

```bash
# Evaluate quality metrics
python tools/eval_cfv_net.py \
  --checkpoint runs/cfv_net_6max_m2/best.pt \
  --data data/cfv/6max_jsonlz \
  --out runs/cfv_net_6max_m2/eval
```

**Quality requirements:**
- ✅ MAE < 0.30 bb
- ✅ PI90 coverage ≥ 85%
- ✅ ECE < 0.05
- ✅ p95 inference ≤ 1.0 ms (M2)

### 4. Export to ONNX

```bash
# Export for production
python tools/export_cfv_net.py \
  --checkpoint runs/cfv_net_6max_m2/best.pt \
  --out assets/cfv_net/6max_best.onnx
```

**Output files:**
- `6max_best.onnx`: ONNX model (opset≥17)
- `stats.json`: Feature normalization stats
- `calib.json`: Calibration data (placeholder)

### 5. Use in Real-Time Solving

```yaml
# configs/6max_training.yaml
rt:
  leaf:
    mode: "cfv_net"
    cfv_net:
      checkpoint: "assets/cfv_net/6max_best.onnx"
      cache_max_size: 10000
      gating:
        tau_flop: 0.20
        tau_turn: 0.16
        tau_river: 0.12
        ood_sigma: 4.0
        clamp_abs_bb: 25.0
        boost_ip: 1.10
        boost_oop: 0.90
      fallback: "rollout"
```

**Python API:**
```python
from holdem.rt_resolver import LeafEvaluator

evaluator = LeafEvaluator(
    blueprint=blueprint,
    mode="cfv_net",
    cfv_net_config={
        'checkpoint': 'assets/cfv_net/6max_best.onnx',
        'cache_max_size': 10000,
        'gating': {
            'tau_flop': 0.20,
            'tau_turn': 0.16,
            'tau_river': 0.12
        }
    }
)

# Automatic gating + fallback
value = evaluator.evaluate(
    state=state,
    hero_hand=hero_hand,
    villain_range=villain_range,
    hero_position=0,
    bucket_public=public_bucket,
    bucket_ranges=ranges
)

# Get metrics
stats = evaluator.get_cfv_net_stats()
print(f"Accept rate: {stats['cfv_net_accept_rate']:.1%}")
print(f"Latency p95: {stats['cfv_net_latency_p95']:.2f} ms")
```

## Performance Targets

### RT Performance (vs rollouts)
- **Decision time**: p95 ≤ 65 ms (-15 ms min)
- **OR iterations**: +20% min (same time budget)
- **EV**: ≥ EV_rollouts - 0.1 bb/100
- **Accept rate**: ≥ 60%
- **Failsafe**: ≤ 5%

### H2H Performance
- **200k deals**: No significant bb/100 degradation (±CI95)
- **Duplicate testing**: Rotation across seats

## Metrics & Monitoring

### TensorBoard Logs
```python
# Training
writer.add_scalar('train/loss', loss, step)
writer.add_scalar('train/lr', lr, step)
writer.add_scalar('val/mae', mae, epoch)
writer.add_scalar('val/pi_coverage', coverage, epoch)
writer.add_scalar('val/ece', ece, epoch)

# Real-time evaluation
writer.add_scalar('eval/cfv_accept_rate_flop', rate, step)
writer.add_scalar('eval/cfv_latency_p95', latency, step)
writer.add_scalar('eval/cfv_pi_width_turn', width, step)
writer.add_scalar('rt/decision_time_p95', time, step)
writer.add_scalar('rt/failsafe_rate', rate, step)
```

### Cache Statistics
- **Hit rate**: Target > 50% (LRU with 10k entries)
- **Size**: Monitor cache_size / cache_max_size
- **Evictions**: Tracked implicitly

## Safety & Invariants

### Hard Requirements
1. ✅ **No crashes**: Always fallback if CFV Net fails
2. ✅ **Deterministic**: Seeded RNG for reproducibility
3. ✅ **Metadata check**: Bucket/num_players compatibility
4. ✅ **Atomic writes**: All I/O uses temp files + rename

### Gating Stages
1. **OOD detection**: Reject if any feature > 4σ
2. **PI width**: Reject if uncertainty too high
3. **Value clamp**: Reject if |CFV| > 25 bb
4. **Street filter**: Always reject preflop (use blueprint)

### Fallback Chain
```
CFV Net → Gating → Accept ✓
                 → Reject → Rollout → Value
                                   → Blueprint → Value
```

## Configuration Files

### M2 Config (`configs/cfv_net_m2.yaml`)
- Batch: 2048 (effective: 8k with accumulation)
- Hidden: [512, 512, 256]
- Inference: ≤1 ms target

### Server Config (`configs/cfv_net_server.yaml`)
- Batch: 4096 (effective: 16k)
- Hidden: [768, 768, 512]
- Inference: ≤5 ms budget

## Development & Testing

### Run Tests
```bash
# Feature tests
pytest tests/test_cfv_features.py -v

# Dataset tests
pytest tests/test_cfv_dataset.py -v

# Inference/gating tests
pytest tests/test_cfv_infer_gating.py -v

# Integration tests
pytest tests/test_leaf_evaluator_cfv.py -v
```

### Performance Optimization
```bash
# Set threading (M2 optimization)
export OMP_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
```

## Troubleshooting

### Common Issues

**1. Low accept rate (<60%)**
- Check gating thresholds (may be too strict)
- Verify feature normalization stats
- Check for OOD inputs (distribution shift)

**2. High latency (>1ms)**
- Verify ONNX Runtime CPU provider
- Check cache hit rate (should be >50%)
- Consider smaller model (reduce hidden dims)

**3. Poor calibration (ECE >0.05)**
- Retrain with more data
- Adjust quantile loss weights
- Apply isotonic calibration post-training

**4. Training divergence**
- Reduce learning rate
- Increase gradient accumulation
- Check for data quality issues

## References

- **Pluribus**: Brown & Sandholm (2019) - Superhuman AI for multiplayer poker
- **Quantile Regression**: Koenker & Bassett (1978) - Regression quantiles
- **ONNX**: Open Neural Network Exchange - https://onnx.ai/
