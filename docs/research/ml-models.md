# ML Model Selection & Research

## Source Separation Models

### Demucs (Chosen)

**Developer**: Meta AI Research;
**License**: MIT;
**Model Size**: ~350MB;
**Performance**: State-of-the-art (MDX Challenge winner 2021)

**Variants**:
- **htdemucs** (4-stem): drums, bass, vocals, other
- **htdemucs_6s** (6-stem): drums, bass, vocals, guitar, piano, other
- **htdemucs_ft** (fine-tuned): Better quality, slightly slower

**Pros**:
- Best quality among open-source models
- Active development
- GPU-accelerated (PyTorch)
- Good documentation

**Cons**:
- Large model size
- Slower than Spleeter (~30-60s per song)
- Requires ~4GB VRAM

**When to Use**: MVP and production (quality > speed)

---

### Spleeter (Alternative)

**Developer**: Deezer;
**License**: MIT;
**Model Size**: ~200MB;
**Performance**: Good, but surpassed by Demucs

**Pros**:
- Faster than Demucs (~10-20s per song)
- Smaller model
- TensorFlow-based

**Cons**:
- Lower quality separation
- No longer actively maintained (last update 2020)
- 2-stem and 5-stem models available

**When to Use**: If speed critical and quality acceptable

---

### X-UMX (Alternative)

**Developer**: Open-source community;
**License**: MIT;
**Performance**: Comparable to early Demucs versions

**Pros**:
- Open-source
- Good quality

**Cons**:
- Slower than both Demucs and Spleeter
- Less documentation

**When to Use**: Research purposes only

---

### Comparison

| Model | Quality (SDR) | Speed (GPU) | Model Size | Maintenance |
|-------|--------------|-------------|------------|-------------|
| Demucs v4 | 9.0 dB | 30-60s | 350MB | Active |
| Spleeter | 6.5 dB | 10-20s | 200MB | Abandoned |
| X-UMX | 7.0 dB | 60-90s | 180MB | Low |

**SDR** = Signal-to-Distortion Ratio (higher is better)

**Decision**: Use Demucs htdemucs for MVP, consider htdemucs_6s for multi-instrument in Phase 2.

---

## Transcription Models

### YourMT3+ (Primary)

**Developer**: KAIST (Korea Advanced Institute of Science and Technology)
**License**: Apache 2.0
**Model Size**: ~536MB (YPTF.MoE+Multi checkpoint)
**Performance**: **State-of-the-art** multi-instrument transcription

**Architecture**:
- Perceiver-TF encoder with Rotary Position Embeddings (RoPE)
- Mixture of Experts (MoE) feedforward layers (8 experts, top-2)
- Multi-channel T5 decoder for 13 instrument classes
- Float16 precision for GPU optimization

**Pros**:
- **80-85% note accuracy** (vs 70% for basic-pitch)
- Multi-instrument aware (13 instrument classes)
- Handles complex polyphony
- Active development (2024)
- Open-source, well-documented
- Optimized for Apple Silicon MPS (14x speedup with float16)
- Good rhythm and onset detection

**Cons**:
- Large model size (~536MB download)
- Requires additional setup (model checkpoint download)
- Slower than basic-pitch (~30-40s per song on GPU)
- Higher memory requirements (~1.1GB VRAM)

**When to Use**: **Production (primary transcriber)** - Best quality for self-hosted solution

**Current Status**: Integrated into main backend, enabled by default with automatic fallback

---

### basic-pitch (Fallback)

**Developer**: Spotify
**License**: Apache 2.0
**Model Size**: ~30MB
**Performance**: Good polyphonic transcription (70% accuracy)

**Pros**:
- Handles polyphonic music (multiple simultaneous notes)
- Trained on diverse dataset (30k+ songs)
- Outputs MIDI with velocities
- Fast (~5-10s per stem)
- Active maintenance
- Lightweight, no setup required

**Cons**:
- Lower accuracy than YourMT3+ (~70% vs 80-85%)
- Rhythm quantization can be off
- Struggles with very dense polyphony

**When to Use**: **Automatic fallback** when YourMT3+ unavailable or disabled

---

### MT3 (Music Transformer) - Not Used

**Developer**: Google Magenta
**License**: Apache 2.0
**Model Size**: ~500MB
**Performance**: Good, but surpassed by YourMT3+

