"""Example demonstrating VisionMetrics usage.

This script shows how to:
1. Create and configure VisionMetrics
2. Track OCR, amount, and card recognition results
3. Monitor alerts
4. Generate reports
"""

import sys
sys.path.insert(0, 'src')

from holdem.vision.vision_metrics import (
    VisionMetrics,
    VisionMetricsConfig,
    AlertLevel,
    get_vision_metrics,
)


def example_basic_usage():
    """Basic VisionMetrics usage."""
    print("=" * 60)
    print("EXAMPLE 1: Basic Usage")
    print("=" * 60)
    
    # Create metrics tracker with default configuration
    metrics = VisionMetrics()
    
    # Simulate OCR readings
    print("\nRecording OCR results...")
    for i in range(10):
        # 90% accuracy: 9 correct, 1 incorrect
        detected = str(i) if i < 9 else "X"
        expected = str(i)
        metrics.record_ocr(detected, expected_text=expected, latency_ms=12.5)
    
    print(f"OCR Accuracy: {metrics.get_ocr_accuracy():.1%}")
    
    # Simulate amount readings (stacks, pots, bets)
    print("\nRecording amount readings...")
    for i in range(10):
        # Simulate small errors in OCR amounts
        true_amount = 100.0
        detected_amount = true_amount + (i * 0.5)  # Increasing error
        metrics.record_amount(
            detected_amount=detected_amount,
            expected_amount=true_amount,
            category="stack"
        )
    
    print(f"Amount MAE: {metrics.get_amount_mae():.2f}")
    
    # Simulate card recognition
    print("\nRecording card recognition...")
    cards = ["Ah", "Kd", "Qs", "Jh", "Tc"]
    for card in cards:
        metrics.record_card_recognition(
            detected_card=card,
            expected_card=card,
            confidence=0.95,
            latency_ms=5.2
        )
    
    print(f"Card Accuracy: {metrics.get_card_accuracy():.1%}")
    
    # Display summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    summary = metrics.get_summary()
    print(f"Total OCR readings: {summary['ocr']['total_readings']}")
    print(f"Total amount readings: {summary['amounts']['total_readings']}")
    print(f"Total card recognitions: {summary['cards']['total_recognitions']}")
    print(f"Total alerts: {summary['alerts']['total']}")


def example_with_alerts():
    """Example demonstrating alert system."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 2: Alert System")
    print("=" * 60)
    
    # Create metrics with stricter thresholds
    config = VisionMetricsConfig(
        ocr_accuracy_warning=0.90,
        ocr_accuracy_critical=0.80,
        amount_mae_warning=1.0,
        amount_mae_critical=2.0,
        min_samples_for_alert=5
    )
    metrics = VisionMetrics(config=config)
    
    # Simulate poor OCR accuracy (will trigger alert)
    print("\nSimulating poor OCR accuracy...")
    for i in range(5):
        # Only 40% accuracy (2 out of 5 correct)
        detected = str(i) if i < 2 else "X"
        expected = str(i)
        metrics.record_ocr(detected, expected_text=expected)
    
    # Check for alerts
    critical_alerts = metrics.get_alerts(level=AlertLevel.CRITICAL)
    warning_alerts = metrics.get_alerts(level=AlertLevel.WARNING)
    
    print(f"\nCritical alerts: {len(critical_alerts)}")
    print(f"Warning alerts: {len(warning_alerts)}")
    
    if critical_alerts:
        print("\nCritical Alerts:")
        for alert in critical_alerts:
            print(f"  - {alert.message}")
            print(f"    Current: {alert.current_value:.1%}, Threshold: {alert.threshold:.1%}")


def example_report_generation():
    """Example demonstrating report generation."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 3: Report Generation")
    print("=" * 60)
    
    # Create metrics and add some data
    metrics = VisionMetrics()
    
    # Add various types of data
    for i in range(20):
        metrics.record_ocr(str(i), expected_text=str(i), latency_ms=10.0 + i * 0.5)
        metrics.record_amount(100.0 + i, expected_amount=100.0, category="stack")
        metrics.record_card_recognition(f"A{i%4}", expected_card=f"A{i%4}", confidence=0.92)
    
    metrics.record_parse_latency(45.0)
    metrics.record_parse_latency(50.0)
    
    # Generate text report
    print("\nText Report:")
    print("-" * 60)
    print(metrics.generate_report(format="text"))
    
    # Generate JSON report
    print("\nJSON Report (truncated):")
    print("-" * 60)
    import json
    json_report = metrics.generate_report(format="json")
    data = json.loads(json_report)
    print(json.dumps(data, indent=2)[:500] + "...")


def example_with_state_parser():
    """Example showing integration with StateParser (conceptual)."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 4: Integration with StateParser")
    print("=" * 60)
    
    print("""
To use VisionMetrics with StateParser:

from holdem.vision.parse_state import StateParser
from holdem.vision.vision_metrics import VisionMetrics

# Create metrics tracker
metrics = VisionMetrics()

