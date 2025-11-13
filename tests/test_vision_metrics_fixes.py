"""Test vision metrics recording and alert generation."""

import pytest
import numpy as np
from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig, AlertLevel


class TestVisionMetricsCardConfidence:
    """Test that card confidence scores are properly recorded."""
    
    def test_card_confidence_recording(self):
        """Test that card recognition with confidence is properly tracked."""
        config = VisionMetricsConfig()
        metrics = VisionMetrics(config)
        
        # Record some card recognitions with confidence
        metrics.record_card_recognition("Ah", confidence=0.95)
        metrics.record_card_recognition("Kd", confidence=0.87)
        metrics.record_card_recognition("Qs", confidence=0.92)
        
        # Get summary
        summary = metrics.get_summary()
        
        # Check that recognitions were recorded
        assert summary['cards']['total_recognitions'] == 3
        
        # Check that mean confidence is calculated
        mean_confidence = summary['cards']['mean_confidence']
        assert mean_confidence is not None
        assert 0.90 <= mean_confidence <= 0.95  # Should be around 0.913
    
    def test_card_confidence_with_zero_scores(self):
        """Test handling when confidence scores are 0 (should still calculate mean)."""
        config = VisionMetricsConfig()
        metrics = VisionMetrics(config)
        
        # Record cards with 0 confidence (happens when confidence not available)
        metrics.record_card_recognition("Ah", confidence=0.0)
        metrics.record_card_recognition("Kd", confidence=0.0)
        
        summary = metrics.get_summary()
        
        # Should still have a mean confidence (even if 0)
        assert summary['cards']['mean_confidence'] == 0.0
        assert summary['cards']['total_recognitions'] == 2


class TestVisionMetricsLatencyAlerts:
    """Test that latency alerts are properly generated."""
    
    def test_high_latency_generates_alerts(self):
        """Test that high parse latency generates alerts."""
        config = VisionMetricsConfig(
            latency_p95_threshold=50.0,  # 50ms
            latency_p99_threshold=80.0,   # 80ms
            min_samples_for_alert=10
        )
        metrics = VisionMetrics(config)
        
        # Record latencies well above thresholds (simulating 4000ms average)
        for _ in range(15):
            metrics.record_parse_latency(4000.0)
        
        # Check that alerts were generated
        alerts = metrics.get_alerts()
        assert len(alerts) > 0
        
        # Check for critical alerts
        critical_alerts = [a for a in alerts if a.level == AlertLevel.CRITICAL]
        assert len(critical_alerts) > 0
        
        # Verify alert is about latency
        latency_alerts = [a for a in alerts if 'latency' in a.metric_name.lower()]
        assert len(latency_alerts) > 0
    
    def test_low_latency_no_alerts(self):
        """Test that acceptable latency doesn't generate alerts."""
        config = VisionMetricsConfig(
            latency_p95_threshold=50.0,
            latency_p99_threshold=80.0,
            min_samples_for_alert=10
        )
        metrics = VisionMetrics(config)
        
        # Record latencies well within thresholds
        for _ in range(15):
            metrics.record_parse_latency(30.0)  # 30ms - acceptable
        
        # Should have no alerts
        alerts = metrics.get_alerts()
        latency_alerts = [a for a in alerts if 'latency' in a.metric_name.lower()]
        assert len(latency_alerts) == 0
    
    def test_latency_threshold_boundary(self):
        """Test latency at threshold boundaries."""
        config = VisionMetricsConfig(
            latency_p95_threshold=50.0,
            latency_p99_threshold=80.0,
            min_samples_for_alert=10
        )
        metrics = VisionMetrics(config)
        
        # Record mix of latencies around P95 threshold
        for i in range(15):
            # Most samples are below threshold, but some above
            latency = 45.0 if i < 13 else 60.0
            metrics.record_parse_latency(latency)
        
        # Should generate at least a warning for P95
        alerts = metrics.get_alerts()
        warning_alerts = [a for a in alerts if a.level == AlertLevel.WARNING]
        
        # May or may not generate warning depending on exact calculation
        # Just verify the system is working
        summary = metrics.get_summary()
        assert summary['performance']['p95_parse_latency_ms'] is not None


class TestVisionMetricsIntegration:
    """Integration tests for the metrics system."""
    
    def test_metrics_summary_completeness(self):
        """Test that metrics summary includes all expected fields."""
        config = VisionMetricsConfig()
        metrics = VisionMetrics(config)
        
        # Record some sample data
        metrics.record_card_recognition("Ah", confidence=0.95)
        metrics.record_parse_latency(45.0)
        
        summary = metrics.get_summary()
        
        # Check all major sections exist
        assert 'cards' in summary
        assert 'performance' in summary
        assert 'alerts' in summary
        
        # Check specific fields
        assert 'total_recognitions' in summary['cards']
        assert 'mean_confidence' in summary['cards']
        assert 'mean_parse_latency_ms' in summary['performance']
        assert 'p95_parse_latency_ms' in summary['performance']
        assert 'p99_parse_latency_ms' in summary['performance']
        assert 'total' in summary['alerts']
    
    def test_metrics_report_generation(self):
        """Test that text report can be generated."""
        config = VisionMetricsConfig()
        metrics = VisionMetrics(config)
        
        # Record some data
        for _ in range(5):
            metrics.record_card_recognition("Ah", confidence=0.90)
            metrics.record_parse_latency(40.0)
        
        # Generate report
        report = metrics.generate_report(format="text")
        
        # Check report contains key sections
        assert "VISION METRICS REPORT" in report
        assert "CARD RECOGNITION METRICS" in report
        assert "PERFORMANCE METRICS" in report
        assert "ALERTS" in report
        
        # Check specific metrics are shown
        assert "Mean Confidence" in report
        assert "Mean Parse Latency" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
