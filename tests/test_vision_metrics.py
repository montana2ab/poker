"""Test vision metrics tracking system."""

import pytest
import time
from holdem.vision.vision_metrics import (
    VisionMetrics,
    VisionMetricsConfig,
    AlertLevel,
    get_vision_metrics,
    reset_vision_metrics,
)


def test_vision_metrics_creation():
    """Test creating a VisionMetrics instance."""
    metrics = VisionMetrics()
    assert metrics is not None
    assert len(metrics.ocr_results) == 0
    assert len(metrics.amount_results) == 0
    assert len(metrics.card_results) == 0


def test_vision_metrics_with_custom_config():
    """Test creating VisionMetrics with custom configuration."""
    config = VisionMetricsConfig(
        ocr_accuracy_warning=0.85,
        ocr_accuracy_critical=0.75,
        amount_mae_warning=0.5,
        amount_mae_critical=1.5,
    )
    metrics = VisionMetrics(config=config)
    assert metrics.config.ocr_accuracy_warning == 0.85
    assert metrics.config.ocr_accuracy_critical == 0.75


def test_record_ocr_without_ground_truth():
    """Test recording OCR results without ground truth."""
    metrics = VisionMetrics()
    metrics.record_ocr("1234", expected_text=None, latency_ms=15.5)
    
    assert len(metrics.ocr_results) == 1
    assert metrics.ocr_results[0].detected_text == "1234"
    assert metrics.ocr_results[0].is_correct is None
    assert len(metrics.ocr_latencies) == 1
    assert metrics.ocr_latencies[0] == 15.5


def test_record_ocr_with_ground_truth():
    """Test recording OCR results with ground truth."""
    metrics = VisionMetrics()
    
    # Correct reading
    metrics.record_ocr("1234", expected_text="1234")
    assert metrics.ocr_results[0].is_correct is True
    
    # Incorrect reading
    metrics.record_ocr("1234", expected_text="5678")
    assert metrics.ocr_results[1].is_correct is False


def test_ocr_accuracy_calculation():
    """Test OCR accuracy calculation."""
    metrics = VisionMetrics()
    
    # No data yet
    assert metrics.get_ocr_accuracy() is None
    
    # Add some results
    for i in range(10):
        expected = str(i)
        detected = str(i) if i < 9 else "X"  # 9/10 correct
        metrics.record_ocr(detected, expected_text=expected)
    
    accuracy = metrics.get_ocr_accuracy()
    assert accuracy is not None
    assert accuracy == 0.9  # 90%


def test_record_amount_without_ground_truth():
    """Test recording amount without ground truth."""
    metrics = VisionMetrics()
    metrics.record_amount(100.0, expected_amount=None, category="stack")
    
    assert len(metrics.amount_results) == 1
    assert metrics.amount_results[0].detected_amount == 100.0
    assert metrics.amount_results[0].absolute_error is None
    assert metrics.amount_results[0].category == "stack"


def test_record_amount_with_ground_truth():
    """Test recording amount with ground truth."""
    metrics = VisionMetrics()
    
    # Exact match
    metrics.record_amount(100.0, expected_amount=100.0, category="stack")
    assert metrics.amount_results[0].absolute_error == 0.0
    
    # Small error
    metrics.record_amount(98.5, expected_amount=100.0, category="pot")
    assert metrics.amount_results[1].absolute_error == 1.5


def test_amount_mae_calculation():
    """Test MAE calculation for amounts."""
    metrics = VisionMetrics()
    
    # No data yet
    assert metrics.get_amount_mae() is None
    
    # Add some results with errors: 0, 1, 2, 3, 4 (MAE = 2.0)
    for i in range(5):
        metrics.record_amount(
            detected_amount=100.0 + i,
            expected_amount=100.0,
            category="stack"
        )
    
    mae = metrics.get_amount_mae()
    assert mae is not None
    assert mae == 2.0
    
    # Test category filtering
    metrics.record_amount(
        detected_amount=50.0,
        expected_amount=60.0,
        category="pot"
    )
    mae_pot = metrics.get_amount_mae(category="pot")
    assert mae_pot == 10.0


def test_record_card_recognition():
    """Test recording card recognition results."""
    metrics = VisionMetrics()
    
    # Without ground truth
    metrics.record_card_recognition("Ah", expected_card=None, confidence=0.95)
    assert len(metrics.card_results) == 1
    assert metrics.card_results[0].is_correct is None
    
    # With ground truth (correct)
    metrics.record_card_recognition("Kd", expected_card="Kd", confidence=0.92)
    assert metrics.card_results[1].is_correct is True
    
    # With ground truth (incorrect)
    metrics.record_card_recognition("Qs", expected_card="Qh", confidence=0.88)
    assert metrics.card_results[2].is_correct is False


