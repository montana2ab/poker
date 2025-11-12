# VisionMetrics Guide

Comprehensive vision system metrics tracking with OCR accuracy, MAE/MAPE for amounts, card confusion matrix, flicker detection, thresholds/alerts, and observability exports.

## Overview

VisionMetrics provides end-to-end tracking of the vision system's performance, including:

- **OCR Accuracy**: Percentage of correct text readings
- **Amount MAE & MAPE**: Mean Absolute Error (in units) and Mean Absolute Percentage Error for stack sizes, pot amounts, and bets
- **Granular Tracking**: Per-field and per-seat position metrics
- **Card Recognition Accuracy**: Percentage of correctly recognized cards, by street (preflop/flop/turn/river)
- **Card Confusion Matrix**: Track rank and suit misidentifications
- **Performance Metrics**: Latency tracking (p50/p95/p99) for OCR, card recognition, and full state parsing
- **Flicker Detection**: Detect rapidly oscillating values with hysteresis-based alerting
- **Context Tracking**: Monitor UI theme, resolution, zoom level for drift detection
- **Alert System**: Configurable thresholds with INFO, WARNING and CRITICAL alert levels
- **Reporting**: Comprehensive reports in text and JSON formats
- **Exports**: JSON Lines and Prometheus metrics for Grafana integration

## What's New in Enhanced Version

### Enhanced Amount Metrics
- **MAPE Tracking**: Calculate Mean Absolute Percentage Error alongside MAE
- **Strict Thresholds**: MAE < 0.02 units (2 cents), MAPE < 0.2% (Warning 0.5%, Critical 1%)
- **Granular Tracking**: Track amounts per field name and seat position

### Card Recognition Enhancements
- **Street-Level Accuracy**: Track accuracy separately for preflop, flop, turn, river
- **Confusion Matrix**: Identify systematic rank/suit misidentifications
- **Per-Seat Tracking**: Monitor card recognition per player position

### Latency Monitoring
- **P99 Latency**: Track 99th percentile alongside p50 and p95
- **Threshold Checks**: Configurable thresholds (default: p95 ≤ 50ms, p99 ≤ 80ms)

### Flicker & Drift Detection
- **Oscillation Detection**: Count value changes in sliding time windows
- **Hysteresis Alerting**: Require N consecutive windows before alerting
- **Context Tracking**: Monitor UI theme, resolution, zoom for drift detection

### Observability & Exports
- **JSON Lines**: Append-friendly format for log aggregation
- **Prometheus Metrics**: Gauges, counters, and histograms for Grafana
- **Ground Truth Versioning**: Track profile/template hashes for reproducibility

## Quick Start

### Basic Usage

```python
from holdem.vision.vision_metrics import VisionMetrics

# Create metrics tracker
metrics = VisionMetrics()

# Record OCR results
metrics.record_ocr(
    detected_text="1234",
    expected_text="1234",  # Optional ground truth
    latency_ms=12.5        # Optional latency
)

# Record amount readings with granular tracking
metrics.record_amount(
    detected_amount=100.5,
    expected_amount=100.0,  # Optional ground truth
    category="stack",       # "stack", "pot", or "bet"
    field_name="stack_seat_0",  # Optional field name for flicker detection
    seat_position=0         # Optional seat position (0-8 for 9-max, 0-5 for 6-max)
)

# Record card recognition with street tracking
metrics.record_card_recognition(
    detected_card="Ah",
    expected_card="Ah",     # Optional ground truth
    confidence=0.95,
    latency_ms=5.2,         # Optional latency
    street="flop",          # Optional: "preflop", "flop", "turn", "river"
    seat_position=0         # Optional seat position for hole cards
)

# Get metrics
print(f"OCR Accuracy: {metrics.get_ocr_accuracy():.1%}")
print(f"Amount MAE: {metrics.get_amount_mae():.4f} units")
print(f"Amount MAPE: {metrics.get_amount_mape():.2%}")
print(f"Card Accuracy (All): {metrics.get_card_accuracy():.1%}")
print(f"Card Accuracy (Flop): {metrics.get_card_accuracy(street='flop'):.1%}")

# Generate report
print(metrics.generate_report(format="text"))
```

