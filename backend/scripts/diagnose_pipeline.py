#!/usr/bin/env python3
"""
Diagnose pipeline accuracy issues by analyzing each stage.

Usage (from backend directory):
    python scripts/diagnose_pipeline.py <job_id>

Example:
    python scripts/diagnose_pipeline.py test_e2e
"""
import sys
from pathlib import Path
import soundfile as sf
import numpy as np
import mido

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings


def analyze_audio_file(audio_path: Path, label: str):
    """Analyze audio file characteristics."""
    print(f"\n{label}:")
    print(f"  Path: {audio_path}")

    if not audio_path.exists():
        print(f"  ❌ File not found!")
        return

    # Read audio
    data, samplerate = sf.read(audio_path)

    # Calculate statistics
    duration = len(data) / samplerate
    channels = 1 if len(data.shape) == 1 else data.shape[1]

    # RMS energy (loudness)
    if channels == 1:
        rms = np.sqrt(np.mean(data**2))
    else:
        rms = np.sqrt(np.mean(data**2, axis=0))

    # Peak amplitude
    peak = np.max(np.abs(data))

    # Dynamic range
    if channels == 1:
        dynamic_range = 20 * np.log10(peak / (rms + 1e-10))
    else:
        dynamic_range = 20 * np.log10(peak / (np.mean(rms) + 1e-10))

    print(f"  Duration: {duration:.1f}s")
    print(f"  Sample rate: {samplerate} Hz")
    print(f"  Channels: {channels}")
    print(f"  Peak amplitude: {peak:.3f}")

    if channels == 1:
        print(f"  RMS energy: {rms:.3f}")
    else:
        print(f"  RMS energy (L/R): {rms[0]:.3f} / {rms[1]:.3f}")

    print(f"  Dynamic range: {dynamic_range:.1f} dB")

    # Check for clipping
    clipped_samples = np.sum(np.abs(data) >= 0.99)
    if clipped_samples > 0:
        print(f"  ⚠️  Clipped samples: {clipped_samples} ({clipped_samples/len(data)*100:.2f}%)")

    # Check for silence
    silence_threshold = 0.01
    if channels == 1:
        silent_samples = np.sum(np.abs(data) < silence_threshold)
    else:
        silent_samples = np.sum(np.max(np.abs(data), axis=1) < silence_threshold)

    if silent_samples > len(data) * 0.1:
        print(f"  ⚠️  Silence: {silent_samples/len(data)*100:.1f}% of audio")

    # Check if mostly quiet (could indicate poor separation)
    if isinstance(rms, np.ndarray):
        avg_rms = np.mean(rms)
    else:
        avg_rms = rms

    if avg_rms < 0.01:
        print(f"  ⚠️  Very quiet audio (RMS: {avg_rms:.4f}) - may indicate poor source separation")
    elif avg_rms < 0.05:
        print(f"  ⚠️  Quiet audio (RMS: {avg_rms:.4f}) - basic-pitch may struggle")


def analyze_midi_file(midi_path: Path, label: str):
    """Analyze MIDI file."""
    print(f"\n{label}:")
    print(f"  Path: {midi_path}")

    if not midi_path.exists():
        print(f"  ❌ File not found!")
        return

    mid = mido.MidiFile(midi_path)

    # Count notes
    note_count = 0
    note_pitches = []
    note_velocities = []

    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                note_count += 1
                note_pitches.append(msg.note)
                note_velocities.append(msg.velocity)

    print(f"  Duration: {mid.length:.1f}s")
    print(f"  Total notes: {note_count}")
    print(f"  Notes per second: {note_count / mid.length:.2f}")

    if note_pitches:
        print(f"  Pitch range: {min(note_pitches)} - {max(note_pitches)}")
        print(f"  Avg velocity: {np.mean(note_velocities):.1f}")
        print(f"  Velocity range: {min(note_velocities)} - {max(note_velocities)}")


