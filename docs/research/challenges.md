# Known Technical Challenges & Limitations

## Transcription Accuracy

### Challenge: Imperfect Note Detection

**Problem**: ML models make mistakes:
- Missed notes (false negatives)
- Ghost notes (false positives)
- Wrong pitches (especially in dense chords)
- Timing errors (notes start/end at wrong time)

**Impact**: Users will need to edit ~20-40% of notes for complex music

**Ghost Notes - Sustained Note Decay Artifacts**:
When sustained piano notes fade in the original audio, the ML transcription model can incorrectly detect the fading tail as new note onsets. This creates "ghost notes" appearing in later measures that are actually just the fading remnants of earlier sustained notes.

**Solution Implemented** (as of recent update):
1. **Velocity Envelope Analysis**: Detects and merges false onsets from sustained note decay patterns
   - Identifies decreasing velocity sequences (e.g., 80 → 50 → 35) as likely sustain artifacts
   - Preserves intentional repeated notes (staccato) with similar velocities
   - Configurable via `velocity_decay_threshold`, `sustain_artifact_gap_ms`, `min_velocity_similarity`

2. **Tempo-Adaptive Thresholds**: Adjusts filtering strictness based on detected tempo
   - Fast music (>140 BPM): Stricter onset/velocity thresholds to reduce false positives
   - Slow music (<80 BPM): More permissive to catch soft dynamics
   - Medium tempos: Standard thresholds

3. **Proper MusicXML Ties**: Adds tie notation for sustained notes across measure boundaries
   - Uses music21's tie.Tie class ('start' and 'stop' markers)
   - Improves notation readability and editing experience

**Expected Results**: 70-90% reduction in ghost notes from sustained note decay, while preserving intentional repeated notes (staccato passages).

**General Mitigation**:
1. **Good editor**: Make editing fast and intuitive
2. **Visual feedback**: Highlight low-confidence notes
3. **Set expectations**: Tell users transcription is a starting point, not final output
4. **Pre-processing**: Clean audio (denoise, normalize)
5. **Post-processing**: Quantize rhythms, apply music theory rules

---

### Challenge: Polyphonic Complexity

**Problem**: Piano can play 10+ notes simultaneously. ML models struggle with dense chords.

**Examples**:
- Rachmaninoff: Many notes, complex voicing → accuracy drops to ~60%
- Stride piano: Bass + chord + melody → bass line often lost
- Fast passages: Lots of notes → rhythm becomes mushy

**Mitigation**:
1. Start with simpler music for MVP testing
2. Consider reducing polyphony (keep top 3-4 notes per chord)
3. Warn users that complex music will require more editing

---

### Challenge: Rhythm Quantization

**Problem**: ML models output exact timings (e.g., note starts at 1.237s), but sheet music uses discrete rhythms (quarter, eighth, etc.).

**Quantization Errors**:
- Swing rhythm becomes triplets
- Rubato (tempo variation) → weird note durations
- Grace notes detected as full notes

**Mitigation**:
1. Quantize to 16th note grid (standard)
2. Detect tempo changes before quantizing
3. Let users adjust quantization (8th, 16th, 32nd note grid)

---

## Source Separation Quality

### Challenge: Instrument Bleed

**Problem**: Demucs doesn't perfectly isolate instruments. Piano often leaks into "vocals" or "other" stem.

**Impact**:
- Transcribing "other" stem may include drums/bass artifacts
- Extra notes detected from bleed

