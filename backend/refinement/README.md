# BiLSTM Refinement Training

Post-transcription refinement using Bidirectional LSTM to correct ensemble errors.

## Overview

The BiLSTM refiner improves transcription accuracy by:
- **Correcting isolated errors**: Removing spurious notes that don't fit musical context
- **Fixing timing errors**: Adjusting onset/offset misalignments
- **Smoothing sequences**: Using temporal context from surrounding notes

**Expected improvement**: +1-2% F1
**Training time**: 8-12 hours on single GPU
**Model size**: ~13 MB

---

## Quick Start (Longleaf Cluster)

### Step 1: Prepare Training Data (One-time, ~1-2 days)

```bash
# SSH to Longleaf
ssh calebhan@longleaf.unc.edu
cd /work/users/c/a/calebhan/rescored/rescored

# Submit dataset preparation job
sbatch backend/refinement/training/prepare_dataset.sh

# Monitor progress
squeue -u calebhan
tail -f logs/slurm/bilstm_prep_*.log
```

This generates ensemble predictions for MAESTRO:
- Train split: ~960 examples (~1-2 days)
- Validation split: ~137 examples (~3-4 hours)

Output: `/work/users/c/a/calebhan/rescored/data/bilstm_training/`

### Step 2: Train BiLSTM Model (~8-12 hours)

```bash
# Submit training job (after dataset prep completes)
sbatch backend/refinement/training/train_bilstm.sh

# Monitor progress
tail -f logs/slurm/bilstm_train_*.log
```

Output: `backend/refinement/checkpoints/bilstm_best.pt`

### Step 3: Enable BiLSTM in Config

```python
# backend/app_config.py
enable_bilstm_refinement: bool = True
```

### Step 4: Evaluate Improvement

Run evaluation to measure accuracy gain:
```bash
sbatch backend/evaluation/evaluate_phase1.sh
```

---

## Architecture

```
Input: Piano roll (time × 88 keys) from ensemble
  ↓
BiLSTM: 2 layers, 256 hidden units, bidirectional
  ↓
Self-Attention: 4-head multi-head attention
  ↓
Output: Refined piano roll (corrected onset probabilities)
```

**Model Parameters**: 3.49M
**Checkpoint Size**: ~13 MB

---

## Training Details

### Dataset Format

Training data format (.npz files):
```python
{
    'ensemble_roll': np.ndarray,      # (time, 88) ensemble prediction
    'ground_truth_roll': np.ndarray,  # (time, 88) ground truth
    'audio_filename': str,
    'duration': float
}
```

### Loss Function

Combined loss:
```python
loss = BCE(pred, target) + 0.5 * F1_loss(pred, target)
```

- **BCE**: Binary cross-entropy for pixel-wise accuracy
- **F1 loss**: Differentiable F1 to optimize metric directly

### Training Configuration

```python
batch_size = 16
learning_rate = 1e-3
epochs = 50
optimizer = Adam
scheduler = ReduceLROnPlateau(patience=5, factor=0.5)
```

### Training Pipeline

1. Load preprocessed .npz files
2. Chunk sequences to max_length=10000 frames (~100s)
3. Train with combined loss
4. Validate every epoch
5. Save best checkpoint (lowest val loss)

---

## Files

### Core Implementation
- `bilstm_refiner.py` - Model architecture and inference pipeline
- `training/dataset_builder.py` - Generate training data from MAESTRO
- `training/train_bilstm.py` - Training script

### SLURM Scripts (Longleaf)
- `training/prepare_dataset.sh` - Dataset preparation job
- `training/train_bilstm.sh` - Training job

### Outputs
- `checkpoints/bilstm_best.pt` - Best model checkpoint
- `checkpoints/bilstm_final.pt` - Final epoch checkpoint
- `checkpoints/training_history.json` - Training curves

---

## Local Testing (CPU/Local GPU)

### Prepare Small Dataset

```bash
# Quick test with 10 examples
python -m backend.refinement.training.dataset_builder \
    --maestro-root data/maestro-v3.0.0 \
    --output-dir data/bilstm_training_test/train \
    --split train \
    --max-items 10

python -m backend.refinement.training.dataset_builder \
    --maestro-root data/maestro-v3.0.0 \
    --output-dir data/bilstm_training_test/validation \
    --split validation \
    --max-items 5
```

### Train Model

```bash
python -m backend.refinement.training.train_bilstm \
    --train-dir data/bilstm_training_test/train \
    --val-dir data/bilstm_training_test/validation \
    --output-dir backend/refinement/checkpoints \
    --batch-size 8 \
    --epochs 10 \
    --device cuda  # or mps, cpu
```

---

## Usage

### Python API

```python
from backend.refinement.bilstm_refiner import BiLSTMRefinementPipeline
from pathlib import Path

# Initialize refiner
refiner = BiLSTMRefinementPipeline(
    checkpoint_path=Path("backend/refinement/checkpoints/bilstm_best.pt"),
    device='cuda',
    fps=100
)

# Refine MIDI file
ensemble_midi = Path("output/ensemble.mid")
refined_midi = refiner.refine_midi(
    ensemble_midi,
    output_dir=Path("output/"),
    threshold=0.5
)

print(f"Refined MIDI: {refined_midi}")
```

### CLI (via Pipeline)

```python
# Enable in app_config.py
enable_bilstm_refinement = True
bilstm_checkpoint_path = Path("backend/refinement/checkpoints/bilstm_best.pt")

# Run pipeline (BiLSTM applied automatically after ensemble)
from backend.pipeline import TranscriptionPipeline

pipeline = TranscriptionPipeline(...)
midi_path = pipeline.run(youtube_url="...")
```

