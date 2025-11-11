#!/usr/bin/env python3
"""Train CFV Net model.

Usage:
    python tools/train_cfv_net.py \\
        --data data/cfv/6max_jsonlz \\
        --config configs/cfv_net_m2.yaml \\
        --logdir runs/cfv_net_6max_m2

This tool:
1. Loads CFV training dataset (sharded .jsonl.zst)
2. Trains CFVNet with AdamW, cosine decay, warmup
3. Logs metrics to TensorBoard
4. Saves checkpoints and best model
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict
import yaml

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.utils.tensorboard import SummaryWriter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from holdem.value_net import (
    CFVDatasetReader,
    CFVNet,
    CFVLoss,
    compute_metrics,
    create_optimizer,
    create_scheduler,
    EarlyStopping,
    CFVFeatureBuilder,
    FeatureStats,
    get_feature_dimension,
    create_bucket_embeddings,
    split_dataset
)
from holdem.types import Street, Position


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Train CFV Net")
    
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Dataset directory (sharded .jsonl.zst)"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Training config file (YAML)"
    )
    parser.add_argument(
        "--logdir",
        type=str,
        required=True,
        help="TensorBoard log directory"
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Resume from checkpoint"
    )
    
    return parser.parse_args()


def load_config(config_path: str) -> Dict:
    """Load training configuration.
    
    Args:
        config_path: Path to YAML config
        
    Returns:
        Config dictionary
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


class CFVDataset(Dataset):
    """PyTorch dataset for CFV training."""
    
    def __init__(
        self,
        examples: list,
        feature_builder: CFVFeatureBuilder,
        feature_stats: FeatureStats = None
    ):
        """Initialize dataset.
        
        Args:
            examples: List of example dictionaries
            feature_builder: Feature builder
            feature_stats: Feature normalization stats (optional)
        """
        self.examples = examples
        self.feature_builder = feature_builder
        self.feature_stats = feature_stats
    
    def __len__(self):
        return len(self.examples)
    
    def __getitem__(self, idx):
        example = self.examples[idx]
        
        # Parse example
        street = Street[example['street']]
        hero_pos = Position[example['hero_pos']]
        num_players = example['num_players']
        spr = example['spr']
        public_bucket = example['public_bucket']
        
        scalars = example['scalars']
        pot_norm = scalars['pot_norm']
        pot_size = pot_norm * 100.0  # Denormalize
        to_call = scalars['to_call_over_pot'] * pot_size
        last_bet = scalars['last_bet_over_pot'] * pot_size
        aset = scalars['aset']
        
        # Convert ranges
        ranges = {}
        for pos_str, topk in example['ranges'].items():
            pos = Position[pos_str]
            ranges[pos] = [(int(bid), float(w)) for bid, w in topk]
        
        # Build features
        features_obj = self.feature_builder.build_features(
            street=street,
            num_players=num_players,
            hero_position=hero_pos,
            spr=spr,
            pot_size=pot_size,
            to_call=to_call,
            last_bet=last_bet,
            action_set=aset,
            public_bucket=public_bucket,
            ranges=ranges
        )
        
        features = features_obj.to_vector()
        
        # Normalize if stats available
        if self.feature_stats is not None:
            features = self.feature_stats.normalize(features)
        
        # Target
        target = example['target_cfv_bb']
        
        return torch.from_numpy(features).float(), torch.tensor(target).float()


def compute_feature_stats(dataset: CFVDataset) -> FeatureStats:
    """Compute feature normalization statistics.
    
    Args:
        dataset: Training dataset
        
    Returns:
        FeatureStats object
    """
    print("Computing feature statistics...")
    
    all_features = []
    for i in range(min(len(dataset), 10000)):  # Sample for efficiency
        features, _ = dataset[i]
        all_features.append(features.numpy())
    
    all_features = np.stack(all_features, axis=0)
    
    mean = all_features.mean(axis=0)
    std = all_features.std(axis=0)
    
    return FeatureStats(mean=mean, std=std)