**Mitigation**:
1. Only transcribe "other" stem for MVP (assume it's mostly piano)
2. Add confidence threshold filtering (ignore low-amplitude notes)
3. In Phase 2, use 6-stem model (htdemucs_6s) with dedicated piano stem

---

### Challenge: Mix-Dependent Quality

**Problem**: Separation quality depends on recording:
- Studio recordings (dry, well-separated) → excellent separation
- Live recordings (reverb, crowd noise) → poor separation
- YouTube rips (compressed, low quality) → degraded separation

**Mitigation**:
1. Test with diverse YouTube videos to set realistic expectations
2. Warn users if audio quality is low (detect bitrate < 128kbps)
3. Offer "best effort" disclaimer

---

## Processing Time vs. Quality Trade-Off

### Challenge: Slow Processing

**Current Pipeline**:
- Download: 5-15 seconds
- Demucs: 30-60 seconds (GPU) or 8-15 minutes (CPU)
- basic-pitch: 5-10 seconds
- MusicXML: 2-5 seconds
- **Total: 1-2 minutes (GPU) or 10-15 minutes (CPU)**

**User Expectation**: "Instant" results (< 10 seconds)

**Mitigation**:
1. **Set expectations**: Show estimated time (1-2 min) upfront
2. **Progress updates**: WebSocket keeps user engaged
3. **Optimize**: Use GPU, pre-warm workers, batch processing
4. **Future**: Faster models (trade quality for speed)

---

### Challenge: GPU Availability

**Problem**: GPUs are expensive and scarce.

**Costs**:
- Modal A10G GPU: ~$0.60/hour
- 1000 jobs/month × 1 min/job = 16 hours/month = **$10/month**
- 10k jobs/month = **$100/month**

**Mitigation**:
1. **MVP**: Run on local GPU (free)
2. **Production**: Use serverless GPU (pay-per-use)
3. **Optimization**: Keep GPU warm during peak hours, cold-start otherwise
4. **Pricing**: Charge users for processing (e.g., $0.10/song) or subscription

---

## Copyright & Legal Issues

### Challenge: YouTube Content Rights

**Problem**: Users may transcribe copyrighted music without permission.

**Legal Risk**: DMCA takedown notices, copyright infringement lawsuits

**Mitigation**:
1. **Terms of Service**: Users responsible for copyright compliance
2. **DMCA Safe Harbor**: Platform not liable if users misuse (US law)
3. **No storage**: Don't store transcriptions long-term (users download immediately)
4. **Rate limiting**: Prevent mass scraping
5. **Block known copyright**: Detect and block known copyrighted URLs (future)

**Note**: This is similar to yt-dlp, which doesn't face legal issues as a tool. Users are responsible for their use.

---

## File Format Edge Cases


### Challenge: Large Scores Slow Down Frontend

**Problem**: VexFlow renders SVG. Large scores (100+ measures) make DOM huge and slow.

**Impact**:
- Lag when editing
- Slow scrolling
- High memory usage

**Mitigation**:
1. **Pagination**: Render one page at a time
2. **Virtualization**: Only render visible measures (like react-window)
3. **Canvas backend**: Use Canvas instead of SVG for better performance
4. **Simplify**: Reduce polyphony (fewer notes per chord)

---

## Metadata Detection

### Challenge: Key Signature Detection

**Problem**: music21's key detection isn't always accurate, especially for:
- Atonal music
- Modal music (Dorian, Phrygian)
- Key changes mid-song

**Impact**: Wrong key signature displayed, notes have wrong accidentals

**Mitigation**:
1. Use most common key as default (C major, A minor)
2. Let users override key in editor
3. In Phase 2, train ML model to detect key from audio

---

### Challenge: Time Signature Detection

**Problem**: basic-pitch outputs MIDI without time signature info. music21 guesses from note patterns, but often wrong.

**Impact**: Measures have wrong number of beats, bar lines in wrong places

**Mitigation**:
1. Default to 4/4 (most common)
2. Let users change time signature
3. Detect from beat tracking (librosa) in future

---

## User Experience Challenges

### Challenge: Setting Realistic Expectations

**Problem**: Users expect perfect transcription ("just like a human musician")

**Reality**: 70-80% accuracy at best, requires editing

**Mitigation**:
1. **Onboarding**: Show sample before/after (raw vs. edited)
2. **Marketing**: Position as "transcription assistant," not "perfect transcription"
3. **Tutorial**: Teach users how to edit efficiently

---

### Challenge: Complex Editor Learning Curve

**Problem**: Music notation editing is complex. Users need to learn:
- How to add/delete notes
- How to change durations
- Music theory basics (what is a quarter note?)

**Mitigation**:
1. **Tooltips**: Show keyboard shortcuts and help text
2. **Tutorial**: Interactive walkthrough on first use
3. **Presets**: Common editing tasks as buttons (fix rhythm, transpose, etc.)

---

## Infrastructure Challenges

### Challenge: Cold Starts

**Problem**: Serverless GPU workers take 10-20 seconds to cold-start (load model into memory)

**Impact**: First job takes longer, bad UX

**Mitigation**:
1. **Pre-warm**: Keep 1-2 workers hot during peak hours
2. **Progress messages**: "Starting worker..." so user knows why it's slow
3. **Model caching**: Use volumes to cache models (Modal, RunPod)

---

### Challenge: Scaling Costs

**Problem**: GPU costs scale linearly with usage. 10k jobs/month = $100/month in GPU costs.

**Break-Even Analysis**:
- Free tier: Lose money on every job
- $5/month subscription: Need 50 jobs/month to break even
- Pay-per-job ($0.10/song): Break even immediately

**Mitigation**:
1. **Freemium**: Free tier with limits (5 songs/month), paid for more
2. **Optimize**: Reduce processing time to cut costs
3. **Sponsors**: Ads or sponsors for free users

---

## Next Steps

1. Test MVP with diverse YouTube videos to identify which challenges are most critical
2. Prioritize fixes based on user feedback
3. Document workarounds in user guide

See [MVP Scope](../features/mvp.md) for what to build first despite these challenges.