---

## Monitoring Training

### Check Progress

```bash
# On Longleaf
tail -f logs/slurm/bilstm_train_*.log
```

### Training Metrics

Training script outputs:
```
Epoch 1/50:
  Train Loss: 0.2453
  Val Loss:   0.2178
  Val F1:     0.9124
  ✓ Saved best checkpoint
```

### View Training History

```python
import json

with open('backend/refinement/checkpoints/training_history.json') as f:
    history = json.load(f)

# Plot training curves
import matplotlib.pyplot as plt

plt.plot(history['train_loss'], label='Train Loss')
plt.plot(history['val_loss'], label='Val Loss')
plt.legend()
plt.show()
```

---

## Troubleshooting

### Dataset Preparation Fails

**Error**: `MAESTRO dataset not found`

**Solution**:
```bash
# Verify MAESTRO location
ls -la /work/users/c/a/calebhan/rescored/data/maestro-v3.0.0/

# Check metadata file exists
ls -la /work/users/c/a/calebhan/rescored/data/maestro-v3.0.0/maestro-v3.0.0.json
```

### Training Fails with OOM

**Error**: `CUDA out of memory`

**Solutions**:
```bash
# Reduce batch size
--batch-size 8  # Instead of 16

# Or reduce max sequence length in dataset_builder.py
max_length = 5000  # Instead of 10000
```

### Checkpoint Not Found

**Error**: `BiLSTM model not loaded`

**Solution**:
```bash
# Verify checkpoint exists
ls -la backend/refinement/checkpoints/bilstm_best.pt

# If missing, train the model first
sbatch backend/refinement/training/train_bilstm.sh
```

### Poor Validation F1

**Issue**: Val F1 < 0.85 after training

**Solutions**:
1. **Train longer**: Increase epochs to 100
2. **Adjust learning rate**: Try 5e-4 or 2e-3
3. **Check data quality**: Verify ensemble predictions are reasonable
4. **Add regularization**: Increase dropout to 0.3

---

## Performance Tuning

### Speed Up Training

1. **Use A100 GPU** (2x faster than V100):
```bash
#SBATCH --gres=gpu:a100:1
```

2. **Increase batch size** (if memory allows):
```bash
--batch-size 32  # Faster training
```

3. **Reduce dataset size** (for testing):
```bash
--max-items 100  # Quick test run
```

### Improve Accuracy

1. **More training data**: Use full MAESTRO train split (960 examples)
2. **Longer training**: 100 epochs instead of 50
3. **Ensemble augmentation**: Generate multiple ensemble predictions per example
4. **Architecture changes**:
   - Increase hidden_dim to 512
   - Add more LSTM layers (3-4)
   - Increase attention heads to 8

---

## Expected Results

### Training Metrics

After 50 epochs on full MAESTRO:
- **Train Loss**: ~0.15-0.20
- **Val Loss**: ~0.18-0.22
- **Val F1**: ~0.90-0.92

### Evaluation Metrics

On MAESTRO test split:
- **Baseline ensemble**: 90-95% F1
- **+ BiLSTM**: 91-96% F1
- **Improvement**: +1-2% F1

### What BiLSTM Fixes

| Error Type | Example | Correction |
|------------|---------|------------|
| Isolated false positive | Single spurious note | Removed |
| Timing error | Onset 10ms early | Adjusted |
| Missing note | Soft note not detected | Added (rare) |
| Rhythm smoothing | Irregular timing | Regularized |

---

## Integration with Phase 1

BiLSTM refiner is the final step in Phase 1 pipeline:

```
Audio
  ↓
Source Separation (BS-RoFormer + Demucs)
  ↓
Ensemble Transcription (YourMT3+ + ByteDance)
  ├─ Phase 1.1: Enhanced Confidence Filtering (+1-2% F1)
  ├─ Phase 1.2: Test-Time Augmentation (+2-3% F1, optional)
  └─ Phase 1.3: BiLSTM Refinement (+1-2% F1)
  ↓
MusicXML Generation
```

**Total Phase 1 improvement**: +3-5% F1 (90-95% → 93-98%)

---

## Next Steps

After completing BiLSTM training:

1. **Evaluate improvement**:
```bash
sbatch backend/evaluation/evaluate_phase1.sh
```

2. **Compare all Phase 1 components**:
   - Baseline (no improvements)
   - + Confidence filtering
   - + TTA
   - + BiLSTM

3. **Decide next phase**:
   - **Phase 2**: D3RM diffusion refinement (+3-4% F1)
   - **Phase 3**: Audio-visual fusion (+5-8% F1, if applicable)

---

## References

- **Architecture**: Bidirectional LSTM + Multi-head Attention
- **Loss**: Combined BCE + F1 loss
- **Dataset**: MAESTRO v3.0.0
- **Training**: 50 epochs, Adam optimizer, ReduceLROnPlateau scheduler

---

## Summary

BiLSTM refinement is **ready to train**:
- ✅ Model architecture implemented
- ✅ Training pipeline complete
- ✅ SLURM scripts for Longleaf
- ✅ Integration with main pipeline
- ✅ Documentation complete

**To start training**:
```bash
# On Longleaf
sbatch backend/refinement/training/prepare_dataset.sh
# Wait ~1-2 days for dataset prep
sbatch backend/refinement/training/train_bilstm.sh
# Wait ~8-12 hours for training
```

Expected outcome: **+1-2% F1 improvement** 🎯
