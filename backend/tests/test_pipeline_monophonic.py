"""Tests for monophonic melody extraction and frequency filtering."""
import pytest
import mido
from pathlib import Path
from pipeline import TranscriptionPipeline
from config import Settings


@pytest.fixture
def pipeline(tmp_path):
    """Create pipeline instance for testing."""
    config = Settings(storage_path=tmp_path)
    return TranscriptionPipeline(
        job_id="test-mono",
        youtube_url="https://test.com",
        storage_path=tmp_path,
        config=config
    )


@pytest.fixture
def midi_with_octaves(tmp_path):
    """Create MIDI file with simultaneous octave notes (C4 + C6)."""
    mid = mido.MidiFile(ticks_per_beat=220)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Simultaneous C4 (60) + C6 (84) - octave duplicate
    track.append(mido.Message('note_on', note=60, velocity=64, time=0))
    track.append(mido.Message('note_on', note=84, velocity=64, time=0))
    track.append(mido.Message('note_off', note=60, velocity=0, time=480))
    track.append(mido.Message('note_off', note=84, velocity=0, time=0))
    track.append(mido.MetaMessage('end_of_track', time=0))

    path = tmp_path / "octaves.mid"
    mid.save(str(path))
    return path


@pytest.fixture
def midi_with_single_notes(tmp_path):
    """Create MIDI file with sequential single notes."""
    mid = mido.MidiFile(ticks_per_beat=220)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # C4, D4, E4 in sequence
    track.append(mido.Message('note_on', note=60, velocity=64, time=0))
    track.append(mido.Message('note_off', note=60, velocity=0, time=480))
    track.append(mido.Message('note_on', note=62, velocity=64, time=0))
    track.append(mido.Message('note_off', note=62, velocity=0, time=480))
    track.append(mido.Message('note_on', note=64, velocity=64, time=0))
    track.append(mido.Message('note_off', note=64, velocity=0, time=480))
    track.append(mido.MetaMessage('end_of_track', time=0))

    path = tmp_path / "single_notes.mid"
    mid.save(str(path))
    return path


@pytest.fixture
def midi_with_close_onset(tmp_path):
    """Create MIDI file with notes starting within ONSET_TOLERANCE (10 ticks)."""
    mid = mido.MidiFile(ticks_per_beat=220)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # C4 at time 0, G4 at time 5 (within tolerance, should be treated as simultaneous)
    track.append(mido.Message('note_on', note=60, velocity=64, time=0))
    track.append(mido.Message('note_on', note=67, velocity=64, time=5))
    track.append(mido.Message('note_off', note=60, velocity=0, time=475))
    track.append(mido.Message('note_off', note=67, velocity=0, time=0))
    track.append(mido.MetaMessage('end_of_track', time=0))

    path = tmp_path / "close_onset.mid"
    mid.save(str(path))
    return path


@pytest.fixture
def midi_with_consecutive_same_pitch(tmp_path):
    """Create MIDI file with consecutive same-pitch notes (not simultaneous)."""
    mid = mido.MidiFile(ticks_per_beat=220)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # C4 at time 0, C4 at time 500 (sequential, not simultaneous)
    track.append(mido.Message('note_on', note=60, velocity=64, time=0))
    track.append(mido.Message('note_off', note=60, velocity=0, time=480))
    track.append(mido.Message('note_on', note=60, velocity=64, time=20))
    track.append(mido.Message('note_off', note=60, velocity=0, time=480))
    track.append(mido.MetaMessage('end_of_track', time=0))

    path = tmp_path / "consecutive_same.mid"
    mid.save(str(path))
    return path


