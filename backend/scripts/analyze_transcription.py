#!/usr/bin/env python3
"""
Analyze transcription quality and identify common issues.

Usage (from backend directory):
    python scripts/analyze_transcription.py <midi_path>

Example:
    python scripts/analyze_transcription.py /tmp/rescored/temp/test_e2e/piano.mid
"""
import sys
from pathlib import Path
import mido
from collections import Counter
import statistics


def analyze_midi(midi_path: Path):
    """Analyze MIDI file for common transcription issues."""
    mid = mido.MidiFile(midi_path)

    # Collect all notes with timing
    notes = []  # (time, pitch, velocity, duration)

    for track in mid.tracks:
        absolute_time = 0
        active_notes = {}  # pitch -> (start_time, velocity)

        for msg in track:
            absolute_time += msg.time

            if msg.type == 'note_on' and msg.velocity > 0:
                active_notes[msg.note] = (absolute_time, msg.velocity)

            elif msg.type in ['note_off', 'note_on']:  # note_on with velocity 0 is also note_off
                if msg.note in active_notes:
                    start_time, velocity = active_notes.pop(msg.note)
                    duration = absolute_time - start_time
                    notes.append((start_time, msg.note, velocity, duration))

    if not notes:
        print("No notes found in MIDI file!")
        return

    # Sort notes by time
    notes.sort(key=lambda n: n[0])

    # Analysis
    print("=" * 60)
    print("MIDI Transcription Analysis")
    print("=" * 60)
    print(f"File: {midi_path.name}")
    print(f"Duration: {mid.length:.1f} seconds")
    print(f"Total notes: {len(notes)}")
    print(f"Notes per second: {len(notes) / mid.length:.2f}")
    print()

    # Pitch analysis
    pitches = [n[1] for n in notes]
    pitch_counts = Counter(pitches)
    print("Pitch Range:")
    print(f"  Lowest: {min(pitches)} (MIDI) = {_midi_to_note(min(pitches))}")
    print(f"  Highest: {max(pitches)} (MIDI) = {_midi_to_note(max(pitches))}")
    print(f"  Range: {max(pitches) - min(pitches)} semitones")
    print()

    # Duration analysis
    durations_ticks = [n[3] for n in notes]
    durations_seconds = [mido.tick2second(d, mid.ticks_per_beat, 500000) for d in durations_ticks]
    print("Note Durations:")
    print(f"  Average: {statistics.mean(durations_seconds):.3f} seconds")
    print(f"  Median: {statistics.median(durations_seconds):.3f} seconds")
    print(f"  Min: {min(durations_seconds):.3f} seconds")
    print(f"  Max: {max(durations_seconds):.3f} seconds")

    # Identify very short notes (likely noise/false positives)
    very_short_notes = [d for d in durations_seconds if d < 0.1]  # < 100ms
    short_notes = [d for d in durations_seconds if d < 0.2]  # < 200ms
    print(f"  Very short notes (< 100ms): {len(very_short_notes)} ({len(very_short_notes)/len(notes)*100:.1f}%)")
    print(f"  Short notes (< 200ms): {len(short_notes)} ({len(short_notes)/len(notes)*100:.1f}%)")
    print()

    # Velocity analysis
    velocities = [n[2] for n in notes]
    print("Velocity (dynamics):")
    print(f"  Average: {statistics.mean(velocities):.1f}")
    print(f"  Min: {min(velocities)}")
    print(f"  Max: {max(velocities)}")
    print(f"  Range: {max(velocities) - min(velocities)}")

    # Identify very quiet notes (likely noise/false positives)
    quiet_notes = [v for v in velocities if v < 30]
    print(f"  Very quiet notes (velocity < 30): {len(quiet_notes)} ({len(quiet_notes)/len(notes)*100:.1f}%)")
    print()

    # Polyphony analysis (notes happening at same time)
    time_windows = {}  # time_window -> count
    window_size = 50  # 50 ticks
    for note_time, _, _, _ in notes:
        window = note_time // window_size
        time_windows[window] = time_windows.get(window, 0) + 1

    max_polyphony = max(time_windows.values())
    avg_polyphony = statistics.mean(time_windows.values())
    print("Polyphony (simultaneous notes):")
    print(f"  Max simultaneous: ~{max_polyphony}")
    print(f"  Average: ~{avg_polyphony:.1f}")
    print()

    # Most common pitches
    print("Most frequent pitches (top 10):")
    for pitch, count in pitch_counts.most_common(10):
        print(f"  {_midi_to_note(pitch):>3s} (MIDI {pitch:>2d}): {count:>4d} times ({count/len(notes)*100:>5.1f}%)")
    print()

    # Identify potential issues
    print("Potential Issues:")
    issues = []

    if len(very_short_notes) / len(notes) > 0.3:
        issues.append(f"⚠️  {len(very_short_notes)/len(notes)*100:.1f}% of notes are very short (< 100ms) - likely false positives")

    if len(quiet_notes) / len(notes) > 0.3:
        issues.append(f"⚠️  {len(quiet_notes)/len(notes)*100:.1f}% of notes are very quiet (velocity < 30) - likely noise")

    if len(notes) / mid.length > 15:
        issues.append(f"⚠️  Very high note density ({len(notes) / mid.length:.1f} notes/sec) - likely over-transcribing")

    if max_polyphony > 20:
        issues.append(f"⚠️  Very high polyphony (max {max_polyphony} notes) - likely detecting noise as notes")

    if min(pitches) < 21 or max(pitches) > 108:
        issues.append(f"⚠️  Notes outside piano range (MIDI 21-108) detected")

    if not issues:
        print("  ✓ No obvious issues detected")
    else:
        for issue in issues:
            print(f"  {issue}")

    print()
    print("Recommendations:")
    if len(very_short_notes) / len(notes) > 0.3:
        print("  • Increase minimum-note-length threshold in basic-pitch")
    if len(quiet_notes) / len(notes) > 0.3:
        print("  • Increase frame-threshold in basic-pitch to ignore quieter notes")
    if len(notes) / mid.length > 15:
        print("  • Increase onset-threshold in basic-pitch to be less sensitive")
    if max_polyphony > 20:
        print("  • Use median filtering or harmonic analysis to remove noise")

    print("=" * 60)


def _midi_to_note(midi_num):
    """Convert MIDI number to note name."""
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (midi_num // 12) - 1
    note = notes[midi_num % 12]
    return f"{note}{octave}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_transcription.py <midi_path>")
        print("\nExample:")
        print("  python analyze_transcription.py /tmp/rescored/temp/test_e2e/piano.mid")
        sys.exit(1)

    midi_path = Path(sys.argv[1])
    if not midi_path.exists():
        print(f"Error: File not found: {midi_path}")
        sys.exit(1)

    analyze_midi(midi_path)