### Enhanced Features Usage

```python
from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig

# Create metrics with enhanced configuration
config = VisionMetricsConfig(
    # Amount thresholds
    amount_mae_warning=0.02,            # 2 cents
    amount_mae_critical=0.05,           # 5 cents
    amount_mape_warning=0.002,          # 0.2%
    amount_mape_alert_threshold=0.005,  # 0.5%
    amount_mape_critical=0.01,          # 1.0%
    
    # Latency thresholds
    latency_p95_threshold=50.0,         # 50ms
    latency_p99_threshold=80.0,         # 80ms
    
    # Flicker detection
    flicker_window_seconds=10.0,        # 10s window
    flicker_threshold_count=5,          # 5 changes to trigger
    alert_hysteresis_windows=3,         # 3 consecutive windows for alert
)
metrics = VisionMetrics(config=config)

# Set context for drift detection
metrics.set_context(
    ui_theme="dark",
    resolution=(1920, 1080),
    zoom_level=1.0,
    profile_version="v1.2.3",
    template_hash="abc123def456"
)

# Ingest ground truth data
metrics.ingest_ground_truth({
    "image_id": "test_001",
    "stacks": [100, 200, 300],
    "pot": 50
})

# Get advanced metrics
print(f"P99 Latency: {metrics.get_latency_percentile('parse', 99):.1f}ms")
print(f"Confusion Matrix: {metrics.get_card_confusion_matrix()}")

# Export for observability
metrics.export_jsonlines("metrics.jsonl")
print(metrics.export_prometheus_metrics())
```

### Integration with StateParser

VisionMetrics can be automatically integrated with the StateParser to track all vision operations:

```python
from holdem.vision.parse_state import StateParser
from holdem.vision.vision_metrics import VisionMetrics
from holdem.vision.calibrate import TableProfile
from holdem.vision.cards import CardRecognizer
from holdem.vision.ocr import OCREngine

# Create metrics tracker
metrics = VisionMetrics()

# Load table profile
profile = TableProfile.load("assets/table_profiles/default_profile.json")

# Create components
card_recognizer = CardRecognizer("assets/templates/")
ocr_engine = OCREngine(backend="paddleocr")

# Create StateParser with metrics
parser = StateParser(
    profile=profile,
    card_recognizer=card_recognizer,
    ocr_engine=ocr_engine,
    vision_metrics=metrics  # Pass metrics here
)

# Parse game states - metrics are tracked automatically
for screenshot in screenshots:
    state = parser.parse(screenshot)

# Generate report after parsing
print(metrics.generate_report())
```

## Configuration

### Using YAML Configuration

Create a configuration file with custom thresholds:

```yaml
# configs/vision_metrics_config.yaml
vision_metrics:
  # OCR thresholds
  ocr_accuracy_warning: 0.90
  ocr_accuracy_critical: 0.80
  
  # Amount MAE thresholds (in currency units)
  amount_mae_warning: 0.02      # 2 cents
  amount_mae_critical: 0.05     # 5 cents
  
  # Amount MAPE thresholds
  amount_mape_warning: 0.002              # 0.2%
  amount_mape_alert_threshold: 0.005      # 0.5%
  amount_mape_critical: 0.01              # 1.0%
  
  # Card recognition thresholds
  card_accuracy_warning: 0.95
  card_accuracy_critical: 0.90
  
  # Latency thresholds (milliseconds)
  latency_p95_threshold: 50.0
  latency_p99_threshold: 80.0
  
  # Flicker detection
  flicker_window_seconds: 10.0
  flicker_threshold_count: 5
  alert_hysteresis_windows: 3
  
  # Minimum samples before alerting
  min_samples_for_alert: 10
```