@pytest.fixture
def midi_with_triple_octaves(tmp_path):
    """Create MIDI file with three simultaneous octaves (C4 + C5 + C6)."""
    mid = mido.MidiFile(ticks_per_beat=220)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Simultaneous C4 (60) + C5 (72) + C6 (84)
    track.append(mido.Message('note_on', note=60, velocity=64, time=0))
    track.append(mido.Message('note_on', note=72, velocity=64, time=0))
    track.append(mido.Message('note_on', note=84, velocity=64, time=0))
    track.append(mido.Message('note_off', note=60, velocity=0, time=480))
    track.append(mido.Message('note_off', note=72, velocity=0, time=0))
    track.append(mido.Message('note_off', note=84, velocity=0, time=0))
    track.append(mido.MetaMessage('end_of_track', time=0))

    path = tmp_path / "triple_octaves.mid"
    mid.save(str(path))
    return path


@pytest.fixture
def midi_with_different_pitch_classes(tmp_path):
    """Create MIDI file with bass + treble (different pitch classes) simultaneous."""
    mid = mido.MidiFile(ticks_per_beat=220)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Simultaneous D2 (38, pitch class 2) + A5 (81, pitch class 9)
    # This simulates piano with left hand bass + right hand treble
    track.append(mido.Message('note_on', note=38, velocity=64, time=0))
    track.append(mido.Message('note_on', note=81, velocity=64, time=0))
    track.append(mido.Message('note_off', note=38, velocity=0, time=480))
    track.append(mido.Message('note_off', note=81, velocity=0, time=0))
    track.append(mido.MetaMessage('end_of_track', time=0))

    path = tmp_path / "different_pitch_classes.mid"
    mid.save(str(path))
    return path


@pytest.fixture
def midi_wide_range(tmp_path):
    """Create MIDI file with wide range (>24 semitones) - simulates piano."""
    mid = mido.MidiFile(ticks_per_beat=220)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # D2 (38) to E6 (88) = 50 semitones (wide range)
    track.append(mido.Message('note_on', note=38, velocity=64, time=0))
    track.append(mido.Message('note_off', note=38, velocity=0, time=480))
    track.append(mido.Message('note_on', note=88, velocity=64, time=0))
    track.append(mido.Message('note_off', note=88, velocity=0, time=480))
    track.append(mido.MetaMessage('end_of_track', time=0))

    path = tmp_path / "wide_range.mid"
    mid.save(str(path))
    return path


@pytest.fixture
def midi_narrow_range(tmp_path):
    """Create MIDI file with narrow range (≤24 semitones) - simulates monophonic melody."""
    mid = mido.MidiFile(ticks_per_beat=220)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # C4 (60) to A4 (69) = 9 semitones (narrow range)
    track.append(mido.Message('note_on', note=60, velocity=64, time=0))
    track.append(mido.Message('note_off', note=60, velocity=0, time=480))
    track.append(mido.Message('note_on', note=69, velocity=64, time=0))
    track.append(mido.Message('note_off', note=69, velocity=0, time=480))
    track.append(mido.MetaMessage('end_of_track', time=0))

    path = tmp_path / "narrow_range.mid"
    mid.save(str(path))
    return path


