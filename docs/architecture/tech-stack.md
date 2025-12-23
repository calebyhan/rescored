# Technology Stack & Decisions

## Overview

This document details the technology choices for Rescored, including alternatives considered and trade-offs that informed each decision.

## Frontend Technologies

### UI Framework: React

**Chosen**: React 18+

**Why**:
- Largest ecosystem for music-related JavaScript libraries
- VexFlow and Tone.js have good React integration patterns
- Component model fits notation editing (each measure/staff as component)
- Excellent dev tooling (React DevTools, Fast Refresh)
- Familiarity and hiring pool

**Alternatives Considered**:

| Option | Pros | Cons | Why Not Chosen |
|--------|------|------|----------------|
| Vue 3 | Simpler API, lighter weight | Smaller ecosystem for music libraries | Less community support for music notation |
| Svelte | Excellent performance, less boilerplate | Immature ecosystem | Risk for complex audio/notation needs |
| Vanilla JS | Full control, no framework overhead | Much more code to manage state | Notation editing is complex, need good state management |

**Decision**: React's ecosystem and component model outweigh its learning curve.

---

### Notation Rendering: VexFlow

**Chosen**: VexFlow 4.x

**Why**:
- Pure JavaScript, runs entirely in browser
- Programmatic API for rendering notation (good for editing)
- Generates clean SVG that we can attach event listeners to
- Active maintenance, good documentation
- Used in production by Flat.io, Soundslice

**Alternatives Considered**:

| Option | Pros | Cons | Why Not Chosen |
|--------|------|------|----------------|
| OpenSheetMusicDisplay (OSMD) | Better MusicXML support, prettier output | Harder to build editing on top, heavier bundle | Optimized for display, not editing |
| music21.js | Pythonic API, good theory support | Limited rendering, not designed for web | Better as backend tool |
| abcjs | Lightweight, simple syntax | ABC notation less standard than MusicXML | MusicXML is industry standard |
| Custom renderer | Full control | Months of work to match VexFlow quality | Not worth reinventing wheel |

**Decision**: VexFlow strikes the best balance between rendering quality and edit-ability.

---

### Audio Playback: Tone.js

**Chosen**: Tone.js 14+

**Why**:
- High-level abstractions over Web Audio API
- Built-in scheduling for precise timing
- Multiple synthesis methods (samples, FM, AM)
- Transport controls (play, pause, seek, loop)
- MIDI playback support via `Tone.Sampler`

**Alternatives Considered**:

| Option | Pros | Cons | Why Not Chosen |
|--------|------|------|----------------|
| Web Audio API (raw) | Maximum control, no dependencies | Requires lots of boilerplate | Too low-level for quick MVP |
| Howler.js | Simple API, good for sound effects | Not designed for music, no MIDI | No timing control for notation sync |
| MIDIjs | Simple MIDI playback | Limited synthesis, GM soundfonts | Lower quality sound than Tone.js samplers |
| SoundFont2.js | Authentic GM sounds | Large file sizes, older API | Tone.js can load SoundFonts if needed |

**Decision**: Tone.js provides the right abstraction level for MIDI playback with good sound quality.

---

### State Management: Zustand

**Chosen**: Zustand (tentative)

**Why**:
- Minimal boilerplate compared to Redux
- Works well with React hooks
- Good for global state (notation data, playback state)
- Small bundle size (~1KB)

**Alternatives Considered**:

| Option | Pros | Cons | Why Not Chosen |
|--------|------|------|----------------|
| Redux Toolkit | Battle-tested, great DevTools | More boilerplate, steeper learning curve | Overkill for MVP |
| React Context | Built-in, no deps | Performance issues with frequent updates | Notation editing has lots of updates |
| Jotai/Recoil | Atomic state, very modern | Newer, smaller ecosystem | Zustand more proven |
| Local state only | Simplest | Hard to share state across components | Need global notation state |

**Decision**: Zustand for MVP, can migrate to Redux if needed later.

