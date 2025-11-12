"""Test enhanced vision metrics features."""

import pytest
import time
import json
import tempfile
from pathlib import Path
from holdem.vision.vision_metrics import (
    VisionMetrics,
    VisionMetricsConfig,
    AlertLevel,
    VisionContext,
    FlickerEvent,
)


def test_amount_mape_calculation():
    """Test MAPE (Mean Absolute Percentage Error) calculation."""
    metrics = VisionMetrics()
    
    # No data yet
    assert metrics.get_amount_mape() is None
    
    # Add some results with percentage errors
    # 100 -> 105: 5% error
    metrics.record_amount(105.0, expected_amount=100.0, category="stack")
    # 200 -> 210: 5% error
    metrics.record_amount(210.0, expected_amount=200.0, category="pot")
    # 50 -> 52: 4% error
    metrics.record_amount(52.0, expected_amount=50.0, category="bet")
    
    # Average percentage error: (0.05 + 0.05 + 0.04) / 3 ≈ 0.0467
    mape = metrics.get_amount_mape()
    assert mape is not None
    assert abs(mape - 0.0467) < 0.001


def test_amount_mape_by_category():
    """Test MAPE calculation by category."""
    metrics = VisionMetrics()
    
    # Add stack amounts with 2% error
    for _ in range(3):
        metrics.record_amount(102.0, expected_amount=100.0, category="stack")
    
    # Add pot amounts with 5% error
    for _ in range(3):
        metrics.record_amount(105.0, expected_amount=100.0, category="pot")
    
    mape_stack = metrics.get_amount_mape(category="stack")
    mape_pot = metrics.get_amount_mape(category="pot")
    
    assert abs(mape_stack - 0.02) < 0.001
    assert abs(mape_pot - 0.05) < 0.001


def test_amount_mape_alerts():
    """Test MAPE alert generation."""
    config = VisionMetricsConfig(
        amount_mape_warning=0.002,  # 0.2%
        amount_mape_alert_threshold=0.005,  # 0.5%
        amount_mape_critical=0.01,  # 1.0%
        min_samples_for_alert=5
    )
    metrics = VisionMetrics(config=config)
    
    # Add amounts with 0.6% error (should trigger WARNING at 0.5% threshold)
    for _ in range(5):
        metrics.record_amount(100.6, expected_amount=100.0, category="stack")
    
    warning_alerts = metrics.get_alerts(level=AlertLevel.WARNING)
    assert len(warning_alerts) > 0
    assert any(a.metric_name == "amount_mape" for a in warning_alerts)


def test_granular_tracking_by_seat():
    """Test per-seat position tracking."""
    metrics = VisionMetrics()
    
    # Record amounts for different seats
    metrics.record_amount(100.0, expected_amount=100.0, category="stack", seat_position=0)
    metrics.record_amount(105.0, expected_amount=100.0, category="stack", seat_position=1)
    metrics.record_amount(110.0, expected_amount=100.0, category="stack", seat_position=2)
    
    # Get MAE for specific seat
    mae_seat_0 = metrics.get_amount_mae(seat_position=0)
    mae_seat_1 = metrics.get_amount_mae(seat_position=1)
    mae_seat_2 = metrics.get_amount_mae(seat_position=2)
    
    assert mae_seat_0 == 0.0
    assert mae_seat_1 == 5.0
    assert mae_seat_2 == 10.0


def test_card_recognition_by_street():
    """Test card recognition accuracy by street."""
    metrics = VisionMetrics()
    
    # Preflop: 100% accuracy
    for card in ["Ah", "Kd"]:
        metrics.record_card_recognition(card, expected_card=card, street="preflop")
    
    # Flop: 66% accuracy (2/3 correct)
    metrics.record_card_recognition("Qs", expected_card="Qs", street="flop")
    metrics.record_card_recognition("Jh", expected_card="Jh", street="flop")
    metrics.record_card_recognition("Xx", expected_card="Tc", street="flop")
    
    # Turn: 0% accuracy
    metrics.record_card_recognition("Xx", expected_card="9s", street="turn")
    
    acc_preflop = metrics.get_card_accuracy(street="preflop")
    acc_flop = metrics.get_card_accuracy(street="flop")
    acc_turn = metrics.get_card_accuracy(street="turn")
    
    assert acc_preflop == 1.0
    assert abs(acc_flop - 0.6667) < 0.001
    assert acc_turn == 0.0


