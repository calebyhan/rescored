"""
BiLSTM Training Script

Trains the BiLSTM refinement model on MAESTRO dataset.

Prerequisites:
1. MAESTRO dataset downloaded
2. Dataset preparation completed (run dataset_builder.py first)

Training time: 8-12 hours on single GPU
Expected improvement: +1-2% F1
"""

import argparse
from pathlib import Path
import json
from datetime import datetime
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm


class MAESTROPianoRollDataset(Dataset):
    """Dataset of (ensemble prediction, ground truth) piano roll pairs."""

    def __init__(self, data_dir: Path, max_length: int = 10000):
        """
        Initialize dataset.

        Args:
            data_dir: Directory with .npz files from dataset_builder
            max_length: Maximum sequence length (frames). Longer sequences are chunked.
        """
        self.data_dir = Path(data_dir)
        self.max_length = max_length

        # Find all .npz files
        self.files = list(self.data_dir.glob("*.npz"))

        if len(self.files) == 0:
            raise ValueError(f"No .npz files found in {data_dir}")

        print(f"Loaded {len(self.files)} files from {data_dir}")

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        # Load .npz file
        data = np.load(self.files[idx])

        ensemble_roll = data['ensemble_roll']  # (time, 88)
        gt_roll = data['ground_truth_roll']    # (time, 88)

        # Chunk if too long
        if len(ensemble_roll) > self.max_length:
            # Random chunk for training variety
            start_idx = np.random.randint(0, len(ensemble_roll) - self.max_length)
            ensemble_roll = ensemble_roll[start_idx:start_idx + self.max_length]
            gt_roll = gt_roll[start_idx:start_idx + self.max_length]
        elif len(ensemble_roll) < self.max_length:
            # Pad if too short (zero-padding at the end)
            pad_length = self.max_length - len(ensemble_roll)
            ensemble_roll = np.pad(ensemble_roll, ((0, pad_length), (0, 0)), mode='constant', constant_values=0)
            gt_roll = np.pad(gt_roll, ((0, pad_length), (0, 0)), mode='constant', constant_values=0)

        return {
            'input': torch.from_numpy(ensemble_roll).float(),
            'target': torch.from_numpy(gt_roll).float()
        }


def combined_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """
    Combined loss function: Weighted BCE + differentiable soft F1 loss.

    Piano rolls are extremely sparse (~0.1% positive), so we use:
    1. Weighted BCE to upweight positive samples
    2. Soft F1 loss that's actually differentiable (no hard threshold)

    Args:
        pred: Predicted probabilities (batch, time, 88)
        target: Ground truth (batch, time, 88)

    Returns:
        Combined loss value
    """
    # Calculate positive class weight based on sparsity
    # If 0.5% of data is positive, weight positives 200x more
    num_pos = target.sum()
    num_neg = target.numel() - num_pos
    pos_weight = num_neg / (num_pos + 1e-8)
    pos_weight = torch.clamp(pos_weight, max=100.0)  # Cap at 100x to avoid instability

    # Weighted binary cross-entropy
    bce = nn.functional.binary_cross_entropy(
        pred, target,
        weight=target * pos_weight + (1 - target)  # Weight positives higher
    )

    # Differentiable SOFT F1 loss (use predictions directly, not thresholded)
    # This allows gradients to flow through
    pred_flat = pred.view(-1)
    target_flat = target.view(-1)

    # Soft counts using probabilities
    tp = (pred_flat * target_flat).sum()
    fp = (pred_flat * (1 - target_flat)).sum()
    fn = ((1 - pred_flat) * target_flat).sum()

    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    f1 = 2 * precision * recall / (precision + recall + 1e-8)
    f1_loss = 1 - f1

    # Combined loss (equal weight to BCE and F1)
    return bce + 0.5 * f1_loss


