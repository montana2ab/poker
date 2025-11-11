"""CFV Net model architecture and training utilities.

MLP with [512, 512, 256] hidden layers, GELU activation, LayerNorm, Dropout.
Multiple prediction heads: mean (Huber loss), q10/q90 (pinball loss).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple, Optional
import numpy as np


class CFVNet(nn.Module):
    """Counterfactual Value Network.
    
    Architecture:
    - Input: Feature vector (≈470 dims)
    - Hidden: [512, 512, 256] with GELU, LayerNorm, Dropout
    - Heads: mean (Huber), q10 (pinball), q90 (pinball)
    """
    
    def __init__(
        self,
        input_dim: int,
        hidden_dims: list = [512, 512, 256],
        dropout: float = 0.05,
        quantiles: list = [0.10, 0.90]
    ):
        """Initialize CFV Net.
        
        Args:
            input_dim: Input feature dimension
            hidden_dims: Hidden layer dimensions
            dropout: Dropout probability
            quantiles: Quantiles to predict (e.g., [0.10, 0.90])
        """
        super().__init__()
        
        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.dropout_p = dropout
        self.quantiles = quantiles
        
        # Build MLP layers
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.LayerNorm(hidden_dim))
            layers.append(nn.GELU())
            layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim
        
        self.backbone = nn.Sequential(*layers)
        
        # Prediction heads
        self.mean_head = nn.Linear(prev_dim, 1)
        self.quantile_heads = nn.ModuleList([
            nn.Linear(prev_dim, 1) for _ in quantiles
        ])
    
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Forward pass.
        
        Args:
            x: Input features [batch_size, input_dim]
            
        Returns:
            Dictionary with 'mean', 'q10', 'q90' predictions
        """
        # Backbone
        h = self.backbone(x)
        
        # Predictions
        mean_pred = self.mean_head(h).squeeze(-1)  # [batch_size]
        quantile_preds = [head(h).squeeze(-1) for head in self.quantile_heads]
        
        output = {'mean': mean_pred}
        for i, q in enumerate(self.quantiles):
            q_name = f'q{int(q * 100)}'
            output[q_name] = quantile_preds[i]
        
        return output


