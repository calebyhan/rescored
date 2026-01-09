---
title: Rescored
emoji: 🎵
colorFrom: purple
colorTo: blue
sdk: docker
sdk_version: latest
app_file: backend/app.py
pinned: false
---

# Rescored - AI Music Transcription

Convert YouTube videos into editable sheet music using AI.

## Deployment

**Status**: Live and operational!

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
  - YourMT3+ + ByteDance ensemble (90% accuracy on piano)
  - Audio preprocessing + confidence/key filtering

## Quick Start

### Prerequisites

- **macOS** (Apple Silicon recommended for MPS GPU acceleration) OR **Linux** (with NVIDIA GPU)
- **Python 3.10** (required for madmom compatibility)
- **Node.js 18+**
- **Redis 7+**
- **FFmpeg**
- **Homebrew** (macOS only, for Redis installation)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/rescored.git
cd rescored

# Pull large files with Git LFS (required for YourMT3+ model checkpoint)
git lfs pull
```

**Note:** This repository uses **Git LFS** (Large File Storage) to store the YourMT3+ model checkpoint (~536MB). If you don't have Git LFS installed:

```bash
# macOS
brew install git-lfs
git lfs install
git lfs pull

# Linux (Debian/Ubuntu)
sudo apt-get install git-lfs
git lfs install
git lfs pull
```

### Setup Redis (macOS)

```bash
# Install Redis via Homebrew
brew install redis

# Start Redis service
brew services start redis

# Verify Redis is running
redis-cli ping  # Should return PONG
```

### Setup Backend (Python 3.10 + MPS GPU Acceleration)

```bash
cd backend

# Ensure Python 3.10 is installed
python3.10 --version  # Should show Python 3.10.x

# Create virtual environment
python3.10 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip, setuptools, and wheel
pip install --upgrade pip setuptools wheel

# Install all dependencies (takes 10-15 minutes)
pip install -r requirements.txt

# Verify installation
python -c "import torch; print(f'PyTorch {torch.__version__} installed')"
python -c "import librosa; print(f'librosa installed')"

# Copy environment file and configure
cp .env.example .env
# Edit .env - ensure YOURMT3_DEVICE=mps for Apple Silicon GPU acceleration
```

**What gets installed:**
- Core ML frameworks: PyTorch 2.9+, torchaudio 2.9+
- Audio processing: librosa, soundfile, demucs, audio-separator
- Transcription: YourMT3+ dependencies (transformers, lightning, einops)
- Music notation: mido, pretty_midi
- Web framework: FastAPI, uvicorn, celery, redis
- Testing: pytest, pytest-asyncio, pytest-cov, pytest-mock
- **Total: ~200 packages, ~3-4GB download**

**Troubleshooting Installation:**

If you encounter errors during `pip install -r requirements.txt`:

1. **scipy build errors**: Make sure you have the latest pip/setuptools:
   ```bash
   pip install --upgrade pip setuptools wheel
   ```

2. **numpy version conflicts**: The requirements.txt is configured to use numpy 2.x which works with all packages. If you see conflicts, try:
   ```bash
   pip install --no-deps -r requirements.txt
   pip check  # Verify no broken dependencies
   ```

3. **torch installation issues on macOS**: PyTorch should install pre-built wheels. If it tries to build from source:
   ```bash
   pip install --only-binary :all: torch torchaudio
   ```

4. **madmom build errors**: madmom requires Cython. Install it first:
   ```bash
   pip install Cython
   pip install madmom
   ```

### Setup Frontend

```bash
cd frontend

# Install dependencies
npm install
```

### REQUIRED: YouTube Cookies Setup

YouTube requires authentication for video downloads (as of December 2024). You **MUST** export your YouTube cookies before the application will work.

**Quick Setup (5 minutes):**

1. **Install Browser Extension**
   - Install [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/cclelndahbckbenkjhflpdbgdldlbecc) for Chrome/Edge/Brave

2. **Export Cookies**
   - Open a **NEW private/incognito window** (this is important!)
   - **Sign in to YouTube** with your Google account
   - **Visit any YouTube video page**
   - **Click the extension icon** in your browser toolbar
   - **Click "Export"** or "Download"
   - **Save the file** to your computer

3. **Place Cookie File**
   ```bash
   # Create storage directory if it doesn't exist
   mkdir -p storage

   # Move the exported file (adjust path if needed)
   mv ~/Downloads/youtube.com_cookies.txt ./storage/youtube_cookies.txt
   ```

## Running the Application

### Start All Services (Recommended)

Use the provided shell scripts to start/stop all services at once:

```bash
# Make sure nothing is running
./stop.sh

