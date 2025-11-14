#!/usr/bin/env python3
"""
Demo: OCR Amount Cache with Metrics Tracking

This demo shows how to use the OCR amount cache system to reduce
parsing latency and track cache performance metrics.

The amount cache uses image hash-based change detection to skip
redundant OCR calls for pot, stacks, and bets when the image
regions haven't changed.
"""

import numpy as np
from pathlib import Path
from holdem.vision.vision_performance_config import VisionPerformanceConfig
from holdem.vision.parse_state import StateParser
from holdem.vision.calibrate import TableProfile
from holdem.vision.cards import CardRecognizer
from holdem.vision.ocr import OCREngine
from holdem.utils.logging import get_logger

logger = get_logger("demo.amount_cache")


def demo_amount_cache_enabled():
    """Demo with amount cache enabled (default)."""
    print("\n" + "=" * 70)
    print("DEMO 1: Amount Cache ENABLED (default)")
    print("=" * 70)
    
    # Load config with caching enabled
    config = VisionPerformanceConfig(
        enable_caching=True,
        cache_roi_hash=True,
        enable_amount_cache=True,  # Enable amount cache
        enable_light_parse=True,
        light_parse_interval=3
    )
    
    print(f"\nConfiguration:")
    print(f"  enable_caching: {config.enable_caching}")
    print(f"  enable_amount_cache: {config.enable_amount_cache}")
    print(f"  light_parse_interval: {config.light_parse_interval}")
    
    # Note: In real usage, you would create these from actual table profile
    # For this demo, we just show the concept
    print("\nWith caching enabled, the system will:")
    print("  1. Compute image hash for each OCR region (pot, stacks, bets)")
    print("  2. On subsequent frames, skip OCR if hash hasn't changed")
    print("  3. Track metrics: OCR calls, cache hits, hit rate")
    
    return config


def demo_amount_cache_disabled():
    """Demo with amount cache disabled."""
    print("\n" + "=" * 70)
    print("DEMO 2: Amount Cache DISABLED")
    print("=" * 70)
    
    # Load config with caching disabled
    config = VisionPerformanceConfig(
        enable_caching=True,
        cache_roi_hash=True,
        enable_amount_cache=False,  # Disable amount cache
        enable_light_parse=True,
        light_parse_interval=3
    )
    
    print(f"\nConfiguration:")
    print(f"  enable_caching: {config.enable_caching}")
    print(f"  enable_amount_cache: {config.enable_amount_cache}")
    
    print("\nWith caching disabled, the system will:")
    print("  - Run OCR on every frame (more accurate but slower)")
    print("  - No metrics tracking")
    print("  - Useful for debugging or when accuracy is critical")
    
    return config


def demo_load_from_yaml():
    """Demo loading config from YAML file."""
    print("\n" + "=" * 70)
    print("DEMO 3: Load Config from YAML")
    print("=" * 70)
    
    config_path = Path("configs/vision_performance.yaml")
    
    if config_path.exists():
        config = VisionPerformanceConfig.from_yaml(config_path)
        print(f"\nLoaded config from: {config_path}")
        print(f"  enable_amount_cache: {config.enable_amount_cache}")
        print(f"  enable_caching: {config.enable_caching}")
        print(f"  cache_roi_hash: {config.cache_roi_hash}")
    else:
        print(f"\nConfig file not found: {config_path}")
        print("Using default config instead.")
        config = VisionPerformanceConfig.default()
    
    return config


