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

### basic-pitch (Chosen)

**Developer**: Spotify;
**License**: Apache 2.0;
**Model Size**: ~30MB;
**Performance**: Good polyphonic transcription

**Pros**:
- Handles polyphonic music (multiple simultaneous notes)
- Trained on diverse dataset (30k+ songs)
- Outputs MIDI with velocities
- Fast (~5-10s per stem)
- Active maintenance

**Cons**:
- Not perfect (~70-80% note accuracy)
- Rhythm quantization can be off
- Struggles with very dense polyphony

**When to Use**: MVP and production (best open-source option)

---

### MT3 (Music Transformer) - Alternative

**Developer**: Google Magenta;
**License**: Apache 2.0;
**Model Size**: ~500MB;
**Performance**: Better than basic-pitch on benchmarks

**Pros**:
- Multi-instrument aware (trained on full mixes)
- Handles multiple instruments simultaneously
- Better rhythm accuracy

**Cons**:
- Much slower (~30-60s per song)
- Larger model
- More complex setup (Transformer architecture)
- Higher computational requirements

**When to Use**: Future enhancement if quality > speed

---

### Omnizart (Alternative)

**Developer**: MCTLab (Taiwan);
**License**: MIT;
**Performance**: Specialized models per instrument

**Pros**:
- Separate models for piano, guitar, drums, vocals
- Good single-instrument accuracy
- Academic backing

**Cons**:
- Need to run different models for each instrument
- Slower overall
- Less active development

**When to Use**: If targeting specific instruments only

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

| Model | Polyphonic | Speed (GPU) | Accuracy | Use Case |
|-------|-----------|-------------|----------|----------|
| basic-pitch | Yes | 5-10s | 70-80% | General-purpose (chosen) |
| MT3 | Yes | 30-60s | 80-85% | High-quality (future) |
| Omnizart | Yes | 15-30s | 75-80% | Instrument-specific |
| Tony | No | 2-5s | 90%+ | Vocals only |

**Decision**: Use basic-pitch for MVP. Consider MT3 for Phase 3 if users demand better quality.

---

## Model Accuracy Expectations

### Realistic Transcription Accuracy

**Simple Piano Melody** (Twinkle Twinkle):
- Note accuracy: 90-95%
- Rhythm accuracy: 80-85%

**Classical Piano** (Chopin Nocturne):
- Note accuracy: 70-80%
- Rhythm accuracy: 60-70%

**Jazz Piano** (Bill Evans):
- Note accuracy: 60-70% (complex chords)
- Rhythm accuracy: 50-60% (swing feel)

**Rock/Pop with Band**:
- Piano separation: 70-80% (depends on mix)
- Note accuracy: 60-70%

**Key Insight**: Transcription won't be perfect. Editor is **critical** for users to fix errors.

---

## Future Model Improvements

### Fine-Tuning

Train basic-pitch on piano-specific dataset:
- Collect 1000+ piano YouTube videos
- Manually correct transcriptions
- Fine-tune model
- Expected improvement: +5-10% accuracy

### Ensemble Models

Combine multiple models:
- Run basic-pitch + MT3
- Merge results using voting or confidence scores
- Expected improvement: +3-5% accuracy
- Cost: 2-3x processing time

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