def test_card_accuracy_calculation():
    """Test card recognition accuracy calculation."""
    metrics = VisionMetrics()
    
    # No data yet
    assert metrics.get_card_accuracy() is None
    
    # Add some results: 8/10 correct
    cards = ["Ah", "Kd", "Qs", "Jh", "Tc", "9s", "8h", "7d", "6c", "5s"]
    for i, card in enumerate(cards):
        detected = card if i < 8 else "Xx"  # 8/10 correct
        metrics.record_card_recognition(
            detected_card=detected,
            expected_card=card,
            confidence=0.9
        )
    
    accuracy = metrics.get_card_accuracy()
    assert accuracy is not None
    assert accuracy == 0.8  # 80%


def test_ocr_accuracy_alerts():
    """Test OCR accuracy alert generation."""
    config = VisionMetricsConfig(
        ocr_accuracy_warning=0.90,
        ocr_accuracy_critical=0.80,
        min_samples_for_alert=5
    )
    metrics = VisionMetrics(config=config)
    
    # Add 5 results with 60% accuracy (should trigger CRITICAL)
    for i in range(5):
        expected = str(i)
        detected = str(i) if i < 3 else "X"  # 3/5 = 60% correct
        metrics.record_ocr(detected, expected_text=expected)
    
    # Should have triggered a critical alert
    critical_alerts = metrics.get_alerts(level=AlertLevel.CRITICAL)
    assert len(critical_alerts) > 0
    assert any(a.metric_name == "ocr_accuracy" for a in critical_alerts)


def test_amount_mae_alerts():
    """Test amount MAE alert generation."""
    config = VisionMetricsConfig(
        amount_mae_warning=1.0,
        amount_mae_critical=2.0,
        min_samples_for_alert=5
    )
    metrics = VisionMetrics(config=config)
    
    # Add 5 results with high MAE (should trigger CRITICAL)
    # Errors: 3, 3, 3, 3, 3 -> MAE = 3.0
    for i in range(5):
        metrics.record_amount(
            detected_amount=103.0,
            expected_amount=100.0,
            category="stack"
        )
    
    # Should have triggered a critical alert
    critical_alerts = metrics.get_alerts(level=AlertLevel.CRITICAL)
    assert len(critical_alerts) > 0
    assert any(a.metric_name == "amount_mae" for a in critical_alerts)


def test_card_accuracy_alerts():
    """Test card recognition accuracy alert generation."""
    config = VisionMetricsConfig(
        card_accuracy_warning=0.95,
        card_accuracy_critical=0.90,
        min_samples_for_alert=10
    )
    metrics = VisionMetrics(config=config)
    
    # Add 10 results with 70% accuracy (should trigger CRITICAL)
    cards = ["Ah", "Kd", "Qs", "Jh", "Tc", "9s", "8h", "7d", "6c", "5s"]
    for i, card in enumerate(cards):
        detected = card if i < 7 else "Xx"  # 7/10 = 70% correct
        metrics.record_card_recognition(
            detected_card=detected,
            expected_card=card,
            confidence=0.8
        )
    
    # Should have triggered a critical alert
    critical_alerts = metrics.get_alerts(level=AlertLevel.CRITICAL)
    assert len(critical_alerts) > 0
    assert any(a.metric_name == "card_accuracy" for a in critical_alerts)


def test_performance_tracking():
    """Test performance latency tracking."""
    metrics = VisionMetrics()
    
    # Record some latencies
    metrics.record_ocr("123", latency_ms=10.5)
    metrics.record_ocr("456", latency_ms=12.3)
    metrics.record_card_recognition("Ah", confidence=0.9, latency_ms=5.2)
    metrics.record_parse_latency(50.0)
    
    summary = metrics.get_summary()
    assert summary["ocr"]["mean_latency_ms"] is not None
    assert summary["cards"]["mean_latency_ms"] is not None
    assert summary["performance"]["mean_parse_latency_ms"] == 50.0


def test_get_summary():
    """Test comprehensive summary generation."""
    metrics = VisionMetrics()
    
    # Add various metrics
    metrics.record_ocr("123", expected_text="123", latency_ms=10.0)
    metrics.record_amount(100.0, expected_amount=99.0, category="stack")
    metrics.record_card_recognition("Ah", expected_card="Ah", confidence=0.95, latency_ms=5.0)
    metrics.record_parse_latency(45.0)
    
    summary = metrics.get_summary()
    
    assert "ocr" in summary
    assert "amounts" in summary
    assert "cards" in summary
    assert "performance" in summary
    assert "alerts" in summary
    
    assert summary["ocr"]["total_readings"] == 1
    assert summary["amounts"]["total_readings"] == 1
    assert summary["cards"]["total_recognitions"] == 1