def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: CFVLoss,
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler._LRScheduler,
    device: torch.device,
    grad_accumulation: int,
    grad_clip: float,
    writer: SummaryWriter,
    epoch: int,
    log_interval: int
) -> Dict[str, float]:
    """Train for one epoch.
    
    Args:
        model: Model to train
        dataloader: Training dataloader
        criterion: Loss function
        optimizer: Optimizer
        scheduler: Learning rate scheduler
        device: Device to train on
        grad_accumulation: Gradient accumulation steps
        grad_clip: Gradient clipping norm
        writer: TensorBoard writer
        epoch: Current epoch
        log_interval: Log interval
        
    Returns:
        Dictionary of metrics
    """
    model.train()
    
    total_loss = 0.0
    total_metrics = {}
    num_batches = 0
    
    optimizer.zero_grad()
    
    for batch_idx, (features, targets) in enumerate(dataloader):
        features = features.to(device)
        targets = targets.to(device)
        
        # Forward
        predictions = model(features)
        loss, loss_dict = criterion(predictions, targets)
        
        # Backward (with accumulation)
        loss = loss / grad_accumulation
        loss.backward()
        
        if (batch_idx + 1) % grad_accumulation == 0:
            # Gradient clipping
            if grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            
            # Optimizer step
            optimizer.step()
            optimizer.zero_grad()
            scheduler.step()
        
        # Metrics
        total_loss += loss_dict['loss']
        for key, value in loss_dict.items():
            total_metrics[key] = total_metrics.get(key, 0.0) + value
        
        num_batches += 1
        
        # Logging
        if (batch_idx + 1) % log_interval == 0:
            global_step = epoch * len(dataloader) + batch_idx
            avg_loss = total_loss / num_batches
            
            writer.add_scalar('train/loss', avg_loss, global_step)
            writer.add_scalar('train/lr', scheduler.get_last_lr()[0], global_step)
            
            print(f"Epoch {epoch} [{batch_idx + 1}/{len(dataloader)}] "
                  f"Loss: {avg_loss:.4f} LR: {scheduler.get_last_lr()[0]:.6f}")
    
    # Average metrics
    avg_metrics = {k: v / num_batches for k, v in total_metrics.items()}
    
    return avg_metrics


def validate(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: CFVLoss,
    device: torch.device
) -> Dict[str, float]:
    """Validate model.
    
    Args:
        model: Model to validate
        dataloader: Validation dataloader
        criterion: Loss function
        device: Device
        
    Returns:
        Dictionary of metrics
    """
    model.eval()
    
    all_predictions = {'mean': [], 'q10': [], 'q90': []}
    all_targets = []
    total_loss = 0.0
    
    with torch.no_grad():
        for features, targets in dataloader:
            features = features.to(device)
            targets = targets.to(device)
            
            # Forward
            predictions = model(features)
            loss, loss_dict = criterion(predictions, targets)
            
            total_loss += loss_dict['loss']
            
            # Collect predictions
            all_predictions['mean'].append(predictions['mean'])
            all_predictions['q10'].append(predictions['q10'])
            all_predictions['q90'].append(predictions['q90'])
            all_targets.append(targets)
    
    # Concatenate
    predictions = {
        'mean': torch.cat(all_predictions['mean']),
        'q10': torch.cat(all_predictions['q10']),
        'q90': torch.cat(all_predictions['q90'])
    }
    targets = torch.cat(all_targets)
    
    # Compute metrics
    metrics = compute_metrics(predictions, targets)
    metrics['loss'] = total_loss / len(dataloader)
    
    return metrics