Load and use the configuration:

```python
from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig
import yaml

# Load configuration
with open('configs/vision_metrics_config.yaml') as f:
    config_dict = yaml.safe_load(f)

# Create config object
config = VisionMetricsConfig(**config_dict['vision_metrics'])

# Create metrics with config
metrics = VisionMetrics(config=config)
```

### Programmatic Configuration

```python
from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig

# Create custom configuration
config = VisionMetricsConfig(
    ocr_accuracy_warning=0.85,
    ocr_accuracy_critical=0.75,
    amount_mae_warning=0.5,
    amount_mae_critical=1.5,
    card_accuracy_warning=0.93,
    card_accuracy_critical=0.88,
    min_samples_for_alert=5
)

# Create metrics with config
metrics = VisionMetrics(config=config)
```

## Alert System

VisionMetrics includes an alert system that monitors metrics and generates alerts when they fall below configured thresholds.

### Alert Levels

- **INFO**: Informational messages (not currently used)
- **WARNING**: Metrics below warning threshold but above critical
- **CRITICAL**: Metrics below critical threshold - immediate attention needed

### Monitoring Alerts

```python
from holdem.vision.vision_metrics import AlertLevel

# Get all alerts
all_alerts = metrics.get_alerts()

# Get critical alerts only
critical_alerts = metrics.get_alerts(level=AlertLevel.CRITICAL)

# Get recent alerts (last hour)
import time
one_hour_ago = time.time() - 3600
recent_alerts = metrics.get_alerts(since=one_hour_ago)

# Print alerts
for alert in critical_alerts:
    print(f"[{alert.level.value}] {alert.message}")
    print(f"  Current: {alert.current_value:.2%}")
    print(f"  Threshold: {alert.threshold:.2%}")
```

### Automatic Alert Generation

Alerts are automatically generated when recording metrics:

```python
config = VisionMetricsConfig(
    ocr_accuracy_critical=0.80,
    min_samples_for_alert=5
)
metrics = VisionMetrics(config=config)

# Record poor OCR accuracy
for i in range(5):
    metrics.record_ocr("wrong", expected_text="right")

# Alert is automatically generated and logged
# [ERROR] OCR accuracy critically low: 0.0%
```

## Metrics Reference

### OCR Metrics

- **Total Readings**: Number of OCR operations performed
- **With Ground Truth**: Number of readings with expected values for validation
- **Accuracy**: Percentage of correct readings (requires ground truth)
- **Mean Latency**: Average time taken for OCR (milliseconds)
- **P50/P95 Latency**: Median and 95th percentile latency

### Amount Metrics

- **Total Readings**: Number of amount readings (stacks, pots, bets)
- **With Ground Truth**: Number of readings with expected values
- **MAE (All)**: Mean Absolute Error across all categories
- **MAE (Stack/Pot/Bet)**: MAE per category

### Card Recognition Metrics

- **Total Recognitions**: Number of card recognition operations
- **With Ground Truth**: Number with expected values
- **Accuracy**: Percentage of correctly recognized cards
- **Mean Confidence**: Average confidence score
- **Mean Latency**: Average recognition time (milliseconds)

### Performance Metrics

- **Mean Parse Latency**: Average time for full state parse (milliseconds)
- **P50/P95 Parse Latency**: Median and 95th percentile parse time

## Report Generation

### Text Reports

Generate human-readable text reports:

```python
report = metrics.generate_report(format="text")
print(report)
```

Example output:

