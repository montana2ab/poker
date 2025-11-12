# Vision Metrics Integration Guide

## Overview

The vision metrics tracking system has been **activated by default** in all CLI commands (`run_dry_run.py`, `run_autoplay.py`) to provide comprehensive real-time monitoring of the vision system's performance.

## Features

The vision metrics system tracks:

### 1. OCR Accuracy
- **Total readings**: Number of OCR operations performed
- **Accuracy percentage**: Percentage of correct OCR readings (when ground truth is available)
- **Latency metrics**: Mean, P50, P95, P99 latency in milliseconds

### 2. Amount Recognition (Stacks, Pot, Bets)
- **MAE (Mean Absolute Error)**: Average error in currency units
- **MAPE (Mean Absolute Percentage Error)**: Percentage-based error metric
- **Category-specific metrics**: Separate tracking for stacks, pot, and bets
- **Seat-specific tracking**: Per-player metrics

### 3. Card Recognition
- **Accuracy percentage**: Overall and per-street (preflop, flop, turn, river)
- **Confidence scores**: Average confidence of card detection
- **Confusion matrix**: Tracks which cards/suits are commonly misidentified
- **Street-specific tracking**: Separate metrics for each poker street

### 4. Performance Metrics
- **Parse latency**: Full table state parsing time
- **Threshold monitoring**: Alerts when latency exceeds configured thresholds
- **P95/P99 tracking**: High-percentile latency monitoring

### 5. Alert System
- **Configurable thresholds**: Customizable warning and critical levels
- **Multi-level alerts**: INFO, WARNING, CRITICAL
- **Hysteresis**: Prevents alert spam from transient issues
- **Alert history**: Tracks all alerts with timestamps

### 6. Flicker Detection
- **Value oscillation**: Detects rapid changes in OCR readings
- **Configurable window**: Time window for flicker detection (default: 10s)
- **Change threshold**: Number of changes to trigger alert (default: 5)

## Usage

### CLI Arguments

All vision-enabled CLI commands now support the following arguments:

```bash
# Enable vision metrics (default behavior)
--enable-vision-metrics

# Disable vision metrics
--disable-vision-metrics

# Set reporting interval (default: 60 seconds, 0 = only at end)
--metrics-report-interval 60

# Save metrics report to file
--metrics-output /path/to/metrics_report.txt

# Choose report format (text or json)
--metrics-format text
```

### Example: Dry-Run with Metrics

```bash
# Run dry-run with default metrics (60s reporting interval)
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --enable-vision-metrics

# Run with custom reporting interval (every 30 seconds)
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --metrics-report-interval 30

# Run with JSON output saved to file
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --metrics-output results/vision_metrics.json \
  --metrics-format json

# Run without metrics
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --disable-vision-metrics
```

### Example: Auto-Play with Metrics

```bash
# Run auto-play with metrics tracking
python -m holdem.cli.run_autoplay \
  --profile assets/table_profiles/default_profile.json \
  --policy runs/blueprint/avg_policy.json \
  --i-understand-the-tos \
  --enable-vision-metrics \
  --metrics-output results/autoplay_metrics.txt
```

## Report Formats

### Text Format

Human-readable format with clear sections:

```
================================================================================
VISION METRICS REPORT
================================================================================
Session Duration: 120.5 seconds

OCR METRICS:
  Total Readings: 150
  With Ground Truth: 120
  Accuracy: 98.3%
  Mean Latency: 5.2ms
  P50 Latency: 5.0ms
  P95 Latency: 7.5ms

AMOUNT METRICS:
  Total Readings: 450
  With Ground Truth: 400
  MAE (All): 0.05 units
  MAE (Stacks): 0.03 units
  MAE (Pot): 0.08 units
  MAE (Bets): 0.04 units
  MAPE (All): 0.25%

CARD RECOGNITION METRICS:
  Total Recognitions: 200
  With Ground Truth: 180
  Accuracy (All): 97.2%
  Accuracy (Preflop): 99.0%
  Accuracy (Flop): 96.5%
  Accuracy (Turn): 97.0%
  Accuracy (River): 96.8%
  Mean Confidence: 0.94

PERFORMANCE METRICS:
  Mean Parse Latency: 18.5ms
  P50 Parse Latency: 17.2ms
  P95 Parse Latency: 24.5ms
  P99 Parse Latency: 28.3ms
  P95 Threshold Met (50.0ms): ✓
  P99 Threshold Met (80.0ms): ✓

ALERTS:
  Total: 2
  Critical: 0
  Warning: 2
  Info: 0
================================================================================
```

### JSON Format

Machine-readable format for further analysis:

```json
{
  "session_duration_seconds": 120.5,
  "context": {
    "ui_theme": "dark",
    "resolution": [1920, 1080],
    "zoom_level": 1.0,
    "profile_version": "v1.2.3",
    "template_hash": "abc123"
  },
  "ocr": {
    "total_readings": 150,
    "with_ground_truth": 120,
    "accuracy": 0.983,
    "mean_latency_ms": 5.2,
    "p50_latency_ms": 5.0,
    "p95_latency_ms": 7.5,
    "p99_latency_ms": 9.2
  },
  "amounts": {
    "total_readings": 450,
    "with_ground_truth": 400,
    "mae_all": 0.05,
    "mae_stack": 0.03,
    "mae_pot": 0.08,
    "mae_bet": 0.04,
    "mape_all": 0.0025
  },
  "cards": {
    "total_recognitions": 200,
    "with_ground_truth": 180,
    "accuracy_all": 0.972,
    "accuracy_preflop": 0.99,
    "accuracy_flop": 0.965,
    "accuracy_turn": 0.97,
    "accuracy_river": 0.968,
    "mean_confidence": 0.94
  }
}
```

## Configuration

### Threshold Configuration

You can customize alert thresholds by modifying `VisionMetricsConfig`:

```python
from holdem.vision.vision_metrics import VisionMetricsConfig, VisionMetrics

# Custom configuration
config = VisionMetricsConfig(
    # OCR thresholds
    ocr_accuracy_warning=0.90,    # 90%
    ocr_accuracy_critical=0.80,   # 80%
    
    # Amount MAE thresholds
    amount_mae_warning=0.02,      # 2 cents
    amount_mae_critical=0.05,     # 5 cents
    
    # Amount MAPE thresholds
    amount_mape_warning=0.002,    # 0.2%
    amount_mape_critical=0.01,    # 1.0%
    
    # Card recognition thresholds
    card_accuracy_warning=0.95,   # 95%
    card_accuracy_critical=0.90,  # 90%
    
    # Latency thresholds
    latency_p95_threshold=50.0,   # 50ms
    latency_p99_threshold=80.0,   # 80ms
    
    # Flicker detection
    flicker_window_seconds=10.0,
    flicker_threshold_count=5,
    
    # Alert hysteresis
    alert_hysteresis_windows=3,
    min_samples_for_alert=10
)

metrics = VisionMetrics(config)
```

## Export Formats

### JSON Lines (JSONL)

When you specify `--metrics-output`, the system automatically exports a `.jsonl` file alongside the report:

```bash
python -m holdem.cli.run_dry_run \
  --profile profile.json \
  --policy policy.json \
  --metrics-output results/report.txt

# Creates:
# - results/report.txt (text/json report)
# - results/report.jsonl (structured data)
```

The JSONL file contains:
1. Context line (UI theme, resolution, etc.)
2. Summary line (complete metrics snapshot)

### Prometheus Format

For integration with monitoring systems:

```python
from holdem.vision.vision_metrics import get_vision_metrics

metrics = get_vision_metrics()
prometheus_text = metrics.export_prometheus_metrics()
print(prometheus_text)
```