# Create StateParser with metrics
parser = StateParser(
    profile=table_profile,
    card_recognizer=card_recognizer,
    ocr_engine=ocr_engine,
    vision_metrics=metrics  # Pass metrics here
)

# Parse game states - metrics are tracked automatically
for screenshot in screenshots:
    state = parser.parse(screenshot)

# Generate report
print(metrics.generate_report())
    """)


def example_global_instance():
    """Example using global metrics instance."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 5: Global Metrics Instance")
    print("=" * 60)
    
    # Get global instance
    metrics = get_vision_metrics()
    
    # Use it anywhere in your code
    metrics.record_ocr("test", expected_text="test")
    
    print(f"Global metrics: {len(metrics.ocr_results)} OCR results")
    print("Note: Use get_vision_metrics() to access the same instance everywhere")


def example_enhanced_features():
    """Example demonstrating enhanced features (MAPE, granular tracking, etc.)."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 6: Enhanced Features")
    print("=" * 60)
    
    # Create metrics with enhanced configuration
    config = VisionMetricsConfig(
        amount_mae_warning=0.02,  # 2 cents
        amount_mape_warning=0.002,  # 0.2%
        amount_mape_alert_threshold=0.005,  # 0.5%
        amount_mape_critical=0.01,  # 1.0%
        latency_p95_threshold=50.0,  # 50ms
        latency_p99_threshold=80.0,  # 80ms
    )
    metrics = VisionMetrics(config=config)
    
    # Set context for drift detection
    print("\nSetting vision context...")
    metrics.set_context(
        ui_theme="dark",
        resolution=(1920, 1080),
        zoom_level=1.0,
        profile_version="v1.2.3",
        template_hash="abc123def456"
    )
    
    # Record amounts with MAPE tracking
    print("\nRecording amounts with MAPE tracking...")
    metrics.record_amount(
        detected_amount=100.5,
        expected_amount=100.0,
        category="stack",
        field_name="stack_seat_0",
        seat_position=0
    )
    metrics.record_amount(
        detected_amount=201.0,
        expected_amount=200.0,
        category="pot",
        field_name="pot_main"
    )
    
    print(f"Amount MAE: {metrics.get_amount_mae():.4f} units")
    print(f"Amount MAPE: {metrics.get_amount_mape():.2%}")
    
    # Record cards with street tracking
    print("\nRecording cards with street tracking...")
    metrics.record_card_recognition("Ah", expected_card="Ah", street="preflop", seat_position=0)
    metrics.record_card_recognition("Kd", expected_card="Kd", street="preflop", seat_position=0)
    metrics.record_card_recognition("Qs", expected_card="Qs", street="flop")
    metrics.record_card_recognition("Jh", expected_card="Jh", street="flop")
    metrics.record_card_recognition("Tc", expected_card="Tc", street="flop")
    
    print(f"Card Accuracy (All): {metrics.get_card_accuracy():.1%}")
    print(f"Card Accuracy (Preflop): {metrics.get_card_accuracy(street='preflop'):.1%}")
    print(f"Card Accuracy (Flop): {metrics.get_card_accuracy(street='flop'):.1%}")
    
    # Track latencies including p99
    print("\nRecording latencies...")
    for i in range(20):
        metrics.record_parse_latency(40.0 + i)  # 40-59ms
    
    print(f"P50 Latency: {metrics.get_latency_percentile('parse', 50):.1f}ms")
    print(f"P95 Latency: {metrics.get_latency_percentile('parse', 95):.1f}ms")
    print(f"P99 Latency: {metrics.get_latency_percentile('parse', 99):.1f}ms")
    
    # Get confusion matrix
    confusion = metrics.get_card_confusion_matrix()
    if confusion:
        print("\nCard Confusion Matrix:")
        for key, values in list(confusion.items())[:3]:  # Show first 3
            print(f"  {key}: {dict(values)}")


def example_export_formats():
    """Example demonstrating export formats (JSON Lines, Prometheus)."""
    print("\n\n" + "=" * 60)
    print("EXAMPLE 7: Export Formats")
    print("=" * 60)
    
    metrics = VisionMetrics()
    
    # Add some data
    metrics.set_context(ui_theme="light", resolution=(1920, 1080))
    metrics.record_ocr("123", expected_text="123", latency_ms=10.0)
    metrics.record_amount(100.5, expected_amount=100.0, category="stack")
    metrics.record_card_recognition("Ah", expected_card="Ah", street="flop")
    metrics.record_parse_latency(45.0)
    
    # Export to JSON Lines
    print("\nJSON Lines export (to file):")
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.jsonl', delete=False) as f:
        filepath = f.name
    metrics.export_jsonlines(filepath)
    print(f"  Exported to: {filepath}")
    
    # Export to Prometheus format
    print("\nPrometheus metrics export:")
    print("-" * 60)
    prom_metrics = metrics.export_prometheus_metrics()
    print(prom_metrics[:500] + "...")  # Show first 500 chars


if __name__ == "__main__":
    example_basic_usage()
    example_with_alerts()
    example_report_generation()
    example_with_state_parser()
    example_global_instance()
    example_enhanced_features()
    example_export_formats()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
