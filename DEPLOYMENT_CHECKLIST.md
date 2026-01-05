# Deployment Checklist

## Pre-Deployment (Do Once)

- [ ] Clone repo locally
- [ ] Run `git lfs pull` to download models
- [ ] Test backend locally: `cd backend && python -m uvicorn main:app --reload`
- [ ] Test frontend locally: `cd frontend && npm run dev`
- [ ] Confirm transcription works on localhost

## Deploy Backend (HF Spaces)

- [ ] Create HF Spaces account at [huggingface.co](https://huggingface.co)
- [ ] Create new Space:
  - Name: `rescored`
  - SDK: Docker
  - Visibility: Public
- [ ] Add git remote:
  ```bash
  git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/rescored
  ```
- [ ] Push code:
  ```bash
  git lfs pull
  git push hf main
  ```
- [ ] Wait for Docker build (5-10 min)
- [ ] Test health endpoint:
  ```bash
  curl https://YOUR_USERNAME-rescored.hf.space/health
  ```
- [ ] Note your backend URL: `https://YOUR_USERNAME-rescored.hf.space`

## Deploy Frontend (Vercel)

- [ ] Create Vercel account at [vercel.com](https://vercel.com)
- [ ] Import GitHub project
- [ ] Configure build:
  - Build Command: `cd frontend && npm run build`
  - Output Directory: `frontend/dist`
  - Install Command: `cd frontend && npm install --legacy-peer-deps`
- [ ] Add environment variable:
  ```
  VITE_API_URL=https://YOUR_USERNAME-rescored.hf.space
  ```
- [ ] Deploy
- [ ] Test frontend loads at provided Vercel URL
- [ ] Note your frontend URL: `https://your-project.vercel.app`

## Post-Deployment Configuration

- [ ] Update backend CORS:
  ```
  CORS_ORIGINS=http://localhost:5173,https://your-project.vercel.app,https://YOUR_USERNAME-rescored.hf.space
  ```
- [ ] Commit and push to HF Spaces:
  ```bash
  git push hf main
  ```
- [ ] Wait for rebuild (2-3 min)
- [ ] Test WebSocket connection from frontend

## Final Testing

- [ ] Visit frontend URL: `https://your-project.vercel.app`
- [ ] Submit a test transcription job
- [ ] Verify progress updates via WebSocket
- [ ] Check console for any errors
- [ ] Wait for job to complete (~15-20 min)
- [ ] Verify MIDI/score downloads work

## Optional: Auto-Deploy with GitHub Actions

- [ ] Go to your GitHub repo → Settings → Secrets → Actions
- [ ] Add secrets:
  - `HF_USERNAME` = your HF username
  - `HF_TOKEN` = your HF API token
- [ ] Now each push to `main` will auto-deploy to HF Spaces
- [ ] Vercel auto-deploys on GitHub push automatically

## Troubleshooting

| Issue | Action |
|-------|--------|
| CORS error on WebSocket | Restart HF Spaces space, verify CORS_ORIGINS env var |
| Git LFS files not found | Run `git lfs pull` and re-push to HF |
| Vercel build fails | Check build logs, ensure `npm install --legacy-peer-deps` |
| HF Spaces Docker build fails | Check HF Spaces logs, verify Dockerfile.hf exists |
| WebSocket connection timeout | Wait - space may be hibernating (first request slow) |
| "Connection refused" from frontend | Verify backend CORS includes frontend URL |

## Done! 🎉

Your app is now live and fully functional:

- **Frontend**: `https://your-project.vercel.app`
- **Backend API**: `https://YOUR_USERNAME-rescored.hf.space`
- **WebSocket**: `wss://YOUR_USERNAME-rescored.hf.space/api/v1/jobs/{job_id}/stream`

**Cost**: $0/month (completely free)

---

## Next Steps

1. Share the frontend URL with others
2. Monitor HF Spaces for errors
3. Gather feedback and iterate
4. Consider upgrading if you need:
   - Persistent storage
   - Custom domain
   - 24/7 uptime (no hibernation)
