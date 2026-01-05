# Deployment Configuration Complete ✅

This document summarizes the deployment files created for Vercel + HF Spaces.

## Files Created/Modified

### Configuration Files
- **`vercel.json`** - Vercel deployment config (auto-detected build settings)
- **`frontend/.env.example`** - Frontend environment template
- **`.env.hf.example`** - Backend environment for HF Spaces
- **`backend/Dockerfile.hf`** - Docker image optimized for HF Spaces

### Documentation
- **`DEPLOYMENT.md`** - Comprehensive deployment guide (20+ min read)
- **`QUICKSTART_DEPLOY.md`** - 2-step quick deployment (5 min read)

### Backend Updates
- **`app_config.py`** - Updated CORS to support `*.vercel.app` and `*.hf.space`
- **`backend/main.py`** - Added startup logging for deployment info

---

## Architecture Overview

```
┌──────────────────────────────────────┐
│  Vercel Frontend                     │
│  - React + Vite                      │
│  - Free tier ($0)                    │
│  - Fast CDN, auto-deploys from GitHub│
│  https://your-project.vercel.app     │
└─────────────┬────────────────────────┘
              │
              │ HTTP REST API
              │ WebSocket (wss://)
              │
┌─────────────▼────────────────────────┐
│  HF Spaces Backend                   │
│  - FastAPI + Python ML models        │
│  - Free tier with CPU ($0)           │
│  - Auto-hibernates after 48h         │
│  https://user-rescored.hf.space      │
└──────────────────────────────────────┘
```

### Key Features

✅ **WebSocket Support**: Real-time progress updates with Redis pub/sub
✅ **CORS Configured**: Automatic cross-origin requests handling
✅ **Git LFS Compatible**: Models downloaded during Docker build
✅ **CPU-Optimized**: ~15-20 min transcription on HF Spaces CPU
✅ **Zero Cost**: Completely free deployment

---

## Getting Started

### Option 1: Quick Deploy (5 min)
Follow [QUICKSTART_DEPLOY.md](QUICKSTART_DEPLOY.md) for step-by-step instructions.

### Option 2: Detailed Setup (20+ min)
Read [DEPLOYMENT.md](DEPLOYMENT.md) for comprehensive guide with troubleshooting.

### Option 3: Local Development
```bash
# Terminal 1: Backend
cd backend && python -m uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Visit http://localhost:5173
```

---

## Environment Variables

### Frontend (Vercel)
```
VITE_API_URL=https://YOUR_HF_USERNAME-rescored.hf.space
```

### Backend (HF Spaces)
```
CORS_ORIGINS=http://localhost:5173,https://your-project.vercel.app,https://YOUR_HF_USERNAME-rescored.hf.space
REDIS_URL=memory://           # In-memory Redis (no external service)
YOURMT3_DEVICE=cpu            # CPU only (MPS/CUDA not available)
API_PORT=7860                 # Required for HF Spaces
```

---

## Important Notes

1. **Git LFS**: Must run `git lfs pull` locally before pushing to HF Spaces
2. **CORS Wildcard**: Backend accepts `*.vercel.app` and `*.hf.space` by default
3. **WebSocket**: Works across CORS - no special proxy needed
4. **Hibernation**: HF Spaces free tier hibernates after 48h inactivity (first request slow)
5. **Port 7860**: HF Spaces requires FastAPI to listen on port 7860

---

## Performance Expectations

| Stage | Time | Notes |
|-------|------|-------|
| YouTube download | ~10 sec | With LFS models cached |
| Source separation | 8-10 min | Demucs on CPU |
| Transcription | 3-5 min | YourMT3+ on CPU |
| **Total** | **15-20 min** | Acceptable for hobby use |

Your local MPS (~10 min) is faster, but HF Spaces is free!

---

## Scaling Paths (Future)

If you outgrow free tier:

1. **Upgrade HF Spaces** (~$7/mo) → Remove hibernation
2. **Add Vercel Pro** (~$20/mo) → Custom domain, faster builds
3. **Move to VPS** (~$5-20/mo) → Full control, persistent storage

For now, **free tier is perfect** for testing and hobby use.

---

## Support

- **HF Spaces Docs**: [huggingface.co/docs/hub/spaces](https://huggingface.co/docs/hub/spaces)
- **Vercel Docs**: [vercel.com/docs](https://vercel.com/docs)
- **FastAPI WebSocket**: [fastapi.tiangolo.com/advanced/websockets/](https://fastapi.tiangolo.com/advanced/websockets/)

Happy transcribing! 🎵
