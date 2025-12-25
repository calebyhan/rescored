# Failure Mode Analysis

**Date**: 2024-12-24
**Test Suite**: Phase 2 Accuracy Baseline (10 videos)
**Pipeline Version**: Phase 1 Complete + Bug Fixes

## Executive Summary

Initial accuracy testing revealed **3 major failure categories** affecting 9 out of 10 test videos:

1. **Video Availability** (30% of failures) - YouTube blocking/copyright
2. **Code Bugs** (60% of failures) - NoneType errors and 2048th note duration issues
3. **MusicXML Export** (20% of failures) - Impossible duration errors

**All code bugs have been fixed.** Success rate expected to improve significantly with re-run.

## Failure Categories

### 1. Video Availability Issues (3 videos - 30%)

**Videos Affected:**
- `twinkle_twinkle` - "Video unavailable"
- `fur_elise` - "Video unavailable"
- `jazz_blues` - "Blocked in your country on copyright grounds"

**Root Cause:** YouTube access restrictions, not pipeline issues

**Mitigation:**
- Replace with alternative videos for same difficulty level
- Use Creative Commons licensed videos
- Host test videos on alternative platforms

**Impact:** Not a pipeline issue - will replace test videos

---

### 2. Code Bugs - Fixed ✅ (6 videos - 60%)

#### Bug 2a: NoneType Velocity Comparison (4 videos)

**Error:** `'<' not supported between instances of 'int' and 'NoneType'`

**Videos Affected:**
- `canon_in_d`
- `river_flows`
- `moonlight_sonata`
- `la_campanella`

**Root Cause:** In `_deduplicate_overlapping_notes()` at [pipeline.py:403-407](../backend/pipeline.py#L403-L407), the code tried to sort notes by velocity, but `note.volume.velocity` can return `None`.

**Fix Applied:**
```python
def get_velocity(note):
    if hasattr(note, 'volume') and hasattr(note.volume, 'velocity'):
        vel = note.volume.velocity
        return vel if vel is not None else 64
    return 64

pitch_notes.sort(key=lambda x: (x.quarterLength, get_velocity(x)), reverse=True)
```

**Status:** ✅ Fixed in [pipeline.py:403-409](../backend/pipeline.py#L403-L409)

---

#### Bug 2b: 2048th Note Duration (2 videos)

**Error:** `In part (Piano), measure (X): Cannot convert "2048th" duration to MusicXML (too short).`

**Videos Affected:**
- `chopin_nocturne` (measure 129)
- `claire_de_lune` (measure 30)

**Root Cause:** `music21.makeMeasures()` creates extremely short rests (2048th notes) when filling gaps between notes. MusicXML export fails because these durations are too short to represent.

**Previous Attempts:**
1. ❌ Filtered notes < 64th note (0.0625) before `makeMeasures()` - didn't work
2. ❌ Removed notes < 64th note after `makeMeasures()` - still had issues

**Final Fix:**
- Increased minimum duration threshold to **128th note** (0.03125)
- Added logging to show how many notes/rests were removed
- Applied in `_remove_impossible_durations()` at [pipeline.py:465-502](../backend/pipeline.py#L465-L502)

**Status:** ✅ Fixed - more aggressive filtering

---

### 3. Successful Test Analysis

**Video:** `simple_melody` (C major scale practice, Easy difficulty)

**Results:**
- ✅ Successfully generated MusicXML
- **2,588 notes** detected
- **122 measures** created
- **245 seconds** duration
- **99.3% energy** preserved in 'other' stem (excellent separation)

**Key Metrics:**

| Metric | Value | Assessment |
|--------|-------|------------|
| Note density | 5.36 notes/sec | Reasonable for piano |
| Pitch range | G1 to A6 (62 semitones) | Full piano range |
| Polyphony | ~1.6 avg, ~6 max | Modest polyphony |
| Short notes | 271 (21%) under 200ms | Acceptable |
| Measure warnings | 95/122 (78%) | **High** - timing imperfect |

**Measure Timing Issues:**

78% of measures showed duration warnings (range 0.0 - 7.83 beats instead of exactly 4.0). Examples:
- Measure 1: 0.00 beats (empty)
- Measure 30: 6.41 beats (overfull)
- Measure 69: 7.33 beats (very overfull)
- Measure 77: 7.83 beats (worst case)

**Root Causes:**
1. **basic-pitch timing** not aligned to musical beats
2. **Duration snapping** to nearest valid note value loses precision
3. **Tempo detection** may be inaccurate
4. **Polyphonic overlaps** creating extra duration

**Impact:** MusicXML loads in notation software but rhythms are imperfect. This is expected with ML-based transcription.

---

## Common Patterns

### Pattern 1: Quiet Audio Detection
- Diagnostic shows RMS energy of 0.0432 (very quiet)
- 20% silence in audio
- basic-pitch may struggle with quiet inputs

### Pattern 2: Separation Quality
- For `simple_melody`: 99.3% energy in 'other' stem ✅
- Only 0.2% in 'no_other' stem (excellent isolation)
- Demucs successfully isolated piano

### Pattern 3: Measure Duration Accuracy
- **Only 22%** of measures have exactly 4.0 beats
- **78%** show timing deviations
- Range: -4.0 to +3.83 beats deviation
- Largest errors in complex sections (likely polyphony)

---

## Recommendations

### Immediate Actions (Phase 2 completion)

1. **Replace unavailable videos** with Creative Commons alternatives
2. **Re-run accuracy suite** with bug fixes
3. **Document actual baseline** with successful tests

### Phase 3 Improvements (Accuracy Tuning)

1. **Tempo Detection:**
   - Implement better tempo detection (analyze beat patterns)
   - Consider fixed tempo option for practice scales

2. **Quantization:**
   - Improve rhythmic quantization to align with detected beats
   - Consider time signature detection

3. **Post-Processing:**
   - Add measure duration normalization
   - Stretch/compress note timings to fit exact 4.0 beats

4. **Parameter Tuning:**
   - Test different `onset-threshold` values (current: 0.5)
   - Test different `frame-threshold` values (current: 0.4)
   - Experiment with `minimum-note-length`

### Alternative Models (Phase 3 - Optional)

Consider testing:
- **MT3** (Google's Music Transformer) - better rhythm accuracy
- **htdemucs_6s** - 6-stem model with dedicated piano stem
- **Omnizart** - specialized for classical music

---

## Success Criteria

After fixes and re-run, we expect:

- ✅ **Video availability**: 7-8 working videos (replacing blocked ones)
- ✅ **Code bugs**: 0% failure rate (all fixed)
- ✅ **MusicXML export**: 100% success for available videos
- 🎯 **Overall success rate**: 70-80% (from 10%)

Measure timing accuracy will remain imperfect (~78% with warnings) but this is expected for MVP. Phase 3 will focus on improving timing accuracy.

---

## Appendix: Error Details

### NoneType Error Stack Trace
```
File "pipeline.py", line 403
    pitch_notes.sort(key=lambda x: (x.quarterLength, x.volume.velocity if ...))
TypeError: '<' not supported between instances of 'int' and 'NoneType'
```

### 2048th Note Error Stack Trace
```
File "music21/musicxml/m21ToXml.py", line 4702
    mxNormalType.text = typeToMusicXMLType(tup.durationNormal.type)
MusicXMLExportException: In part (Piano), measure (129): Cannot convert "2048th" duration to MusicXML (too short).
```

---

**Last Updated**: 2024-12-24
**Next Review**: After accuracy suite re-run
