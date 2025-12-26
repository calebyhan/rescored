"""Unit tests for pipeline fixes (Issues #6, #7, #8)."""
import pytest
from pathlib import Path
import mido
from music21 import note, chord, stream, converter
from pipeline import TranscriptionPipeline
from config import Settings


@pytest.fixture
def pipeline(temp_storage_dir):
    """Create a TranscriptionPipeline instance for testing."""
    config = Settings(storage_path=temp_storage_dir)
    return TranscriptionPipeline(
        job_id="test-job",
        youtube_url="https://www.youtube.com/watch?v=test",
        storage_path=temp_storage_dir,
        config=config
    )


@pytest.fixture
def midi_with_sequential_notes(temp_storage_dir):
    """Create MIDI file with sequential notes of same pitch with small gaps."""
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Note 1: C4 (60) from 0-480 ticks (1 beat)
    track.append(mido.Message('note_on', note=60, velocity=64, time=0))
    track.append(mido.Message('note_off', note=60, velocity=64, time=480))

    # Tiny gap of 10 ticks (~20ms at 120 BPM)
    # Note 2: C4 (60) from 490-970 ticks (1 beat)
    track.append(mido.Message('note_on', note=60, velocity=64, time=10))
    track.append(mido.Message('note_off', note=60, velocity=64, time=480))

    track.append(mido.MetaMessage('end_of_track', time=0))

    midi_path = temp_storage_dir / "sequential_notes.mid"
    mid.save(str(midi_path))
    return midi_path


@pytest.fixture
def midi_with_low_velocity_notes(temp_storage_dir):
    """Create MIDI file with low velocity notes (noise)."""
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Loud note (should keep)
    track.append(mido.Message('note_on', note=60, velocity=64, time=0))
    track.append(mido.Message('note_off', note=60, velocity=64, time=480))

    # Very quiet note (should filter - velocity < 45)
    track.append(mido.Message('note_on', note=62, velocity=30, time=0))
    track.append(mido.Message('note_off', note=62, velocity=30, time=480))

    # Another loud note
    track.append(mido.Message('note_on', note=64, velocity=80, time=0))
    track.append(mido.Message('note_off', note=64, velocity=80, time=480))

    track.append(mido.MetaMessage('end_of_track', time=0))

    midi_path = temp_storage_dir / "low_velocity.mid"
    mid.save(str(midi_path))
    return midi_path


@pytest.fixture
def score_with_tiny_gaps():
    """Create music21 score with sequential notes that have tiny gaps."""
    s = stream.Score()
    p = stream.Part()

    # Note 1: C4 at offset 0.0, duration 1.0 QN
    n1 = note.Note('C4', quarterLength=1.0)
    p.insert(0.0, n1)

    # Note 2: C4 at offset 1.01 (tiny gap of 0.01 QN) - should merge
    n2 = note.Note('C4', quarterLength=1.0)
    p.insert(1.01, n2)

    # Note 3: C4 at offset 2.05 (larger gap of 0.04 QN) - should still merge (< 0.02 threshold)
    # Actually, this should NOT merge as gap > 0.02
    n3 = note.Note('C4', quarterLength=1.0)
    p.insert(2.05, n3)

    s.append(p)
    return s


@pytest.fixture
def score_with_chord():
    """Create music21 score with a chord (should not merge chord notes)."""
    s = stream.Score()
    p = stream.Part()

    # Chord: C4, E4, G4 at offset 0.0
    c = chord.Chord(['C4', 'E4', 'G4'], quarterLength=2.0)
    p.insert(0.0, c)

    s.append(p)
    return s


@pytest.fixture
def score_with_staccato():
    """Create music21 score with staccato notes (large gaps - should NOT merge)."""
    s = stream.Score()
    p = stream.Part()

    # Note 1: C4 at offset 0.0, duration 0.5 QN
    n1 = note.Note('C4', quarterLength=0.5)
    p.insert(0.0, n1)

    # Note 2: C4 at offset 1.0 (gap of 0.5 QN - staccato, should NOT merge)
    n2 = note.Note('C4', quarterLength=0.5)
    p.insert(1.0, n2)

    s.append(p)
    return s