def train_bilstm(
    train_dir: Path,
    val_dir: Path,
    output_dir: Path,
    batch_size: int = 8,  # Reduced from 16 to avoid OOM with attention
    lr: float = 1e-3,
    epochs: int = 50,
    device: str = 'cuda'
):
    """
    Train BiLSTM refinement model.

    Args:
        train_dir: Directory with training .npz files
        val_dir: Directory with validation .npz files
        output_dir: Directory to save checkpoints and logs
        batch_size: Training batch size
        lr: Learning rate
        epochs: Number of training epochs
        device: Device to train on
    """
    from backend.refinement.bilstm_refiner import BiLSTMRefiner

    print(f"\n{'=' * 70}")
    print("BiLSTM Refinement Training")
    print(f"{'=' * 70}")
    print(f"Train data: {train_dir}")
    print(f"Val data: {val_dir}")
    print(f"Output dir: {output_dir}")
    print(f"Device: {device}")
    print(f"Batch size: {batch_size}")
    print(f"Learning rate: {lr}")
    print(f"Epochs: {epochs}")
    print(f"{'=' * 70}\n")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load datasets
    # Reduced max_length to 5000 (50s @ 100fps) to avoid OOM with attention mechanism
    train_dataset = MAESTROPianoRollDataset(train_dir, max_length=5000)
    val_dataset = MAESTROPianoRollDataset(val_dir, max_length=5000)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=4,
        pin_memory=True if device == 'cuda' else False
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=4,
        pin_memory=True if device == 'cuda' else False
    )

    print(f"Training samples: {len(train_dataset)}")
    print(f"Validation samples: {len(val_dataset)}")
    print(f"Batches per epoch: {len(train_loader)}")
    print()

    # Initialize model
    model = BiLSTMRefiner(
        input_dim=88,
        hidden_dim=256,
        num_layers=2,
        dropout=0.2,
        use_attention=False  # Disabled to avoid OOM on shared GPUs
    ).to(device)

    # Optimizer and scheduler
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode='min',
        factor=0.5,
        patience=5
        # Note: 'verbose' parameter removed (deprecated in PyTorch 2.x)
    )

    # Training loop
    best_val_loss = float('inf')
    history = {
        'train_loss': [],
        'val_loss': [],
        'val_f1': []
    }

    for epoch in range(epochs):
        print(f"\n{'=' * 70}")
        print(f"Epoch {epoch + 1}/{epochs}")
        print(f"{'=' * 70}")

        # Training
        model.train()
        train_losses = []

        for batch in tqdm(train_loader, desc="Training"):
            inputs = batch['input'].to(device)
            targets = batch['target'].to(device)

            optimizer.zero_grad()

            # Forward pass
            outputs = model(inputs)
            loss = combined_loss(outputs, targets)

            # Backward pass
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_losses.append(loss.item())

        avg_train_loss = np.mean(train_losses)
        history['train_loss'].append(avg_train_loss)

        # Validation
        model.eval()
        val_losses = []
        val_f1_scores = []

        with torch.no_grad():
            for batch in tqdm(val_loader, desc="Validation"):
                inputs = batch['input'].to(device)
                targets = batch['target'].to(device)

                outputs = model(inputs)
                loss = combined_loss(outputs, targets)
                val_losses.append(loss.item())

                # Compute F1 score
                pred_binary = (outputs > 0.5).float()
                pred_flat = pred_binary.view(-1).cpu().numpy()
                target_flat = targets.view(-1).cpu().numpy()

                tp = np.sum((pred_flat == 1) & (target_flat == 1))
                fp = np.sum((pred_flat == 1) & (target_flat == 0))
                fn = np.sum((pred_flat == 0) & (target_flat == 1))

                # Debug output for first batch of first epoch
                if epoch == 0 and len(val_losses) == 1:
                    print(f"\n  [DEBUG] First validation batch stats:")
                    print(f"    Output range: [{outputs.min().item():.4f}, {outputs.max().item():.4f}]")
                    print(f"    Output mean: {outputs.mean().item():.4f}")
                    print(f"    Target positives: {int(target_flat.sum())} / {len(target_flat)}")
                    print(f"    Pred positives (>0.5): {int(pred_flat.sum())}")
                    print(f"    TP={tp}, FP={fp}, FN={fn}")

                if (tp + fp) > 0 and (tp + fn) > 0:
                    precision = tp / (tp + fp)
                    recall = tp / (tp + fn)
                    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
                    val_f1_scores.append(f1)

        avg_val_loss = np.mean(val_losses)
        avg_val_f1 = np.mean(val_f1_scores) if val_f1_scores else 0.0

        history['val_loss'].append(avg_val_loss)
        history['val_f1'].append(avg_val_f1)

        print(f"\nEpoch {epoch + 1} Results:")
        print(f"  Train Loss: {avg_train_loss:.4f}")
        print(f"  Val Loss:   {avg_val_loss:.4f}")
        print(f"  Val F1:     {avg_val_f1:.4f}")

        # Learning rate scheduler
        scheduler.step(avg_val_loss)

        # Save best checkpoint
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            checkpoint_path = output_dir / "bilstm_best.pt"
            torch.save(model.state_dict(), checkpoint_path)
            print(f"  ✓ Saved best checkpoint: {checkpoint_path.name}")

        # Save regular checkpoint
        if (epoch + 1) % 10 == 0:
            checkpoint_path = output_dir / f"bilstm_epoch_{epoch+1}.pt"
            torch.save(model.state_dict(), checkpoint_path)
            print(f"  ✓ Saved checkpoint: {checkpoint_path.name}")

    # Save final checkpoint
    final_checkpoint = output_dir / "bilstm_final.pt"
    torch.save(model.state_dict(), final_checkpoint)

    # Save training history
    history_path = output_dir / "training_history.json"
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)

    print(f"\n{'=' * 70}")
    print("Training Complete!")
    print(f"{'=' * 70}")
    print(f"Best validation loss: {best_val_loss:.4f}")
    print(f"Best checkpoint: {output_dir / 'bilstm_best.pt'}")
    print(f"Training history: {history_path}")
    print(f"{'=' * 70}\n")


def main():
    """CLI for BiLSTM training."""
    parser = argparse.ArgumentParser(description="Train BiLSTM refinement model")

    parser.add_argument(
        '--train-dir',
        type=str,
        required=True,
        help='Directory with training .npz files'
    )

    parser.add_argument(
        '--val-dir',
        type=str,
        required=True,
        help='Directory with validation .npz files'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='backend/refinement/checkpoints',
        help='Output directory for checkpoints'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=16,
        help='Training batch size'
    )

    parser.add_argument(
        '--lr',
        type=float,
        default=1e-3,
        help='Learning rate'
    )

    parser.add_argument(
        '--epochs',
        type=int,
        default=50,
        help='Number of training epochs'
    )

    parser.add_argument(
        '--device',
        type=str,
        default='cuda',
        choices=['cuda', 'mps', 'cpu'],
        help='Device to train on'
    )

    args = parser.parse_args()

    # Auto-detect device if CUDA not available
    if args.device == 'cuda' and not torch.cuda.is_available():
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            args.device = 'mps'
        else:
            args.device = 'cpu'
        print(f"CUDA not available, using {args.device}")

    train_bilstm(
        train_dir=Path(args.train_dir),
        val_dir=Path(args.val_dir),
        output_dir=Path(args.output_dir),
        batch_size=args.batch_size,
        lr=args.lr,
        epochs=args.epochs,
        device=args.device
    )


if __name__ == "__main__":
    main()
