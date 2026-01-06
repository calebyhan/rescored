# Evaluation Framework

Comprehensive evaluation framework for measuring transcription accuracy improvements.

## Overview

The evaluation framework provides:
- ✅ **Metrics calculation** using mir_eval (standard MIR library)
- ✅ **Benchmark dataset loaders** (MAESTRO, custom datasets)
- ✅ **Model comparison** across multiple configurations
- ✅ **Results tracking** with JSON export

## Quick Start

### 1. Install Dependencies

```bash
pip install mir_eval
```

### 2. Download MAESTRO Dataset (Optional)

For comprehensive evaluation, download the MAESTRO dataset:

```bash
# Download MAESTRO v3.0.0 (~200GB)
wget https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0.zip
unzip maestro-v3.0.0.zip -d data/
```

### 3. Run Quick Test

Test on a small subset (no MAESTRO required):

```python
from backend.evaluation.metrics_calculator import MirEvalMetrics

# Test metrics calculator
calculator = MirEvalMetrics(onset_tolerance=0.05)  # 50ms tolerance
metrics = calculator.compute(prediction_midi, ground_truth_midi)

print(f"F1 Score: {metrics['f1']:.1%}")
print(f"Precision: {metrics['precision']:.1%}")
print(f"Recall: {metrics['recall']:.1%}")
```

### 4. Evaluate Phase 1 Improvements

Compare baseline vs Phase 1.1 vs Phase 1.2:

```bash
# Evaluate on 10 MAESTRO test examples
python -m backend.evaluation.run_evaluation \
    --dataset maestro \
    --max-items 10 \
    --models baseline phase1.1 phase1.2

# Full MAESTRO test split (177 examples, ~2-3 hours)
python -m backend.evaluation.run_evaluation \
    --dataset maestro \
    --split test \
    --models all
```

## Modules

### 1. `metrics_calculator.py`

Computes standard transcription metrics using mir_eval.

**Features**:
- Note-level metrics (onset F1, precision, recall)
- Offset metrics (onset + offset matching)
- Frame-level metrics (continuous evaluation)
- Configurable tolerances

**Example**:
```python
from backend.evaluation.metrics_calculator import MirEvalMetrics, print_metrics_summary

calculator = MirEvalMetrics(onset_tolerance=0.05)
metrics = calculator.compute(prediction, ground_truth)
print_metrics_summary(metrics, "My Model")
```

**Output**:
```
============================================================
My Model
============================================================

Primary Metrics (Onset-only, tolerance=50ms):
  Precision: 92.5%
  Recall:    91.2%
  F1 Score:  91.8%  ⭐

Secondary Metrics (Onset + Offset):
  Precision: 89.1%
  Recall:    87.9%
  F1 Score:  88.5%

Counts:
  Ground Truth Notes: 1250
  Predicted Notes:    1280
  True Positives:     1184
  False Positives:    96
  False Negatives:    66
============================================================
```

---

### 2. `benchmark_datasets.py`

Loads benchmark datasets (MAESTRO, custom).

**MAESTRO Dataset**:
```python
from backend.evaluation.benchmark_datasets import MAESTRODataset

dataset = MAESTRODataset(maestro_root=Path("data/maestro-v3.0.0"))

# Get test split
test_pairs = dataset.get_split('test')  # 177 examples
print(f"Test split: {len(test_pairs)} audio/MIDI pairs")

# Get small subset for quick testing
quick_test = dataset.get_test_subset(n=10)
```

**Custom Benchmark**:
```python
from backend.evaluation.benchmark_datasets import CustomBenchmark

# Directory structure:
# benchmark_root/
#   audio/
#     song1.wav
#     song2.wav
#   ground_truth/
#     song1.mid
#     song2.mid

dataset = CustomBenchmark(benchmark_root=Path("data/my_benchmark"))
pairs = dataset.get_all()
```

---

### 3. `evaluator.py`

Main evaluation orchestrator - runs transcription and computes metrics.