class CFVLoss(nn.Module):
    """Combined loss for CFV Net.
    
    - Mean: Huber loss (δ=1.0)
    - Quantiles: Pinball loss
    - Weights: mean 0.6, quantiles 0.2/0.2
    """
    
    def __init__(
        self,
        quantiles: list = [0.10, 0.90],
        huber_delta: float = 1.0,
        mean_weight: float = 0.6,
        quantile_weight: float = 0.2
    ):
        """Initialize loss.
        
        Args:
            quantiles: Quantiles to predict
            huber_delta: Huber loss delta parameter
            mean_weight: Weight for mean loss
            quantile_weight: Weight per quantile loss
        """
        super().__init__()
        
        self.quantiles = quantiles
        self.huber_delta = huber_delta
        self.mean_weight = mean_weight
        self.quantile_weight = quantile_weight
    
    def forward(
        self,
        predictions: Dict[str, torch.Tensor],
        targets: torch.Tensor
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """Compute loss.
        
        Args:
            predictions: Dictionary with 'mean', 'q10', 'q90'
            targets: Target values [batch_size]
            
        Returns:
            Tuple of (total_loss, loss_dict)
        """
        # Mean loss (Huber)
        mean_loss = F.huber_loss(
            predictions['mean'],
            targets,
            delta=self.huber_delta,
            reduction='mean'
        )
        
        # Quantile losses (Pinball)
        quantile_losses = []
        for i, q in enumerate(self.quantiles):
            q_name = f'q{int(q * 100)}'
            q_pred = predictions[q_name]
            q_loss = self.pinball_loss(q_pred, targets, q)
            quantile_losses.append(q_loss)
        
        # Total loss
        total_loss = (
            self.mean_weight * mean_loss +
            sum(self.quantile_weight * ql for ql in quantile_losses)
        )
        
        # Loss dict for logging
        loss_dict = {
            'loss': total_loss.item(),
            'mean_loss': mean_loss.item()
        }
        for i, q in enumerate(self.quantiles):
            q_name = f'q{int(q * 100)}'
            loss_dict[f'{q_name}_loss'] = quantile_losses[i].item()
        
        return total_loss, loss_dict
    
    def pinball_loss(
        self,
        pred: torch.Tensor,
        target: torch.Tensor,
        quantile: float
    ) -> torch.Tensor:
        """Compute pinball (quantile) loss.
        
        Args:
            pred: Predictions [batch_size]
            target: Targets [batch_size]
            quantile: Quantile level (0-1)
            
        Returns:
            Scalar loss
        """
        errors = target - pred
        loss = torch.where(
            errors >= 0,
            quantile * errors,
            (quantile - 1) * errors
        )
        return loss.mean()


def compute_metrics(
    predictions: Dict[str, torch.Tensor],
    targets: torch.Tensor
) -> Dict[str, float]:
    """Compute evaluation metrics.
    
    Args:
        predictions: Dictionary with 'mean', 'q10', 'q90'
        targets: Target values
        
    Returns:
        Dictionary of metrics
    """
    mean_pred = predictions['mean'].detach().cpu().numpy()
    q10_pred = predictions['q10'].detach().cpu().numpy()
    q90_pred = predictions['q90'].detach().cpu().numpy()
    targets_np = targets.detach().cpu().numpy()
    
    # MAE
    mae = np.abs(mean_pred - targets_np).mean()
    
    # MSE
    mse = ((mean_pred - targets_np) ** 2).mean()
    
    # PI width (q90 - q10)
    pi_width = (q90_pred - q10_pred).mean()
    
    # PI coverage (fraction of targets within [q10, q90])
    in_interval = (targets_np >= q10_pred) & (targets_np <= q90_pred)
    pi_coverage = in_interval.mean()
    
    # Calibration error (ECE - Expected Calibration Error)
    # Simplified version: check if coverage is close to 80%
    expected_coverage = 0.80  # q90 - q10 = 80% interval
    ece = abs(pi_coverage - expected_coverage)
    
    return {
        'mae': mae,
        'mse': mse,
        'rmse': np.sqrt(mse),
        'pi_width': pi_width,
        'pi_coverage': pi_coverage,
        'ece': ece
    }


def create_optimizer(
    model: nn.Module,
    lr: float = 1e-3,
    weight_decay: float = 1e-4
) -> torch.optim.Optimizer:
    """Create AdamW optimizer.
    
    Args:
        model: Model to optimize
        lr: Learning rate
        weight_decay: Weight decay (L2 regularization)
        
    Returns:
        AdamW optimizer
    """
    return torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=weight_decay,
        betas=(0.9, 0.999)
    )


def create_scheduler(
    optimizer: torch.optim.Optimizer,
    num_epochs: int,
    steps_per_epoch: int,
    warmup_frac: float = 0.05
) -> torch.optim.lr_scheduler._LRScheduler:
    """Create cosine annealing scheduler with warmup.
    
    Args:
        optimizer: Optimizer
        num_epochs: Total number of epochs
        steps_per_epoch: Steps per epoch
        warmup_frac: Fraction of training for warmup
        
    Returns:
        Learning rate scheduler
    """
    total_steps = num_epochs * steps_per_epoch
    warmup_steps = int(total_steps * warmup_frac)
    
    def lr_lambda(step):
        if step < warmup_steps:
            # Linear warmup
            return step / warmup_steps
        else:
            # Cosine decay
            progress = (step - warmup_steps) / (total_steps - warmup_steps)
            return 0.5 * (1 + np.cos(np.pi * progress))
    
    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


class EarlyStopping:
    """Early stopping with patience."""
    
    def __init__(self, patience: int = 3, min_delta: float = 0.0, mode: str = 'min'):
        """Initialize early stopping.
        
        Args:
            patience: Number of epochs to wait before stopping
            min_delta: Minimum change to qualify as improvement
            mode: 'min' (lower is better) or 'max' (higher is better)
        """
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        
        self.counter = 0
        self.best_value = None
        self.should_stop = False
    
    def __call__(self, value: float) -> bool:
        """Check if should stop.
        
        Args:
            value: Metric value to monitor
            
        Returns:
            True if should stop training
        """
        if self.best_value is None:
            self.best_value = value
            return False
        
        # Check for improvement
        if self.mode == 'min':
            improved = value < (self.best_value - self.min_delta)
        else:
            improved = value > (self.best_value + self.min_delta)
        
        if improved:
            self.best_value = value
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
        
        return self.should_stop
    
    def reset(self):
        """Reset early stopping state."""
        self.counter = 0
        self.best_value = None
        self.should_stop = False