class TestIssue8MergeMusic21Notes:
    """Tests for Issue #8: Tiny rests between notes."""

    def test_merge_sequential_notes_same_pitch(self, pipeline, score_with_tiny_gaps):
        """Sequential notes of same pitch with small gap should merge."""
        # Get notes before merging
        notes_before = list(score_with_tiny_gaps.flatten().notes)
        assert len(notes_before) == 3  # 3 separate C4 notes

        # Merge with 0.02 QN threshold
        merged_score = pipeline._merge_music21_notes(score_with_tiny_gaps, gap_threshold_qn=0.02)

        # Get notes after merging
        notes_after = list(merged_score.flatten().notes)

        # First two notes should merge (gap 0.01 < 0.02)
        # Third note should NOT merge (gap 0.04 > 0.02 from second note's end)
        # Actually need to recalculate: n1 ends at 1.0, n2 at 2.01, gap to n3 at 2.05 = 0.04
        assert len(notes_after) == 2, f"Expected 2 notes after merging, got {len(notes_after)}"

        # First note should have extended duration
        first_note = notes_after[0]
        assert first_note.pitch.midi == 60  # C4
        # Duration should cover both first and second note: 0.0 to 2.01 = 2.01 QN
        assert abs(first_note.quarterLength - 2.01) < 0.001, \
            f"Expected duration ~2.01, got {first_note.quarterLength}"

    def test_dont_merge_different_pitches(self, pipeline):
        """Notes with different pitches should NOT merge."""
        s = stream.Score()
        p = stream.Part()

        # C4, then D4 with tiny gap - should NOT merge
        p.insert(0.0, note.Note('C4', quarterLength=1.0))
        p.insert(1.01, note.Note('D4', quarterLength=1.0))

        s.append(p)

        merged_score = pipeline._merge_music21_notes(s, gap_threshold_qn=0.02)
        notes_after = list(merged_score.flatten().notes)

        assert len(notes_after) == 2, "Different pitches should not merge"
        assert notes_after[0].pitch.midi == 60  # C4
        assert notes_after[1].pitch.midi == 62  # D4

    def test_dont_merge_large_gaps(self, pipeline, score_with_staccato):
        """Notes with large gaps (staccato) should NOT merge."""
        notes_before = list(score_with_staccato.flatten().notes)
        assert len(notes_before) == 2

        merged_score = pipeline._merge_music21_notes(score_with_staccato, gap_threshold_qn=0.02)
        notes_after = list(merged_score.flatten().notes)

        # Gap is 0.5 QN (n1 ends at 0.5, n2 starts at 1.0)
        # Should NOT merge (0.5 > 0.02)
        assert len(notes_after) == 2, "Staccato notes with large gaps should not merge"
        assert notes_after[0].quarterLength == 0.5
        assert notes_after[1].quarterLength == 0.5

    def test_dont_merge_same_chord_notes(self, pipeline, score_with_chord):
        """Notes from the SAME chord should NOT merge into one note."""
        chords_before = list(score_with_chord.flatten().getElementsByClass(chord.Chord))
        assert len(chords_before) == 1
        assert len(chords_before[0].pitches) == 3  # C, E, G

        merged_score = pipeline._merge_music21_notes(score_with_chord, gap_threshold_qn=0.02)

        # Chord should remain intact
        chords_after = list(merged_score.flatten().getElementsByClass(chord.Chord))
        assert len(chords_after) == 1, "Chord should remain"
        assert len(chords_after[0].pitches) == 3, "Chord should still have 3 notes"

    def test_merge_across_different_velocities(self, pipeline):
        """Sequential notes with different velocities but same pitch should merge."""
        s = stream.Score()
        p = stream.Part()

        # Create notes with different velocities
        n1 = note.Note('C4', quarterLength=1.0)
        n1.volume.velocity = 64
        p.insert(0.0, n1)

        n2 = note.Note('C4', quarterLength=1.0)
        n2.volume.velocity = 80
        p.insert(1.01, n2)  # Small gap

        s.append(p)

        merged_score = pipeline._merge_music21_notes(s, gap_threshold_qn=0.02)
        notes_after = list(merged_score.flatten().notes)

        # Should merge despite different velocities
        assert len(notes_after) == 1, "Notes with different velocities should still merge"
        assert abs(notes_after[0].quarterLength - 2.01) < 0.001


