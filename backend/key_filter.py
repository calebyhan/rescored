"""
Key-Aware MIDI Filtering

Filters out notes that are inconsistent with the detected key signature.
Removes isolated out-of-key notes that are likely false positives.

Expected Impact: +1-2% precision improvement (especially for tonal music)
"""

from pathlib import Path
from typing import List, Set, Optional
import pretty_midi
from music21 import scale, pitch


class KeyAwareFilter:
    """
    Filter MIDI notes based on key signature analysis.

    Removes isolated out-of-key notes that are likely false positives while
    preserving intentional chromatic notes (passing tones, accidentals).
    """

    def __init__(
        self,
        allow_chromatic: bool = True,
        isolation_threshold: float = 0.5
    ):
        """
        Initialize key-aware filter.

        Args:
            allow_chromatic: Allow chromatic passing tones (brief out-of-key notes)
            isolation_threshold: Time threshold (seconds) to consider note "isolated"
        """
        self.allow_chromatic = allow_chromatic
        self.isolation_threshold = isolation_threshold

    def filter_midi_by_key(
        self,
        midi_path: Path,
        detected_key: str,
        output_path: Optional[Path] = None,
        tempo_bpm: Optional[float] = None
    ) -> Path:
        """
        Filter MIDI notes based on key signature.

        Args:
            midi_path: Input MIDI file
            detected_key: Detected key (e.g., "C major", "A minor")
            output_path: Output path (default: input_path with _key_filtered suffix)
            tempo_bpm: Correct tempo in BPM (if None, uses estimate_tempo which may be wrong)

        Returns:
            Path to filtered MIDI file
        """
        # Parse key signature
        key_pitches = self._get_key_pitches(detected_key)

        # Load MIDI
        pm = pretty_midi.PrettyMIDI(str(midi_path))

        # Create new MIDI with filtered notes - use provided tempo or estimate
        if tempo_bpm is not None:
            filtered_pm = pretty_midi.PrettyMIDI(initial_tempo=tempo_bpm)
        else:
            filtered_pm = pretty_midi.PrettyMIDI(initial_tempo=pm.estimate_tempo())

        total_notes = 0
        kept_notes = 0

        for inst in pm.instruments:
            if inst.is_drum:
                # Keep drum tracks as-is
                filtered_pm.instruments.append(inst)
                continue

            # Create new instrument with filtered notes
            filtered_inst = pretty_midi.Instrument(
                program=inst.program,
                is_drum=inst.is_drum,
                name=inst.name
            )

            # Sort notes by onset for isolation detection
            sorted_notes = sorted(inst.notes, key=lambda n: n.start)

            for i, note in enumerate(sorted_notes):
                total_notes += 1

                # Check if note should be kept
                if self._should_keep_note(note, key_pitches, sorted_notes, i):
                    filtered_inst.notes.append(note)
                    kept_notes += 1

            filtered_pm.instruments.append(filtered_inst)

        # Set output path
        if output_path is None:
            output_path = midi_path.with_stem(f"{midi_path.stem}_key_filtered")

        # Save filtered MIDI
        filtered_pm.write(str(output_path))

        removed = total_notes - kept_notes
        print(f"   Key-aware filtering: kept {kept_notes}/{total_notes} notes (removed {removed})")

        return output_path

    def _get_key_pitches(self, detected_key: str) -> Set[int]:
        """
        Get pitch classes that are in the detected key.

        Args:
            detected_key: Key signature (e.g., "C major", "A minor")

        Returns:
            Set of pitch classes (0-11) in the key
        """
        # Parse key signature
        key_parts = detected_key.split()
        if len(key_parts) != 2:
            # Default to C major if parsing fails
            print(f"   ⚠ Could not parse key '{detected_key}', defaulting to C major")
            key_parts = ["C", "major"]

        key_root = key_parts[0]
        key_mode = key_parts[1].lower()

        # Create scale
        try:
            if key_mode == "major":
                key_scale = scale.MajorScale(key_root)
            elif key_mode == "minor":
                key_scale = scale.MinorScale(key_root)
            else:
                # Default to major
                key_scale = scale.MajorScale(key_root)

            # Get pitch classes in key
            pitch_classes = set()
            for p in key_scale.pitches:
                pitch_classes.add(p.pitchClass)

            return pitch_classes

        except Exception as e:
            print(f"   ⚠ Error creating scale for '{detected_key}': {e}")
            # Default to chromatic (all notes) if error
            return set(range(12))

    def _is_in_key(self, note_pitch: int, key_pitches: Set[int]) -> bool:
        """
        Check if a note is in the key signature.

        Args:
            note_pitch: MIDI note number (0-127)
            key_pitches: Set of pitch classes (0-11) in the key

        Returns:
            True if note is in key, False otherwise
        """
        pitch_class = note_pitch % 12
        return pitch_class in key_pitches

    def _is_isolated(
        self,
        note: pretty_midi.Note,
        sorted_notes: List[pretty_midi.Note],
        note_index: int
    ) -> bool:
        """
        Check if a note is isolated (no nearby notes).

        An isolated out-of-key note is likely a false positive.

        Args:
            note: Note to check
            sorted_notes: All notes sorted by onset time
            note_index: Index of note in sorted_notes

        Returns:
            True if note is isolated, False otherwise
        """
        # Check for nearby notes (within isolation_threshold)
        has_nearby = False

        # Check previous notes
        for i in range(note_index - 1, -1, -1):
            prev_note = sorted_notes[i]
            time_gap = note.start - prev_note.start

            if time_gap > self.isolation_threshold:
                break  # Too far back

            # Nearby note found
            has_nearby = True
            break

        # Check next notes
        for i in range(note_index + 1, len(sorted_notes)):
            next_note = sorted_notes[i]
            time_gap = next_note.start - note.start

            if time_gap > self.isolation_threshold:
                break  # Too far forward

            # Nearby note found
            has_nearby = True
            break

        return not has_nearby

    def _is_chromatic_passing_tone(
        self,
        note: pretty_midi.Note,
        sorted_notes: List[pretty_midi.Note],
        note_index: int,
        key_pitches: Set[int]
    ) -> bool:
        """
        Check if an out-of-key note is a chromatic passing tone.

        A chromatic passing tone:
        - Is short duration
        - Is surrounded by in-key notes
        - Steps between the surrounding notes (semitone or whole tone)

        Args:
            note: Note to check
            sorted_notes: All notes sorted by onset time
            note_index: Index of note in sorted_notes
            key_pitches: Set of pitch classes in the key

        Returns:
            True if note is likely a chromatic passing tone, False otherwise
        """
        # Must be short duration (< 0.25 seconds)
        if note.end - note.start > 0.25:
            return False

        # Check surrounding notes
        prev_note = None
        next_note = None

        # Find previous in-key note
        for i in range(note_index - 1, -1, -1):
            candidate = sorted_notes[i]
            if self._is_in_key(candidate.pitch, key_pitches):
                prev_note = candidate
                break

        # Find next in-key note
        for i in range(note_index + 1, len(sorted_notes)):
            candidate = sorted_notes[i]
            if self._is_in_key(candidate.pitch, key_pitches):
                next_note = candidate
                break

        # Must be surrounded by in-key notes
        if prev_note is None or next_note is None:
            return False

        # Check if it's a passing tone (connects prev and next)
        pitch_interval = abs(next_note.pitch - prev_note.pitch)
        is_step = pitch_interval in [1, 2, 3]  # Semitone, whole tone, or minor third

        # Check if note is between prev and next
        is_between = (
            (prev_note.pitch < note.pitch < next_note.pitch) or
            (prev_note.pitch > note.pitch > next_note.pitch)
        )

        return is_step and is_between

    def _should_keep_note(
        self,
        note: pretty_midi.Note,
        key_pitches: Set[int],
        sorted_notes: List[pretty_midi.Note],
        note_index: int
    ) -> bool:
        """
        Determine whether to keep a note based on key signature analysis.

        Keep rules:
        1. All in-key notes → keep
        2. Out-of-key but chromatic passing tone → keep (if allow_chromatic)
        3. Out-of-key and isolated → remove (likely false positive)
        4. Out-of-key with nearby notes → keep (intentional accidental)

        Args:
            note: Note to evaluate
            key_pitches: Set of pitch classes in the key
            sorted_notes: All notes sorted by onset time
            note_index: Index of note in sorted_notes

        Returns:
            True if note should be kept, False otherwise
        """
        # In-key notes always kept
        if self._is_in_key(note.pitch, key_pitches):
            return True

        # Out-of-key note - apply filtering logic

        # Check if it's a chromatic passing tone
        if self.allow_chromatic:
            if self._is_chromatic_passing_tone(note, sorted_notes, note_index, key_pitches):
                return True  # Keep passing tones

        # Check if isolated
        if self._is_isolated(note, sorted_notes, note_index):
            # Isolated out-of-key note → likely false positive → remove
            return False

        # Out-of-key but not isolated → likely intentional accidental → keep
        return True


if __name__ == "__main__":
    # Test the key filter
    import argparse

    parser = argparse.ArgumentParser(description="Test Key-Aware Filter")
    parser.add_argument("midi_file", type=str, help="Path to MIDI file")
    parser.add_argument("--key", type=str, required=True,
                       help="Detected key (e.g., 'C major', 'A minor')")
    parser.add_argument("--output", type=str, default=None,
                       help="Output MIDI file path")
    parser.add_argument("--no-chromatic", action="store_true",
                       help="Disallow chromatic passing tones")
    args = parser.parse_args()

    filter = KeyAwareFilter(
        allow_chromatic=not args.no_chromatic,
        isolation_threshold=0.5
    )

    midi_path = Path(args.midi_file)
    output_path = Path(args.output) if args.output else None

    # Filter MIDI
    filtered_path = filter.filter_midi_by_key(
        midi_path,
        detected_key=args.key,
        output_path=output_path
    )

    print(f"\n✓ Key-filtered MIDI saved: {filtered_path}")