```
================================================================================
VISION METRICS REPORT
================================================================================
Session Duration: 120.5 seconds

OCR METRICS:
  Total Readings: 450
  With Ground Truth: 120
  Accuracy: 94.2%
  Mean Latency: 12.3ms
  P50 Latency: 11.8ms
  P95 Latency: 18.5ms

AMOUNT METRICS:
  Total Readings: 320
  With Ground Truth: 80
  MAE (All): 0.85
  MAE (Stacks): 0.75
  MAE (Pot): 0.92
  MAE (Bets): 0.88

CARD RECOGNITION METRICS:
  Total Recognitions: 180
  With Ground Truth: 60
  Accuracy: 98.3%
  Mean Confidence: 0.94
  Mean Latency: 5.2ms

PERFORMANCE METRICS:
  Mean Parse Latency: 45.2ms
  P50 Parse Latency: 42.0ms
  P95 Parse Latency: 58.3ms

ALERTS:
  Total: 3
  Critical: 1
  Warning: 2
  Info: 0
================================================================================
```

### JSON Reports

Generate machine-readable JSON reports:

```python
import json

report_json = metrics.generate_report(format="json")
data = json.loads(report_json)

# Access specific metrics
ocr_accuracy = data['ocr']['accuracy']
amount_mae = data['amounts']['mae_all']
```

### Summary Dictionary

Get metrics as a Python dictionary:

```python
summary = metrics.get_summary()

# Access metrics
print(f"OCR Accuracy: {summary['ocr']['accuracy']:.1%}")
print(f"Total Alerts: {summary['alerts']['total']}")
```

## Global Metrics Instance

Use a global metrics instance for convenient access across your codebase:

```python
from holdem.vision.vision_metrics import get_vision_metrics, reset_vision_metrics

# Get global instance (created on first call)
metrics = get_vision_metrics()

# Use it anywhere
metrics.record_ocr("test", expected_text="test")

# Reset when needed
reset_vision_metrics()

# Get fresh instance
metrics = get_vision_metrics()
```

## Advanced Usage

### Tracking Ground Truth

When you have ground truth data (e.g., from test datasets or manual validation):

```python
# OCR with ground truth
metrics.record_ocr(
    detected_text="123.45",
    expected_text="123.45"  # Ground truth
)

# Amount with ground truth
metrics.record_amount(
    detected_amount=102.3,
    expected_amount=100.0,  # True value
    category="stack"
)

# Card with ground truth
metrics.record_card_recognition(
    detected_card="Ah",
    expected_card="Ah",  # True card
    confidence=0.95
)
```

### Category-Specific MAE

Get MAE for specific amount categories:

```python
# All amounts
mae_all = metrics.get_amount_mae()

# Stacks only
mae_stacks = metrics.get_amount_mae(category="stack")

# Pots only
mae_pots = metrics.get_amount_mae(category="pot")

# Bets only
mae_bets = metrics.get_amount_mae(category="bet")
```

### Resetting Metrics

Reset metrics to start a new tracking session:

```python
# Clear all metrics and alerts
metrics.reset()

# Metrics are now empty
assert metrics.get_ocr_accuracy() is None
assert len(metrics.get_alerts()) == 0
```

## Enhanced Features

### MAPE Tracking

Calculate Mean Absolute Percentage Error for more robust amount tracking:

```python
# Record amounts with ground truth
metrics.record_amount(102.0, expected_amount=100.0, category="stack")
metrics.record_amount(205.0, expected_amount=200.0, category="pot")

# Get MAPE
mape_all = metrics.get_amount_mape()  # All categories
mape_stack = metrics.get_amount_mape(category="stack")  # Stacks only

print(f"MAPE (All): {mape_all:.2%}")  # e.g., "0.25%"
print(f"MAPE (Stack): {mape_stack:.2%}")  # e.g., "2.00%"
```

### Granular Tracking

Track metrics per field name and seat position:

```python
# Track stack for each seat
for seat in range(6):  # 6-max table
    metrics.record_amount(
        detected_amount=100.0 + seat * 10,
        expected_amount=100.0,
        category="stack",
        field_name=f"stack_seat_{seat}",
        seat_position=seat
    )

# Get MAE for specific seat
mae_seat_0 = metrics.get_amount_mae(seat_position=0)
mae_seat_1 = metrics.get_amount_mae(seat_position=1)
```

### Card Confusion Matrix

Track systematic card recognition errors:

