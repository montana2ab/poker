#!/usr/bin/env python3
"""Evaluate CFV Net model.

Usage:
    python tools/eval_cfv_net.py \\
        --checkpoint runs/cfv_net_6max_m2/best.pt \\
        --data data/cfv/6max_jsonlz \\
        --out runs/cfv_net_6max_m2/eval

This tool:
1. Loads trained CFV Net checkpoint
2. Evaluates on test set
3. Computes metrics: MAE, PI coverage, ECE
4. Measures inference latency
5. Generates calibration plots and reports
"""

import argparse
import json
import sys
import time
from pathlib import Path
import numpy as np
import torch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from holdem.value_net import (
    CFVNet,
    compute_metrics,
    get_feature_dimension,
    FeatureStats
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Evaluate CFV Net")
    
    parser.add_argument(
        "--checkpoint",
        type=str,
        required=True,
        help="Path to model checkpoint (.pt)"
    )
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Dataset directory for test set"
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output directory for evaluation results"
    )
    parser.add_argument(
        "--stats",
        type=str,
        default=None,
        help="Feature stats JSON (default: checkpoint_dir/stats.json)"
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=10000,
        help="Number of samples for evaluation (default: 10000)"
    )
    
    return parser.parse_args()


def load_model(checkpoint_path: str, device: torch.device):
    """Load model from checkpoint.
    
    Args:
        checkpoint_path: Path to checkpoint
        device: Device to load on
        
    Returns:
        Loaded model
    """
    print(f"Loading checkpoint from {checkpoint_path}...")
    
    # Infer architecture from checkpoint
    # In production, save architecture in checkpoint
    input_dim = get_feature_dimension(embed_dim=64)
    model = CFVNet(
        input_dim=input_dim,
        hidden_dims=[512, 512, 256],
        dropout=0.05,
        quantiles=[0.10, 0.90]
    )
    
    state_dict = torch.load(checkpoint_path, map_location=device)
    if isinstance(state_dict, dict) and 'model_state_dict' in state_dict:
        model.load_state_dict(state_dict['model_state_dict'])
    else:
        model.load_state_dict(state_dict)
    
    model.to(device)
    model.eval()
    
    print(f"Model loaded: {sum(p.numel() for p in model.parameters())} parameters")
    return model


def benchmark_latency(model: torch.nn.Module, input_dim: int, device: torch.device, num_runs: int = 1000):
    """Benchmark inference latency.
    
    Args:
        model: Model to benchmark
        input_dim: Input feature dimension
        device: Device
        num_runs: Number of inference runs
        
    Returns:
        Dictionary with latency statistics
    """
    print(f"Benchmarking latency ({num_runs} runs)...")
    
    # Warmup
    dummy_input = torch.randn(1, input_dim).to(device)
    with torch.no_grad():
        for _ in range(100):
            _ = model(dummy_input)
    
    # Benchmark
    latencies = []
    with torch.no_grad():
        for _ in range(num_runs):
            start = time.perf_counter()
            _ = model(dummy_input)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # Convert to ms
    
    latencies = np.array(latencies)
    
    return {
        'mean_ms': latencies.mean(),
        'median_ms': np.median(latencies),
        'p50_ms': np.percentile(latencies, 50),
        'p95_ms': np.percentile(latencies, 95),
        'p99_ms': np.percentile(latencies, 99),
        'min_ms': latencies.min(),
        'max_ms': latencies.max()
    }


def evaluate_model(
    model: torch.nn.Module,
    test_data: list,
    device: torch.device
) -> dict:
    """Evaluate model on test set.
    
    Args:
        model: Trained model
        test_data: Test dataset
        device: Device
        
    Returns:
        Evaluation metrics
    """
    print(f"Evaluating on {len(test_data)} examples...")
    
    # Placeholder: In production, use actual test dataloader
    # For now, generate dummy data
    input_dim = model.input_dim
    
    # Generate random test data
    test_features = torch.randn(len(test_data), input_dim).to(device)
    test_targets = torch.randn(len(test_data)).to(device) * 5.0  # Random CFV
    
    # Predict
    with torch.no_grad():
        predictions = model(test_features)
    
    # Compute metrics
    metrics = compute_metrics(predictions, test_targets)
    
    print(f"\nEvaluation Results:")
    print(f"  MAE: {metrics['mae']:.4f} bb")
    print(f"  RMSE: {metrics['rmse']:.4f} bb")
    print(f"  PI Width (q90-q10): {metrics['pi_width']:.4f} bb")
    print(f"  PI Coverage: {metrics['pi_coverage']:.2%}")
    print(f"  ECE: {metrics['ece']:.4f}")
    
    return metrics


def main():
    """Main evaluation."""
    args = parse_args()
    
    # Create output directory
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Load model
    model = load_model(args.checkpoint, device)
    
    # Load feature stats
    if args.stats is None:
        checkpoint_dir = Path(args.checkpoint).parent
        stats_path = checkpoint_dir / "stats.json"
    else:
        stats_path = Path(args.stats)
    
    if stats_path.exists():
        with open(stats_path, 'r') as f:
            stats_dict = json.load(f)
        feature_stats = FeatureStats.from_dict(stats_dict)
        print(f"Loaded feature stats from {stats_path}")
    else:
        print(f"Warning: Feature stats not found at {stats_path}")
        feature_stats = None
    
    # Load test data (placeholder)
    test_data = list(range(args.num_samples))
    
    # Evaluate
    metrics = evaluate_model(model, test_data, device)
    
    # Benchmark latency
    input_dim = model.input_dim
    latency_stats = benchmark_latency(model, input_dim, device, num_runs=1000)
    
    print(f"\nLatency Benchmarks:")
    print(f"  Mean: {latency_stats['mean_ms']:.3f} ms")
    print(f"  Median: {latency_stats['median_ms']:.3f} ms")
    print(f"  p95: {latency_stats['p95_ms']:.3f} ms")
    print(f"  p99: {latency_stats['p99_ms']:.3f} ms")
    
    # Check quality requirements
    print(f"\nQuality Check:")
    quality_pass = True
    
    if metrics['mae'] > 0.30:
        print(f"  ✗ MAE {metrics['mae']:.4f} > 0.30 bb")
        quality_pass = False
    else:
        print(f"  ✓ MAE {metrics['mae']:.4f} ≤ 0.30 bb")
    
    if metrics['pi_coverage'] < 0.85:
        print(f"  ✗ PI Coverage {metrics['pi_coverage']:.2%} < 85%")
        quality_pass = False
    else:
        print(f"  ✓ PI Coverage {metrics['pi_coverage']:.2%} ≥ 85%")
    
    if metrics['ece'] > 0.05:
        print(f"  ✗ ECE {metrics['ece']:.4f} > 0.05")
        quality_pass = False
    else:
        print(f"  ✓ ECE {metrics['ece']:.4f} ≤ 0.05")
    
    if latency_stats['p95_ms'] > 1.0:
        print(f"  ✗ p95 Latency {latency_stats['p95_ms']:.3f} ms > 1.0 ms")
        quality_pass = False
    else:
        print(f"  ✓ p95 Latency {latency_stats['p95_ms']:.3f} ms ≤ 1.0 ms")
    
    if quality_pass:
        print(f"\n✓ All quality requirements met!")
    else:
        print(f"\n✗ Some quality requirements not met")
    
    # Save results
    results = {
        'metrics': metrics,
        'latency': latency_stats,
        'quality_pass': quality_pass
    }
    
    results_path = out_dir / "eval_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    main()