class TestExtractMonophonicMelody:
    """Tests for the extract_monophonic_melody() function."""

    def test_skyline_algorithm_keeps_highest_pitch(self, pipeline, midi_with_octaves):
        """Skyline algorithm should keep C6 (highest) and remove C4."""
        result_path = pipeline.extract_monophonic_melody(midi_with_octaves)

        # Load result and extract notes
        mid = mido.MidiFile(result_path)
        notes = []
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes.append(msg.note)

        assert len(notes) == 1, f"Should have exactly one note, got {len(notes)}"
        assert notes[0] == 84, f"Should keep C6 (84), not C4 (60), got {notes[0]}"

    def test_preserves_single_notes_unchanged(self, pipeline, midi_with_single_notes):
        """Single sequential notes should pass through unchanged."""
        result_path = pipeline.extract_monophonic_melody(midi_with_single_notes)

        # Load result and extract notes
        mid = mido.MidiFile(result_path)
        notes = []
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes.append(msg.note)

        assert len(notes) == 3, f"Should preserve all 3 notes, got {len(notes)}"
        assert notes == [60, 62, 64], f"Should preserve C4, D4, E4, got {notes}"

    def test_handles_onset_tolerance(self, pipeline, midi_with_close_onset):
        """Notes within ONSET_TOLERANCE (10 ticks) should be treated as simultaneous."""
        result_path = pipeline.extract_monophonic_melody(midi_with_close_onset)

        # Load result and extract notes
        mid = mido.MidiFile(result_path)
        notes = []
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes.append(msg.note)

        # C4 (60, pitch class 0) and G4 (67, pitch class 7) start within 5 ticks
        # Different pitch classes → both should be kept
        assert len(notes) == 2, f"Should keep both notes (different pitch classes), got {len(notes)}"
        assert set(notes) == {60, 67}, f"Should keep both C4 (60) and G4 (67), got {notes}"

    def test_consecutive_same_pitch_preserved(self, pipeline, midi_with_consecutive_same_pitch):
        """Consecutive same-pitch notes should be preserved (not merged)."""
        result_path = pipeline.extract_monophonic_melody(midi_with_consecutive_same_pitch)

        # Load result and extract notes
        mid = mido.MidiFile(result_path)
        notes = []
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes.append(msg.note)

        assert len(notes) == 2, f"Should preserve both C4 notes, got {len(notes)}"
        assert notes == [60, 60], f"Should have two C4 notes, got {notes}"

    def test_removes_multiple_octave_duplicates(self, pipeline, midi_with_triple_octaves):
        """Should keep only the highest pitch from multiple simultaneous octaves."""
        result_path = pipeline.extract_monophonic_melody(midi_with_triple_octaves)

        # Load result and extract notes
        mid = mido.MidiFile(result_path)
        notes = []
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes.append(msg.note)

        assert len(notes) == 1, f"Should have exactly one note from three octaves, got {len(notes)}"
        assert notes[0] == 84, f"Should keep C6 (84) as highest, got {notes[0]}"

    def test_preserves_different_pitch_classes(self, pipeline, midi_with_different_pitch_classes):
        """Should preserve notes of different pitch classes (bass + treble)."""
        result_path = pipeline.extract_monophonic_melody(midi_with_different_pitch_classes)

        # Load result and extract notes
        mid = mido.MidiFile(result_path)
        notes = []
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes.append(msg.note)

        # D2 (38, pitch class 2) and A5 (81, pitch class 9) are different
        # Both should be preserved (simulates piano left + right hand)
        assert len(notes) == 2, f"Should preserve both bass and treble notes, got {len(notes)}"
        assert set(notes) == {38, 81}, f"Should keep both D2 (38) and A5 (81), got {notes}"


class TestRangeDetection:
    """Tests for MIDI range detection and adaptive processing."""

    def test_detects_wide_range_piano(self, pipeline, midi_wide_range):
        """Should detect wide range (>24 semitones) as polyphonic."""
        range_semitones = pipeline._get_midi_range(midi_wide_range)

        # D2 (38) to E6 (88) = 50 semitones
        assert range_semitones == 50, f"Expected 50 semitones, got {range_semitones}"
        assert range_semitones > 24, "Should be detected as wide range (polyphonic)"

    def test_detects_narrow_range_melody(self, pipeline, midi_narrow_range):
        """Should detect narrow range (≤24 semitones) as monophonic."""
        range_semitones = pipeline._get_midi_range(midi_narrow_range)

        # C4 (60) to A4 (69) = 9 semitones
        assert range_semitones == 9, f"Expected 9 semitones, got {range_semitones}"
        assert range_semitones <= 24, "Should be detected as narrow range (monophonic)"

    def test_empty_midi_returns_zero_range(self, pipeline, tmp_path):
        """Should return 0 for MIDI with no notes."""
        mid = mido.MidiFile(ticks_per_beat=220)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage('end_of_track', time=0))

        path = tmp_path / "empty.mid"
        mid.save(str(path))

        range_semitones = pipeline._get_midi_range(path)
        assert range_semitones == 0, f"Expected 0 for empty MIDI, got {range_semitones}"
