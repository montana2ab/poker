#!/usr/bin/env python3
"""Export CFV Net to ONNX format.

Usage:
    python tools/export_cfv_net.py \\
        --checkpoint runs/cfv_net_6max_m2/best.pt \\
        --out assets/cfv_net/6max_best.onnx

This tool:
1. Loads trained CFV Net checkpoint
2. Exports to ONNX format (opset≥17)
3. Saves feature normalization stats (stats.json)
4. Optionally saves calibration data (calib.json)
"""

import argparse
import json
import sys
from pathlib import Path
import torch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from holdem.value_net import (
    CFVNet,
    get_feature_dimension,
    export_to_onnx,
    FeatureStats
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Export CFV Net to ONNX")
    
    parser.add_argument(
        "--checkpoint",
        type=str,
        required=True,
        help="Path to model checkpoint (.pt)"
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output ONNX file path"
    )
    parser.add_argument(
        "--stats",
        type=str,
        default=None,
        help="Feature stats JSON (default: checkpoint_dir/stats.json)"
    )
    parser.add_argument(
        "--opset-version",
        type=int,
        default=17,
        help="ONNX opset version (default: 17)"
    )
    
    return parser.parse_args()


def load_model(checkpoint_path: str):
    """Load model from checkpoint.
    
    Args:
        checkpoint_path: Path to checkpoint
        
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
    
    state_dict = torch.load(checkpoint_path, map_location='cpu')
    if isinstance(state_dict, dict) and 'model_state_dict' in state_dict:
        model.load_state_dict(state_dict['model_state_dict'])
    else:
        model.load_state_dict(state_dict)
    
    model.eval()
    
    print(f"Model loaded: {sum(p.numel() for p in model.parameters())} parameters")
    return model


def main():
    """Main export."""
    args = parse_args()
    
    # Create output directory
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load model
    model = load_model(args.checkpoint)
    
    # Export to ONNX
    input_dim = model.input_dim
    print(f"Exporting to ONNX (opset {args.opset_version})...")
    export_to_onnx(
        model,
        str(out_path),
        input_dim=input_dim,
        opset_version=args.opset_version
    )
    
    print(f"✓ ONNX model saved to {out_path}")
    
    # Copy feature stats
    if args.stats is None:
        checkpoint_dir = Path(args.checkpoint).parent
        stats_src = checkpoint_dir / "stats.json"
    else:
        stats_src = Path(args.stats)
    
    if stats_src.exists():
        stats_dst = out_path.parent / "stats.json"
        with open(stats_src, 'r') as f:
            stats = json.load(f)
        with open(stats_dst, 'w') as f:
            json.dump(stats, f, indent=2)
        print(f"✓ Feature stats saved to {stats_dst}")
    else:
        print(f"Warning: Feature stats not found at {stats_src}")
    
    # Create placeholder calibration data
    calib_data = {
        "isotonic_calibration": {
            "q10": {"x": [], "y": []},
            "q90": {"x": [], "y": []}
        },
        "note": "Calibration data should be computed from validation set"
    }
    
    calib_path = out_path.parent / "calib.json"
    with open(calib_path, 'w') as f:
        json.dump(calib_data, f, indent=2)
    print(f"✓ Calibration placeholder saved to {calib_path}")
    
    # Verify ONNX model
    try:
        import onnxruntime as ort
        
        print(f"\nVerifying ONNX model...")
        session = ort.InferenceSession(
            str(out_path),
            providers=['CPUExecutionProvider']
        )
        
        # Test inference
        import numpy as np
        dummy_input = np.random.randn(1, input_dim).astype(np.float32)
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: dummy_input})
        
        print(f"✓ ONNX model verified")
        print(f"  Input shape: {dummy_input.shape}")
        print(f"  Output shapes: {[out.shape for out in outputs]}")
        
    except ImportError:
        print(f"\nWarning: onnxruntime not available, skipping verification")
    except Exception as e:
        print(f"\nError verifying ONNX model: {e}")
    
    print(f"\n✓ Export complete!")
    print(f"  Model: {out_path}")
    print(f"  Stats: {out_path.parent / 'stats.json'}")
    print(f"  Calib: {out_path.parent / 'calib.json'}")


if __name__ == "__main__":
    main()