# Start all services (backend API, Celery worker, frontend)
./start.sh
```

This starts all services in the background with logs written to the `logs/` directory.

**View logs in real-time:**
```bash
tail -f logs/api.log      # Backend API logs
tail -f logs/worker.log   # Celery worker logs
tail -f logs/frontend.log # Frontend logs
```

**Stop all services:**
```bash
./stop.sh
```

**Services available at:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Manual Start (Alternative)

If you prefer to run services manually in separate terminals:

**Terminal 1 - Backend API:**
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Celery Worker:**
```bash
cd backend
source .venv/bin/activate
# Use --pool=solo on macOS to avoid fork() crashes with ML libraries
celery -A tasks worker --loglevel=info --pool=solo
```

**Terminal 3 - Frontend:**
```bash
cd frontend
npm run dev
```

**Verification:**
```bash
ls -lh storage/youtube_cookies.txt
```
You should see the file listed.

**Troubleshooting:**

- **"Please sign in" error**: Make sure you exported from a private/incognito window. Export fresh cookies (don't reuse old ones). Ensure the file is named exactly `youtube_cookies.txt` and isn't empty.

- **File format errors**: The first line should be `# Netscape HTTP Cookie File`. If not, use the browser extension method.

- **Cookies expire quickly**: Export from a NEW incognito window each time. You may need to re-export periodically.

