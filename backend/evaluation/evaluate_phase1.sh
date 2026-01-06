#!/bin/bash
#SBATCH --job-name=phase1_eval
#SBATCH --output=/work/users/c/a/calebhan/rescored/logs/slurm/phase1_eval_%j.log
#SBATCH --error=/work/users/c/a/calebhan/rescored/logs/slurm/phase1_eval_%j.err
#SBATCH --time=2-00:00:00              # 2 days (should be sufficient for full test split)
#SBATCH --cpus-per-task=8              # 8 CPUs for parallel processing
#SBATCH --mem=32G                      # 32GB RAM for transcription models
#SBATCH --partition=l40-gpu                # GPU partition for faster transcription
#SBATCH --qos=gpu_access             # Required QoS
#SBATCH --gres=gpu:1                   # 1 GPU (A100/V100)

################################################################################
# Phase 1 Evaluation Script
#
# Evaluates Phase 1 improvements (confidence filtering + TTA) on MAESTRO test split
#
# Expected results:
# - Baseline: 90-95% F1
# - Phase 1.1 (Confidence): 91-96% F1 (+1-2%)
# - Phase 1.2 (+ TTA): 92-97% F1 (+2-3%)
#
# Runtime estimates (177 test examples):
# - Baseline: ~2-3 hours
# - Phase 1.1: ~2-3 hours
# - Phase 1.2: ~10-15 hours (5x slower due to TTA)
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Print start time
echo "========================================"
echo "Phase 1 Evaluation - MAESTRO Dataset"
echo "========================================"
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

# Navigate to project directory
cd "$RESCORED_DIR"

# Load required modules
echo "Loading modules..."
module load anaconda
source activate /work/users/c/a/calebhan/.venv

# Verify MAESTRO dataset exists
if [ ! -d "$MAESTRO_ROOT" ]; then
    echo "ERROR: MAESTRO dataset not found at $MAESTRO_ROOT"
    echo "Please download MAESTRO v3.0.0 and place it in $WORK_DIR/data/"
    exit 1
fi

echo ""
echo "MAESTRO dataset found: $MAESTRO_ROOT"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Set Python path
export PYTHONPATH="$RESCORED_DIR:$PYTHONPATH"

# GPU info
echo "GPU Information:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
echo ""

################################################################################
# Evaluation Configuration
################################################################################

# Evaluation mode (choose one):
# - quick: Test on 10 examples (~30 min)
# - test: Full test split (177 examples, ~2-15 hours depending on models)
EVAL_MODE="test"  # Change to "quick" for testing

# Models to evaluate (choose):
# - baseline: No confidence filtering, no TTA
# - phase1.1: With confidence filtering
# - phase1.2: With confidence filtering + TTA (very slow!)
# - all: All three models
MODELS="baseline phase1.1"  # Exclude phase1.2 (TTA) by default due to time

# Maximum items (only used if EVAL_MODE=quick)
MAX_ITEMS=10

echo "Evaluation Configuration:"
echo "  Mode: $EVAL_MODE"
echo "  Models: $MODELS"
if [ "$EVAL_MODE" = "quick" ]; then
    echo "  Max items: $MAX_ITEMS"
fi
echo ""

################################################################################
# Run Evaluation
################################################################################

echo "========================================"
echo "Starting Evaluation"
echo "========================================"
echo ""

if [ "$EVAL_MODE" = "quick" ]; then
    # Quick test (10 examples)
    echo "Running QUICK evaluation ($MAX_ITEMS examples)..."
    python -m backend.evaluation.run_evaluation \
        --dataset maestro \
        --dataset-root "$MAESTRO_ROOT" \
        --split test \
        --max-items $MAX_ITEMS \
        --models $MODELS \
        --output-dir "$OUTPUT_DIR"
else
    # Full test split (177 examples)
    echo "Running FULL evaluation (177 examples)..."
    echo "This will take 2-15 hours depending on models..."
    python -m backend.evaluation.run_evaluation \
        --dataset maestro \
        --dataset-root "$MAESTRO_ROOT" \
        --split test \
        --models $MODELS \
        --output-dir "$OUTPUT_DIR"
fi

# Check exit status
if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "Evaluation Complete!"
    echo "========================================"
    echo "Results saved to: $OUTPUT_DIR"
    echo ""

    # List result files
    echo "Result files:"
    ls -lh "$OUTPUT_DIR/results/"

    echo ""
    echo "To view results, check:"
    echo "  - JSON files: $OUTPUT_DIR/results/*.json"
    echo "  - Log file: logs/slurm/phase1_eval_$SLURM_JOB_ID.log"
else
    echo ""
    echo "========================================"
    echo "Evaluation FAILED"
    echo "========================================"
    echo "Check error log: logs/slurm/phase1_eval_$SLURM_JOB_ID.err"
    exit 1
fi

# Print end time and duration
END_TIME=$(date)
echo ""
echo "========================================"
echo "Job Statistics"
echo "========================================"
echo "End time: $END_TIME"
echo "Duration: $SECONDS seconds"
echo "========================================"

# Deactivate virtual environment
deactivate
