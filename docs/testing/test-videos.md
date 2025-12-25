# Test Video Collection

Curated collection of YouTube videos for testing transcription quality and edge cases.

## Table of Contents

- [Simple Piano Tests](#simple-piano-tests)
- [Classical Piano](#classical-piano)
- [Pop Piano Covers](#pop-piano-covers)
- [Jazz Piano](#jazz-piano)
- [Complex/Challenging](#complexchallenging)
- [Edge Cases](#edge-cases)
- [Testing Criteria](#testing-criteria)

## Simple Piano Tests

Use these for basic functionality and quick iteration.

### 1. Twinkle Twinkle Little Star (Beginner Piano)
- **Duration**: ~1 minute
- **Tempo**: Slow (60-80 BPM)
- **Complexity**: Very simple melody, single notes
- **Expected Accuracy**: 95%+
- **Use For**: Smoke tests, basic functionality

### 2. Mary Had a Little Lamb
- **Duration**: ~1 minute
- **Tempo**: Moderate (100 BPM)
- **Complexity**: Simple melody with consistent rhythm
- **Expected Accuracy**: 90%+
- **Use For**: Key signature detection, basic transcription

### 3. Happy Birthday (Piano Solo)
- **Duration**: ~1 minute
- **Tempo**: Moderate (120 BPM)
- **Complexity**: Simple melody with occasional harmony
- **Expected Accuracy**: 85%+
- **Use For**: Time signature detection (3/4 time)

## Classical Piano

Test with well-known classical pieces to verify quality.

### 4. Chopin - Nocturne Op. 9 No. 2
- **Duration**: 4-5 minutes
- **Tempo**: Andante (60-70 BPM)
- **Complexity**: Expressive melody with arpeggiated accompaniment
- **Expected Accuracy**: 75-80%
- **Use For**:
  - Pedal sustain handling
  - Rubato tempo changes
  - Expressive timing

**Challenges**:
- Overlapping notes from pedal
- Tempo fluctuations
- Decorative grace notes

### 5. Beethoven - Für Elise
- **Duration**: 3 minutes
- **Tempo**: Poco moto (120-130 BPM)
- **Complexity**: Famous melody with consistent rhythm
- **Expected Accuracy**: 80-85%
- **Use For**:
  - A minor key signature
  - Repeated patterns
  - Multiple sections

**Challenges**:
- Fast 16th note passages
- Dynamic contrasts

### 6. Mozart - Piano Sonata K. 545 (1st Movement)
- **Duration**: 3-4 minutes
- **Tempo**: Allegro (120-140 BPM)
- **Complexity**: Clear melody with Alberti bass
- **Expected Accuracy**: 75-80%
- **Use For**:
  - C major scale passages
  - Alberti bass pattern recognition
  - Classical form

**Challenges**:
- Fast running passages
- Hand coordination

## Pop Piano Covers

Test with contemporary music to verify modern styles.

### 7. Let It Be (Piano Cover)
- **Duration**: 3-4 minutes
- **Tempo**: Moderate (76 BPM)
- **Complexity**: Block chords with melody
- **Expected Accuracy**: 70-75%
- **Use For**:
  - Chord detection
  - Popular music transcription
  - Mixed rhythm patterns

**Challenges**:
- Dense chords
- Vocal line vs accompaniment

### 8. Someone Like You (Piano Cover)
- **Duration**: 4-5 minutes
- **Tempo**: Slow (67 BPM)
- **Complexity**: Arpeggiated chords with melody
- **Expected Accuracy**: 70-75%
- **Use For**:
  - Sustained notes
  - Emotional expression
  - Modern pop harmony

**Challenges**:
- Overlapping arpeggios
- Pedal sustain

### 9. River Flows in You (Original Piano)
- **Duration**: 3-4 minutes
- **Tempo**: Moderato (110 BPM)
- **Complexity**: Flowing arpeggios with melody
- **Expected Accuracy**: 75-80%
- **Use For**:
  - Continuous motion
  - Pattern recognition
  - Popular instrumental

**Challenges**:
- Rapid note sequences
- Consistent texture

## Jazz Piano

Test improvisation and complex harmony.

### 10. Bill Evans - Waltz for Debby
- **Duration**: 5-7 minutes
- **Tempo**: Moderate waltz (140-160 BPM)
- **Complexity**: Jazz voicings, walking bass, improvisation
- **Expected Accuracy**: 60-70%
- **Use For**:
  - Jazz harmony
  - 3/4 time signature
  - Complex chord voicings

**Challenges**:
- Extended chords (7ths, 9ths, 11ths)
- Improvised passages
- Swing feel

### 11. Oscar Peterson - C Jam Blues
- **Duration**: 3-4 minutes
- **Tempo**: Fast (200+ BPM)
- **Complexity**: Blues progression with virtuosic runs
- **Expected Accuracy**: 55-65%
- **Use For**:
  - Fast tempo handling
  - Blues scale
  - Virtuosic passages

**Challenges**:
- Extremely fast notes
- Grace notes and ornaments
- Complex rhythm

## Complex/Challenging

Stress tests for the transcription system.

### 12. Flight of the Bumblebee (Piano)
- **Duration**: 1-2 minutes
- **Tempo**: Presto (170-200 BPM)
- **Complexity**: Extremely fast chromatic runs
- **Expected Accuracy**: 50-60%
- **Use For**:
  - Stress testing
  - Fast passage detection
  - Chromatic scales

**Challenges**:
- Very fast notes (32nd notes)
- Chromatic passages
- Continuous motion

### 13. Liszt - La Campanella
- **Duration**: 4-5 minutes
- **Tempo**: Allegretto (120 BPM)
- **Complexity**: Virtuosic with wide leaps and rapid passages
- **Expected Accuracy**: 55-65%
- **Use For**:
  - Wide register jumps
  - Repeated notes
  - Virtuosic technique

**Challenges**:
- Octave leaps
- Repeated staccato notes
- Ornamentation

### 14. Rachmaninoff - Prelude in C# Minor
- **Duration**: 3-4 minutes
- **Tempo**: Lento (60 BPM) to Agitato
- **Complexity**: Dense chords, dramatic dynamics
- **Expected Accuracy**: 60-70%
- **Use For**:
  - Heavy chords
  - Dramatic contrasts
  - Multiple voices

**Challenges**:
- 6+ note chords
- Extreme dynamics
- Multiple simultaneous voices

## Edge Cases

Special cases to test error handling and boundaries.

### 15. Prepared Piano / Extended Techniques
- **Use For**: Testing unusual timbres
- **Expected Accuracy**: 30-50%
- **Expected Behavior**: Should handle gracefully

### 16. Piano with Background Noise
- **Use For**: Testing source separation quality
- **Expected Accuracy**: Variable
- **Expected Behavior**: Should isolate piano reasonably

### 17. Poor Audio Quality
- **Use For**: Testing robustness
- **Expected Accuracy**: Reduced
- **Expected Behavior**: Should not crash

### 18. Non-Piano Video (Should Fail Gracefully)
- **Examples**:
  - Drum solo
  - A cappella singing
  - Electronic music
- **Expected Behavior**: Should complete but with poor results

## Testing Criteria

### Accuracy Metrics

**High Priority (Must Work Well)**:
- Note pitch accuracy: 85%+ for simple pieces
- Note onset timing: 80%+ within 50ms
- Note duration: 70%+ within one quantization unit

**Medium Priority (Should Work)**:
- Key signature detection: 80%+ accuracy
- Time signature detection: 75%+ accuracy
- Tempo detection: 70%+ within 10 BPM

**Low Priority (Nice to Have)**:
- Dynamic markings: Not implemented in MVP
- Articulations: Not implemented in MVP
- Pedal markings: Not implemented in MVP

### Performance Benchmarks

| Video Duration | Target Processing Time (GPU) | Max Processing Time (CPU) |
|---------------|------------------------------|---------------------------|
| 1 minute      | < 30 seconds                 | < 5 minutes               |
| 3 minutes     | < 2 minutes                  | < 10 minutes              |
| 5 minutes     | < 3 minutes                  | < 15 minutes              |

### Success Criteria

A transcription is considered successful if:

1. **Job completes without error**: 95%+ success rate
2. **Basic pitch accuracy**: 70%+ correct notes for simple pieces, 60%+ for complex
3. **Playback sounds recognizable**: User can identify the piece
4. **Usable for editing**: Notation is clean enough to edit and correct

### Quality Grades

**A (90%+ accuracy)**:
- Simple melodies
- Clear recordings
- Slow to moderate tempo
- Minimal harmony

**B (75-89% accuracy)**:
- Standard classical pieces
- Good recordings
- Moderate tempo
- Some harmony

**C (60-74% accuracy)**:
- Complex pieces
- Standard recordings
- Fast tempo or complex harmony
- Multiple voices

**D (50-59% accuracy)**:
- Virtuosic pieces
- Poor recordings
- Very fast or complex
- Jazz/improvisation

**F (< 50% accuracy)**:
- Extended techniques
- Very poor quality
- Non-piano instruments
- Extreme complexity

## Using Test Videos

### Manual Testing

1. Submit each video URL through the UI
2. Wait for processing to complete
3. Check for errors in each pipeline stage
4. Download and inspect MusicXML output
5. Load in MuseScore or similar to verify quality
6. Note accuracy, timing issues, and artifacts

### Automated Testing

```python
# In tests/test_integration.py
@pytest.mark.parametrize("video_id,expected_grade", [
    ("simple_melody", "A"),
    ("fur_elise", "B"),
    ("jazz_piece", "C"),
])
def test_transcription_quality(video_id, expected_grade):
    """Test transcription quality meets expectations."""
    result = transcribe_video(video_id)

    assert result['status'] == 'success'
    accuracy = calculate_accuracy(result['musicxml'])
    assert accuracy >= grade_threshold(expected_grade)
```

### Regression Testing

Maintain a suite of test videos and track accuracy over time:

```bash
# Run regression test suite
python scripts/run_regression_tests.py

# Compare with baseline
python scripts/compare_results.py --baseline v1.0.0 --current HEAD
```

## Maintaining Test Collection

1. **Add new test cases** when bugs are found
2. **Update expected accuracy** as system improves
3. **Remove broken links** and replace with alternatives
4. **Document edge cases** that reveal system limitations
5. **Share results** with team to track progress

## Test Video Sources

When selecting test videos:

- ✅ Use videos with clear audio
- ✅ Prefer solo piano recordings
- ✅ Choose varied difficulty levels
- ✅ Include different musical styles
- ✅ Ensure videos are publicly accessible
- ✅ Respect copyright and fair use
- ❌ Avoid videos with talking/commentary
- ❌ Avoid poor audio quality unless testing robustness
- ❌ Don't use videos over 15 minutes (MVP limit)