class TestIssue6NoiseFiltering:
    """Tests for Issue #6: Random noise notes."""

    def test_filters_low_velocity_notes(self, pipeline, midi_with_low_velocity_notes):
        """Notes with velocity < 45 should be filtered."""
        # Process MIDI through cleanup
        cleaned_midi = pipeline.clean_midi(midi_with_low_velocity_notes)

        # Load cleaned MIDI
        mid = mido.MidiFile(cleaned_midi)

        # Count note_on messages
        note_ons = []
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    note_ons.append((msg.note, msg.velocity))

        # Should have 2 notes (60 vel=64, 64 vel=80), not 3
        assert len(note_ons) == 2, f"Expected 2 notes after filtering, got {len(note_ons)}"

        # Check that low velocity note (62) is not present
        notes = [n[0] for n in note_ons]
        assert 62 not in notes, "Low velocity note should be filtered"
        assert 60 in notes, "High velocity note should remain"
        assert 64 in notes, "High velocity note should remain"

    def test_keeps_moderate_velocity_notes(self, pipeline, temp_storage_dir):
        """Notes with velocity >= 45 should be kept."""
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)

        # Note with velocity exactly at threshold (45)
        track.append(mido.Message('note_on', note=60, velocity=45, time=0))
        track.append(mido.Message('note_off', note=60, velocity=45, time=480))

        # Note with velocity above threshold (60)
        track.append(mido.Message('note_on', note=62, velocity=60, time=0))
        track.append(mido.Message('note_off', note=62, velocity=60, time=480))

        track.append(mido.MetaMessage('end_of_track', time=0))

        midi_path = temp_storage_dir / "moderate_velocity.mid"
        mid.save(str(midi_path))

        cleaned_midi = pipeline.clean_midi(midi_path)
        mid_cleaned = mido.MidiFile(cleaned_midi)

        note_ons = []
        for track in mid_cleaned.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    note_ons.append(msg.note)

        # Both notes should be kept
        assert len(note_ons) == 2, "Notes with velocity >= 45 should be kept"
        assert 60 in note_ons
        assert 62 in note_ons


