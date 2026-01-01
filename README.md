# Rescored - AI Music Transcription

Convert YouTube videos into editable sheet music using AI.

## Overview

Rescored transcribes YouTube videos to professional-quality music notation:
1. **Submit** a YouTube URL
2. **AI Processing** extracts audio, separates instruments, and transcribes to MIDI
3. **Edit** the notation in an interactive editor
4. **Export** as MusicXML or MIDI

**Tech Stack**:
- **Backend**: Python/FastAPI + Celery + Redis
- **Frontend**: React + VexFlow (notation) + Tone.js (playback)
- **ML**: Demucs (source separation) + YourMT3+ (transcription, 80-85% accuracy) + basic-pitch (fallback)

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

# Activate Python 3.10 virtual environment (already configured)
source .venv/bin/activate

# Verify Python version
python --version  # Should show Python 3.10.x

# Backend dependencies are already installed in .venv
# If you need to reinstall:
# pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# Edit .env - ensure YOURMT3_DEVICE=mps for Apple Silicon GPU acceleration
```

### Setup Frontend

```bash
cd frontend

# Install dependencies
npm install
```

### ⚠️ REQUIRED: YouTube Cookies Setup

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

4. **Start Services**

   **Option A: Single Command (Recommended)**
   ```bash
   ./start.sh
   ```
   This starts all services in the background. Logs are written to `logs/` directory.

   To stop all services:
   ```bash
   ./stop.sh
   # Or press Ctrl+C in the terminal running start.sh
   ```

   To view logs while running:
   ```bash
   tail -f logs/api.log      # Backend API logs
   tail -f logs/worker.log   # Celery worker logs
   tail -f logs/frontend.log # Frontend logs
   ```

   **Option B: Manual (3 separate terminals)**

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

   **Services will be available at:**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

**Verification:**
```bash
ls -lh storage/youtube_cookies.txt
```
You should see the file listed.

**Troubleshooting:**

- **"Please sign in" error**: Make sure you exported from a private/incognito window. Export fresh cookies (don't reuse old ones). Ensure the file is named exactly `youtube_cookies.txt` and isn't empty.

- **File format errors**: The first line should be `# Netscape HTTP Cookie File`. If not, use the browser extension method.

- **Cookies expire quickly**: Export from a NEW incognito window each time. You may need to re-export periodically.

**Security Note:** ⚠️ Never commit `youtube_cookies.txt` to git (it's already in `.gitignore`). Your cookies contain authentication tokens for your Google account—keep them private!

**Why Is This Required?** YouTube implemented bot detection in late 2024 that blocks unauthenticated downloads. Even though our tool is for legitimate transcription purposes, YouTube's systems can't distinguish it from scrapers. By providing your cookies, you're proving you're a real user who has agreed to YouTube's terms of service.

### YourMT3+ Setup

The backend uses **YourMT3+** as the primary transcription model (80-85% accuracy) with automatic fallback to basic-pitch (70% accuracy) if YourMT3+ is unavailable.

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
6. Export as MusicXML or MIDI

## MVP Features

✅ YouTube URL input and validation
✅ Piano-only transcription (MVP limitation)
✅ Single staff notation (treble clef)
✅ Basic editing: select, delete, add notes
✅ Play/pause with tempo control
✅ Export MusicXML

### Coming in Phase 2

- Multi-instrument transcription
- Grand staff (treble + bass)
- Advanced editing (copy/paste, undo/redo)
- MIDI export
- PDF export

## Project Structure

```
rescored/
├── backend/                # Python/FastAPI backend
│   ├── main.py            # REST API + WebSocket server
│   ├── tasks.py           # Celery background workers
│   ├── pipeline.py        # Audio processing pipeline
│   ├── config.py          # Configuration
│   └── requirements.txt   # Python dependencies
├── frontend/              # React frontend
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── store/         # Zustand state management
│   │   └── api/           # API client
│   └── package.json       # Node dependencies
├── docs/                  # Comprehensive documentation
└── docker-compose.yml     # Docker setup
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

**With YourMT3+ (recommended):**
- Simple piano: **80-85% accurate**
- Complex pieces: **70-75% accurate**

**With basic-pitch (fallback):**
- Simple piano: **70-75% accurate**
- Complex pieces: **60-70% accurate**

The interactive editor is designed to make fixing errors easy regardless of which transcription model is used.

## Development

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

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

- **YourMT3+** (KAIST) - State-of-the-art music transcription ([Paper](https://arxiv.org/abs/2407.04822))
- **Demucs** (Meta AI Research) - Source separation
- **basic-pitch** (Spotify) - Fallback audio transcription
- **VexFlow** - Music notation rendering
- **Tone.js** - Web audio synthesis

## Roadmap

- **Phase 1 (MVP)**: ✅ Piano transcription with basic editing
- **Phase 2**: Multi-instrument, advanced editing, PDF export
- **Phase 3**: User accounts, cloud storage, collaboration
- **Phase 4**: Mobile app, real-time collaboration

---

**Note**: This is an educational project. Users are responsible for copyright compliance when transcribing YouTube content.