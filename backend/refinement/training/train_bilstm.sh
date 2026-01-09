#!/bin/bash
#SBATCH --job-name=bilstm_train
#SBATCH --output=/work/users/c/a/calebhan/rescored/logs/slurm/bilstm_train_%j.log
#SBATCH --error=/work/users/c/a/calebhan/rescored/logs/slurm/bilstm_train_%j.err
#SBATCH --time=1-00:00:00              # 1 day for training
#SBATCH --cpus-per-task=8              # 8 CPUs
#SBATCH --mem=64G                      # 64GB RAM
#SBATCH --partition=l40-gpu                # GPU partition
#SBATCH --qos=gpu_access             # Required QoS
#SBATCH --gres=gpu:1                   # 1 GPU (A100 preferred)

################################################################################
# BiLSTM Training Script
#
# Trains BiLSTM refinement model on preprocessed MAESTRO dataset.
#
# Prerequisites:
# 1. Dataset preparation completed (run prepare_dataset.sh first)
# 2. Training data available at: /work/users/c/a/calebhan/rescored/data/bilstm_training/
#
# Runtime: ~8-12 hours on A100, ~12-16 hours on V100
# Expected improvement: +1-2% F1
################################################################################

set -e
set -u

echo "========================================"
echo "BiLSTM Refinement Training"
echo "========================================"
echo "Start time: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "========================================"
echo ""

# Paths
WORK_DIR="/work/users/c/a/calebhan/rescored"
DATA_DIR="$WORK_DIR/data/bilstm_training"
RESCORED_DIR="$WORK_DIR/rescored"
OUTPUT_DIR="$RESCORED_DIR/backend/refinement/checkpoints"

cd "$RESCORED_DIR"

# Verify dataset exists
if [ ! -d "$DATA_DIR/train" ] || [ ! -d "$DATA_DIR/validation" ]; then
    echo "ERROR: Training data not found!"
    echo "Please run prepare_dataset.sh first to generate training data."
    echo "Expected location: $DATA_DIR"
    exit 1
fi

# Count data files
TRAIN_FILES=$(ls $DATA_DIR/train/*.npz 2>/dev/null | wc -l)
VAL_FILES=$(ls $DATA_DIR/validation/*.npz 2>/dev/null | wc -l)

echo "Dataset found:"
echo "  Train files: $TRAIN_FILES"
echo "  Val files: $VAL_FILES"
echo ""

if [ $TRAIN_FILES -eq 0 ] || [ $VAL_FILES -eq 0 ]; then
    echo "ERROR: No .npz files found in dataset"
    exit 1
fi

# Load modules
module load python/3.10
module load cuda/11.8

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

export PYTHONPATH="$RESCORED_DIR:$PYTHONPATH"

# GPU info
echo "GPU Information:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
echo ""

################################################################################
# Train BiLSTM Model
################################################################################

echo "========================================"
echo "Starting BiLSTM Training"
echo "========================================"
echo ""

python -m backend.refinement.training.train_bilstm \
    --train-dir "$DATA_DIR/train" \
    --val-dir "$DATA_DIR/validation" \
    --output-dir "$OUTPUT_DIR" \
    --batch-size 16 \
    --lr 1e-3 \
    --epochs 50 \
    --device cuda

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "✓ Training Complete!"
    echo "========================================"
    echo "Checkpoints saved to: $OUTPUT_DIR"
    echo ""

    # List checkpoints
    echo "Checkpoints:"
    ls -lh "$OUTPUT_DIR"/*.pt
    echo ""

    echo "Best checkpoint: $OUTPUT_DIR/bilstm_best.pt"
    echo ""
    echo "Next steps:"
    echo "1. Enable BiLSTM in app_config.py:"
    echo "   enable_bilstm_refinement = True"
    echo "2. Run evaluation to measure improvement"
else
    echo "ERROR: Training failed"
    exit 1
fi

echo ""
echo "End time: $(date)"
echo "Duration: $SECONDS seconds ($((SECONDS/3600)) hours)"

deactivate