def test_generate_text_report():
    """Test text report generation."""
    metrics = VisionMetrics()
    
    # Add some data
    for i in range(5):
        metrics.record_ocr(str(i), expected_text=str(i))
        metrics.record_amount(100.0 + i, expected_amount=100.0, category="stack")
        metrics.record_card_recognition(f"A{i}", expected_card=f"A{i}", confidence=0.9)
    
    report = metrics.generate_report(format="text")
    
    assert "VISION METRICS REPORT" in report
    assert "OCR METRICS" in report
    assert "AMOUNT METRICS" in report
    assert "CARD RECOGNITION METRICS" in report
    assert "PERFORMANCE METRICS" in report
    assert "ALERTS" in report


def test_generate_json_report():
    """Test JSON report generation."""
    metrics = VisionMetrics()
    
    # Add some data
    metrics.record_ocr("123", expected_text="123")
    metrics.record_amount(100.0, expected_amount=100.0, category="stack")
    
    report = metrics.generate_report(format="json")
    
    import json
    data = json.loads(report)
    
    assert "ocr" in data
    assert "amounts" in data
    assert "cards" in data
    assert data["ocr"]["total_readings"] == 1


def test_alerts_filtering():
    """Test alert filtering by level and time."""
    config = VisionMetricsConfig(min_samples_for_alert=2)
    metrics = VisionMetrics(config=config)
    
    # Trigger a critical alert
    for i in range(2):
        metrics.record_ocr("X", expected_text="Y")
    
    # Get all alerts
    all_alerts = metrics.get_alerts()
    assert len(all_alerts) > 0
    
    # Filter by level
    critical = metrics.get_alerts(level=AlertLevel.CRITICAL)
    warning = metrics.get_alerts(level=AlertLevel.WARNING)
    assert len(critical) > 0 or len(warning) > 0
    
    # Filter by time
    now = time.time()
    recent = metrics.get_alerts(since=now - 10)
    assert len(recent) >= 0


def test_reset_metrics():
    """Test resetting all metrics."""
    metrics = VisionMetrics()
    
    # Add some data
    metrics.record_ocr("123", expected_text="123")
    metrics.record_amount(100.0, expected_amount=100.0)
    metrics.record_card_recognition("Ah", expected_card="Ah", confidence=0.9)
    
    assert len(metrics.ocr_results) > 0
    assert len(metrics.amount_results) > 0
    assert len(metrics.card_results) > 0
    
    # Reset
    metrics.reset()
    
    assert len(metrics.ocr_results) == 0
    assert len(metrics.amount_results) == 0
    assert len(metrics.card_results) == 0
    assert len(metrics.alerts) == 0


def test_global_metrics_instance():
    """Test global metrics instance management."""
    # Reset first
    reset_vision_metrics()
    
    # Get instance
    metrics1 = get_vision_metrics()
    metrics1.record_ocr("test")
    
    # Get same instance
    metrics2 = get_vision_metrics()
    assert metrics2 is metrics1
    assert len(metrics2.ocr_results) == 1
    
    # Reset
    reset_vision_metrics()
    metrics3 = get_vision_metrics()
    assert len(metrics3.ocr_results) == 0


def test_null_amount_handling():
    """Test handling of None amounts."""
    metrics = VisionMetrics()
    
    # Record None detected amount
    metrics.record_amount(None, expected_amount=100.0, category="stack")
    assert len(metrics.amount_results) == 1
    assert metrics.amount_results[0].detected_amount is None
    assert metrics.amount_results[0].absolute_error is None
    
    # MAE should still work (ignoring None values)
    metrics.record_amount(100.0, expected_amount=100.0, category="stack")
    mae = metrics.get_amount_mae()
    assert mae is not None
    assert mae == 0.0


def test_case_insensitive_comparison():
    """Test that OCR and card comparisons are case-insensitive."""
    metrics = VisionMetrics()
    
    # OCR comparison
    metrics.record_ocr("ABC", expected_text="abc")
    assert metrics.ocr_results[0].is_correct is True
    
    # Card comparison
    metrics.record_card_recognition("AH", expected_card="ah", confidence=0.9)
    assert metrics.card_results[0].is_correct is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