def test_card_confusion_matrix():
    """Test card confusion matrix tracking."""
    metrics = VisionMetrics()
    
    # Record some card recognitions
    metrics.record_card_recognition("Ah", expected_card="Ah")  # Correct
    metrics.record_card_recognition("Kh", expected_card="Ah")  # Wrong rank, correct suit
    metrics.record_card_recognition("Ad", expected_card="Ah")  # Correct rank, wrong suit
    metrics.record_card_recognition("Kd", expected_card="Ah")  # Wrong rank and suit
    
    confusion = metrics.get_card_confusion_matrix()
    
    # Check rank confusion for Ace
    assert confusion["rank_A"]["A"] == 2  # 2 correct
    assert confusion["rank_A"]["K"] == 2  # 2 misidentified as King
    
    # Check suit confusion for hearts
    assert confusion["suit_h"]["h"] == 2  # 2 correct
    assert confusion["suit_h"]["d"] == 2  # 2 misidentified as diamonds


def test_latency_p99():
    """Test p99 latency calculation."""
    metrics = VisionMetrics()
    
    # Add parse latencies: [10, 20, 30, ..., 100]
    for i in range(1, 11):
        metrics.record_parse_latency(i * 10.0)
    
    p50 = metrics.get_latency_percentile("parse", 50)
    p95 = metrics.get_latency_percentile("parse", 95)
    p99 = metrics.get_latency_percentile("parse", 99)
    
    assert p50 == 55.0  # Median
    assert p95 == 95.5  # 95th percentile
    assert p99 == 99.1  # 99th percentile


def test_latency_thresholds_in_summary():
    """Test latency threshold checking in summary."""
    config = VisionMetricsConfig(
        latency_p95_threshold=50.0,
        latency_p99_threshold=80.0
    )
    metrics = VisionMetrics(config=config)
    
    # Add latencies that exceed thresholds
    for i in range(10):
        metrics.record_parse_latency(i * 10.0)  # 0, 10, 20, ..., 90
    
    summary = metrics.get_summary()
    
    # P95 should be around 85-90, exceeding 50ms threshold
    assert summary['performance']['p95_threshold_met'] is False
    # P99 should be around 90, exceeding 80ms threshold
    assert summary['performance']['p99_threshold_met'] is False


def test_flicker_detection():
    """Test flicker detection for rapidly changing values."""
    config = VisionMetricsConfig(
        flicker_window_seconds=2.0,
        flicker_threshold_count=3,
        min_samples_for_alert=1
    )
    metrics = VisionMetrics(config=config)
    
    # Simulate rapid value changes
    field_name = "stack_seat_0"
    values = [100, 105, 100, 105, 100]  # 4 changes
    
    for value in values:
        metrics.record_amount(value, category="stack", field_name=field_name)
        time.sleep(0.1)  # Small delay
    
    # Should have detected flicker
    assert len(metrics.flicker_events) > 0
    assert metrics.flicker_events[0].field_name == field_name


def test_context_tracking():
    """Test vision context tracking."""
    metrics = VisionMetrics()
    
    # Set context
    metrics.set_context(
        ui_theme="dark",
        resolution=(1920, 1080),
        zoom_level=1.25,
        profile_version="v1.2.3",
        template_hash="abc123def456"
    )
    
    assert metrics.context.ui_theme == "dark"
    assert metrics.context.resolution == (1920, 1080)
    assert metrics.context.zoom_level == 1.25
    assert metrics.context.profile_version == "v1.2.3"
    assert metrics.context.template_hash == "abc123def456"
    
    # Check context in summary
    summary = metrics.get_summary()
    assert summary['context']['ui_theme'] == "dark"
    assert summary['context']['resolution'] == (1920, 1080)


def test_ground_truth_ingestion():
    """Test ground truth data ingestion."""
    metrics = VisionMetrics()
    
    # Ingest ground truth
    gt_data = {
        "image_id": "test_001",
        "stacks": [100, 200, 300],
        "pot": 50,
        "cards": ["Ah", "Kd", "Qs"]
    }
    metrics.ingest_ground_truth(gt_data)
    
    assert len(metrics.ground_truth_data) == 1
    assert metrics.ground_truth_data[0]["image_id"] == "test_001"


def test_jsonlines_export():
    """Test JSON Lines export format."""
    metrics = VisionMetrics()
    
    # Add some metrics
    metrics.set_context(ui_theme="light", resolution=(1920, 1080))
    metrics.record_ocr("123", expected_text="123")
    metrics.record_amount(100.0, expected_amount=100.0, category="stack")
    
    # Export to JSON Lines
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.jsonl', delete=False) as f:
        filepath = f.name
    
    try:
        metrics.export_jsonlines(filepath)
        
        # Read and verify
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 2  # Context + summary
        
        # Parse first line (context)
        context_line = json.loads(lines[0])
        assert context_line['type'] == 'context'
        assert context_line['data']['ui_theme'] == 'light'
        
        # Parse second line (summary)
        summary_line = json.loads(lines[1])
        assert summary_line['type'] == 'summary'
        assert summary_line['data']['ocr']['total_readings'] == 1
    finally:
        Path(filepath).unlink(missing_ok=True)