def main():
    """Main training loop."""
    args = parse_args()
    
    # Load config
    config = load_config(args.config)
    print(f"Config: {json.dumps(config, indent=2)}")
    
    # Create log directory
    logdir = Path(args.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    
    # Save config
    with open(logdir / "config.yaml", 'w') as f:
        yaml.dump(config, f)
    
    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Set seeds
    seed = config['train']['seed']
    torch.manual_seed(seed)
    np.random.seed(seed)
    
    # Set threading (M2 optimization)
    import os
    os.environ['OMP_NUM_THREADS'] = '1'
    os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    os.environ['NUMEXPR_NUM_THREADS'] = '1'
    
    # Split dataset
    print("Splitting dataset...")
    split = split_dataset(
        args.data,
        train_frac=config['split']['train'],
        val_frac=config['split']['val'],
        test_frac=config['split']['test'],
        seed=seed
    )
    
    print(f"Train shards: {len(split['train'])}")
    print(f"Val shards: {len(split['val'])}")
    print(f"Test shards: {len(split['test'])}")
    
    # Load examples (simplified - in production, use efficient streaming)
    print("Loading training examples...")
    reader = CFVDatasetReader(args.data, shuffle=True, seed=seed)
    all_examples = list(reader)[:100000]  # Limit for demo
    
    num_train = int(len(all_examples) * config['split']['train'])
    train_examples = all_examples[:num_train]
    val_examples = all_examples[num_train:]
    
    print(f"Train examples: {len(train_examples)}")
    print(f"Val examples: {len(val_examples)}")
    
    # Create bucket embeddings
    num_buckets = 1000  # Placeholder
    embed_dim = config['features']['embed_dim']
    bucket_embeddings = create_bucket_embeddings(num_buckets, embed_dim, seed)
    
    # Create feature builder
    feature_builder = CFVFeatureBuilder(
        bucket_embeddings=bucket_embeddings,
        topk_range=config['features']['topk_range'],
        embed_dim=embed_dim
    )
    
    # Create datasets
    train_dataset = CFVDataset(train_examples, feature_builder)
    
    # Compute feature stats
    feature_stats = compute_feature_stats(train_dataset)
    
    # Apply stats to datasets
    train_dataset.feature_stats = feature_stats
    val_dataset = CFVDataset(val_examples, feature_builder, feature_stats)
    
    # Save feature stats
    stats_path = logdir / "stats.json"
    with open(stats_path, 'w') as f:
        json.dump(feature_stats.to_dict(), f, indent=2)
    print(f"Saved feature stats to {stats_path}")
    
    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=config['opt']['batch_size'],
        shuffle=True,
        num_workers=config['train']['num_workers'],
        pin_memory=config['train']['pin_memory']
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=config['opt']['batch_size'],
        shuffle=False,
        num_workers=config['train']['num_workers'],
        pin_memory=config['train']['pin_memory']
    )
    
    # Create model
    input_dim = get_feature_dimension(embed_dim)
    model = CFVNet(
        input_dim=input_dim,
        hidden_dims=config['model']['hidden'],
        dropout=config['model']['dropout'],
        quantiles=config['model']['quantiles']
    ).to(device)
    
    print(f"Model: {sum(p.numel() for p in model.parameters())} parameters")
    
    # Create loss, optimizer, scheduler
    criterion = CFVLoss(
        quantiles=config['model']['quantiles'],
        huber_delta=config['loss']['huber_delta'],
        mean_weight=config['loss']['mean_weight'],
        quantile_weight=config['loss']['quantile_weight']
    )
    
    optimizer = create_optimizer(
        model,
        lr=config['opt']['lr'],
        weight_decay=config['opt']['weight_decay']
    )
    
    scheduler = create_scheduler(
        optimizer,
        num_epochs=config['opt']['epochs'],
        steps_per_epoch=len(train_loader) // config['opt']['grad_accumulation'],
        warmup_frac=config['sched']['warmup_frac']
    )
    
    # Early stopping
    early_stop = EarlyStopping(
        patience=config['early_stop']['patience'],
        mode='min'
    )
    
    # TensorBoard writer
    writer = SummaryWriter(log_dir=str(logdir))
    
    # Training loop
    best_val_metric = float('inf')
    
    for epoch in range(config['opt']['epochs']):
        print(f"\n{'='*60}")
        print(f"Epoch {epoch + 1}/{config['opt']['epochs']}")
        print(f"{'='*60}")
        
        # Train
        train_metrics = train_epoch(
            model, train_loader, criterion, optimizer, scheduler,
            device,
            grad_accumulation=config['opt']['grad_accumulation'],
            grad_clip=config['opt']['grad_clip'],
            writer=writer,
            epoch=epoch,
            log_interval=config['train']['log_interval']
        )
        
        # Validate
        print("Validating...")
        val_metrics = validate(model, val_loader, criterion, device)
        
        print(f"\nTrain Loss: {train_metrics['loss']:.4f}")
        print(f"Val Loss: {val_metrics['loss']:.4f}")
        print(f"Val MAE: {val_metrics['mae']:.4f} bb")
        print(f"Val PI Coverage: {val_metrics['pi_coverage']:.2%}")
        print(f"Val ECE: {val_metrics['ece']:.4f}")
        
        # Log to TensorBoard
        writer.add_scalar('val/loss', val_metrics['loss'], epoch)
        writer.add_scalar('val/mae', val_metrics['mae'], epoch)
        writer.add_scalar('val/pi_coverage', val_metrics['pi_coverage'], epoch)
        writer.add_scalar('val/ece', val_metrics['ece'], epoch)
        
        # Save checkpoint
        checkpoint_path = logdir / f"checkpoint_epoch{epoch + 1}.pt"
        torch.save({
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'scheduler_state_dict': scheduler.state_dict(),
            'val_metrics': val_metrics
        }, checkpoint_path)
        
        # Save best model
        if val_metrics['mae'] < best_val_metric:
            best_val_metric = val_metrics['mae']
            best_path = logdir / "best.pt"
            torch.save(model.state_dict(), best_path)
            print(f"✓ Saved best model (MAE: {best_val_metric:.4f})")
        
        # Early stopping
        if early_stop(val_metrics['mae']):
            print(f"\nEarly stopping at epoch {epoch + 1}")
            break
    
    writer.close()
    print(f"\nTraining complete! Best MAE: {best_val_metric:.4f} bb")
    print(f"Logs saved to {logdir}")


if __name__ == "__main__":
    main()