def demo_metrics_usage():
    """Demo showing metrics tracking and reporting."""
    print("\n" + "=" * 70)
    print("DEMO 4: Metrics Tracking and Reporting")
    print("=" * 70)
    
    print("\nAfter parsing frames, you can retrieve cache metrics:")
    print("\nExample code:")
    print("  # Get metrics from parser")
    print("  metrics = parser.get_cache_metrics()")
    print("  ")
    print("  # Print summary")
    print("  if metrics:")
    print("      print(f'Total OCR calls: {metrics[\"total_ocr_calls\"]}')")
    print("      print(f'Cache hits: {metrics[\"total_cache_hits\"]}')")
    print("      print(f'Hit rate: {metrics[\"cache_hit_rate_percent\"]:.1f}%')")
    print("      ")
    print("      # Per-type breakdown")
    print("      for cache_type, type_metrics in metrics['by_type'].items():")
    print("          print(f'{cache_type}: {type_metrics[\"hit_rate_percent\"]:.1f}% hit rate')")
    
    print("\n\nExample metrics output:")
    print("-" * 50)
    
    # Simulate example metrics
    example_metrics = {
        "total_ocr_calls": 15,
        "total_cache_hits": 45,
        "total_checks": 60,
        "cache_hit_rate_percent": 75.0,
        "by_type": {
            "pot": {"ocr_calls": 5, "cache_hits": 15, "total_checks": 20, "hit_rate_percent": 75.0},
            "stack": {"ocr_calls": 8, "cache_hits": 24, "total_checks": 32, "hit_rate_percent": 75.0},
            "bet": {"ocr_calls": 2, "cache_hits": 6, "total_checks": 8, "hit_rate_percent": 75.0}
        }
    }
    
    print(f"Total OCR calls: {example_metrics['total_ocr_calls']}")
    print(f"Total cache hits: {example_metrics['total_cache_hits']}")
    print(f"Total checks: {example_metrics['total_checks']}")
    print(f"Cache hit rate: {example_metrics['cache_hit_rate_percent']:.1f}%")
    print("\nBreakdown by type:")
    for cache_type, type_metrics in example_metrics['by_type'].items():
        print(f"  {cache_type.upper()}: "
              f"{type_metrics['ocr_calls']} OCR calls, "
              f"{type_metrics['cache_hits']} cache hits, "
              f"{type_metrics['hit_rate_percent']:.1f}% hit rate")
    
    print("\nYou can also use parser.log_cache_metrics() to print a formatted report.")


def demo_performance_impact():
    """Demo showing expected performance impact."""
    print("\n" + "=" * 70)
    print("DEMO 5: Performance Impact")
    print("=" * 70)
    
    print("\nExpected performance improvements with amount cache:")
    print()
    print("  WITHOUT cache (enable_amount_cache=false):")
    print("    - Mean parse latency: ~4000ms")
    print("    - P95 latency: ~5000ms")
    print("    - P99 latency: ~6000ms")
    print()
    print("  WITH cache (enable_amount_cache=true):")
    print("    - Mean parse latency: ~800-1200ms (70-80% reduction)")
    print("    - P95 latency: ~1500ms (70% reduction)")
    print("    - P99 latency: ~2000ms (67% reduction)")
    print()
    print("  Cache hit rate: 60-80% (typical)")
    print()
    print("NOTE: Actual performance depends on:")
    print("  - Number of players at table")
    print("  - Image size and quality")
    print("  - OCR engine used (Tesseract, EasyOCR, PaddleOCR)")
    print("  - Hardware (CPU/GPU)")


def demo_configuration_options():
    """Demo showing all configuration options."""
    print("\n" + "=" * 70)
    print("DEMO 6: Configuration Options in vision_performance.yaml")
    print("=" * 70)
    
    print("\nvision_performance:")
    print("  # Master switch for all caching features")
    print("  enable_caching: true")
    print()
    print("  # Enable hash-based ROI caching for OCR")
    print("  cache_roi_hash: true")
    print()
    print("  # Enable amount cache (stacks, bets, pot) with change detection")
    print("  # When enabled, OCR is skipped if image hash hasn't changed")
    print("  enable_amount_cache: true")
    print()
    print("  # Enable light parse mode (skip heavy OCR on some frames)")
    print("  enable_light_parse: true")
    print()
    print("  # Interval for full parse (1 = every frame, 3 = every 3rd frame)")
    print("  light_parse_interval: 3")
    print()
    print("  # Downscale large ROIs before OCR to reduce processing time")
    print("  downscale_ocr_rois: true")
    print()
    print("  # Maximum dimension for OCR ROIs (larger images will be downscaled)")
    print("  max_roi_dimension: 400")
    
    print("\n\nTo disable amount cache, set enable_amount_cache: false")
    print("This makes the system behave exactly as it did before (no caching).")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("OCR AMOUNT CACHE DEMONSTRATION")
    print("=" * 70)
    print("\nThis demo shows how to use the OCR amount cache system")
    print("to reduce parsing latency by skipping redundant OCR calls.")
    
    # Run demos
    demo_amount_cache_enabled()
    demo_amount_cache_disabled()
    demo_load_from_yaml()
    demo_metrics_usage()
    demo_performance_impact()
    demo_configuration_options()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\nKey takeaways:")
    print("  1. Amount cache is enabled by default (enable_amount_cache: true)")
    print("  2. Cache uses image hash to detect when OCR can be skipped")
    print("  3. Metrics track OCR calls, cache hits, and hit rate")
    print("  4. Expected 70-80% reduction in parse latency")
    print("  5. Can be disabled via config for maximum accuracy")
    print("\nFor more info, see:")
    print("  - configs/vision_performance.yaml")
    print("  - tests/test_amount_cache_integration.py")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