---

## Backend Technologies

### API Framework: FastAPI

**Chosen**: FastAPI (Python 3.11+)

**Why**:
- Async Python (critical for WebSocket connections)
- Auto-generated OpenAPI docs (Swagger UI)
- Native WebSocket support
- Type hints for better code quality
- Integrates well with Python ML libraries (Demucs, basic-pitch)
- Excellent performance (on par with Node.js)

**Alternatives Considered**:

| Option | Pros | Cons | Why Not Chosen |
|--------|------|------|----------------|
| Node.js (Express) | Async by default, JavaScript everywhere | Worse ML library support | ML models are Python-first |
| Flask | Simple, well-known | No async support, manual WebSocket setup | FastAPI is modern Flask |
| Django | Full-featured, admin panel | Heavy, slower, less async support | Overkill for API-only service |
| Go (Gin/Fiber) | Excellent performance | Weaker ML ecosystem, FFI overhead | Python has better audio/ML tools |

**Decision**: FastAPI combines async support with Python's ML ecosystem.

---

### Task Queue: Celery + Redis

**Chosen**: Celery 5.x with Redis as broker

**Why**:
- Industry standard for async Python tasks
- Reliable, battle-tested in production
- Priority queues (transcription vs. export jobs)
- Automatic retries and error handling
- Redis is fast, simple, good for both queue and caching

**Alternatives Considered**:

| Option | Pros | Cons | Why Not Chosen |
|--------|------|------|----------------|
| RQ (Redis Queue) | Simpler API than Celery | Fewer features, less ecosystem | Need advanced features (priorities, chaining) |
| Dramatiq | Modern, better API than Celery | Smaller community, less mature | Celery's ecosystem worth the complexity |
| BullMQ (Node) | Excellent, modern | Requires Node backend | Using Python for ML libraries |
| Cloud tasks (GCP/AWS) | Managed service, no infrastructure | Vendor lock-in, cold starts | Local dev first |

**Decision**: Celery's maturity and feature set justify the learning curve.

---

## ML/Audio Technologies

### Source Separation: Demucs

**Chosen**: Demucs v4 (Meta Research)

**Why**:
- State-of-the-art audio separation quality (MDX leaderboard winner)
- 4-stem model (drums, bass, vocals, other) is good default
- 6-stem model available (drums, bass, vocals, guitar, piano, other)
- Open-source, MIT license
- PyTorch model, runs on GPU

**Alternatives Considered**:

| Option | Pros | Cons | Why Not Chosen |
|--------|------|------|----------------|
| Spleeter | Faster, lighter | Lower quality, no longer actively developed | Quality matters more than speed |
| X-UMX | Open-source, good quality | Slower than Demucs | Demucs quality worth extra time |
| commercial APIs | No GPU needed, better quality | Costly ($0.10+/song), privacy concerns | Local processing preferred for MVP |

**Decision**: Demucs offers best quality for a self-hosted solution.

---

### Transcription: basic-pitch

**Chosen**: basic-pitch (Spotify)

**Why**:
- Polyphonic transcription (multiple notes at once)
- Trained on large dataset (30k+ songs)
- Open-source, Apache 2.0 license
- Outputs MIDI with note velocities
- Actively maintained by Spotify

**Alternatives Considered**:

| Option | Pros | Cons | Why Not Chosen |
|--------|------|------|----------------|
| MT3 (Music Transformer) | Google's latest, multi-instrument aware | Slower, larger model, harder to run | basic-pitch faster for MVP |
| Omnizart | Multi-instrument, good documentation | More complex setup, slower | basic-pitch simpler |
| Tony (pYIN) | Excellent for monophonic | Only monophonic | Need polyphonic support |
| commercial APIs | Better quality | Expensive, privacy | Local processing preferred |

**Decision**: basic-pitch is the best open-source polyphonic transcription model.

---

## File Formats

### Primary Format: MusicXML

