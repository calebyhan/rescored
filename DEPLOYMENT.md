# Deployment Guide: Vercel + Hugging Face Spaces

This guide covers deploying Rescored with:
- **Frontend**: Vercel (free tier)
- **Backend**: Hugging Face Spaces (free tier)
- **Communication**: WebSocket over CORS

## Prerequisites

- GitHub account with this repo pushed
- Hugging Face account (free)
- Vercel account (free) - optional, or use `vercel.json` for easy setup

---

## Step 1: Deploy Backend on Hugging Face Spaces

### 1.1 Create a Space

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. **Name**: `rescored` (or your preferred name)
4. **License**: MIT
5. **Space SDK**: Docker
6. **Visibility**: Public (for Vercel to access)
7. Click "Create Space"

### 1.2 Connect Repository

You can either:

**Option A: Push directly to HF Spaces (Recommended)**

```bash
# Clone your repo if not already
git clone <your-github-repo>
cd rescored

# Add HF Spaces as remote
git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/rescored

# Ensure Git LFS files are present locally
git lfs pull

# Push to HF Spaces (will auto-build)
git push hf main
```

**Option B: Connect GitHub (Auto-sync)**

In Space settings → "Sync with GitHub" and select your repository.

### 1.3 Configure Environment Variables

In Space settings → "Repository secrets", add:

```
CORS_ORIGINS=http://localhost:5173,https://yourdomain.vercel.app,https://YOUR_HF_USERNAME-rescored.hf.space
REDIS_URL=memory://
YOURMT3_DEVICE=cpu
API_PORT=7860
```

### 1.4 Verify Deployment

Wait for the Docker build to complete (5-10 minutes). Then test:

```bash
curl https://YOUR_HF_USERNAME-rescored.hf.space/health
```

Should return `{"status": "ok"}` or similar.

---

## Step 2: Deploy Frontend on Vercel

### 2.1 Connect GitHub

1. Go to [vercel.com](https://vercel.com)
2. Click "New Project"
3. Select your GitHub repository
4. Click "Import"

### 2.2 Configure Build Settings

Vercel should auto-detect Vite settings. Manually set if needed:

- **Build Command**: `cd frontend && npm run build`
- **Output Directory**: `frontend/dist`
- **Install Command**: `cd frontend && npm install --legacy-peer-deps`
- **Node Version**: 18

### 2.3 Add Environment Variables

In Project Settings → "Environment Variables", add:

```
VITE_API_URL=https://YOUR_HF_USERNAME-rescored.hf.space
```

### 2.4 Deploy

Click "Deploy". Vercel will build and deploy automatically.

Your frontend is now live at `https://your-project.vercel.app`

---

## Step 3: Update CORS on Backend

Update the HF Spaces environment variable:

```
CORS_ORIGINS=http://localhost:5173,https://your-project.vercel.app,https://YOUR_HF_USERNAME-rescored.hf.space
```

Push to HF Spaces to rebuild:

```bash
git push hf main
```

---

## Architecture

```
┌─────────────────────────────────┐
│  Vercel Frontend                │
│  (React + Vite)                 │
│  https://your-project.vercel.app│
└────────────┬────────────────────┘
             │
             │ HTTP REST + WebSocket
             │
┌────────────▼────────────────────┐
│  HF Spaces Backend              │
│  (FastAPI + YourMT3+)           │
│  https://user-rescored.hf.space │
└─────────────────────────────────┘
```

---

## Performance Notes

### Transcription Time on CPU (HF Spaces)

- YouTube download: ~10 seconds
- Source separation (Demucs): ~8-10 minutes
- Transcription (YourMT3+): ~3-5 minutes
- **Total**: ~15-20 minutes per job

This is acceptable for hobby use on free tier.

### Model Storage

- YourMT3+ checkpoint: ~536 MB (downloaded on first use)
- Demucs models: ~100 MB
- Total: ~650 MB (included in Docker image)

---

## WebSocket Connection Flow

1. **Frontend** submits transcription job via HTTP POST to `/api/v1/transcribe`
2. **Backend** returns `job_id` and `websocket_url`
3. **Frontend** connects to WebSocket at `/api/v1/jobs/{job_id}/stream`
4. **Backend** publishes progress updates via Redis pub/sub → WebSocket
5. Frontend receives real-time progress updates

**Note**: WebSocket works across CORS boundaries because:
- Vercel frontend makes request to HF Spaces
- HF Spaces backend allows both origins in CORS
- No special proxy needed

---

## Troubleshooting

### "CORS error on WebSocket"

- Check `CORS_ORIGINS` includes your Vercel domain
- Restart HF Spaces space (Settings → Space settings → Restart space)

### "WebSocket connection timeout"

- HF Spaces spaces hibernate after 48 hours of inactivity
- First request after hibernation will be slow (~30 seconds)
- Subsequent requests are normal

### "Git LFS files not found"

- Ensure you ran `git lfs pull` before pushing to HF Spaces
- Or: Configure HF Spaces to auto-pull LFS (usually enabled by default)

### "Out of memory on transcription"

- HF Spaces free tier has limited RAM
- Try disabling ensemble transcription in config
- Or use less complex audio files

---

## Cost Breakdown

| Component | Cost | Notes |
|-----------|------|-------|
| Vercel Frontend | $0 | Generous free tier |
| HF Spaces Backend | $0 | Free tier with 48h hibernation |
| **Total** | **$0** | Completely free for hobby use |

**Optional**: 
- If you need persistent backend, upgrade HF Spaces Pro (~$7/mo)
- If you need custom domain, use Vercel Pro (~$20/mo)

---

## Local Development

To test locally before deploying:

```bash
# Terminal 1: Backend
cd backend
python -m uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Then visit `http://localhost:5173`

---

## Next Steps

1. Test the deployment with a simple song
2. Monitor HF Spaces logs for errors
3. Iterate on frontend UI/UX
4. Consider adding user authentication if needed
5. Scale to paid tier if traffic increases
