# Evaluation Scripts for Longleaf Cluster

SLURM scripts for running Phase 1 evaluation on UNC's Longleaf cluster with MAESTRO dataset.

## Scripts

### 1. `evaluate_phase1.sh` (Recommended)
**Purpose**: Evaluate baseline + Phase 1.1 (confidence filtering)
**Runtime**: ~2-3 hours for 177 test examples
**Resources**: 1 GPU, 8 CPUs, 32GB RAM

Compares:
- Baseline: Ensemble without confidence filtering
- Phase 1.1: Ensemble with confidence filtering (+1-2% F1)

**Usage**:
```bash
# From /work/users/c/a/calebhan/rescored/rescored
sbatch scripts/evaluate_phase1.sh

# Check status
squeue -u calebhan

# Monitor output
tail -f logs/slurm/phase1_eval_*.log
```

---

### 2. `evaluate_phase1_with_tta.sh` (Slow!)
**Purpose**: Full evaluation including TTA (Test-Time Augmentation)
**Runtime**: ~15-20 hours for 177 test examples
**Resources**: 1 GPU, 8 CPUs, 64GB RAM

⚠️ **WARNING**: TTA is 5x slower! Only use if you need maximum accuracy.

Compares:
- Baseline: 90-95% F1
- Phase 1.1: 91-96% F1 (+1-2%)
- Phase 1.2 (+ TTA): 92-97% F1 (+2-3%)

**Usage**:
```bash
sbatch scripts/evaluate_phase1_with_tta.sh
```

---

## Quick Start

### 1. Setup (One-time)

```bash
# Navigate to project on Longleaf
cd /work/users/c/a/calebhan/rescored/rescored

# Verify MAESTRO dataset is present
ls -la ../data/maestro-v3.0.0/

# Verify scripts are executable
chmod +x scripts/*.sh

# Create log directories
mkdir -p logs/slurm
```

### 2. Run Quick Test (10 examples, ~10 min)

Edit `evaluate_phase1.sh` and change:
```bash
EVAL_MODE="quick"  # Instead of "test"
MAX_ITEMS=10
```

Then submit:
```bash
sbatch scripts/evaluate_phase1.sh
```

### 3. Run Full Evaluation

Use default settings:
```bash
sbatch scripts/evaluate_phase1.sh
```

### 4. Monitor Job

```bash
# Check job status
squeue -u calebhan

# View live output
tail -f logs/slurm/phase1_eval_<JOB_ID>.log

# View errors
tail -f logs/slurm/phase1_eval_<JOB_ID>.err

# Cancel job if needed
scancel <JOB_ID>
```

---

## Configuration Options

Edit the script to customize:

### Evaluation Mode
```bash
# Quick test (10 examples)
EVAL_MODE="quick"
MAX_ITEMS=10

# Full test split (177 examples)
EVAL_MODE="test"
```

### Models to Evaluate
```bash
# Only baseline
MODELS="baseline"

# Baseline + Phase 1.1 (recommended)
MODELS="baseline phase1.1"

# All models including TTA (very slow!)
MODELS="all"
```

### Resource Requirements
```bash
# For standard evaluation
#SBATCH --time=2-00:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=8

# For TTA evaluation (slower)
#SBATCH --time=5-00:00:00
#SBATCH --mem=64G
#SBATCH --cpus-per-task=8
```

---

## Expected Results

### Baseline (90-95% F1)
- Ensemble: YourMT3+ (40%) + ByteDance (60%)
- Fixed model weights
- No confidence filtering

### Phase 1.1 (+1-2% F1)
- Enhanced confidence filtering
- ByteDance frame-level confidence scores used
- Low-confidence notes downweighted

### Phase 1.2 (+2-3% F1)
- All Phase 1.1 improvements
- Test-Time Augmentation (5 augmentations)
- 5x slower processing time

**Example Output**:
```
============================================================
MODEL COMPARISON
============================================================

Model                          F1 Score        Precision    Recall       Success
--------------------------------------------------------------------------------
phase1.1_confidence            93.2% ± 2.1%     94.1%        92.4%         177/177
baseline                       91.5% ± 2.3%     92.3%        90.7%         177/177
--------------------------------------------------------------------------------

Improvement over baseline:
  phase1.1_confidence: +1.7% (91.5% → 93.2%)
```

---

## Output Files

Results saved to: `backend/evaluation/results/`

```
results/
├── baseline_results.json
├── phase1.1_confidence_results.json
├── phase1.2_confidence_tta_results.json  (if TTA enabled)
└── yourmt3_midi/  (predicted MIDI files)
```

### Results JSON Format

