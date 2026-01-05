# Quick Start: Vercel + HF Spaces Deployment

Deploy Rescored for **free** with WebSocket support in **2 steps**:

## Step 1: Backend on HF Spaces (5 min)

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Fill in:
   - **Name**: `rescored`
   - **SDK**: Docker
   - **Visibility**: Public
4. Once created, push your code:

```bash
git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/rescored
git lfs pull  # Ensure models are downloaded locally
git push hf main
```

Wait for Docker build (5-10 min). Test:

```bash
curl https://YOUR_HF_USERNAME-rescored.hf.space/health
```

## Step 2: Frontend on Vercel (2 min)

1. Go to [vercel.com](https://vercel.com)
2. Click "New Project" → Select this GitHub repo
3. **Build Command**: `cd frontend && npm run build`
4. **Output Directory**: `frontend/dist`
5. Add Environment Variable:
   ```
   VITE_API_URL=https://YOUR_HF_USERNAME-rescored.hf.space
   ```
6. Click "Deploy"

---

## Update Backend CORS

Update HF Spaces secret with your Vercel URL:

```
CORS_ORIGINS=http://localhost:5173,https://YOUR_PROJECT.vercel.app,https://YOUR_HF_USERNAME-rescored.hf.space
```

Then push to rebuild:

```bash
git push hf main
```

---

## You're Done! 🎉

- Frontend: `https://YOUR_PROJECT.vercel.app`
- Backend: `https://YOUR_HF_USERNAME-rescored.hf.space`
- WebSocket connection: Automatic via CORS

**Cost**: $0 (completely free)

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| CORS error | Restart HF Spaces (Space settings → Restart) |
| WebSocket timeout | Space hibernates after 48h - first request slow |
| Git LFS failed | Run `git lfs pull` before pushing to HF |
| Build failed | Check HF Spaces logs (Space settings → Logs) |

For detailed setup, see [DEPLOYMENT.md](DEPLOYMENT.md)