Output:
```
# HELP vision_ocr_accuracy OCR accuracy percentage
# TYPE vision_ocr_accuracy gauge
vision_ocr_accuracy 0.983

# HELP vision_amount_mae_units Amount Mean Absolute Error in units
# TYPE vision_amount_mae_units gauge
vision_amount_mae_units{category="all"} 0.05
vision_amount_mae_units{category="stack"} 0.03

# HELP vision_card_accuracy Card recognition accuracy percentage
# TYPE vision_card_accuracy gauge
vision_card_accuracy{street="all"} 0.972
vision_card_accuracy{street="preflop"} 0.99
```

## Programmatic Usage

### In Python Code

```python
from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig

# Create metrics instance
config = VisionMetricsConfig()
metrics = VisionMetrics(config)

# Record OCR reading
metrics.record_ocr(
    detected_text="12.50",
    expected_text="12.50",
    latency_ms=5.2
)

# Record amount
metrics.record_amount(
    detected_amount=100.0,
    expected_amount=100.0,
    category="stack",
    seat_position=0
)

# Record card recognition
metrics.record_card_recognition(
    detected_card="Ah",
    expected_card="Ah",
    confidence=0.95,
    street="preflop",
    seat_position=0
)

# Get summary
summary = metrics.get_summary()
print(f"OCR Accuracy: {summary['ocr']['accuracy']:.1%}")

# Generate report
report = metrics.generate_report(format="text")
print(report)

# Get alerts
from holdem.vision.vision_metrics import AlertLevel
critical_alerts = metrics.get_alerts(level=AlertLevel.CRITICAL)
for alert in critical_alerts:
    print(f"[{alert.level.value}] {alert.message}")
```

## Troubleshooting

### No Metrics Being Recorded

1. Check that `--enable-vision-metrics` is set (it's the default)
2. Verify that `--disable-vision-metrics` is NOT set
3. Check logs for vision metrics initialization messages

### Metrics Report Not Appearing

1. Verify `--metrics-report-interval` is > 0 for periodic reports
2. Reports appear on Ctrl+C (final report) even if interval is 0
3. Check `--metrics-output` file if specified

### Alert Spam

If you're getting too many alerts:

1. Adjust thresholds in `VisionMetricsConfig`
2. Increase `alert_hysteresis_windows` (default: 3)
3. Increase `min_samples_for_alert` (default: 10)

### Flicker Detection False Positives

If flicker detection is too sensitive:

1. Increase `flicker_window_seconds` (default: 10.0)
2. Increase `flicker_threshold_count` (default: 5)

## Performance Impact

Vision metrics tracking has **minimal performance impact**:

- **Memory**: ~1-2 MB for typical session
- **CPU**: <1% additional overhead
- **I/O**: Only on report generation (periodic or final)

## Best Practices

1. **Always enable metrics in production** to track vision system health
2. **Set appropriate report intervals**: 
   - Short sessions (< 5 min): 30s
   - Medium sessions (5-30 min): 60s (default)
   - Long sessions (> 30 min): 120-300s
3. **Save metrics to files** for post-session analysis
4. **Monitor alerts** to catch vision system degradation early
5. **Use JSON format** for automated analysis pipelines

## Future Enhancements

Potential improvements to the vision metrics system:

- [ ] Real-time dashboard/overlay
- [ ] Metrics persistence across sessions
- [ ] Comparison with baseline metrics
- [ ] Automated calibration recommendations
- [ ] Integration with TensorBoard
- [ ] Per-table-profile metrics tracking
- [ ] Anomaly detection using ML

## See Also

- [VISION_METRICS_GUIDE.md](VISION_METRICS_GUIDE.md) - Original metrics documentation
- [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) - Table calibration guide
- [OCR_ENHANCEMENT_SUMMARY.md](OCR_ENHANCEMENT_SUMMARY.md) - OCR improvements
