# VisionMetrics Guide

Comprehensive vision system metrics tracking with OCR accuracy, MAE for amounts, thresholds/alerts, and reporting.

## Overview

VisionMetrics provides end-to-end tracking of the vision system's performance, including:

- **OCR Accuracy**: Percentage of correct text readings
- **Amount MAE**: Mean Absolute Error for stack sizes, pot amounts, and bets
- **Card Recognition Accuracy**: Percentage of correctly recognized cards
- **Performance Metrics**: Latency tracking for OCR, card recognition, and full state parsing
- **Alert System**: Configurable thresholds with WARNING and CRITICAL alert levels
- **Reporting**: Comprehensive reports in text and JSON formats

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

# Record amount readings
metrics.record_amount(
    detected_amount=100.0,
    expected_amount=99.0,  # Optional ground truth
    category="stack"       # "stack", "pot", or "bet"
)

# Record card recognition
metrics.record_card_recognition(
    detected_card="Ah",
    expected_card="Ah",    # Optional ground truth
    confidence=0.95,
    latency_ms=5.2         # Optional latency
)

# Get metrics
print(f"OCR Accuracy: {metrics.get_ocr_accuracy():.1%}")
print(f"Amount MAE: {metrics.get_amount_mae():.2f}")
print(f"Card Accuracy: {metrics.get_card_accuracy():.1%}")

# Generate report
print(metrics.generate_report(format="text"))
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
  ocr_accuracy_warning: 0.90
  ocr_accuracy_critical: 0.80
  amount_mae_warning: 1.0
  amount_mae_critical: 2.0
  card_accuracy_warning: 0.95
  card_accuracy_critical: 0.90
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

### High MAE Values

If amount MAE is high:
1. Check OCR engine configuration
2. Verify image preprocessing
3. Review region coordinates in table profile
4. Consider OCR backend (PaddleOCR vs pytesseract)

## API Reference

### VisionMetrics

Main class for tracking vision metrics.

**Methods:**
- `record_ocr(detected_text, expected_text=None, latency_ms=None)`
- `record_amount(detected_amount, expected_amount=None, category="unknown")`
- `record_card_recognition(detected_card, expected_card=None, confidence=0.0, latency_ms=None)`
- `record_parse_latency(latency_ms)`
- `get_ocr_accuracy() -> Optional[float]`
- `get_amount_mae(category=None) -> Optional[float]`
- `get_card_accuracy() -> Optional[float]`
- `get_summary() -> Dict[str, Any]`
- `get_alerts(level=None, since=None) -> List[Alert]`
- `generate_report(format="text") -> str`
- `reset()`

### VisionMetricsConfig

Configuration dataclass for thresholds.

**Attributes:**
- `ocr_accuracy_warning: float = 0.90`
- `ocr_accuracy_critical: float = 0.80`
- `amount_mae_warning: float = 1.0`
- `amount_mae_critical: float = 2.0`
- `card_accuracy_warning: float = 0.95`
- `card_accuracy_critical: float = 0.90`
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
