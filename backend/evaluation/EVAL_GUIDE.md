# Phase 1 Evaluation Guide

This guide explains how to run the Phase 1 evaluation on the MAESTRO dataset.

## Quick Start

### Local Testing (10 examples, ~30 minutes)
```bash
python -m backend.evaluation.run_evaluation \
    --dataset maestro \
    --split test \
    --max-items 10 \
    --models baseline phase1.3 phase1.3c \
    --output-dir backend/evaluation/results
```

### SLURM Cluster (Full evaluation, ~2-15 hours)
```bash
# Edit evaluate_phase1.sh to configure:
# - EVAL_MODE: "quick" (10 examples) or "test" (177 examples)
# - MODELS: Space-separated list of models to test

# Submit job
sbatch backend/evaluation/evaluate_phase1.sh

# Check job status
squeue -u $USER

# Monitor logs (replace JOBID with actual job ID)
tail -f /work/users/c/a/calebhan/rescored/logs/slurm/phase1_eval_JOBID.log
tail -f /work/users/c/a/calebhan/rescored/logs/slurm/phase1_eval_JOBID.err
```

## Available Models

| Model | Description | F1 Score | Notes |
|-------|-------------|----------|-------|
| **baseline** | Ensemble only (no confidence, no BiLSTM) | 93.1% | Baseline for comparison |
| **phase1.1** | Ensemble + confidence filtering | 93.6% | +0.5% improvement |
| **phase1.2** | Ensemble + confidence + TTA | 81.0% | ❌ TTA broken (slow, unreliable) |
| **phase1.3** | Ensemble + confidence + BiLSTM | **96.1%** | ✅ Best overall (current) |
| **phase1.3b** | YourMT3+ + BiLSTM | 96.0% | Simpler pipeline, same accuracy |
| **phase1.3c** | ByteDance + BiLSTM | **??.?%** | 🔬 Testing now - may be best! |
| **phase1.4** | Full pipeline (confidence + TTA + BiLSTM) | N/A | ❌ Very slow, TTA broken |
| **all** | All models (baseline + phase1.1 + phase1.2 + phase1.3 + phase1.3b + phase1.3c + phase1.4) | N/A | Full comparison |

## Configuration Options

### Model Selection Examples

**Test single model:**
```bash
MODELS="phase1.3c"
```

**Compare BiLSTM configurations:**
```bash
MODELS="phase1.3 phase1.3b phase1.3c"
```

**Full comparison:**
```bash
MODELS="all"
```

**Skip slow models:**
```bash
MODELS="baseline phase1.1 phase1.3 phase1.3b phase1.3c"
```

### Evaluation Modes

**Quick mode (10 examples, ~30 min):**
```bash
EVAL_MODE="quick"
MAX_ITEMS=10
```

**Full mode (177 examples, 2-15 hours):**
```bash
EVAL_MODE="test"
# MAX_ITEMS is ignored
```

## Resource Requirements

### Quick Mode (10 examples)
- **Time**: ~30 minutes
- **GPU**: 1x A100/L40 (8GB VRAM minimum)
- **RAM**: 16GB
- **CPUs**: 4-8

### Full Mode (177 examples)
- **Time**:
  - Without TTA: ~2-4 hours
  - With TTA: ~10-15 hours (5x slower)
- **GPU**: 1x A100/L40 (8GB VRAM minimum)
- **RAM**: 32GB
- **CPUs**: 8
- **Storage**: ~20GB for intermediate files

## SLURM Configuration

Edit `evaluate_phase1.sh` SLURM directives:

```bash
#SBATCH --job-name=phase1_eval
#SBATCH --time=2-00:00:00              # 2 days max
#SBATCH --cpus-per-task=8              # 8 CPUs
#SBATCH --mem=32G                      # 32GB RAM
#SBATCH --partition=l40-gpu            # GPU partition
#SBATCH --qos=gpu_access               # QoS
#SBATCH --gres=gpu:1                   # 1 GPU
```

## Output Files

Results are saved to `backend/evaluation/results/`:

```
results/
├── baseline/
│   └── [audio_files]/                  # Transcription outputs
├── phase1.1_confidence/
│   └── [audio_files]/
├── phase1.3_confidence_bilstm/
│   └── [audio_files]/
├── phase1.3b_bilstm_only/
│   └── [audio_files]/
├── phase1.3c_bytedance_bilstm/        # NEW!
│   └── [audio_files]/
└── results/
    ├── baseline_results.json
    ├── phase1.1_confidence_results.json
    ├── phase1.3_confidence_bilstm_results.json
    ├── phase1.3b_bilstm_only_results.json
    ├── phase1.3c_bytedance_bilstm_results.json  # NEW!
    └── comparison.json                 # Summary comparison
```

## Interpreting Results

Each model's JSON file contains:
- `f1_score`: Overall F1 score (0-100%)
- `precision`: Precision (0-100%)
- `recall`: Recall (0-100%)
- `per_file_scores`: Individual file results
- `failed_files`: List of failed transcriptions

### Reading the comparison
```bash
# View summary
cat backend/evaluation/results/results/comparison.json

# View specific model results
cat backend/evaluation/results/results/phase1.3c_bytedance_bilstm_results.json
```

## Common Issues

### BiLSTM cuDNN Error (15% failure rate)
**Error**: `cuDNN error: CUDNN_STATUS_NOT_SUPPORTED`
**Status**: ✅ Fixed in latest code (added `.contiguous()` call)
**Impact**: Should now have 100% success rate instead of 85%

### GPU Out of Memory
**Error**: `CUDA out of memory`
**Fix**:
- Reduce batch size (not applicable for eval)
- Use smaller model
- Request GPU with more VRAM

### TTA Very Slow
**Issue**: TTA takes 5x longer than baseline
**Fix**: Don't use TTA (proven ineffective anyway, -12.6% F1)

## Tips

1. **Start with quick mode** to verify everything works before full evaluation
2. **Skip TTA models** (phase1.2, phase1.4) - they're broken and slow
3. **Test Phase 1.3c first** - it might be the best configuration!
4. **Monitor GPU usage** with `watch -n 1 nvidia-smi` during evaluation
5. **Check logs regularly** for errors or warnings

## Example Workflows

### Test new cuDNN fix
```bash
# Quick test to verify BiLSTM doesn't fail
EVAL_MODE="quick"
MAX_ITEMS=10
MODELS="phase1.3 phase1.3b phase1.3c"
```

### Compare all BiLSTM variants
```bash
# Full evaluation of all BiLSTM configurations
EVAL_MODE="test"
MODELS="phase1.3 phase1.3b phase1.3c"
```

### Full benchmark
```bash
# Everything except broken TTA models
EVAL_MODE="test"
MODELS="baseline phase1.1 phase1.3 phase1.3b phase1.3c"
```

## Next Steps After Evaluation

1. **Review results** in `results/results/comparison.json`
2. **Update README.md** with new Phase 1.3c results
3. **If Phase 1.3c is best**, update production recommendation
4. **If cuDNN fix works**, consider retraining BiLSTM with more epochs (50 → 100)
