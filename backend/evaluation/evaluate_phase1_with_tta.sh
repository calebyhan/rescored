#!/bin/bash
#SBATCH --job-name=phase1_tta
#SBATCH --output=/work/users/c/a/calebhan/rescored/logs/slurm/phase1_tta_%j.log
#SBATCH --error=/work/users/c/a/calebhan/rescored/logs/slurm/phase1_tta_%j.err
#SBATCH --time=5-00:00:00              # 5 days for TTA evaluation (very slow!)
#SBATCH --cpus-per-task=8              # 8 CPUs
#SBATCH --mem=64G                      # 64GB RAM (TTA needs more memory)
#SBATCH --partition=l40-gpu                # GPU partition
#SBATCH --qos=gpu_access             # Required QoS
#SBATCH --gres=gpu:1                   # 1 GPU (A100 preferred)


################################################################################
# Phase 1 Evaluation Script WITH TTA (Test-Time Augmentation)
#
# ⚠️  WARNING: TTA is 5x slower than baseline!
# ⚠️  Expected runtime: ~10-15 hours for 177 examples
# ⚠️  Only run this if you need maximum accuracy and have time
#
# This script evaluates all three Phase 1 configurations:
# - Baseline: 90-95% F1
# - Phase 1.1 (Confidence): 91-96% F1 (+1-2%)
# - Phase 1.2 (+ TTA): 92-97% F1 (+2-3%)
#
# Total runtime: ~15-20 hours
################################################################################

set -e
set -u

echo "========================================"
echo "Phase 1 Full Evaluation (WITH TTA)"
echo "========================================"
echo "⚠️  This will take ~15-20 hours!"
echo "Start time: $(date)"
echo "Hostname: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"
echo "========================================"
echo ""

# Cluster paths
WORK_DIR="/work/users/c/a/calebhan/rescored"
MAESTRO_ROOT="$WORK_DIR/data/maestro-v3.0.0"
RESCORED_DIR="$WORK_DIR/rescored"
OUTPUT_DIR="$WORK_DIR/rescored/backend/evaluation/results"

cd "$RESCORED_DIR"

# Load modules
echo "Loading modules..."
module load anaconda
source activate /work/users/c/a/calebhan/rescored/rescored/backend/.venv

# Verify MAESTRO
if [ ! -d "$MAESTRO_ROOT" ]; then
    echo "ERROR: MAESTRO dataset not found at $MAESTRO_ROOT"
    exit 1
fi

export PYTHONPATH="$RESCORED_DIR:$PYTHONPATH"

# GPU info
echo "GPU Information:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
echo ""

################################################################################
# Run Full Evaluation (All Models Including TTA)
################################################################################

echo "========================================"
echo "Starting FULL Evaluation with TTA"
echo "========================================"
echo ""
echo "Models to evaluate:"
echo "  1. Baseline (no confidence, no TTA)"
echo "  2. Phase 1.1 (confidence filtering)"
echo "  3. Phase 1.2 (confidence + TTA) ⚠️  SLOW!"
echo ""
echo "Expected duration: 15-20 hours"
echo "========================================"
echo ""

python -m backend.evaluation.run_evaluation \
    --dataset maestro \
    --dataset-root "$MAESTRO_ROOT" \
    --split test \
    --models all \
    --output-dir "$OUTPUT_DIR"

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "✓ Evaluation Complete!"
    echo "========================================"
    echo "Results saved to: $OUTPUT_DIR"
    echo ""

    # Print summary
    echo "Result files:"
    ls -lh "$OUTPUT_DIR/results/"
    echo ""

    echo "To analyze results:"
    echo "  cd $OUTPUT_DIR/results"
    echo "  python -c 'import json; print(json.load(open(\"baseline_results.json\")))'"
else
    echo "ERROR: Evaluation failed"
    exit 1
fi

echo ""
echo "End time: $(date)"
echo "Duration: $SECONDS seconds ($((SECONDS/3600)) hours)"

deactivate