```python
# Record card recognitions
metrics.record_card_recognition("Ah", expected_card="Ah")  # Correct
metrics.record_card_recognition("Kh", expected_card="Ah")  # Wrong rank
metrics.record_card_recognition("Ad", expected_card="Ah")  # Wrong suit

# Get confusion matrix
confusion = metrics.get_card_confusion_matrix()
print(confusion)
# Output:
# {
#   'rank_A': {'A': 2, 'K': 1},
#   'suit_h': {'h': 2, 'd': 1}
# }
```

### Street-Level Card Accuracy

Track card recognition accuracy by poker street:

```python
# Record cards by street
metrics.record_card_recognition("Ah", expected_card="Ah", street="preflop")
metrics.record_card_recognition("Kd", expected_card="Kd", street="preflop")
metrics.record_card_recognition("Qs", expected_card="Qs", street="flop")
metrics.record_card_recognition("Jh", expected_card="Jh", street="flop")
metrics.record_card_recognition("Tc", expected_card="Xx", street="flop")  # Error

# Get accuracy by street
acc_preflop = metrics.get_card_accuracy(street="preflop")  # 100%
acc_flop = metrics.get_card_accuracy(street="flop")        # 66.7%
```

### P99 Latency Tracking

Monitor tail latencies with p99:

```python
# Record latencies
for i in range(100):
    metrics.record_parse_latency(40.0 + i * 0.5)  # 40-90ms

# Get percentiles
p50 = metrics.get_latency_percentile("parse", 50)  # ~65ms
p95 = metrics.get_latency_percentile("parse", 95)  # ~87ms
p99 = metrics.get_latency_percentile("parse", 99)  # ~89ms

# Check against thresholds
summary = metrics.get_summary()
if not summary['performance']['p95_threshold_met']:
    print("Warning: P95 latency exceeds 50ms threshold")
if not summary['performance']['p99_threshold_met']:
    print("Warning: P99 latency exceeds 80ms threshold")
```

### Flicker Detection

Detect rapidly oscillating values:

```python
config = VisionMetricsConfig(
    flicker_window_seconds=10.0,  # 10-second window
    flicker_threshold_count=5,    # Alert after 5 changes
    alert_hysteresis_windows=3    # Require 3 consecutive windows
)
metrics = VisionMetrics(config=config)

# Simulate flickering values
field_name = "pot_main"
for value in [50, 55, 50, 55, 50, 55]:
    metrics.record_amount(value, field_name=field_name)

# Check for flicker events
if len(metrics.flicker_events) > 0:
    print(f"Flicker detected in {field_name}")
```

### Context Tracking & Drift Detection

Monitor UI context for drift detection:

```python
# Set initial context
metrics.set_context(
    ui_theme="dark",
    resolution=(1920, 1080),
    zoom_level=1.0,
    profile_version="v1.2.3",
    template_hash="abc123"
)

# Later, detect changes
if metrics.context.ui_theme != "dark":
    print("UI theme changed - may affect vision accuracy")

if metrics.context.resolution != (1920, 1080):
    print("Resolution changed - recalibration recommended")
```

### Ground Truth Ingestion

Ingest reference data for validation:

```python
# Ingest ground truth from labeled dataset
ground_truth = {
    "image_id": "test_001",
    "timestamp": time.time(),
    "stacks": [100, 200, 150, 0, 0, 175],
    "pot": 50,
    "cards": ["Ah", "Kd", "Qs", "Jh", "Tc"]
}
metrics.ingest_ground_truth(ground_truth)

# Use for batch validation
for gt in labeled_dataset:
    metrics.ingest_ground_truth(gt)
```

### JSON Lines Export

Export metrics for log aggregation:

```python
# Export to JSON Lines (append-friendly)
metrics.export_jsonlines("metrics.jsonl")

# Each line is a valid JSON object
# Line 1: {"type": "context", "timestamp": ..., "data": {...}}
# Line 2: {"type": "summary", "timestamp": ..., "data": {...}}
```