**Chosen**: MusicXML 4.0

**Why**:
- Industry-standard interchange format
- Supported by all major notation software (Finale, Sibelius, MuseScore, Dorico)
- Preserves notation semantics (clefs, articulations, lyrics)
- Human-readable XML (good for debugging)
- VexFlow can parse it directly

**Alternatives Considered**:

| Option | Pros | Cons | Why Not Chosen |
|--------|------|------|----------------|
| MIDI | Universal, compact, great for playback | No notation info (clefs, staff layout) | Complementary, not replacement |
| MEI (Music Encoding Initiative) | More expressive than MusicXML | Less tool support, steeper learning curve | MusicXML more widely adopted |
| ABC Notation | Human-readable text | Limited notation features, less standard | Better for folk music than general use |
| Proprietary (Finale .musx) | Native to notation software | Requires specific tools to read | MusicXML is open standard |

**Decision**: MusicXML is the universal standard for notation exchange.

---

### Intermediate Format: MIDI

**Chosen**: MIDI 1.0 (SMF Type 1)

**Why**:
- Universal output format from transcription models
- Easy to convert to MusicXML
- Useful for export option
- Tone.js plays MIDI directly

**Why Not Sufficient Alone**:
- Lacks notation semantics (clefs, key signatures, measure boundaries)
- No staff layout information
- Ambiguous rhythmic notation

---

## Development Tools

### Python Package Manager: uv or Poetry

**Chosen**: uv (recommended) or Poetry

**Why**:
- Reproducible builds with lock files
- Virtual environment management
- Faster than pip for large dependencies (PyTorch, etc.)

---

### Frontend Build Tool: Vite

**Chosen**: Vite

**Why**:
- Fast dev server with HMR
- Modern, best-in-class DX
- Great for React apps
- Smaller bundles than Webpack

---

### Containerization: Docker

**Chosen**: Docker + Docker Compose

**Why**:
- Consistent dev environment across machines
- Easy GPU passthrough for Demucs
- Simplifies Redis, API, worker orchestration

---

## Infrastructure (Future)

### Frontend Hosting: Vercel

**Recommended**: Vercel

**Why**:
- Excellent React/Vite support
- Global CDN
- Preview deployments for PRs
- Free tier is generous

**Alternative**: Netlify, Cloudflare Pages, AWS S3 + CloudFront

---

### Backend Hosting: Cloud Run or Modal

**Recommended**: Modal (for GPU workers)

**Why**:
- Serverless GPU containers
- Pay-per-use (no idle GPU cost)
- Fast cold starts
- Good Python support

**Alternative**: AWS ECS with GPU instances, GCP Cloud Run (CPU only, need separate GPU service)

---

### Database: PostgreSQL (future)

**Not needed for MVP** (using Redis for job state)

**When to add**:
- User accounts and auth
- Persistent job history
- Sharing features

---

## Decision Criteria Summary

When evaluating technologies, we prioritized:

1. **Quality Over Speed**: Better transcription/rendering > faster processing
2. **Open Source First**: Avoid vendor lock-in, control costs
3. **Python for ML**: Ecosystem too strong to ignore
4. **Standard Formats**: MusicXML/MIDI over proprietary
5. **Proven Tech**: Prefer mature libraries over bleeding edge
6. **Developer Experience**: Good docs and tooling matter

## Trade-off Examples

### Demucs vs. Spleeter
- **Chose Demucs**: Better quality worth 2x processing time
- **Rationale**: Users wait minutes anyway, quality is paramount

### VexFlow vs. OSMD
- **Chose VexFlow**: Editing capability > slightly better rendering
- **Rationale**: Users will edit output, need programmatic access

### FastAPI vs. Django
- **Chose FastAPI**: Async WebSocket support > admin panel
- **Rationale**: Real-time updates critical, don't need admin UI

## Next Steps

See [Deployment Strategy](deployment.md) for how these technologies deploy.