**Why Not Chosen**:
- YourMT3+ offers better accuracy
- Similar computational requirements
- YourMT3+ has better documentation and setup

---

### Omnizart - Removed

**Developer**: MCTLab (Taiwan)
**License**: MIT
**Status**: **Removed from codebase** (replaced by YourMT3+)

**Why Removed**:
- Lower accuracy than YourMT3+ (75-80% vs 80-85%)
- More complex setup with multiple models
- Less active development
- Dual-transcription merging added complexity without accuracy gains

---

### Tony (pYIN) - Alternative

**Developer**: Sonic Visualiser team;
**Performance**: Excellent for monophonic (single note) melody

**Pros**:
- Very accurate for monophonic transcription
- Fast
- Lightweight

**Cons**:
- **Monophonic only** - can't handle chords or polyphony
- Not suitable for piano or guitar

**When to Use**: Vocal melody extraction only

---

### Comparison

| Model | Polyphonic | Speed (GPU) | Accuracy | Status |
|-------|-----------|-------------|----------|--------|
| **YourMT3+** | Yes | 30-40s | **80-85%** | **Primary (Production)** |
| basic-pitch | Yes | 5-10s | 70% | Fallback |
| MT3 | Yes | 30-60s | 75-80% | Not used |
| Omnizart | Yes | 15-30s | 75-80% | Removed |
| Tony | No | 2-5s | 90%+ | Vocals only |

**Decision**: YourMT3+ as primary transcriber with automatic fallback to basic-pitch for reliability.

---

## Model Accuracy Expectations

### Realistic Transcription Accuracy (with YourMT3+)

**Simple Piano Melody** (Twinkle Twinkle):
- Note accuracy: **90-95%** (YourMT3+) / 85-90% (basic-pitch)
- Rhythm accuracy: **85-90%** (YourMT3+) / 75-80% (basic-pitch)

**Classical Piano** (Chopin Nocturne):
- Note accuracy: **75-85%** (YourMT3+) / 65-75% (basic-pitch)
- Rhythm accuracy: **70-75%** (YourMT3+) / 55-65% (basic-pitch)

**Jazz Piano** (Bill Evans):
- Note accuracy: **70-75%** (YourMT3+) / 55-65% (basic-pitch)
- Rhythm accuracy: **60-70%** (YourMT3+) / 45-55% (basic-pitch)

**Rock/Pop with Band**:
- Piano separation: 70-80% (depends on Demucs quality)
- Note accuracy: **70-75%** (YourMT3+) / 55-65% (basic-pitch)

**Key Insight**: YourMT3+ provides 10-15% better accuracy than basic-pitch, but transcription still won't be perfect. Editor is **critical** for users to fix errors.

---

## Future Model Improvements

### Fine-Tuning YourMT3+

Train on piano-specific dataset:
- Collect 1000+ piano YouTube videos with ground truth
- Fine-tune YourMT3+ checkpoint on piano-only data
- Expected improvement: +3-5% accuracy for piano
- Cost: GPU compute for training

### Ensemble Models (Not Currently Used)

Previously attempted basic-pitch + omnizart merging:
- **Result**: Removed due to complexity without significant accuracy gain
- **Learning**: YourMT3+ alone provides better results than merged basic-pitch + omnizart
- **Future**: Could revisit with YourMT3+ + MT3 ensemble if needed

### Post-Processing

Improve rhythm with music theory rules:
- Quantize to nearest 16th note
- Enforce measure boundaries
- Detect time signature from patterns
- Expected improvement: +10-15% rhythm accuracy

---

## Benchmarks to Track

When testing models, measure:
1. **Note Onset Accuracy**: % of notes detected at correct time
2. **Pitch Accuracy**: % of notes with correct pitch
3. **Duration Accuracy**: % of notes with correct duration
4. **Harmonic Accuracy**: % of chords correctly identified

**Tools**: mir_eval library (Python)

---

## Next Steps

1. Test Demucs + basic-pitch on [sample videos](../features/mvp.md#testing-strategy)
2. Measure accuracy and processing time
3. Identify failure modes
4. Document in [Challenges](challenges.md)

See [Backend Pipeline](../backend/pipeline.md) for implementation details.
