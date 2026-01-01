#!/bin/bash
#SBATCH --job-name=rescored_benchmark
#SBATCH --output=../../logs/slurm/benchmark_%j.log
#SBATCH --error=../../logs/slurm/benchmark_%j.err
#SBATCH --time=0-12:00:00              # 12 hours for 8-10 test cases
#SBATCH --partition=l40-gpu            # Use l40-gpu partition
#SBATCH --qos=gpu_access               # Required for l40-gpu partition
#SBATCH --gres=gpu:1                   # 1 GPU (L40) - speeds up YourMT3+ and Demucs
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G                      # 32GB memory

# Piano Transcription Accuracy Benchmark
# Evaluates YourMT3+ baseline on MAESTRO dataset
# Expected runtime: ~8-12 hours for 8 test cases (with GPU)

echo "========================================"
echo "Rescored Transcription Benchmark"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo "========================================"

# Configuration
MAESTRO_DIR=${1:-"../../data/maestro-v3.0.0"}  # Path to MAESTRO dataset
MODEL=${2:-"yourmt3"}                        # Model to benchmark (yourmt3, bytedance, ensemble)
REPO_DIR=${3:-"rescored"}                    # Path to git repo

# Verify MAESTRO dataset exists
if [ ! -d "$MAESTRO_DIR" ]; then
    echo "ERROR: MAESTRO dataset not found: $MAESTRO_DIR"
    echo ""
    echo "Please download MAESTRO v3.0.0 from:"
    echo "  https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0.zip"
    echo ""
    echo "Extract to: ../../data/maestro-v3.0.0/"
    echo ""
    echo "Directory structure should be:"
    echo "  rescored/"
    echo "  ├── data/"
    echo "  │   └── maestro-v3.0.0/  <- MAESTRO dataset here"
    echo "  └── rescored/             <- Git repo here"
    echo "      └── backend/          <- Script runs from here"
    exit 1
fi

# Verify git repo exists
if [ ! -d "$REPO_DIR" ]; then
    echo "ERROR: Rescored repo not found: $REPO_DIR"
    echo "Please clone the repo first:"
    echo "  git clone <repo-url> $REPO_DIR"
    exit 1
fi

# Navigate to backend directory
cd "$REPO_DIR/backend" || exit 1

echo "MAESTRO dataset: $MAESTRO_DIR"
echo "Model: $MODEL"
echo "Repository: $REPO_DIR"
echo ""

# Create necessary directories
mkdir -p logs/slurm
mkdir -p evaluation/results

# Activate virtual environment
module load anaconda/2024.02
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    conda create -n .venv python=3.10
fi

source activate .venv

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip

# Install Cython first (required by madmom)
pip install -q Cython

# Install madmom separately to avoid build isolation issues
pip install -q --no-build-isolation madmom>=0.16.1

# Install remaining dependencies
pip install -q -r requirements.txt

# Display GPU info
echo ""
echo "GPU Information:"
nvidia-smi
echo ""

# Prepare test cases from MAESTRO
echo "========================================"
echo "Step 1: Preparing Test Cases"
echo "========================================"

if [ ! -f "evaluation/test_videos.json" ]; then
    echo "Extracting test subset from MAESTRO..."
    python -m evaluation.prepare_maestro \
        --maestro-dir "$MAESTRO_DIR" \
        --output-json evaluation/test_videos.json

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to prepare test cases"
        exit 1
    fi
else
    echo "✅ Test cases already exist: evaluation/test_videos.json"
fi

NUM_TESTS=$(python -c "import json; print(len(json.load(open('evaluation/test_videos.json'))))")
echo ""
echo "Number of test cases: $NUM_TESTS"
echo ""

# Run benchmark
echo "========================================"
echo "Step 2: Running Benchmark"
echo "========================================"
echo "Model: $MODEL"
echo "Onset tolerance: 50ms (default)"
echo "Expected time: ~60-90 min per test case with GPU"
echo ""

python -m evaluation.run_benchmark \
    --model "$MODEL" \
    --test-cases evaluation/test_videos.json \
    --output-dir evaluation/results \
    2>&1 | tee "logs/slurm/benchmark_${SLURM_JOB_ID}.log"

EXIT_CODE=$?

echo ""
echo "========================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Benchmark completed successfully!"
    echo ""
    echo "Results:"
    ls -lh evaluation/results/${MODEL}_results.*

    echo ""
    echo "Summary (from JSON):"
    python -c "
import json
import sys
try:
    with open('evaluation/results/${MODEL}_results.json', 'r') as f:
        results = json.load(f)

    successful = [r for r in results if r.get('success', False)]
    failed = [r for r in results if not r.get('success', False)]

    print(f'  Total tests: {len(results)}')
    print(f'  Successful: {len(successful)}')
    print(f'  Failed: {len(failed)}')

    if successful:
        avg_f1 = sum(r['f1_score'] for r in successful) / len(successful)
        avg_precision = sum(r['precision'] for r in successful) / len(successful)
        avg_recall = sum(r['recall'] for r in successful) / len(successful)
        avg_time = sum(r['processing_time'] for r in successful) / len(successful)

        print(f'')
        print(f'  Average F1 Score: {avg_f1:.3f}')
        print(f'  Average Precision: {avg_precision:.3f}')
        print(f'  Average Recall: {avg_recall:.3f}')
        print(f'  Avg Processing Time: {avg_time:.1f}s')
except Exception as e:
    print(f'  Could not parse results: {e}')
    sys.exit(1)
"

    echo ""
    echo "📥 Download results to local machine:"
    echo "  scp <cluster>:$(pwd)/evaluation/results/${MODEL}_results.* ."

else
    echo "❌ Benchmark failed with exit code: $EXIT_CODE"
    echo ""
    echo "Check logs:"
    echo "  tail -100 logs/slurm/benchmark_${SLURM_JOB_ID}.log"
fi

echo ""
echo "Job ID: $SLURM_JOB_ID"
echo "========================================"

exit $EXIT_CODE
