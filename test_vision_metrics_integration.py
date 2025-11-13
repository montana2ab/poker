#!/usr/bin/env python3
"""Test vision metrics integration."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig

def test_vision_metrics_basic():
    """Test basic vision metrics functionality."""
    print("Testing VisionMetrics basic functionality...")
    
    # Create metrics instance
    config = VisionMetricsConfig()
    metrics = VisionMetrics(config)
    
    # Test OCR recording
    metrics.record_ocr("12.50", "12.50", latency_ms=5.0)
    metrics.record_ocr("5.00", "5.00", latency_ms=4.5)
    metrics.record_ocr("wrong", "correct", latency_ms=6.0)
    
    # Test amount recording
    metrics.record_amount(100.0, 100.0, category="stack")
    metrics.record_amount(50.0, 49.5, category="pot")
    metrics.record_amount(20.0, 20.5, category="bet")
    
    # Test card recognition recording
    metrics.record_card_recognition("Ah", "Ah", confidence=0.95, street="preflop")
    metrics.record_card_recognition("Kd", "Kd", confidence=0.90, street="flop")
    metrics.record_card_recognition("Qs", "Qc", confidence=0.85, street="turn")
    
    # Test parse latency recording
    metrics.record_parse_latency(15.5)
    metrics.record_parse_latency(18.2)
    metrics.record_parse_latency(16.8)
    
    # Get summary
    summary = metrics.get_summary()
    
    # Print results
    print("\n" + "="*80)
    print("VISION METRICS TEST RESULTS")
    print("="*80)
    
    print(f"\nOCR Metrics:")
    print(f"  Total readings: {summary['ocr']['total_readings']}")
    print(f"  Accuracy: {summary['ocr']['accuracy']:.1%}")
    print(f"  Mean latency: {summary['ocr']['mean_latency_ms']:.2f}ms")
    
    print(f"\nAmount Metrics:")
    print(f"  Total readings: {summary['amounts']['total_readings']}")
    print(f"  MAE (all): {summary['amounts']['mae_all']:.4f}")
    print(f"  MAPE (all): {summary['amounts']['mape_all']:.2%}")
    
    print(f"\nCard Recognition Metrics:")
    print(f"  Total recognitions: {summary['cards']['total_recognitions']}")
    print(f"  Accuracy: {summary['cards']['accuracy_all']:.1%}")
    print(f"  Mean confidence: {summary['cards']['mean_confidence']:.2f}")
    
    print(f"\nPerformance Metrics:")
    print(f"  Mean parse latency: {summary['performance']['mean_parse_latency_ms']:.2f}ms")
    
    # Test report generation
    print("\n" + "="*80)
    print("TEXT REPORT:")
    print("="*80)
    report = metrics.generate_report(format="text")
    print(report)
    
    print("\n" + "="*80)
    print("JSON REPORT:")
    print("="*80)
    json_report = metrics.generate_report(format="json")
    print(json_report)
    
    print("\n✅ VisionMetrics basic test passed!")
    return True

if __name__ == "__main__":
    try:
        test_vision_metrics_basic()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
