# 🚀 Deployment Guide Index

You now have everything set up for **free deployment** with Vercel + HF Spaces!

## 📚 Documentation Files

### Start Here (Pick One)

| File | Time | Best For |
|------|------|----------|
| **[QUICKSTART_DEPLOY.md](QUICKSTART_DEPLOY.md)** | 5 min | Just want to deploy now |
| **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** | 10 min | Step-by-step checklist |
| **[DEPLOYMENT.md](DEPLOYMENT.md)** | 20 min | Full details + troubleshooting |

### Reference

| File | Purpose |
|------|---------|
| **[DEPLOYMENT_COMPLETE.md](DEPLOYMENT_COMPLETE.md)** | Summary of all created files |

---

## 🔧 Configuration Files

### Environment
- **`.env.hf.example`** - Backend environment for HF Spaces
- **`frontend/.env.example`** - Frontend environment (already exists)

### Deployment
- **`vercel.json`** - Vercel build configuration
- **`backend/Dockerfile.hf`** - Docker image for HF Spaces

### GitHub Actions (Optional)
- **`.github/workflows/deploy-hf.yml`** - Auto-deploy to HF Spaces on git push
- **`.github/workflows/setup-secrets.yml`** - Setup instructions

---

## 🏗️ Architecture

```
GitHub (Your Code)
    ↓
    ├→ Vercel Frontend
    │  (Auto-deploy on push)
    │
    └→ HF Spaces Backend
       (Auto-deploy on push, if you set up GitHub Actions)
```

---

## ⚡ Quick Deploy Path

```bash
# 1. Ensure models are downloaded
git lfs pull

# 2. Create HF Spaces (browser)
#    https://huggingface.co/spaces

# 3. Push backend to HF
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/rescored
git push hf main

# 4. Create Vercel project (browser)
#    https://vercel.com

# 5. Add environment variable to Vercel
VITE_API_URL=https://YOUR_USERNAME-rescored.hf.space

# 6. Update backend CORS and push
git push hf main
```

Done! 🎉

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| Frontend load | ~1 sec (Vercel CDN) |
| Transcription time | ~15-20 min (HF Spaces CPU) |
| Cost | **$0/month** |
| Hibernation | 48h inactivity (first request slow) |

---

## 💡 Key Features

✅ WebSocket real-time progress updates
✅ CORS configured for Vercel + HF Spaces
✅ Git LFS support (models auto-downloaded)
✅ Health checks (/health endpoint)
✅ Rate limiting on API
✅ Error handling + retries
✅ Automatic deployments (optional)

---

## 🚨 Important Notes

1. **Must run `git lfs pull` before pushing to HF Spaces**
2. **Port 7860 required for HF Spaces**
3. **CPU only on free HF Spaces tier**
4. **CORS already configured for `*.vercel.app` and `*.hf.space`**
5. **WebSocket works automatically via CORS**

---

## 📞 Support

- **First time?** → Read [QUICKSTART_DEPLOY.md](QUICKSTART_DEPLOY.md)
- **Stuck?** → Check [DEPLOYMENT.md](DEPLOYMENT.md#troubleshooting)
- **Details?** → See [DEPLOYMENT_COMPLETE.md](DEPLOYMENT_COMPLETE.md)

---

## 🎯 Next Steps

1. Pick your guide above (QUICKSTART or CHECKLIST)
2. Follow the steps
3. Test your deployment
4. Share the frontend URL with friends!

Happy deploying! 🎵✨