```json
{
  "metadata": {
    "dataset": "maestro",
    "split": "test",
    "onset_tolerance": 0.05,
    "timestamp": "2025-01-06T12:00:00",
    "n_items": 177
  },
  "results": [
    {
      "audio_filename": "test_audio.wav",
      "model_name": "phase1.1_confidence",
      "metrics": {
        "f1": 0.932,
        "precision": 0.941,
        "recall": 0.924,
        "n_predicted": 1250,
        "n_ground_truth": 1280
      },
      "duration_seconds": 45.2,
      "error": null
    }
  ]
}
```

---

## Troubleshooting

### Job fails with "MAESTRO not found"

Verify dataset location:
```bash
ls -la /work/users/c/a/calebhan/rescored/data/maestro-v3.0.0/
```

If missing, download:
```bash
cd /work/users/c/a/calebhan/rescored/data
wget https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0.zip
unzip maestro-v3.0.0.zip
```

### Out of memory error

Reduce memory usage:
```bash
# Use smaller subset
EVAL_MODE="quick"
MAX_ITEMS=5

# Or increase RAM allocation
#SBATCH --mem=64G
```

### GPU not available

Check GPU availability:
```bash
sinfo -p gpu
```

Or use CPU-only mode (slower):
```bash
#SBATCH --partition=general
# Remove: #SBATCH --gres=gpu:1
```

### Dependencies missing

Install requirements:
```bash
source venv/bin/activate
pip install -r requirements.txt
pip install mir_eval
```

---

## Performance Tips

### 1. Use Quick Mode for Testing

Always test with `EVAL_MODE="quick"` first to verify everything works:
```bash
EVAL_MODE="quick"
MAX_ITEMS=5
```

### 2. Exclude TTA for Faster Results

TTA is 5x slower. Only use if needed:
```bash
# Fast (2-3 hours)
MODELS="baseline phase1.1"

# Slow (15-20 hours)
MODELS="all"  # Includes TTA
```

### 3. Monitor GPU Usage

Check if GPU is being utilized:
```bash
# In job output
nvidia-smi

# Or SSH to compute node
ssh <compute-node>
watch -n 1 nvidia-smi
```

---

## Email Notifications

Scripts are configured to send email when job completes or fails:

```bash
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=calebhan@unc.edu
```

You'll receive emails with:
- Job completion status
- Runtime duration
- Links to output logs

---

## Next Steps After Evaluation

1. **Download results** from Longleaf:
```bash
# On local machine
scp -r calebhan@longleaf.unc.edu:/work/users/c/a/calebhan/rescored/rescored/backend/evaluation/results ./
```

2. **Analyze results**:
```python
import json
import numpy as np

with open('results/phase1.1_confidence_results.json') as f:
    data = json.load(f)

f1_scores = [r['metrics']['f1'] for r in data['results'] if 'f1' in r['metrics']]
print(f"Mean F1: {np.mean(f1_scores):.1%}")
print(f"Std dev: {np.std(f1_scores):.1%}")
```

3. **Decide next phase**:
- If Phase 1.1 shows +1-2% improvement → Proceed to Phase 1.3 (BiLSTM) or Phase 2 (D3RM)
- If results are lower than expected → Investigate issues, tune hyperparameters

---

## Cluster Resources

**Longleaf GPU partitions**:
- `gpu`: General GPU access (V100, A100)
- `gpu-volta`: V100 GPUs specifically
- `gpu-a100`: A100 GPUs (faster, if available)

**Recommended GPU**:
- **A100**: Best performance (~2x faster than V100)
- **V100**: Good performance, more availability

To request specific GPU:
```bash
#SBATCH --gres=gpu:a100:1  # Request A100
#SBATCH --gres=gpu:v100:1  # Request V100
```

---

## Summary

### Quick Test (Recommended First)
```bash
# Edit evaluate_phase1.sh: EVAL_MODE="quick"
sbatch scripts/evaluate_phase1.sh
# Runtime: ~10 minutes
```

### Standard Evaluation (Production)
```bash
sbatch scripts/evaluate_phase1.sh
# Runtime: ~2-3 hours
# Models: baseline + phase1.1
```

### Full Evaluation with TTA (Only if needed)
```bash
sbatch scripts/evaluate_phase1_with_tta.sh
# Runtime: ~15-20 hours
# Models: baseline + phase1.1 + phase1.2 (TTA)
```

---

## Questions?

Check logs:
- Job output: `logs/slurm/phase1_eval_<JOB_ID>.log`
- Job errors: `logs/slurm/phase1_eval_<JOB_ID>.err`

Common issues:
1. MAESTRO not found → Verify dataset path
2. Out of memory → Increase `--mem` or reduce `MAX_ITEMS`
3. GPU not available → Check `sinfo -p gpu` or use `--partition=general`
