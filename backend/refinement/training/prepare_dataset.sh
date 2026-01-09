#!/bin/bash
#SBATCH --job-name=bilstm_prep
#SBATCH --output=logs/slurm/bilstm_prep_%j.log
#SBATCH --error=logs/slurm/bilstm_prep_%j.err
#SBATCH --time=3-00:00:00              # 3 days for dataset preparation
#SBATCH --cpus-per-task=8              # 8 CPUs for transcription
#SBATCH --mem=64G                      # 64GB RAM
#SBATCH --partition=gpu                # GPU partition for faster transcription
#SBATCH --gres=gpu:1                   # 1 GPU
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=calebhan@unc.edu

################################################################################
# BiLSTM Dataset Preparation Script
#
# Generates ensemble predictions for MAESTRO dataset for BiLSTM training.
# This is a preprocessing step that must be run ONCE before training.
#
# Runtime: ~1-2 days for full MAESTRO train split (960 examples)
################################################################################

set -e
set -u

echo "========================================"
echo "BiLSTM Dataset Preparation"
echo "========================================"
echo "Start time: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "========================================"
echo ""

# Paths
WORK_DIR="/work/users/c/a/calebhan/rescored"
MAESTRO_ROOT="$WORK_DIR/data/maestro-v3.0.0"
RESCORED_DIR="$WORK_DIR/rescored"
OUTPUT_DIR="$WORK_DIR/data/bilstm_training"

cd "$RESCORED_DIR"

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
# Prepare Dataset
################################################################################

echo "Preparing MAESTRO dataset for BiLSTM training..."
echo ""

# Prepare training split (960 examples, ~1-2 days)
echo "Processing training split..."
python -m backend.refinement.training.dataset_builder \
    --maestro-root "$MAESTRO_ROOT" \
    --output-dir "$OUTPUT_DIR/train" \
    --split train \
    --fps 100

# Prepare validation split (137 examples, ~3-4 hours)
echo ""
echo "Processing validation split..."
python -m backend.refinement.training.dataset_builder \
    --maestro-root "$MAESTRO_ROOT" \
    --output-dir "$OUTPUT_DIR/validation" \
    --split validation \
    --fps 100

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "✓ Dataset Preparation Complete!"
    echo "========================================"
    echo "Train data: $OUTPUT_DIR/train"
    echo "Val data: $OUTPUT_DIR/validation"
    echo ""

    # Count files
    echo "Dataset statistics:"
    echo "  Train files: $(ls $OUTPUT_DIR/train/*.npz | wc -l)"
    echo "  Val files: $(ls $OUTPUT_DIR/validation/*.npz | wc -l)"
    echo ""

    echo "Ready to train BiLSTM model!"
    echo "Next step: sbatch backend/refinement/training/train_bilstm.sh"
else
    echo "ERROR: Dataset preparation failed"
    exit 1
fi

echo ""
echo "End time: $(date)"
echo "Duration: $SECONDS seconds ($((SECONDS/3600)) hours)"

deactivate