**Single Model Evaluation**:
```python
from backend.evaluation.evaluator import TranscriptionEvaluator

# Initialize evaluator
evaluator = TranscriptionEvaluator(
    dataset='maestro',
    split='test',
    max_items=10  # Quick test
)

# Define transcriber function
def my_transcriber(audio_path, output_dir):
    # Your transcription code here
    midi_path = transcribe(audio_path)
    return midi_path

# Evaluate
results = evaluator.evaluate_model(
    my_transcriber,
    model_name="my_model"
)

# Print summary
evaluator.print_summary(results)
```

**Model Comparison**:
```python
# Compare multiple models
models = {
    'baseline': baseline_transcriber,
    'phase1.1': phase1_1_transcriber,
    'phase1.2': phase1_2_transcriber
}

all_results = evaluator.compare_models(models)

# Prints comparison table:
# Model                          F1 Score        Precision    Recall       Success
# --------------------------------------------------------------------------------
# phase1.2_confidence_tta        94.2% ± 2.1%     95.1%        93.3%          10/10
# phase1.1_confidence            92.8% ± 2.3%     93.5%        92.1%          10/10
# baseline                       90.5% ± 2.8%     91.2%        89.8%          10/10
```

---

### 4. `run_evaluation.py`

Convenient CLI script for running Phase 1 evaluations.

**Usage**:
```bash
# Quick test (10 examples)
python -m backend.evaluation.run_evaluation \
    --dataset maestro \
    --max-items 10 \
    --models baseline phase1.1 phase1.2

# Full test split
python -m backend.evaluation.run_evaluation \
    --dataset maestro \
    --split test \
    --models all

# Custom dataset
python -m backend.evaluation.run_evaluation \
    --dataset custom \
    --dataset-root /path/to/my/benchmark \
    --models all
```

**Options**:
- `--dataset`: `maestro` or `custom`
- `--dataset-root`: Path to dataset (auto-detected for MAESTRO)
- `--split`: `train`, `validation`, or `test` (for MAESTRO)
- `--max-items`: Limit evaluation to N items (for quick testing)
- `--models`: Which models to evaluate (`baseline`, `phase1.1`, `phase1.2`, `all`)
- `--output-dir`: Where to save results (default: `/tmp/rescored_evaluation`)

---

## Metrics Explained

### Primary Metrics (Onset-only)

**Precision**: Of all predicted notes, what % are correct?
- High precision = few false positives
- Formula: `TP / (TP + FP)`

**Recall**: Of all ground truth notes, what % were predicted?
- High recall = few false negatives
- Formula: `TP / (TP + FN)`

**F1 Score**: Harmonic mean of precision and recall
- **Primary metric for evaluation**
- Balances precision and recall
- Formula: `2 × (P × R) / (P + R)`

### Tolerances

**Onset Tolerance**: Time window for matching note onsets (default: 50ms)
- Predicted onset within ±50ms of ground truth = match
- Standard in MIR literature

**Offset Tolerance**: Additional requirement for offset matching
- Used for "onset + offset" metrics
- Default: Within 20% of note duration

### Why These Metrics?

- **Standard**: Used across MIR research for reproducibility
- **mir_eval**: Reference implementation ensures consistency
- **Comprehensive**: Captures both precision (false positives) and recall (false negatives)

---

## Evaluation Workflow

### Step 1: Download MAESTRO (One-time)

```bash
# Download MAESTRO v3.0.0
wget https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0.zip
unzip maestro-v3.0.0.zip -d data/
```

### Step 2: Quick Test (10 examples, ~5 minutes)

```bash
python -m backend.evaluation.run_evaluation \
    --dataset maestro \
    --max-items 10 \
    --models baseline phase1.1
```

### Step 3: Full Evaluation (~2-3 hours for 177 examples)

```bash
python -m backend.evaluation.run_evaluation \
    --dataset maestro \
    --split test \
    --models all \
    --output-dir results/phase1_evaluation
```

### Step 4: Analyze Results

Results saved to `results/phase1_evaluation/results/*.json`

```python
import json

with open('results/phase1_evaluation/results/phase1.1_confidence_results.json') as f:
    results = json.load(f)

# Get mean F1
f1_scores = [r['metrics']['f1'] for r in results['results'] if 'f1' in r['metrics']]
mean_f1 = np.mean(f1_scores)
print(f"Mean F1: {mean_f1:.1%}")
```

---

## Expected Results

Based on Phase 1 implementation:

| Configuration | Expected F1 | Description |
|---------------|-------------|-------------|
| **Baseline** | 90-95% | Ensemble (YourMT3+ + ByteDance) with fixed weights |
| **Phase 1.1** | 91-96% | + Enhanced confidence filtering (+1-2%) |
| **Phase 1.2** | 92-97% | + Test-Time Augmentation (+2-3%) |

**Note**: TTA (Phase 1.2) is 5x slower - optional quality mode

---

## Troubleshooting

### Error: mir_eval not installed

```bash
pip install mir_eval
```

### Error: MAESTRO dataset not found

Download MAESTRO:
```bash
wget https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0.zip
unzip maestro-v3.0.0.zip -d data/
```

Or specify path:
```bash
python -m backend.evaluation.run_evaluation \
    --dataset-root /path/to/maestro-v3.0.0
```

### Error: Out of memory

Reduce batch size or use smaller subset:
```bash
python -m backend.evaluation.run_evaluation --max-items 5
```

### Evaluation too slow

Use smaller subset for quick testing:
```bash
# Test on 10 examples instead of full 177
--max-items 10
```

Or disable TTA:
```bash
# Only test baseline and Phase 1.1 (skip slow TTA)
--models baseline phase1.1
```

---

## Development

### Running Tests

```bash
# Test metrics calculator
python backend/evaluation/metrics_calculator.py

# Test dataset loaders
python backend/evaluation/benchmark_datasets.py

# Test evaluator
python backend/evaluation/evaluator.py
```

### Adding New Metrics

Edit `metrics_calculator.py`:

```python
def compute(self, prediction_midi, ground_truth_midi):
    # ... existing metrics ...

    # Add custom metric
    custom_metric = compute_my_metric(pred_pitches, gt_pitches)

    return {
        # ... existing metrics ...
        'my_custom_metric': custom_metric
    }
```

### Adding New Datasets

Edit `benchmark_datasets.py`:

```python
class MyCustomDataset:
    def __init__(self, root):
        self.root = root
        self.pairs = self._load_pairs()

    def _load_pairs(self):
        # Load audio/MIDI pairs
        return pairs

    def get_all(self):
        return self.pairs
```

---

## References

- **mir_eval**: https://craffel.github.io/mir_eval/
- **MAESTRO Dataset**: https://magenta.tensorflow.org/datasets/maestro
- **Transcription Evaluation**: Bay et al. (2009) "Evaluation of Multiple-F0 Estimation and Tracking Systems"

---

## Next Steps

1. **Run quick evaluation** (10 examples) to verify setup
2. **Run full evaluation** on MAESTRO test split
3. **Analyze results** to confirm Phase 1 improvements
4. **Proceed to Phase 2** (D3RM integration) or Phase 1.3 (BiLSTM) based on results

---

## SLURM Scripts (for Longleaf Cluster)

For running on UNC's Longleaf cluster, use the provided SLURM scripts:

### Quick Evaluation (Recommended)
```bash
# On Longleaf cluster
cd /work/users/c/a/calebhan/rescored/rescored
sbatch backend/evaluation/evaluate_phase1.sh

# Monitor job
squeue -u calebhan
tail -f logs/slurm/phase1_eval_*.log
```

**Runtime**: ~2-3 hours for 177 test examples
**Models**: Baseline + Phase 1.1 (confidence filtering)

### Full Evaluation with TTA
```bash
# ⚠️ WARNING: 15-20 hours runtime!
sbatch backend/evaluation/evaluate_phase1_with_tta.sh
```

**Runtime**: ~15-20 hours
**Models**: Baseline + Phase 1.1 + Phase 1.2 (TTA)

See [SLURM_README.md](SLURM_README.md) for detailed instructions.

---

## Summary

The evaluation framework is **ready to use**:
- ✅ Metrics calculator tested and working
- ✅ Dataset loaders tested
- ✅ Evaluator tested
- ✅ CLI script ready
- ✅ SLURM scripts for Longleaf cluster

**Local testing**:
```bash
python -m backend.evaluation.run_evaluation --max-items 10 --models baseline phase1.1
```

**Longleaf cluster**:
```bash
sbatch backend/evaluation/evaluate_phase1.sh
```