**Security Note:** Never commit `youtube_cookies.txt` to git (it's already in `.gitignore`). Your cookies contain authentication tokens for your Google account—keep them private!

**Why Is This Required?** YouTube implemented bot detection in late 2024 that blocks unauthenticated downloads. Even though our tool is for legitimate transcription purposes, YouTube's systems can't distinguish it from scrapers. By providing your cookies, you're proving you're a real user who has agreed to YouTube's terms of service.

### YourMT3+ Setup

The backend uses a **multi-model ensemble** for transcription:
- **Primary**: YourMT3+ (multi-instrument, 80-85% base accuracy)
- **Specialist**: ByteDance Piano Transcription (piano-specific, ~90% accuracy)
- **Ensemble**: Weighted voting combines both models (90% accuracy on piano)
- **Fallback**: basic-pitch if ensemble unavailable (~70% accuracy)

**YourMT3+ model files and source code are already included in the repository.** The model checkpoint (~536MB) is stored via Git LFS in `backend/ymt/yourmt3_core/`.

**Verify YourMT3+ is working:**
```bash
# Start backend (if not already running)
cd backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal, test YourMT3+ loading
cd backend
source .venv/bin/activate
python -c "from yourmt3_wrapper import YourMT3Transcriber; t = YourMT3Transcriber(device='mps'); print('✓ YourMT3+ loaded successfully!')"
```

You should see:
- `Model loaded successfully on mps`
- `GPU available: True (mps), used: True`
- `✓ YourMT3+ loaded successfully!`

**GPU Acceleration:**
- **Apple Silicon (M1/M2/M3/M4):** Uses MPS (Metal Performance Shaders) with 16-bit mixed precision for optimal performance. Default is `YOURMT3_DEVICE=mps` in `.env`.
- **NVIDIA GPU:** Change `YOURMT3_DEVICE=cuda` in `.env`
- **CPU Only:** Change `YOURMT3_DEVICE=cpu` in `.env` (will be much slower)

**Important:** The symlink at `backend/ymt/yourmt3_core/amt/src/amt/logs` must point to `../../logs` for checkpoint loading to work. This is already configured in the repository.

## Usage

1. **Ensure all services are running:**
   - Redis: `brew services list | grep redis` (should show "started")
   - Backend API: Terminal 1 should show "Uvicorn running on http://0.0.0.0:8000"
   - Celery Worker: Terminal 2 should show "celery@hostname ready"
   - Frontend: Terminal 3 should show "Local: http://localhost:5173"

2. Open [http://localhost:5173](http://localhost:5173)
3. Paste a YouTube URL (piano music recommended for best results)
4. Wait for transcription:
   - **With MPS/GPU**: ~1-2 minutes
   - **With CPU**: ~10-15 minutes
5. Edit the notation in the interactive editor
6. Export as MIDI

## Features

- [x] **YouTube URL input** with validation and health checks
- [x] **Multi-instrument transcription** (piano, guitar, bass, drums, vocals, other)
- [x] **Advanced source separation** (BS-RoFormer + Demucs 6-stem)
- [x] **Ensemble transcription** (YourMT3+ + ByteDance voting system)
- [x] **Audio preprocessing** (noise reduction, spectral denoising)
- [x] **Confidence filtering** (removes low-confidence notes)
- [x] **Key-aware filtering** (removes out-of-key notes)
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
- [ ] User accounts and cloud storage

## Project Structure

```
rescored/
├── backend/                      # Python/FastAPI backend
│   ├── main.py                  # REST API + WebSocket server
│   ├── tasks.py                 # Celery background workers
│   ├── pipeline.py              # Audio processing pipeline
│   ├── app_config.py            # Configuration settings
│   ├── app_utils.py             # Utility functions
│   ├── audio_preprocessor.py   # Audio enhancement pipeline
│   ├── ensemble_transcriber.py # Multi-model voting system
│   ├── confidence_filter.py    # Post-processing filters
│   ├── key_filter.py            # Music theory filters
│   ├── requirements.txt         # Python dependencies (including tests)
│   ├── tests/                   # Test suite (59 tests, 27% coverage)
│   │   ├── test_api.py         # API endpoint tests
│   │   ├── test_pipeline.py    # Pipeline component tests
│   │   ├── test_tasks.py       # Celery task tests
│   │   └── test_utils.py       # Utility function tests
│   └── ymt/                     # YourMT3+ model and wrappers
├── frontend/                    # React frontend
│   ├── src/
│   │   ├── components/         # UI components
│   │   ├── store/              # Zustand state management
│   │   └── api/                # API client
│   └── package.json            # Node dependencies
├── docs/                        # Comprehensive documentation
│   ├── backend/                # Backend implementation guides
│   ├── frontend/               # Frontend implementation guides
│   ├── architecture/           # System design documents
│   └── research/               # ML model comparisons
├── logs/                        # Runtime logs (created by start.sh)
├── storage/                     # YouTube cookies and temp files
├── start.sh                     # Start all services
├── stop.sh                      # Stop all services
└── docker-compose.yml           # Docker setup (optional)
```

## Documentation

Comprehensive documentation is available in the [`docs/`](docs/) directory:

- [Getting Started](docs/getting-started.md)
- [Architecture Overview](docs/architecture/overview.md)
- [Backend Pipeline](docs/backend/pipeline.md)
- [Frontend Rendering](docs/frontend/notation-rendering.md)
- [MVP Scope](docs/features/mvp.md)
- [Known Challenges](docs/research/challenges.md)

## Performance

**With Apple Silicon MPS (M1/M2/M3/M4)**:
- Download: ~10 seconds
- Source separation (Demucs): ~30-60 seconds
- Transcription (YourMT3+): ~20-30 seconds
- **Total: ~1-2 minutes**

**With NVIDIA GPU (RTX 3080)**:
- Download: ~10 seconds
- Source separation: ~45 seconds
- Transcription: ~5 seconds
- **Total: ~1-2 minutes**

**With CPU**:
- Download: ~10 seconds
- Source separation: ~8-10 minutes
- Transcription: ~30 seconds
- **Total: ~10-15 minutes**

## Accuracy Expectations

**With Ensemble (YourMT3+ + ByteDance) - Recommended:**
- Simple piano: **~90% accurate** ✨
- Complex pieces: **80-85% accurate**
- Includes audio preprocessing, ensemble voting, and post-processing filters

**With YourMT3+ only:**
- Simple piano: **80-85% accurate**
- Complex pieces: **70-75% accurate**

**With basic-pitch (fallback):**
- Simple piano: **70-75% accurate**
- Complex pieces: **60-70% accurate**

The interactive editor is designed to make fixing errors easy regardless of which transcription model is used.

**Note**: Ensemble mode is enabled by default in `app_config.py`. ByteDance requires ~4GB VRAM and may fall back to YourMT3+ on systems with limited GPU memory.

## Development

### Running Tests

```bash
# Backend tests (59 tests, ~5-10 seconds)
cd backend
source .venv/bin/activate
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_api.py -v

# Frontend tests
cd frontend
npm test
```

See [docs/backend/testing.md](docs/backend/testing.md) for detailed testing guide.

### API Documentation

Once the backend is running, visit:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Troubleshooting

**Worker not processing jobs?**
- Check Redis is running: `redis-cli ping` (should return PONG)
- If Redis isn't running: `brew services start redis`
- Check worker logs in Terminal 2

**MPS/GPU not being used?**
- Verify MPS is available: `python -c "import torch; print(torch.backends.mps.is_available())"`
- Check `.env` has `YOURMT3_DEVICE=mps`
- For NVIDIA GPU: Set `YOURMT3_DEVICE=cuda`

**YourMT3+ fails to load?**
- Ensure Python 3.10 is being used: `python --version`
- Check symlink exists: `ls -la backend/ymt/yourmt3_core/amt/src/amt/logs`
- Verify checkpoint file exists: `ls -lh backend/ymt/yourmt3_core/logs/2024/*/checkpoints/last.ckpt`

**YouTube download fails?**
- Ensure `storage/youtube_cookies.txt` exists and is recent
- Export fresh cookies from a NEW incognito window
- Video may be age-restricted or private
- Update yt-dlp: `source .venv/bin/activate && pip install -U yt-dlp`

**Module import errors?**
- Make sure you're in the virtual environment: `source backend/.venv/bin/activate`
- Reinstall requirements: `pip install -r requirements.txt`

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

## Roadmap

### [x] Phase 1 (Completed)
- Piano transcription with 90% accuracy (ensemble voting)
- Two-stage source separation (BS-RoFormer + Demucs)
- Audio preprocessing pipeline
- Post-processing filters (confidence + key-aware)
- Vocal transcription support (piano + vocals)
- Basic editing capabilities
- MusicXML export
- Test suite (59 tests, 27% coverage)

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

### Phase 4 (Future)
- Mobile app (iOS/Android)
- Real-time collaboration
- API for third-party integrations

---

**Note**: This is an educational project. Users are responsible for copyright compliance when transcribing YouTube content.