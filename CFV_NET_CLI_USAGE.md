# CFV Net Command-Line Arguments

## Overview

This document describes how to configure CFV net (Counterfactual Value Network) for leaf evaluation using command-line arguments in both dry-run and auto-play modes.

## Command-Line Arguments

### `--cfv-net PATH`

Specifies the path to the CFV net ONNX model file.

- **Type**: Path
- **Default**: `assets/cfv_net/6max_mid_125k_m2.onnx`
- **Example**: `--cfv-net assets/cfv_net/custom_model.onnx`

### `--no-cfv-net`

Disables CFV net and uses only blueprint/rollouts for leaf evaluation.

- **Type**: Flag (boolean)
- **Default**: Not set (CFV net enabled by default)
- **Example**: `--no-cfv-net`

## Usage Examples

### Dry-Run Mode

#### Using default CFV net
```bash
python -m holdem.cli.run_dry_run \
    --profile assets/table_profiles/pokerstars.json \
    --policy assets/blueprints/6max_mid_125k.pkl \
    --buckets assets/abstraction/buckets_6max.pkl
```

#### Using custom CFV net
```bash
python -m holdem.cli.run_dry_run \
    --profile assets/table_profiles/pokerstars.json \
    --policy assets/blueprints/6max_mid_125k.pkl \
    --buckets assets/abstraction/buckets_6max.pkl \
    --cfv-net assets/cfv_net/custom_model.onnx
```

#### Disabling CFV net
```bash
python -m holdem.cli.run_dry_run \
    --profile assets/table_profiles/pokerstars.json \
    --policy assets/blueprints/6max_mid_125k.pkl \
    --buckets assets/abstraction/buckets_6max.pkl \
    --no-cfv-net
```

### Auto-Play Mode

#### Using default CFV net
```bash
python -m holdem.cli.run_autoplay \
    --profile assets/table_profiles/pokerstars.json \
    --policy assets/blueprints/6max_mid_125k.pkl \
    --buckets assets/abstraction/buckets_6max.pkl \
    --i-understand-the-tos
```

#### Using custom CFV net
```bash
python -m holdem.cli.run_autoplay \
    --profile assets/table_profiles/pokerstars.json \
    --policy assets/blueprints/6max_mid_125k.pkl \
    --buckets assets/abstraction/buckets_6max.pkl \
    --cfv-net assets/cfv_net/custom_model.onnx \
    --i-understand-the-tos
```

#### Disabling CFV net
```bash
python -m holdem.cli.run_autoplay \
    --profile assets/table_profiles/pokerstars.json \
    --policy assets/blueprints/6max_mid_125k.pkl \
    --buckets assets/abstraction/buckets_6max.pkl \
    --no-cfv-net \
    --i-understand-the-tos
```

## Behavior

### Default Behavior

When neither `--cfv-net` nor `--no-cfv-net` is specified:
- The system attempts to use the CFV net from the default path: `assets/cfv_net/6max_mid_125k_m2.onnx`
- If the file exists, CFV net mode is enabled
- If the file doesn't exist, the system falls back to blueprint/rollouts mode with a warning

### With `--cfv-net PATH`

When `--cfv-net` is specified with a custom path:
- The system attempts to use the CFV net from the specified path
- If the file exists, CFV net mode is enabled with that model
- If the file doesn't exist, the system falls back to blueprint/rollouts mode with a warning

### With `--no-cfv-net`

When `--no-cfv-net` is specified:
- CFV net is explicitly disabled
- The system uses blueprint/rollouts mode for leaf evaluation
- No attempt is made to load any CFV net file

## CFV Net Configuration

When CFV net is enabled, the following configuration is used:

```python
cfv_net_config = {
    "checkpoint": "<path-to-onnx-file>",
    "cache_max_size": 10000,
    "gating": {
        "tau_flop": 0.20,
        "tau_turn": 0.16,
        "tau_river": 0.12,
    },
}
```

### Gating Parameters

- **tau_flop**: Uncertainty threshold for flop (0.20 bb)
- **tau_turn**: Uncertainty threshold for turn (0.16 bb)
- **tau_river**: Uncertainty threshold for river (0.12 bb)

These thresholds determine when the CFV net prediction is accepted. If the prediction uncertainty exceeds the threshold, the system falls back to blueprint/rollouts.

## Blueprint/Rollouts Mode

When CFV net is disabled or unavailable, the system uses:

```python
LeafEvaluator(
    blueprint=policy,
    mode="blueprint",
    use_cfv=True,
    num_rollout_samples=10,
    enable_cache=True,
    cache_max_size=10000
)
```

This mode uses the blueprint policy's counterfactual values (CFV) when available, otherwise performs Monte Carlo rollouts.

## Logging

The system logs which leaf evaluation mode is being used:

- CFV net enabled: `"Using CFV net for leaf evaluation: <path>"`
- CFV net disabled: `"Using blueprint/rollouts for leaf evaluation (CFV net disabled)"`
- CFV net file not found: `"CFV net file not found: <path>, using blueprint/rollouts instead"` (warning)

## Performance Considerations

### CFV Net Mode
- **Faster**: ≤1ms inference on M2 CPU (vs ~10-50ms for rollouts)
- **Requires**: Pre-trained ONNX model file
- **Memory**: ~10,000 cache entries (~several MB)

### Blueprint/Rollouts Mode
- **Slower**: ~10-50ms for rollout evaluation
- **No requirements**: Works with just the blueprint policy
- **Memory**: Minimal additional memory usage

## Troubleshooting

### CFV net file not found

If you see: `"CFV net file not found: <path>, using blueprint/rollouts instead"`

**Solution**: 
- Create or export your CFV net model to the specified path
- Use `--no-cfv-net` to explicitly disable CFV net
- Ensure the path is correct and the file exists

### Import errors

If you see: `"Failed to initialize CFV Net: <error>"`

**Possible causes**:
- Missing dependencies (onnxruntime, torch)
- Corrupted ONNX file
- Incompatible ONNX opset version

**Solution**: The system automatically falls back to blueprint/rollouts mode

## See Also

- [CFV_NET_README.md](../CFV_NET_README.md) - Full CFV net documentation
- [QUICKSTART.md](../QUICKSTART.md) - Getting started guide
- [RUNTIME_REQUIREMENTS_QUICKREF.md](../RUNTIME_REQUIREMENTS_QUICKREF.md) - Runtime requirements
