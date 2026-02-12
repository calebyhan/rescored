# Rescored - AI Music Transcription

Convert YouTube videos into editable sheet music using AI.

## Deployment

**Status**: Live and operational! (for best results, use the local deployment)

- Backend: https://calebhan-rescored.hf.space
- Frontend: https://rescored.vercel.app

## Overview

Rescored transcribes YouTube videos to professional-quality music notation:
1. **Submit** a YouTube URL
2. **AI Processing** extracts audio, separates instruments, and transcribes to MIDI
3. **Edit** the notation in an interactive editor
4. **Export** as MIDI

**Tech Stack**:
- **Backend**: Python/FastAPI + Celery + Redis
- **Frontend**: React + VexFlow (notation) + Tone.js (playback)
- **ML Pipeline**:
  - BS-RoFormer (vocal removal) → Demucs (6-stem separation)
  - YourMT3+ + ByteDance ensemble → BiLSTM refinement (**96.1% accuracy on piano**)
  - Audio preprocessing + confidence filtering

## Getting Started

For local development setup and installation instructions, see [CONTRIBUTING.md](CONTRIBUTING.md)

## Features

- [x] **YouTube URL input** with validation and health checks
- [x] **Multi-instrument transcription** (piano, guitar, bass, drums, vocals, other)
- [x] **Advanced source separation** (BS-RoFormer + Demucs 6-stem)
- [x] **Ensemble transcription** (YourMT3+ + ByteDance voting system)
- [x] **BiLSTM neural refinement** (96.1% F1 accuracy on piano)
- [x] **Audio preprocessing** (noise reduction, spectral denoising)
- [x] **Confidence filtering** (frame-level ByteDance scores)
- [x] **Interactive notation editor** with VexFlow rendering
- [x] **Multi-instrument tabs** (switch between transcribed instruments)
- [x] **Playback controls** (play/pause, tempo adjust, loop)
- [x] **Real-time progress** via WebSocket
- [x] **MIDI export** (download transcribed notation)
- [x] **Grand staff support** (treble + bass clefs)
- [x] **Chord detection** and rendering
- [x] **Note selection** and highlighting
- [ ] Advanced editing (copy/paste, drag-to-reposition, undo/redo)
- [ ] PDF export
- [ ] Articulations and dynamics notation

## Project Structure

```
rescored/
├── backend/                      # Python/FastAPI backend
│   ├── main.py                   # REST API + WebSocket server
│   ├── tasks.py                  # Celery background workers
│   ├── pipeline.py               # Audio processing pipeline
│   ├── app_config.py             # Configuration settings
│   ├── app_utils.py              # Utility functions
│   ├── audio_preprocessor.py     # Audio enhancement pipeline
│   ├── ensemble_transcriber.py   # Multi-model voting system
│   ├── confidence_filter.py      # Post-processing filters
│   ├── key_filter.py             # Music theory filters
│   ├── requirements.txt          # Python dependencies (including tests)
│   ├── tests/                    # Test suite (59 tests, 27% coverage)
│   │   ├── test_api.py           # API endpoint tests
│   │   ├── test_pipeline.py      # Pipeline component tests
│   │   ├── test_tasks.py         # Celery task tests
│   │   └── test_utils.py         # Utility function tests
│   └── ymt/                      # YourMT3+ model and wrappers
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── components/           # UI components
│   │   ├── store/                # Zustand state management
│   │   └── api/                  # API client
│   └── package.json              # Node dependencies
├── docs/                         # Comprehensive documentation
│   ├── backend/                  # Backend implementation guides
│   ├── frontend/                 # Frontend implementation guides
│   ├── architecture/             # System design documents
│   └── research/                 # ML model comparisons
├── logs/                         # Runtime logs (created by start.sh)
├── storage/                      # YouTube cookies and temp files
├── start.sh                      # Start all services
├── stop.sh                       # Stop all services
└── docker-compose.yml            # Docker setup (optional)
```

## Accuracy Expectations

**Production Configuration (Phase 1.3 - Ensemble + BiLSTM):**
- Piano transcription: **96.1% F1 score** (evaluated on MAESTRO test set)
- Full pipeline: YourMT3+ + ByteDance ensemble → Confidence filtering → BiLSTM refinement
- Includes audio preprocessing, two-stage source separation, and neural post-processing
- Enabled by default in `app_config.py`

**Alternative Configurations:**
- **Ensemble only** (no BiLSTM): **93.6% F1** - faster, still very accurate
- **YourMT3+ only**: **~85% F1** - generalist model
- **basic-pitch** (fallback): **~70% F1** - lightweight backup

The interactive editor is designed to make fixing remaining errors easy regardless of which transcription configuration is used.

**Hardware Requirements:**
- BiLSTM refinement: ~100MB checkpoint, works on CPU/GPU/MPS
- ByteDance ensemble: ~4GB VRAM (may fall back to YourMT3+ only on systems with limited GPU memory)

## Evaluation Results