class TestIssue7MeasureNormalization:
    """Tests for Issue #7: Corrupted measures."""

    def test_deduplication_bucketing_precision(self, pipeline):
        """Deduplication should use 0.005 QN bucketing (5ms at 120 BPM)."""
        s = stream.Score()
        p = stream.Part()

        # Create two notes very close together (should be in same bucket)
        # At 0.0 and 0.003 QN (~3ms) - should be bucketed together
        # After bucketing: 0.0 -> bucket 0.0, 0.003 -> bucket 0.005 (rounded)
        # Actually need to be within the same bucket after rounding
        n1 = note.Note('C4', quarterLength=1.0)
        p.insert(0.0, n1)

        n2 = note.Note('C4', quarterLength=1.0)
        p.insert(0.002, n2)  # 0.002 rounds to 0.0 bucket (0.002/0.005 = 0.4 -> rounds to 0)

        s.append(p)

        # Deduplicate
        deduped_score = pipeline._deduplicate_overlapping_notes(s)
        notes_after = list(deduped_score.flatten().notes)

        # Should merge into one note (duplicate in same bucket)
        assert len(notes_after) == 1, "Notes within same 0.005 QN bucket should be deduplicated"

    def test_skip_threshold_relaxed(self, pipeline):
        """Normalization should skip measures within 0.05 QN of correct duration."""
        s = stream.Score()
        p = stream.Part()

        # Create a measure that's slightly off (3.98 QN instead of 4.0)
        # This is within 0.05 tolerance, so should be skipped
        n1 = note.Note('C4', quarterLength=1.98)
        n2 = note.Note('D4', quarterLength=2.0)

        p.insert(0.0, n1)
        p.insert(1.98, n2)

        s.append(p)
        s = s.makeMeasures()

        # Normalize with 4/4 time signature
        normalized = pipeline._normalize_measure_durations(s, 4, 4)

        # Get first measure
        measures = normalized.parts[0].getElementsByClass('Measure')
        if measures:
            first_measure = measures[0]
            elements = list(first_measure.notesAndRests)

            # Measure should not be modified (within tolerance)
            # Total duration should still be ~3.98
            total_duration = sum(e.quarterLength for e in elements)
            assert abs(total_duration - 3.98) < 0.1, \
                "Measure within tolerance should not be heavily modified"

    def test_rest_fill_minimum_lowered(self, pipeline):
        """Gaps > 0.15 QN (new tolerance) should be filled with rests, smaller gaps skipped."""
        s = stream.Score()
        p = stream.Part()

        # Create measure with gap LARGER than tolerance (0.15 QN)
        # Total: 3.80 QN (gap of 0.20 QN to fill to 4.0) - exceeds 0.15 tolerance
        # This should trigger normalization and rest filling
        n1 = note.Note('C4', quarterLength=2.0)
        n2 = note.Note('D4', quarterLength=1.80)

        p.insert(0.0, n1)
        p.insert(2.0, n2)

        s.append(p)
        s = s.makeMeasures()

        # Normalize - should add rest to fill 0.20 QN gap (exceeds 0.15 tolerance)
        normalized = pipeline._normalize_measure_durations(s, 4, 4)

        measures = normalized.parts[0].getElementsByClass('Measure')
        if measures:
            first_measure = measures[0]
            elements = list(first_measure.notesAndRests)

            # Total duration should now be close to 4.0 after normalization
            total_duration = sum(e.quarterLength for e in elements)

            # With 0.20 gap (> 0.15 tolerance), should have been normalized
            # Either proportionally scaled or filled with rest
            assert abs(total_duration - 4.0) < 0.15, \
                f"Measure should be normalized to ~4.0 QN, got {total_duration}"


class TestIntegration:
    """Integration tests for full pipeline."""

    def test_onset_threshold_config(self):
        """Config should have onset_threshold = 0.5 (increased to reduce false positives)."""
        config = Settings()
        assert config.onset_threshold == 0.5, \
            f"onset_threshold should be 0.5, got {config.onset_threshold}"

    def test_sequential_note_merging_in_pipeline(self, pipeline, midi_with_sequential_notes):
        """Full pipeline should merge sequential notes."""
        # Convert MIDI to music21
        score = converter.parse(str(midi_with_sequential_notes))

        # Check notes before merging
        notes_before = list(score.flatten().notes)
        # MIDI has 2 notes with tiny gap
        assert len(notes_before) >= 2, "MIDI should have at least 2 notes"

        # Run merge
        merged_score = pipeline._merge_music21_notes(score, gap_threshold_qn=0.02)

        # After merging, should have 1 note
        notes_after = list(merged_score.flatten().notes)
        assert len(notes_after) == 1, \
            f"Sequential notes should merge into 1, got {len(notes_after)}"


