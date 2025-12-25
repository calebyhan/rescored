# Backend Scripts

Utility scripts for testing and analyzing the Rescored transcription pipeline.

## Scripts

### test_accuracy.py

**NEW** - Comprehensive accuracy testing suite that tests the pipeline with 10 diverse piano videos covering different styles and difficulty levels.

**Usage:**
```bash
cd backend
python scripts/test_accuracy.py
```

**Output:**
- Progress for each of 10 test videos
- Success/failure status per video
- Metrics: note count, measure count, separation quality
- Summary statistics (success rate, average metrics)
- Full results saved to JSON: `/tmp/rescored/accuracy_test_results.json`

**Test Videos** (varying difficulty):
- **Easy**: Simple scales, Twinkle Twinkle
- **Medium**: Für Elise, Canon in D, River Flows in You, Moonlight Sonata, Jazz Blues
- **Hard**: Chopin Nocturne, Clair de Lune
- **Very Hard**: La Campanella (Liszt)

**Expected Runtime**: 30-60 minutes for all 10 videos

**Purpose**: Establish baseline accuracy metrics for the MVP pipeline, identify common failure modes, and track improvements across phases.

### test_e2e.py

End-to-end pipeline testing script. Downloads a YouTube video, runs the full transcription pipeline, and displays results.

**Usage:**
```bash
cd backend
python scripts/test_e2e.py "<youtube_url>"
```

**Example:**
```bash
python scripts/test_e2e.py "https://www.youtube.com/watch?v=PAE88urB1xs"
```

**Output:**
- Progress updates for each pipeline stage
- Total processing time
- MusicXML file path and size
- List of intermediate files
- Preview of generated MusicXML

**Test Videos:**
- Simple piano melody: https://www.youtube.com/watch?v=WyTb3DTu88c
- Classical piano: https://www.youtube.com/watch?v=fJ9rUzIMcZQ

---

### analyze_transcription.py

MIDI file analysis tool. Provides detailed statistics about transcribed notes to identify quality issues.

**Usage:**
```bash
cd backend
python scripts/analyze_transcription.py <midi_path>
```

**Example:**
```bash
python scripts/analyze_transcription.py /tmp/rescored/temp/test_e2e/piano.mid
python scripts/analyze_transcription.py /tmp/rescored/temp/test_e2e/piano_clean.mid
```

**Analysis Includes:**
- Total note count and density (notes/second)
- Pitch range and distribution
- Note duration statistics (average, median, min, max)
- Velocity (dynamics) analysis
- Polyphony (simultaneous notes)
- Detection of potential issues:
  - Very short notes (< 100ms) - likely false positives
  - Very quiet notes (velocity < 30) - likely noise
  - High note density - over-transcription
  - Extreme polyphony - detecting noise as notes
  - Notes outside piano range

**Output Example:**
```
============================================================
MIDI Transcription Analysis
============================================================
File: piano.mid
Duration: 248.1 seconds
Total notes: 1333
Notes per second: 5.37

Pitch Range:
  Lowest: 35 (MIDI) = B1
  Highest: 86 (MIDI) = D6
  Range: 51 semitones

Note Durations:
  Average: 0.433 seconds
  Median: 0.325 seconds
  Very short notes (< 100ms): 0 (0.0%)

Potential Issues:
  ✓ No obvious issues detected
============================================================
```

---

## Workflow

1. **Test the pipeline:**
   ```bash
   python scripts/test_e2e.py "https://www.youtube.com/watch?v=VIDEO_ID"
   ```

2. **Analyze the raw output:**
   ```bash
   python scripts/analyze_transcription.py /tmp/rescored/temp/test_e2e/piano.mid
   ```

3. **Analyze the cleaned output:**
   ```bash
   python scripts/analyze_transcription.py /tmp/rescored/temp/test_e2e/piano_clean.mid
   ```

4. **Listen to the result:**
   ```bash
   # Using MuseScore
   musescore /tmp/rescored/temp/test_e2e/test_e2e.musicxml

   # Or using timidity (MIDI playback)
   timidity /tmp/rescored/temp/test_e2e/piano_clean.mid
   ```

---

## Interpreting Results

### Good Transcription Indicators
- Notes/second: 3-8 for piano (depends on complexity)
- Very short notes: < 10%
- Max polyphony: 3-10 simultaneous notes (piano is typically 2-6)
- Pitch range: Within MIDI 21-108 (A0 to C8)
- No significant issues detected

### Warning Signs
- Notes/second > 10: Likely over-transcribing (too many false positives)
- Very short notes > 30%: Detecting noise as notes
- Max polyphony > 15: Probably including noise
- Many notes outside piano range: Need better filtering

### Tuning Recommendations
If you see issues, adjust parameters in [pipeline.py](../pipeline.py):

**For too many false positives:**
- Increase `onset-threshold` (0.5 → 0.6)
- Increase `frame-threshold` (0.4 → 0.45)
- Increase `minimum-note-length` (127 → 150ms)

**For too many missing notes:**
- Decrease `onset-threshold` (0.5 → 0.45)
- Decrease `frame-threshold` (0.4 → 0.35)

**For timing issues:**
- Adjust quantization in `clean_midi()` method
- Change `ticks_per_16th` to `ticks_per_32nd` for lighter quantization

---

## Notes

- Scripts must be run from the `backend` directory (they use relative imports)
- Temporary files are stored in `/tmp/rescored/temp/<job_id>/`
- MusicXML output is saved in the temp directory with the job_id as filename
- Analysis works on both raw and cleaned MIDI files for comparison
