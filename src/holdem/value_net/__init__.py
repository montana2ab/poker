"""Counterfactual Value Network (CFV Net) for leaf evaluation.

This module provides neural network-based leaf evaluation for real-time poker solving,
replacing rollouts while maintaining EV and fitting within 80-110ms budget.

Main components:
- features.py: Feature construction and normalization
- dataset.py: Dataset reader/writer with .jsonl.zst sharding
- cfv_net.py: PyTorch model definition and training utilities
- infer.py: ONNX inference with gating and caching
"""

from holdem.value_net.features import (
    CFVFeatureBuilder,
    CFVFeatures,
    FeatureStats,
    get_feature_dimension,
    create_bucket_embeddings
)
from holdem.value_net.dataset import (
    CFVDatasetWriter,
    CFVDatasetReader,
    split_dataset
)
from holdem.value_net.cfv_net import (
    CFVNet,
    CFVLoss,
    compute_metrics,
    create_optimizer,
    create_scheduler,
    EarlyStopping
)
from holdem.value_net.infer import (
    CFVInference,
    export_to_onnx
)

__all__ = [
    # Features
    'CFVFeatureBuilder',
    'CFVFeatures',
    'FeatureStats',
    'get_feature_dimension',
    'create_bucket_embeddings',
    # Dataset
    'CFVDatasetWriter',
    'CFVDatasetReader',
    'split_dataset',
    # Model
    'CFVNet',
    'CFVLoss',
    'compute_metrics',
    'create_optimizer',
    'create_scheduler',
    'EarlyStopping',
    # Inference
    'CFVInference',
    'export_to_onnx',
]