class TestEnvelopeAnalysis:
    """Test velocity envelope analysis and sustain artifact detection."""

    @pytest.fixture
    def midi_with_decay_pattern(self, temp_storage_dir):
        """Create MIDI with decreasing velocity pattern (sustain decay artifact)."""
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)

        # Note 1: C4 (60) velocity 80, 0-480 ticks (1 beat)
        track.append(mido.Message('note_on', note=60, velocity=80, time=0))
        track.append(mido.Message('note_off', note=60, velocity=0, time=480))

        # Gap of 120 ticks (~250ms at 120 BPM)
        # Note 2: C4 (60) velocity 50 (decaying), 600-1080 ticks
        track.append(mido.Message('note_on', note=60, velocity=50, time=120))
        track.append(mido.Message('note_off', note=60, velocity=0, time=480))

        # Gap of 100 ticks
        # Note 3: C4 (60) velocity 30 (further decay), 1180-1660 ticks
        track.append(mido.Message('note_on', note=60, velocity=30, time=100))
        track.append(mido.Message('note_off', note=60, velocity=0, time=480))

        track.append(mido.MetaMessage('end_of_track', time=0))

        midi_path = temp_storage_dir / "decay_pattern.mid"
        mid.save(str(midi_path))
        return midi_path

    @pytest.fixture
    def midi_with_staccato_pattern(self, temp_storage_dir):
        """Create MIDI with similar velocities (intentional staccato)."""
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)

        # Note 1: C4 (60) velocity 70
        track.append(mido.Message('note_on', note=60, velocity=70, time=0))
        track.append(mido.Message('note_off', note=60, velocity=0, time=240))

        # Gap
        # Note 2: C4 (60) velocity 68 (similar, intentional)
        track.append(mido.Message('note_on', note=60, velocity=68, time=100))
        track.append(mido.Message('note_off', note=60, velocity=0, time=240))

        # Gap
        # Note 3: C4 (60) velocity 72 (similar, intentional)
        track.append(mido.Message('note_on', note=60, velocity=72, time=100))
        track.append(mido.Message('note_off', note=60, velocity=0, time=240))

        track.append(mido.MetaMessage('end_of_track', time=0))

        midi_path = temp_storage_dir / "staccato_pattern.mid"
        mid.save(str(midi_path))
        return midi_path

    def test_detects_and_merges_decay_pattern(self, pipeline, midi_with_decay_pattern):
        """Test that decreasing velocity patterns are detected and merged."""
        result = pipeline.analyze_note_envelope_and_merge_sustains(
            midi_with_decay_pattern,
            tempo_bpm=120.0
        )

        # Load result and count note_on events
        mid = mido.MidiFile(result)
        note_ons = [msg for msg in mid.tracks[0] if msg.type == 'note_on' and msg.velocity > 0]

        # Should merge 3 decaying notes into 1
        assert len(note_ons) == 1, \
            f"Decay pattern should merge to 1 note, got {len(note_ons)}"

    def test_preserves_staccato_pattern(self, pipeline, midi_with_staccato_pattern):
        """Test that similar velocities are NOT merged (intentional staccato)."""
        result = pipeline.analyze_note_envelope_and_merge_sustains(
            midi_with_staccato_pattern,
            tempo_bpm=120.0
        )

        # Load result and count note_on events
        mid = mido.MidiFile(result)
        note_ons = [msg for msg in mid.tracks[0] if msg.type == 'note_on' and msg.velocity > 0]

        # Should keep all 3 notes (similar velocities = intentional)
        assert len(note_ons) == 3, \
            f"Staccato pattern should keep 3 notes, got {len(note_ons)}"


class TestTempoAdaptiveThresholds:
    """Test tempo-adaptive threshold selection."""

    def test_fast_tempo_uses_strict_thresholds(self, pipeline):
        """Test that fast tempos (>140 BPM) use stricter thresholds."""
        thresholds = pipeline._get_tempo_adaptive_thresholds(160.0)

        assert thresholds['onset_threshold'] == 0.50, "Fast tempo should use 0.50 onset threshold"
        assert thresholds['min_velocity'] == 50, "Fast tempo should use 50 min velocity"
        assert thresholds['min_duration_divisor'] == 6, "Fast tempo should use 48th notes"

    def test_slow_tempo_uses_permissive_thresholds(self, pipeline):
        """Test that slow tempos (<80 BPM) use more permissive thresholds."""
        thresholds = pipeline._get_tempo_adaptive_thresholds(60.0)

        assert thresholds['onset_threshold'] == 0.40, "Slow tempo should use 0.40 onset threshold"
        assert thresholds['min_velocity'] == 40, "Slow tempo should use 40 min velocity"
        assert thresholds['min_duration_divisor'] == 10, "Slow tempo should use permissive divisor"

    def test_medium_tempo_uses_default_thresholds(self, pipeline):
        """Test that medium tempos (80-140 BPM) use default thresholds."""
        thresholds = pipeline._get_tempo_adaptive_thresholds(120.0)

        assert thresholds['onset_threshold'] == 0.45, "Medium tempo should use 0.45 onset threshold"
        assert thresholds['min_velocity'] == 45, "Medium tempo should use 45 min velocity"
        assert thresholds['min_duration_divisor'] == 8, "Medium tempo should use 32nd notes"


