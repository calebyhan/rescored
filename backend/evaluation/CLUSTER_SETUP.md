# Cluster Benchmark Setup

Run transcription benchmarks on a SLURM cluster with GPU acceleration.

## Directory Structure

```
/cluster/path/
├── data/
│   └── maestro-v3.0.0/          # MAESTRO dataset (120GB)
│       ├── 2004/
│       │   ├── *.wav            # Audio files
│       │   └── *.midi           # Ground truth MIDI
│       ├── 2006/
│       ├── 2008/
│       └── ...
└── rescored/                     # Git repo
    └── backend/
        ├── evaluation/
        │   ├── slurm_benchmark.sh
        │   └── ...
        └── requirements.txt
```

## One-Time Setup

### 1. Download MAESTRO Dataset (on cluster)

```bash
# Navigate to data directory
cd /cluster/path/data/

# Download MAESTRO v3.0.0 (120GB - will take a while)
wget https://storage.googleapis.com/magentadata/datasets/maestro/v3.0.0/maestro-v3.0.0.zip

# Extract (creates maestro-v3.0.0/ directory)
unzip maestro-v3.0.0.zip

# Verify structure
ls maestro-v3.0.0/
# Should see: 2004/ 2006/ 2008/ 2009/ 2011/ 2013/ 2014/ 2015/ 2017/ 2018/

# Optional: Remove zip to save space
rm maestro-v3.0.0.zip
```

### 2. Clone Repository (on cluster)

```bash
cd /cluster/path/

# Clone your repo
git clone <your-repo-url> rescored

# Navigate to backend
cd rescored/backend/

# Make benchmark script executable
chmod +x evaluation/slurm_benchmark.sh
```

### 3. Create Virtual Environment (on cluster)

```bash
# In rescored/backend/
python3.10 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip

# Install Cython first (required by madmom)
pip install Cython

# Install madmom separately to avoid build isolation issues
pip install --no-build-isolation madmom>=0.16.1

# Uninstall problematic packages if previously installed
pip uninstall -y torchcodec torchaudio

# Install remaining dependencies (includes torchaudio 2.1.0 which uses SoundFile backend)
pip install -r requirements.txt
```

**Note**: The SLURM script will automatically load FFmpeg module, which is required by Demucs for audio loading. If running manually, load it with `module load ffmpeg`.

## Running Benchmarks

### Baseline Benchmark (YourMT3+)

```bash
# In rescored/backend/
sbatch evaluation/slurm_benchmark.sh

# With custom paths:
sbatch evaluation/slurm_benchmark.sh \
    ../data/maestro-v3.0.0 \  # MAESTRO dataset path
    yourmt3 \                  # Model to benchmark
    .                          # Repo directory (current)
```

### Check Job Status

```bash
# View job queue
squeue -u $USER

# View running job output (live)
tail -f logs/slurm/benchmark_<JOB_ID>.log

# View all output after completion
cat logs/slurm/benchmark_<JOB_ID>.log
```

### Download Results to Local Machine

After job completes:

```bash
# From your local machine
scp <cluster>:/cluster/path/rescored/backend/evaluation/results/yourmt3_results.* .

# Or download entire results directory
scp -r <cluster>:/cluster/path/rescored/backend/evaluation/results/ .
```

## Benchmark Workflow

The SLURM script automatically:

1. **Validates MAESTRO dataset** exists and has correct structure
2. **Prepares test cases** - Extracts 8 curated pieces (easy/medium/hard)
3. **Runs transcription** - Processes each test case through pipeline:
   - YouTube audio download → Demucs separation → YourMT3+ transcription
4. **Calculates metrics** - F1, precision, recall, onset MAE
5. **Saves results** - JSON + CSV format

## Expected Timeline

With **L40 GPU**:
- MAESTRO download: ~30-60 min (one-time)
- Test case preparation: ~1 min
- Benchmark (8 test cases): ~8-12 hours
  - Per test case: ~60-90 min (includes Demucs + YourMT3+)

With **CPU only** (no GPU):
- Benchmark would take ~24-48 hours (not recommended)

## Output Files

After successful run:

```
evaluation/
├── test_videos.json              # Test case metadata (8 pieces)
├── results/
│   ├── yourmt3_results.json      # Detailed results (F1, precision, recall)
│   └── yourmt3_results.csv       # Same data in CSV format
└── logs/
    └── slurm/
        └── benchmark_<JOB_ID>.log  # Full execution log
```

### Results Format (JSON)

```json
[
  {
    "test_case": "MAESTRO_2004_Track03",
    "genre": "classical",
    "difficulty": "easy",
    "f1_score": 0.892,
    "precision": 0.871,
    "recall": 0.914,
    "onset_mae": 0.0382,
    "pitch_accuracy": 0.987,
    "processing_time": 127.3,
    "success": true
  }
]
```

## Benchmarking Multiple Models

After implementing ByteDance (Phase 2) or ensemble (Phase 3):

```bash
# Benchmark ByteDance
sbatch evaluation/slurm_benchmark.sh ../data/maestro-v3.0.0 bytedance

# Benchmark Ensemble
sbatch evaluation/slurm_benchmark.sh ../data/maestro-v3.0.0 ensemble
```

## Troubleshooting

### Job Fails with "MAESTRO dataset not found"

```bash
# Check if dataset exists
ls /cluster/path/data/maestro-v3.0.0/

# If missing, download following "One-Time Setup" instructions
```

### Job Fails with "Module not found"

```bash
# Reinstall dependencies in venv
cd /cluster/path/rescored/backend/
source .venv/bin/activate
pip install -r requirements.txt
```

### GPU Out of Memory

SLURM script already uses conservative settings:
- 1 GPU (L40 with 48GB VRAM)
- 32GB system RAM
- Demucs uses mixed precision

If still failing, check:
```bash
# View GPU usage during job
ssh <node-from-squeue>
nvidia-smi
```

### Job Times Out

Increase time limit in script:
```bash
# Edit slurm_benchmark.sh
#SBATCH --time=1-00:00:00  # Change to 24 hours
```

## Next Steps After Baseline

1. **Analyze results** - Download JSON/CSV, review F1 scores
2. **Implement Phase 2** - ByteDance integration (locally)
3. **Re-benchmark** - Run ByteDance benchmark on cluster
4. **Compare** - YourMT3+ vs ByteDance F1 scores
5. **Iterate** - Continue through Phases 3-5

## Quick Reference

```bash
# Submit job
sbatch evaluation/slurm_benchmark.sh

# Check status
squeue -u $USER

# Cancel job
scancel <JOB_ID>

# View live logs
tail -f logs/slurm/benchmark_<JOB_ID>.log

# Download results
scp <cluster>:/cluster/path/rescored/backend/evaluation/results/* .
```