### Prometheus Metrics Export

Export for Grafana dashboards:

```python
# Generate Prometheus metrics
prom_metrics = metrics.export_prometheus_metrics()

# Serve via HTTP endpoint
from flask import Flask, Response
app = Flask(__name__)

@app.route('/metrics')
def prometheus_metrics():
    return Response(
        metrics.export_prometheus_metrics(),
        mimetype='text/plain'
    )
```

Sample Prometheus output:
```
# HELP vision_ocr_accuracy OCR accuracy percentage
# TYPE vision_ocr_accuracy gauge
vision_ocr_accuracy 0.95

# HELP vision_amount_mae_units Amount Mean Absolute Error in units
# TYPE vision_amount_mae_units gauge
vision_amount_mae_units{category="all"} 0.015
vision_amount_mae_units{category="stack"} 0.012
vision_amount_mae_units{category="pot"} 0.018

# HELP vision_amount_mape Amount Mean Absolute Percentage Error
# TYPE vision_amount_mape gauge
vision_amount_mape{category="all"} 0.0015

# HELP vision_parse_latency_ms Parse latency in milliseconds
# TYPE vision_parse_latency_ms summary
vision_parse_latency_ms{quantile="0.5"} 42.0
vision_parse_latency_ms{quantile="0.95"} 48.5
vision_parse_latency_ms{quantile="0.99"} 52.3
```

## Best Practices

### 1. Use Ground Truth During Testing

Always provide expected values when testing or validating:

```python
# Good - enables accuracy tracking
metrics.record_ocr("123", expected_text="123")

# Acceptable in production - tracks latency only
metrics.record_ocr("123", expected_text=None)
```

### 2. Configure Appropriate Thresholds

Set thresholds based on your requirements:

```python
# Strict thresholds for high-stakes applications
config = VisionMetricsConfig(
    ocr_accuracy_warning=0.95,
    ocr_accuracy_critical=0.90,
    amount_mae_warning=0.5,
    amount_mae_critical=1.0
)

# Relaxed thresholds for development
config = VisionMetricsConfig(
    ocr_accuracy_warning=0.85,
    ocr_accuracy_critical=0.75,
    amount_mae_warning=2.0,
    amount_mae_critical=5.0
)
```

### 3. Monitor Alerts Regularly

Set up monitoring for critical alerts:

```python
# Check for critical alerts periodically
critical_alerts = metrics.get_alerts(level=AlertLevel.CRITICAL)
if critical_alerts:
    send_notification(f"Critical vision alerts: {len(critical_alerts)}")
```

### 4. Generate Reports Periodically

Generate and save reports at intervals:

```python
import time
from pathlib import Path

# Generate report every hour
last_report = time.time()
report_dir = Path("reports/vision_metrics")
report_dir.mkdir(parents=True, exist_ok=True)

while True:
    # ... process screenshots ...
    
    if time.time() - last_report > 3600:  # 1 hour
        timestamp = int(time.time())
        report_path = report_dir / f"metrics_{timestamp}.json"
        
        report_json = metrics.generate_report(format="json")
        report_path.write_text(report_json)
        
        last_report = time.time()
```

### 5. Use Minimal Alert Samples

Adjust `min_samples_for_alert` based on your use case:

```python
# Quick alerts during testing (5 samples)
config = VisionMetricsConfig(min_samples_for_alert=5)

# Stable alerts in production (20 samples)
config = VisionMetricsConfig(min_samples_for_alert=20)
```

## Examples

See `examples/vision_metrics_example.py` for comprehensive examples including:

1. Basic usage with OCR, amounts, and cards
2. Alert system demonstration
3. Report generation
4. Integration with StateParser
5. Global instance usage
6. Enhanced features (MAPE, granular tracking, confusion matrix)
7. Export formats (JSON Lines, Prometheus)

Run the examples:

```bash
python examples/vision_metrics_example.py
```