def diagnose_job(job_id: str):
    """Diagnose a specific transcription job."""
    storage_path = Path(settings.storage_path)
    job_dir = storage_path / "temp" / job_id

    print("=" * 60)
    print("PIPELINE DIAGNOSTIC REPORT")
    print("=" * 60)
    print(f"Job ID: {job_id}")
    print(f"Job Directory: {job_dir}")

    if not job_dir.exists():
        print(f"\n❌ Job directory not found: {job_dir}")
        print("\nRun test_e2e.py first to create a job:")
        print(f'  python scripts/test_e2e.py "https://www.youtube.com/watch?v=VIDEO_ID"')
        sys.exit(1)

    print("\n" + "=" * 60)
    print("STAGE 1: AUDIO DOWNLOAD")
    print("=" * 60)

    audio_path = job_dir / "audio.wav"
    analyze_audio_file(audio_path, "Downloaded Audio")

    print("\n" + "=" * 60)
    print("STAGE 2: SOURCE SEPARATION (Demucs)")
    print("=" * 60)

    demucs_dir = job_dir / "htdemucs" / "audio"
    other_stem = demucs_dir / "other.wav"
    no_other_stem = demucs_dir / "no_other.wav"

    analyze_audio_file(other_stem, "Other Stem (Piano/Melodic)")
    analyze_audio_file(no_other_stem, "No-Other Stem (Drums/Bass/Vocals)")

    # Compare separation quality
    if audio_path.exists() and other_stem.exists() and no_other_stem.exists():
        print("\n  Separation Quality Check:")

        # Read all audio
        original, sr = sf.read(audio_path)
        other, _ = sf.read(other_stem)
        no_other, _ = sf.read(no_other_stem)

        # Calculate energy distribution
        original_energy = np.sum(original**2)
        other_energy = np.sum(other**2)
        no_other_energy = np.sum(no_other**2)
        total_separated_energy = other_energy + no_other_energy

        print(f"  Original energy: {original_energy:.2e}")
        print(f"  Other energy: {other_energy:.2e} ({other_energy/original_energy*100:.1f}%)")
        print(f"  No-other energy: {no_other_energy:.2e} ({no_other_energy/original_energy*100:.1f}%)")
        print(f"  Energy preservation: {total_separated_energy/original_energy*100:.1f}%")

        # Check if 'other' stem is too quiet (bad separation)
        if other_energy / original_energy < 0.1:
            print(f"  ⚠️  'Other' stem has very low energy - poor separation for melodic content")
        elif other_energy / original_energy < 0.2:
            print(f"  ⚠️  'Other' stem has low energy - separation may not be ideal")

    print("\n" + "=" * 60)
    print("STAGE 3: TRANSCRIPTION (basic-pitch)")
    print("=" * 60)

    piano_midi = job_dir / "piano.mid"
    analyze_midi_file(piano_midi, "Raw MIDI Output")

    print("\n" + "=" * 60)
    print("STAGE 4: MIDI CLEANING")
    print("=" * 60)

    clean_midi = job_dir / "piano_clean.mid"
    analyze_midi_file(clean_midi, "Cleaned MIDI Output")

    # Compare raw vs cleaned
    if piano_midi.exists() and clean_midi.exists():
        raw_mid = mido.MidiFile(piano_midi)
        clean_mid = mido.MidiFile(clean_midi)

        raw_notes = sum(1 for track in raw_mid.tracks for msg in track if msg.type == 'note_on' and msg.velocity > 0)
        clean_notes = sum(1 for track in clean_mid.tracks for msg in track if msg.type == 'note_on' and msg.velocity > 0)

        removed_notes = raw_notes - clean_notes
        print(f"\n  Cleaning Impact:")
        print(f"  Notes removed: {removed_notes} ({removed_notes/raw_notes*100:.1f}%)")

        if removed_notes / raw_notes > 0.5:
            print(f"  ⚠️  Removed >50% of notes - cleaning may be too aggressive")

    print("\n" + "=" * 60)
    print("DIAGNOSIS SUMMARY")
    print("=" * 60)

    # Provide recommendations based on analysis
    print("\nPotential Issues:")

    issues_found = False

    # Check 1: Source separation quality
    if other_stem.exists():
        other_data, _ = sf.read(other_stem)
        other_rms = np.sqrt(np.mean(other_data**2))

        if other_rms < 0.05:
            print("  ⚠️  'Other' stem is very quiet - Demucs may not be separating piano well")
            print("     → This is the most likely cause of poor transcription accuracy")
            print("     → The piano might be mixed with other instruments in different stems")
            issues_found = True

    # Check 2: Note density
    if piano_midi.exists():
        mid = mido.MidiFile(piano_midi)
        note_count = sum(1 for track in mid.tracks for msg in track if msg.type == 'note_on' and msg.velocity > 0)
        density = note_count / mid.length

        if density < 2:
            print("  ⚠️  Very low note density - basic-pitch may be too conservative")
            print("     → Try decreasing onset-threshold and frame-threshold")
            issues_found = True
        elif density > 10:
            print("  ⚠️  Very high note density - basic-pitch may be too aggressive")
            print("     → Current thresholds might already be good; check if it's detecting noise")
            issues_found = True

    if not issues_found:
        print("  No obvious technical issues detected")
        print("  The problem may be:")
        print("    • Music is too complex for current models")
        print("    • Need better source separation (try different Demucs model)")
        print("    • basic-pitch limitations with this type of music")

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)

    print("""
Next steps to improve accuracy:

1. LISTEN to the separated stems:
   - Play 'other.wav' to verify piano is properly separated
   - If piano is barely audible, source separation failed

2. Try different Demucs models:
   - Current: htdemucs with --two-stems=other
   - Try: htdemucs_6s (6-stem with dedicated piano separation)
   - Command: demucs --model htdemucs_6s audio.wav

3. Test with simpler music:
   - Solo piano (no other instruments)
   - Clear, slow melodies
   - This helps isolate if issue is separation or transcription

4. Compare with ground truth:
   - Find sheet music for the test song
   - Compare transcribed notes with actual notes
   - Identify patterns (missing high notes? wrong octaves?)

5. Try alternative transcription models:
   - MT3 (Music Transformer) - slower but more accurate
   - Omnizart piano model - specialized for piano
""")

    print("=" * 60)
    print("\nTo listen to the separated 'other' stem:")
    print(f"  play {other_stem}")
    print(f"  # or")
    print(f"  ffplay {other_stem}")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_pipeline.py <job_id>")
        print("\nExample:")
        print("  python scripts/diagnose_pipeline.py test_e2e")
        print("\nFirst run test_e2e.py to create a job:")
        print('  python scripts/test_e2e.py "https://www.youtube.com/watch?v=VIDEO_ID"')
        sys.exit(1)

    job_id = sys.argv[1]
    diagnose_job(job_id)