class TestMusicXMLTies:
    """Test MusicXML tie notation generation."""

    @pytest.fixture
    def score_with_long_note(self):
        """Create a score with a note that spans multiple measures."""
        from music21 import stream, note, meter

        s = stream.Score()
        part = stream.Part()

        # Add 4/4 time signature
        part.append(meter.TimeSignature('4/4'))

        # Measure 1: C4 whole note (4 QN)
        m1 = stream.Measure()
        m1.append(note.Note('C4', quarterLength=4.0))
        part.append(m1)

        # Measure 2: D4 whole note (4 QN)
        m2 = stream.Measure()
        m2.append(note.Note('D4', quarterLength=4.0))
        part.append(m2)

        s.insert(0, part)
        return s

    @pytest.fixture
    def score_with_cross_measure_note(self):
        """Create a score with a note crossing measure boundary."""
        from music21 import stream, note, meter

        s = stream.Score()
        part = stream.Part()

        # Add 4/4 time signature
        part.append(meter.TimeSignature('4/4'))

        # Measure 1: Two quarter notes + note that extends into measure 2
        m1 = stream.Measure()
        m1.append(note.Note('C4', quarterLength=1.0))
        m1.append(note.Note('D4', quarterLength=1.0))
        # This note is 2.5 QN, extends 0.5 QN beyond measure boundary
        m1.append(note.Note('E4', quarterLength=2.5))
        part.append(m1)

        # Measure 2: Continuation
        m2 = stream.Measure()
        # The E4 should continue here with a tie
        m2.append(note.Note('E4', quarterLength=1.0))
        m2.append(note.Note('F4', quarterLength=2.0))
        part.append(m2)

        s.insert(0, part)
        return s

    def test_adds_ties_to_cross_measure_notes(self, pipeline, score_with_cross_measure_note):
        """Test that ties are added to notes crossing measure boundaries."""
        result = pipeline._add_ties_to_score(score_with_cross_measure_note)

        # Get all notes
        all_notes = list(result.flatten().notes)

        # Find E4 notes (should have ties)
        e4_notes = [n for n in all_notes if n.pitch.name == 'E']

        # Should have at least 1 E4 with 'start' tie
        has_start_tie = any(n.tie is not None and n.tie.type == 'start' for n in e4_notes)
        assert has_start_tie, "E4 note crossing measure should have 'start' tie"

    def test_does_not_add_ties_to_within_measure_notes(self, pipeline, score_with_long_note):
        """Test that ties are NOT added to notes within a single measure."""
        result = pipeline._add_ties_to_score(score_with_long_note)

        # Get all notes
        all_notes = list(result.flatten().notes)

        # C4 and D4 are within measures, should not have ties
        c4_notes = [n for n in all_notes if n.pitch.name == 'C']
        d4_notes = [n for n in all_notes if n.pitch.name == 'D']

        # None should have ties (they don't cross boundaries)
        c4_has_ties = any(n.tie is not None for n in c4_notes)
        d4_has_ties = any(n.tie is not None for n in d4_notes)

        assert not c4_has_ties, "C4 within measure should not have tie"
        assert not d4_has_ties, "D4 within measure should not have tie"