Evaluated on [**MAESTRO test set**](https://magenta.tensorflow.org/datasets/maestro) (177 piano recordings):

### Baseline & Improvements

| Configuration | F1 Score | Precision | Recall | Description |
|--------------|----------|-----------|--------|-------------|
| **Baseline** | **93.1%** | 89.7% | 96.8% | Ensemble only (YourMT3+ + ByteDance) |
| **Phase 1.1 (Confidence)** | **93.6%** | 91.5% | 95.7% | + ByteDance confidence filtering |
| **Phase 1.2 (TTA)** | **81.0%** | 70.9% | 94.8% | + Test-time augmentation (broken) |
| **Phase 1.3 (BiLSTM)** | **96.1%** | 96.7% | 95.5% | Ensemble + Confidence + BiLSTM |
| Phase 1.3b (BiLSTM only) | 96.0% | 95.4% | 96.6% | YourMT3+ → BiLSTM (no ensemble) |
| Phase 1.3c (ByteDance + BiLSTM) | 96.0% | 96.3% | 95.7% | ByteDance → BiLSTM (no ensemble) |

### Key Findings

**✅ What Worked:**
1. **BiLSTM refinement (+2.5% F1)**: Neural post-processor improves transcription from 93.6% → 96.1% F1
   - Phase 1.3 (Ensemble + Confidence + BiLSTM): **96.1% F1** (best configuration)
   - Phase 1.3b (YourMT3+ → BiLSTM): **96.0% F1** (simpler, nearly as good)
   - Phase 1.3c (ByteDance → BiLSTM): **96.0% F1** (simpler, nearly as good)
   - All three BiLSTM variants perform nearly identically (~96% F1)
   - BiLSTM successfully learns timing corrections and false positive filtering
   - **Reliability**: Chunked processing handles long sequences (7000+ notes) that exceed cuDNN LSTM limits
2. **Confidence filtering (+0.5% F1)**: Using ByteDance's frame-level confidence scores to filter low-confidence notes
3. **Ensemble voting (93.1% → 93.6%)**: Combining YourMT3+ (generalist) + ByteDance (piano specialist) with asymmetric weights

**❌ What Failed:**
1. **Test-Time Augmentation (-12.6% F1)**: Pitch shift/time stretch augmentations produce misaligned predictions
   - 67-72% of notes appear in only 1 of 5 augmentations
   - Vote counting filtered out too many correct predictions
   - Precision dropped dramatically (91.5% → 70.9%)
   - **Root cause**: Augmentations change model behavior non-linearly, not just adding noise

### Production Configuration

**Current Production Setup (Phase 1.3):**
- Configuration: **Ensemble + Confidence + BiLSTM** → **96.1% F1**
- Enabled in `app_config.py`:
  ```python
  use_ensemble_transcription = True
  use_bytedance_confidence = True
  enable_bilstm_refinement = True
  enable_tta = False  # Disabled (proven ineffective)
  ```
- Full pipeline: YourMT3+ + ByteDance ensemble → Confidence filtering → BiLSTM refinement
- Processing time: ~2-3 minutes per song on GPU

**Alternative Configurations (96.0% F1):**
- **Phase 1.3b (YourMT3+ → BiLSTM)**: Simpler, faster, no ByteDance loading
- **Phase 1.3c (ByteDance → BiLSTM)**: Piano specialist path
- Both achieve nearly identical accuracy with reduced complexity

**Key Insight:**
- BiLSTM post-processing was the breakthrough: +2.5% F1 improvement (93.6% → 96.1%)
- All BiLSTM variants (1.3, 1.3b, 1.3c) perform nearly identically at ~96% F1
- This suggests BiLSTM is the key component, not the upstream transcriber
- Simpler pipelines (1.3b, 1.3c) may be preferable for production due to lower complexity

**For Future Research:**
- Investigate why all BiLSTM variants achieve ~96% regardless of upstream model
- Try training BiLSTM with more epochs (current: 50, suggested: 100)
- Explore Phase 2 (D3RM diffusion refinement) for potential 97-99% F1

## Roadmap

### [x] Phase 1 (COMPLETE - Target: 92-94% F1, Achieved: 96.1% F1) ✅
- Piano transcription with **96.1% F1** (ensemble + confidence filtering + BiLSTM)
- Two-stage source separation (BS-RoFormer + Demucs)
- Audio preprocessing pipeline
- Enhanced confidence filtering (+0.5% F1)
- BiLSTM neural refinement (+2.5% F1)
- Vocal transcription support (piano + vocals)
- Basic editing capabilities
- MusicXML export
- Test suite (59 tests, 27% coverage)
- **Benchmark evaluation** on MAESTRO dataset (177 examples)
- Production deployment with optimal configuration

### Phase 1 (Optional Improvements)
- [ ] Try training BiLSTM with 100 epochs (currently 50, may reach ~97% F1)
- [ ] Simplify to Phase 1.3b (YourMT3+ → BiLSTM) for faster processing
- [ ] Investigate why BiLSTM achieves 96% regardless of upstream model

### Phase 2 (Future)
- Multi-instrument transcription beyond piano+vocals
- Grand staff notation (treble + bass)
- Advanced editing (copy/paste, undo/redo, multi-select)
- MIDI export improvements
- PDF export
- Articulations and dynamics

### Phase 3 (Future)
- User accounts and authentication
- Cloud storage integration
- Job history and saved transcriptions
- Collaboration features

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

### ML Models & Audio Processing
- **YourMT3+** (KAIST) - Multi-instrument music transcription ([Paper](https://arxiv.org/abs/2407.04822))
- **ByteDance Piano Transcription** - Piano-specific CNN+BiGRU model ([GitHub](https://github.com/bytedance/piano_transcription))
- **BS-RoFormer** - Vocal removal for cleaner separation ([GitHub](https://github.com/ZFTurbo/Music-Source-Separation-Training))
- **Demucs** (Meta AI Research) - 6-stem audio source separation ([Paper](https://arxiv.org/abs/2111.03600))
- **audio-separator** - BS-RoFormer wrapper and audio processing utilities

### Music Processing Libraries
- **librosa** - Audio preprocessing and feature extraction
- **madmom** - Beat tracking and tempo detection
- **pretty_midi** - MIDI file manipulation

### Frontend Libraries
- **VexFlow** - Music notation rendering in SVG/Canvas
- **Tone.js** - Web audio synthesis and playback

---

**Note**: This is an educational project. Users are responsible for copyright compliance when transcribing YouTube content.