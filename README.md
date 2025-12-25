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
- **ML**: Demucs (source separation) + basic-pitch (transcription)

## Quick Start

### Prerequisites

- **Docker Desktop** (recommended) OR:
  - Python 3.11+
  - Node.js 18+
  - Redis 7+
  - FFmpeg
  - (Optional) NVIDIA GPU with CUDA for faster processing

### Option 1: Docker Compose (Recommended)

```bash
# Clone repository
git clone https://github.com/yourusername/rescored.git
cd rescored
```

#### ⚠️ REQUIRED: YouTube Cookies Setup

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
   # Create storage directory
   mkdir -p storage
   
   # Move the exported file (adjust path if needed)
   mv ~/Downloads/youtube.com_cookies.txt ./storage/youtube_cookies.txt
   
   # OR on Windows:
   # move %USERPROFILE%\Downloads\youtube.com_cookies.txt storage\youtube_cookies.txt
   ```

4. **Start Services**
   ```bash
   docker-compose up
   
   # Services will be available at:
   # - Frontend: http://localhost:5173
   # - Backend API: http://localhost:8000
   # - API Docs: http://localhost:8000/docs
   ```

**Verification:**
```bash
docker-compose exec worker ls -lh /app/storage/youtube_cookies.txt
```
You should see the file listed.

**Troubleshooting:**

- **"Please sign in" error**: Make sure you exported from a private/incognito window. Export fresh cookies (don't reuse old ones). Ensure the file is named exactly `youtube_cookies.txt` and isn't empty.

- **File format errors**: The first line should be `# Netscape HTTP Cookie File`. If not, use the browser extension method.

- **Cookies expire quickly**: Export from a NEW incognito window each time. You may need to re-export periodically.

**Security Note:** ⚠️ Never commit `youtube_cookies.txt` to git (it's already in `.gitignore`). Your cookies contain authentication tokens for your Google account—keep them private!

**Why Is This Required?** YouTube implemented bot detection in late 2024 that blocks unauthenticated downloads. Even though our tool is for legitimate transcription purposes, YouTube's systems can't distinguish it from scrapers. By providing your cookies, you're proving you're a real user who has agreed to YouTube's terms of service.

### Option 2: Manual Setup

**Backend**:
```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Start Redis (in separate terminal)
redis-server

# Start Celery worker (in separate terminal)
celery -A tasks worker --loglevel=info

# Start API server
python main.py
```

**Frontend**:
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

## Usage

1. Open [http://localhost:5173](http://localhost:5173)
2. Paste a YouTube URL (piano music recommended for best results)
3. Wait 1-2 minutes for transcription (with GPU) or 10-15 minutes (CPU)
4. Edit the notation in the interactive editor
5. Export as MusicXML or MIDI

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

**With GPU (RTX 3080)**:
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

Transcription is **70-80% accurate** for simple piano music, **60-70%** for complex pieces. The interactive editor is designed to make fixing errors easy.

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
- Check worker logs: `docker-compose logs worker`

**GPU not detected?**
- Install NVIDIA Docker runtime
- Uncomment GPU section in `docker-compose.yml`
- Set `GPU_ENABLED=true` in `.env`

**YouTube download fails?**
- Video may be age-restricted or private
- Check yt-dlp is up to date: `pip install -U yt-dlp`

## Contributing

See [CLAUDE.md](CLAUDE.md) for development guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- **Demucs** (Meta AI Research) - Source separation
- **basic-pitch** (Spotify) - Audio transcription
- **VexFlow** - Music notation rendering
- **Tone.js** - Web audio synthesis

## Roadmap

- **Phase 1 (MVP)**: ✅ Piano transcription with basic editing
- **Phase 2**: Multi-instrument, advanced editing, PDF export
- **Phase 3**: User accounts, cloud storage, collaboration
- **Phase 4**: Mobile app, real-time collaboration

---

**Note**: This is an educational project. Users are responsible for copyright compliance when transcribing YouTube content.