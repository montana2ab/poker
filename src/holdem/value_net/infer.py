"""ONNX inference for CFV Net with gating and caching.

Provides fast CPU inference with:
- ONNX Runtime for optimized execution
- LRU cache (10k entries) for repeated states
- Gating logic based on prediction intervals
- Fallback to rollouts when uncertainty is high
"""

import numpy as np
from typing import Dict, Optional, Tuple
from collections import OrderedDict
import json
from pathlib import Path
import hashlib

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False
    ort = None

from holdem.types import Street
from holdem.value_net.features import FeatureStats


class CFVInference:
    """ONNX-based CFV inference with gating and caching."""
    
    def __init__(
        self,
        model_path: str,
        stats_path: str,
        cache_max_size: int = 10000,
        gating_config: Optional[Dict] = None,
        use_torch_fallback: bool = True
    ):
        """Initialize CFV inference.
        
        Args:
            model_path: Path to ONNX model file
            stats_path: Path to feature stats JSON
            cache_max_size: Maximum LRU cache entries
            gating_config: Gating configuration (thresholds, etc.)
            use_torch_fallback: Use PyTorch if ONNX unavailable
        """
        self.model_path = Path(model_path)
        self.stats_path = Path(stats_path)
        self.cache_max_size = cache_max_size
        
        # Load feature normalization stats
        with open(stats_path, 'r') as f:
            stats_dict = json.load(f)
        self.feature_stats = FeatureStats.from_dict(stats_dict)
        
        # Load ONNX model
        if HAS_ONNX:
            self.session = ort.InferenceSession(
                str(model_path),
                providers=['CPUExecutionProvider']
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_names = [out.name for out in self.session.get_outputs()]
            self.use_torch = False
        elif use_torch_fallback:
            # Fallback to PyTorch (slower)
            import torch
            self.model = torch.jit.load(str(model_path))
            self.model.eval()
            self.use_torch = True
            print(f"Warning: Using PyTorch fallback (ONNX not available)")
        else:
            raise ImportError("ONNX Runtime not available and PyTorch fallback disabled")
        
        # Gating configuration
        self.gating_config = gating_config or self._default_gating_config()
        
        # LRU cache
        self.cache: OrderedDict = OrderedDict()
        self.cache_hits = 0
        self.cache_misses = 0
        
        print(f"CFV Inference initialized: model={model_path}, cache_size={cache_max_size}")
    
    def _default_gating_config(self) -> Dict:
        """Default gating configuration."""
        return {
            'tau_flop': 0.20,      # PI width threshold for flop (bb)
            'tau_turn': 0.16,      # PI width threshold for turn
            'tau_river': 0.12,     # PI width threshold for river
            'ood_sigma': 4.0,      # Out-of-distribution threshold (std devs)
            'clamp_abs_bb': 25.0,  # Absolute value clamp (bb)
            'boost_ip': 1.10,      # Multiplier for in-position
            'boost_oop': 0.90,     # Multiplier for out-of-position
        }
    
    def predict(
        self,
        features: np.ndarray,
        street: Street,
        is_ip: bool = True
    ) -> Tuple[float, float, float, bool]:
        """Predict CFV with gating.
        
        Args:
            features: Feature vector [feature_dim]
            street: Current street
            is_ip: True if hero is in position
            
        Returns:
            Tuple of (mean_cfv, q10, q90, accept)
            - mean_cfv: Mean prediction (bb)
            - q10: 10th percentile (bb)
            - q90: 90th percentile (bb)
            - accept: True if gating accepts, False to fallback
        """
        # Check cache
        cache_key = self._hash_features(features)
        if cache_key in self.cache:
            self.cache_hits += 1
            # Move to end (LRU)
            self.cache.move_to_end(cache_key)
            cached_result = self.cache[cache_key]
            return cached_result
        
        self.cache_misses += 1
        
        # Normalize features
        features_norm = self.feature_stats.normalize(features)
        
        # Check for OOD
        ood_sigma = self.gating_config['ood_sigma']
        if np.abs(features_norm).max() > ood_sigma:
            # Out of distribution - reject
            result = (0.0, 0.0, 0.0, False)
            self._add_to_cache(cache_key, result)
            return result
        
        # Run inference
        if self.use_torch:
            mean_cfv, q10, q90 = self._predict_torch(features_norm)
        else:
            mean_cfv, q10, q90 = self._predict_onnx(features_norm)
        
        # Apply gating
        accept = self._gate_prediction(mean_cfv, q10, q90, street, is_ip)
        
        result = (mean_cfv, q10, q90, accept)
        self._add_to_cache(cache_key, result)
        
        return result
    
    def _predict_onnx(self, features_norm: np.ndarray) -> Tuple[float, float, float]:
        """Run ONNX inference.
        
        Args:
            features_norm: Normalized features [feature_dim]
            
        Returns:
            Tuple of (mean, q10, q90)
        """
        # Prepare input
        input_batch = features_norm.astype(np.float32).reshape(1, -1)
        
        # Run inference
        outputs = self.session.run(self.output_names, {self.input_name: input_batch})
        
        # Extract predictions (assuming order: mean, q10, q90)
        mean_cfv = float(outputs[0][0])
        q10 = float(outputs[1][0])
        q90 = float(outputs[2][0])
        
        return mean_cfv, q10, q90
    
    def _predict_torch(self, features_norm: np.ndarray) -> Tuple[float, float, float]:
        """Run PyTorch inference (fallback).
        
        Args:
            features_norm: Normalized features [feature_dim]
            
        Returns:
            Tuple of (mean, q10, q90)
        """
        import torch
        
        input_tensor = torch.from_numpy(features_norm.astype(np.float32)).unsqueeze(0)
        
        with torch.no_grad():
            outputs = self.model(input_tensor)
        
        if isinstance(outputs, dict):
            mean_cfv = outputs['mean'].item()
            q10 = outputs['q10'].item()
            q90 = outputs['q90'].item()
        else:
            # Assume tuple/list output
            mean_cfv = outputs[0].item()
            q10 = outputs[1].item()
            q90 = outputs[2].item()
        
        return mean_cfv, q10, q90
    
    def _gate_prediction(
        self,
        mean_cfv: float,
        q10: float,
        q90: float,
        street: Street,
        is_ip: bool
    ) -> bool:
        """Apply gating logic to decide if prediction should be used.
        
        Args:
            mean_cfv: Mean prediction
            q10: 10th percentile
            q90: 90th percentile
            street: Current street
            is_ip: True if in position
            
        Returns:
            True if accept, False if fallback
        """
        # Get threshold for street
        if street == Street.FLOP:
            tau = self.gating_config['tau_flop']
        elif street == Street.TURN:
            tau = self.gating_config['tau_turn']
        elif street == Street.RIVER:
            tau = self.gating_config['tau_river']
        else:
            # Preflop - always reject (use blueprint)
            return False
        
        # Adjust threshold by position
        if is_ip:
            tau *= self.gating_config['boost_ip']
        else:
            tau *= self.gating_config['boost_oop']
        
        # Check PI width
        pi_width = q90 - q10
        if pi_width > tau:
            # Too uncertain - reject
            return False
        
        # Check absolute value clamp
        clamp_abs = self.gating_config['clamp_abs_bb']
        if abs(mean_cfv) > clamp_abs:
            # Value too extreme - reject
            return False
        
        # Accept
        return True
    
    def _hash_features(self, features: np.ndarray) -> str:
        """Hash feature vector for cache key.
        
        Args:
            features: Feature vector
            
        Returns:
            Hash string
        """
        # Use compact representation (quantize to reduce collisions)
        features_quantized = (features * 1000).astype(np.int32)
        return hashlib.md5(features_quantized.tobytes()).hexdigest()
    
    def _add_to_cache(self, key: str, value: Tuple):
        """Add entry to LRU cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        # Evict if full
        if len(self.cache) >= self.cache_max_size:
            # Remove oldest (first) item
            self.cache.popitem(last=False)
        
        self.cache[key] = value
    
    def get_cache_stats(self) -> Dict[str, float]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        total_accesses = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_accesses if total_accesses > 0 else 0.0
        
        return {
            'cache_size': len(self.cache),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': hit_rate
        }
    
    def clear_cache(self):
        """Clear cache and reset statistics."""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0


def export_to_onnx(
    model,
    output_path: str,
    input_dim: int,
    opset_version: int = 17
):
    """Export PyTorch model to ONNX.
    
    Args:
        model: PyTorch model
        output_path: Output ONNX file path
        input_dim: Input feature dimension
        opset_version: ONNX opset version (≥17)
    """
    import torch
    
    model.eval()
    
    # Dummy input
    dummy_input = torch.randn(1, input_dim)
    
    # Export
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=['features'],
        output_names=['mean', 'q10', 'q90'],
        dynamic_axes={
            'features': {0: 'batch_size'},
            'mean': {0: 'batch_size'},
            'q10': {0: 'batch_size'},
            'q90': {0: 'batch_size'}
        }
    )
    
    print(f"Model exported to ONNX: {output_path}")
