# Deployment Quick Reference Card

## 🎯 2-Step Deployment Summary

### Step 1: Backend (HF Spaces)
```bash
# Create Space at huggingface.co/spaces
# Set SDK = Docker, Visibility = Public

# Then:
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/rescored
git lfs pull
git push hf main

# Result: https://YOUR_USERNAME-rescored.hf.space
```

### Step 2: Frontend (Vercel)
```bash
# Create project at vercel.com
# Connect GitHub repo
# Add env var: VITE_API_URL=https://YOUR_USERNAME-rescored.hf.space
# Deploy

# Result: https://your-project.vercel.app
```

---

## 🔗 Connection Flow

```
User Browser
    ↓
[Vercel Frontend] ←--HTTP REST-→ [HF Spaces Backend]
    ↓
React App      ←--WebSocket-→ FastAPI + Python ML

https://your-project.vercel.app
https://YOUR_USERNAME-rescored.hf.space
```

---

## ⚙️ Key Configuration

| Component | Default | Example |
|-----------|---------|---------|
| Frontend URL | Vercel auto | `https://rescored.vercel.app` |
| Backend URL | HF Spaces auto | `https://user-rescored.hf.space` |
| API Port | 7860 | Set by HF Spaces |
| Device | CPU | Auto-detected |
| Redis | In-memory | `memory://` |

---

## 📋 Required Files

| File | Purpose | Status |
|------|---------|--------|
| `vercel.json` | Vercel config | ✅ Created |
| `backend/Dockerfile.hf` | HF Spaces image | ✅ Created |
| `.env.hf.example` | Backend env template | ✅ Created |
| `frontend/.env.example` | Frontend env template | ✅ Exists |
| `.github/workflows/deploy-hf.yml` | Auto-deploy (optional) | ✅ Created |

---

## ⏱️ Timeline

| Step | Time | Action |
|------|------|--------|
| 1 | 5 min | Create HF Spaces, push code |
| 2 | 10 min | Docker builds on HF |
| 3 | 2 min | Create Vercel, connect GitHub |
| 4 | 2 min | Add env var, deploy |
| 5 | 3 min | Test endpoint |
| **Total** | **~22 min** | **Full deployment** |

---

## 🚨 Critical Steps (Don't Skip!)

1. ✅ **`git lfs pull`** before pushing to HF
2. ✅ **Port 7860** for HF Spaces (don't change)
3. ✅ **CORS origins** include `*.vercel.app`
4. ✅ **`VITE_API_URL`** env var on Vercel
5. ✅ **Test `/health`** endpoint after deploy

---

## 🧪 Test Checklist

```
□ Backend health: curl https://YOUR_USERNAME-rescored.hf.space/health
□ Frontend loads: Visit https://your-project.vercel.app
□ API works: Submit a job from frontend
□ WebSocket: Check browser console for "Connected"
□ Job completes: Wait ~15-20 min for result
□ Download works: Verify MIDI/score download
```

---

## 📞 If Something Goes Wrong

| Error | Fix |
|-------|-----|
| `CORS error` | Restart HF Space, check CORS_ORIGINS env var |
| `Git LFS failed` | Run `git lfs pull` again before push |
| `Vercel build failed` | Check build logs, ensure `npm install --legacy-peer-deps` |
| `WebSocket timeout` | Space is hibernating (wait 30 sec for first request) |
| `Port issues` | HF Spaces requires port 7860 (hardcoded in Dockerfile.hf) |

---

## 💰 Cost Breakdown

```
Vercel Frontend:  $0/month
HF Spaces Backend: $0/month
---
Total:            $0/month 🎉
```

Scaling later?
- HF Spaces Pro: ~$7/mo (no hibernation)
- Vercel Pro: ~$20/mo (custom domain)

---

## 📚 Documentation Map

```
START HERE ──→ DEPLOYMENT_README.md
                 ├─→ QUICKSTART_DEPLOY.md (5 min)
                 ├─→ DEPLOYMENT_CHECKLIST.md (10 min)
                 ├─→ DEPLOYMENT.md (20+ min, detailed)
                 └─→ This file (quick reference)
```

---

## 🎵 You're Ready!

Pick your guide:
1. **5 min?** → QUICKSTART_DEPLOY.md
2. **10 min?** → DEPLOYMENT_CHECKLIST.md
3. **Full details?** → DEPLOYMENT.md

All paths lead to the same working deployment! 🚀
