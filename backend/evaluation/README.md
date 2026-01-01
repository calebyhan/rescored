# Transcription Evaluation Module

Benchmarking infrastructure for measuring piano transcription accuracy.

## Overview

This module provides tools to:
- Calculate F1 score, precision, recall for MIDI transcription
- Benchmark models on MAESTRO dataset
- Track accuracy improvements across development phases
- Generate detailed reports for analysis

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Prepare Test Cases (Option A: MAESTRO Dataset)

Download MAESTRO v3.0.0 from https://magenta.tensorflow.org/datasets/maestro

```bash
# Extract dataset to /tmp/maestro-v3.0.0/
# Then prepare test cases:
python -m evaluation.prepare_maestro \
    --maestro-dir /tmp/maestro-v3.0.0 \
    --output-json evaluation/test_videos.json
```

### 2. Prepare Test Cases (Option B: Custom Videos)

Create `evaluation/test_videos.json` manually:

```json
[
  {
    "name": "Simple Piano Melody",
    "audio_path": "/path/to/audio.wav",
    "ground_truth_midi": "/path/to/ground_truth.mid",
    "genre": "classical",
    "difficulty": "easy"
  }
]
```

### 3. Run Baseline Benchmark

```bash
# Benchmark current YourMT3+ model
python -m evaluation.run_benchmark \
    --model yourmt3 \
    --test-cases evaluation/test_videos.json \
    --output-dir evaluation/results
```

### 4. View Results

Results are saved in two formats:
- **JSON**: `evaluation/results/yourmt3_results.json` (detailed)
- **CSV**: `evaluation/results/yourmt3_results.csv` (for spreadsheets)

Example output:
```
📊 BENCHMARK SUMMARY: yourmt3
========================================
Total tests: 8
Successful: 8
Failed: 0

📈 Overall Accuracy:
   F1 Score: 0.847
   Precision: 0.823
   Recall: 0.872
   Onset MAE: 38.2ms
   Avg Processing Time: 127.3s

📊 By Genre:
   Classical: F1=0.847 (8 tests)

📊 By Difficulty:
   Easy: F1=0.921 (2 tests)
   Medium: F1=0.854 (3 tests)
   Hard: F1=0.782 (3 tests)
```

## Metrics Explained

### F1 Score (Primary Metric)
Harmonic mean of precision and recall. Balances false positives and false negatives.
- **Target**: ≥0.95 (95%+ accuracy)
- **Good**: ≥0.85 (85%+ accuracy)
- **Needs improvement**: <0.80

### Precision
Percentage of predicted notes that are correct.
- High precision = few false positives (wrong notes)

### Recall
Percentage of ground truth notes that were detected.
- High recall = few false negatives (missed notes)

### Onset MAE (Mean Absolute Error)
Average timing error for note onsets, in milliseconds.
- **Excellent**: <30ms
- **Good**: <50ms
- **Acceptable**: <100ms

### Pitch Accuracy
Percentage of matched notes with correct pitch.
- Should be close to 100% if onset matching is working

## Benchmarking Workflow

### Phase 1: Baseline (Current)
```bash
python -m evaluation.run_benchmark --model yourmt3
```

Expected: F1 ~0.80-0.85 (current YourMT3+ performance)

### Phase 2: ByteDance Integration
```bash
# After implementing ByteDance wrapper
python -m evaluation.run_benchmark --model bytedance

# Compare with baseline
python evaluation/compare_results.py yourmt3 bytedance
```

Expected: F1 ~0.83-0.90 (if ByteDance generalizes to YouTube audio)

### Phase 3: Ensemble
```bash
python -m evaluation.run_benchmark --model ensemble
```

Expected: F1 ~0.88-0.95 (ensemble voting)

### Phase 4: With Preprocessing
```bash
# Enable audio preprocessing in app_config.py
# Then re-run ensemble benchmark
```

Expected: F1 ~0.90-0.96 (preprocessing + ensemble)

## Tolerance Settings

Default onset tolerance: **50ms**

For different difficulty levels:
- **Strict** (20ms): Simple melodies, slow tempo
- **Default** (50ms): Standard evaluation
- **Lenient** (100ms): Fast passages, complex music

Change tolerance:
```bash
python -m evaluation.run_benchmark --model yourmt3 --onset-tolerance 0.02  # 20ms
```

## Test Case Structure

Each test case requires:
- **Audio file** (WAV, MP3, FLAC)
- **Ground truth MIDI** (verified transcription)
- **Metadata**: genre, difficulty, name

### Recommended Test Suite

Minimum 10-15 test cases:
- 2-3 simple melodies (easy)
- 5-7 classical piano pieces (medium)
- 3-5 complex/fast passages (hard)
- Mix of genres: classical, pop, jazz

## MAESTRO Dataset

### Subset Selection

We use 8 curated pieces from MAESTRO:
- 2 easy (simple classical)
- 3 medium (Chopin, moderate tempo)
- 3 hard (fast passages, complex harmony)

### Why MAESTRO?

Pros:
- High-quality ground truth MIDI (aligned by humans)
- Professional piano performances
- Varied difficulty and styles

Cons:
- Clean studio recordings (not YouTube quality)
- All classical piano (no pop/jazz)
- May overestimate accuracy on real YouTube videos

### Validation on YouTube

After achieving target accuracy on MAESTRO, validate on real YouTube videos:
1. Transcribe 5-10 YouTube piano videos
2. Manually verify transcriptions in MuseScore
3. Measure accuracy using same metrics

## Development Workflow

1. **Baseline**: Measure current YourMT3+ (Week 1)
2. **Implement enhancement**: ByteDance, ensemble, etc. (Week 2-4)
3. **Benchmark**: Re-run on same test set
4. **Compare**: Did F1 improve by ≥2%?
5. **Iterate**: Tune parameters if needed

## Troubleshooting

### "Test cases file not found"
```bash
# Create test cases first:
python -m evaluation.prepare_maestro --maestro-dir /path/to/maestro-v3.0.0
```

### "Transcription failed"
Check pipeline logs for errors. Common issues:
- Demucs CUDA out of memory → use CPU
- YourMT3+ checkpoint not loaded
- Audio file format not supported

### "F1 score is 0.0"
- Check that MIDI files are valid
- Verify onset tolerance isn't too strict
- Ensure ground truth MIDI has notes

## Files

- `metrics.py` - F1, precision, recall calculation
- `benchmark.py` - Benchmark runner framework
- `prepare_maestro.py` - MAESTRO dataset preparation
- `run_benchmark.py` - Main CLI script
- `test_videos.json` - Test case metadata (created by prepare_maestro)
- `results/` - Benchmark results (JSON + CSV)

## Next Steps

After Phase 1 baseline:
- [ ] Integrate ByteDance model (Phase 2)
- [ ] Implement ensemble voting (Phase 3)
- [ ] Add audio preprocessing (Phase 4)
- [ ] Run comprehensive benchmarks
- [ ] Target: F1 ≥ 0.95 (95%+ accuracy)