def test_prometheus_export():
    """Test Prometheus metrics export."""
    metrics = VisionMetrics()
    
    # Add some metrics
    metrics.record_ocr("123", expected_text="123")
    metrics.record_amount(102.0, expected_amount=100.0, category="stack")
    metrics.record_card_recognition("Ah", expected_card="Ah", street="flop")
    metrics.record_parse_latency(45.0)
    
    # Export to Prometheus format
    prom_metrics = metrics.export_prometheus_metrics()
    
    # Verify format
    assert "# HELP vision_ocr_accuracy" in prom_metrics
    assert "# TYPE vision_ocr_accuracy gauge" in prom_metrics
    assert "vision_ocr_accuracy 1.0" in prom_metrics
    
    assert "# HELP vision_amount_mae_units" in prom_metrics
    assert 'vision_amount_mae_units{category="stack"}' in prom_metrics
    
    assert "# HELP vision_amount_mape" in prom_metrics
    assert 'vision_amount_mape{category="stack"}' in prom_metrics
    
    assert "# HELP vision_card_accuracy" in prom_metrics
    assert 'vision_card_accuracy{street="flop"}' in prom_metrics
    
    assert "# HELP vision_parse_latency_ms" in prom_metrics
    assert 'vision_parse_latency_ms{quantile="0.99"}' in prom_metrics


def test_enhanced_summary():
    """Test enhanced summary includes all new metrics."""
    metrics = VisionMetrics()
    
    # Add comprehensive data
    metrics.set_context(ui_theme="dark", resolution=(1920, 1080))
    metrics.record_amount(102.0, expected_amount=100.0, category="stack", seat_position=0)
    metrics.record_card_recognition("Ah", expected_card="Ah", street="flop")
    metrics.record_parse_latency(45.0)
    
    summary = metrics.get_summary()
    
    # Check new fields
    assert 'context' in summary
    assert 'mape_all' in summary['amounts']
    assert 'accuracy_flop' in summary['cards']
    assert 'confusion_matrix' in summary['cards']
    assert 'p99_parse_latency_ms' in summary['performance']
    assert 'p95_threshold_met' in summary['performance']
    assert 'flicker' in summary


def test_reset_clears_all_data():
    """Test that reset clears all new tracking data."""
    metrics = VisionMetrics()
    
    # Add data
    metrics.set_context(ui_theme="dark")
    metrics.record_amount(100.0, field_name="test_field")
    metrics.record_card_recognition("Ah", expected_card="Ah")
    metrics.ingest_ground_truth({"test": "data"})
    
    # Verify data exists
    assert len(metrics.amount_results) > 0
    assert len(metrics.card_results) > 0
    assert len(metrics.ground_truth_data) > 0
    
    # Reset
    metrics.reset()
    
    # Verify all cleared
    assert len(metrics.amount_results) == 0
    assert len(metrics.card_results) == 0
    assert len(metrics.ground_truth_data) == 0
    assert len(metrics.flicker_events) == 0
    assert len(metrics.value_history) == 0
    assert len(metrics.card_confusion_matrix) == 0
    assert len(metrics.alert_windows) == 0


def test_hysteresis_alert_prevention():
    """Test that hysteresis prevents premature alerts."""
    config = VisionMetricsConfig(
        flicker_window_seconds=1.0,
        flicker_threshold_count=2,
        alert_hysteresis_windows=3,
        min_samples_for_alert=1
    )
    metrics = VisionMetrics(config=config)
    
    field_name = "test_field"
    
    # First flicker event - no alert yet (hysteresis = 1)
    for value in [100, 200, 100]:
        metrics.record_amount(value, field_name=field_name)
    
    alerts_after_first = len(metrics.get_alerts(level=AlertLevel.WARNING))
    
    # Second flicker event - no alert yet (hysteresis = 2)
    for value in [100, 200, 100]:
        metrics.record_amount(value, field_name=field_name)
    
    alerts_after_second = len(metrics.get_alerts(level=AlertLevel.WARNING))
    
    # Hysteresis should prevent alerts until 3rd consecutive window
    assert alerts_after_first == 0
    assert alerts_after_second == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