## Troubleshooting

### No Metrics Available

If `get_ocr_accuracy()` returns `None`, it means no data with ground truth has been recorded yet.

### Alerts Not Triggering

Check:
1. Enough samples recorded (>= `min_samples_for_alert`)
2. Ground truth values provided
3. Thresholds configured correctly

### High MAE/MAPE Values

If amount MAE or MAPE is high:
1. Check OCR engine configuration
2. Verify image preprocessing
3. Review region coordinates in table profile
4. Consider OCR backend (PaddleOCR vs pytesseract)
5. Check for systematic biases in confusion matrix

### Flicker Alerts

If getting excessive flicker alerts:
1. Increase `flicker_threshold_count`
2. Increase `flicker_window_seconds`
3. Increase `alert_hysteresis_windows`
4. Check for actual UI flickering issues

### High P99 Latency

If P99 latency exceeds thresholds:
1. Check system load
2. Profile OCR/card recognition code
3. Consider caching strategies
4. Review image resolution (downscaling may help)

## API Reference

### VisionMetrics

Main class for tracking vision metrics.

**Core Methods:**
- `record_ocr(detected_text, expected_text=None, latency_ms=None)`
- `record_amount(detected_amount, expected_amount=None, category="unknown", field_name=None, seat_position=None)`
- `record_card_recognition(detected_card, expected_card=None, confidence=0.0, latency_ms=None, street=None, seat_position=None)`
- `record_parse_latency(latency_ms)`

**Context & Ground Truth:**
- `set_context(ui_theme=None, resolution=None, zoom_level=None, profile_version=None, template_hash=None)`
- `ingest_ground_truth(data: Dict[str, Any])`

**Getters:**
- `get_ocr_accuracy() -> Optional[float]`
- `get_amount_mae(category=None, seat_position=None) -> Optional[float]`
- `get_amount_mape(category=None, seat_position=None) -> Optional[float]`
- `get_card_accuracy(street=None, seat_position=None) -> Optional[float]`
- `get_card_confusion_matrix() -> Dict[str, Dict[str, int]]`
- `get_latency_percentile(latency_type: str, percentile: int) -> Optional[float]`
- `get_summary() -> Dict[str, Any]`
- `get_alerts(level=None, since=None) -> List[Alert]`

**Reports & Exports:**
- `generate_report(format="text") -> str`
- `export_jsonlines(filepath: str)`
- `export_prometheus_metrics() -> str`

**Utility:**
- `reset()`

### VisionMetricsConfig

Configuration dataclass for thresholds.

**Attributes:**
- `ocr_accuracy_warning: float = 0.90`
- `ocr_accuracy_critical: float = 0.80`
- `amount_mae_warning: float = 0.02`  # units (e.g., cents)
- `amount_mae_critical: float = 0.05`
- `amount_mape_warning: float = 0.002`  # 0.2%
- `amount_mape_alert_threshold: float = 0.005`  # 0.5%
- `amount_mape_critical: float = 0.01`  # 1.0%
- `card_accuracy_warning: float = 0.95`
- `card_accuracy_critical: float = 0.90`
- `latency_p95_threshold: float = 50.0`  # ms
- `latency_p99_threshold: float = 80.0`  # ms
- `flicker_window_seconds: float = 10.0`
- `flicker_threshold_count: int = 5`
- `alert_hysteresis_windows: int = 3`
- `min_samples_for_alert: int = 10`

### AlertLevel

Enumeration of alert severity levels.

**Values:**
- `AlertLevel.INFO`
- `AlertLevel.WARNING`
- `AlertLevel.CRITICAL`

### Global Functions

- `get_vision_metrics() -> VisionMetrics` - Get global instance
- `reset_vision_metrics()` - Reset global instance

## See Also

- [Vision System Overview](../README.md#vision-system)
- [Calibration Guide](CALIBRATION_GUIDE.md)
- [StateParser Documentation](../src/holdem/vision/parse_state.py)
