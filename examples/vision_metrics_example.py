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


if __name__ == "__main__":
    example_basic_usage()
    example_with_alerts()
    example_report_generation()
    example_with_state_parser()
    example_global_instance()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
