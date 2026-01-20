"""
Playability-Focused MIDI Filtering

Transforms full instrumental transcription into a playable piano arrangement.
Prioritizes: playability > note-perfect accuracy

Key filters (applied in order):
1. Basic filtering - velocity and minimum duration thresholds
2. Repeated note filtering - removes guitar strums/arpeggios
3. Duration limiting - caps note duration by register (piano decay)
4. Polyphony reduction - limits simultaneous notes to playable range

Expected Impact: Converts dense multi-instrument transcription to playable piano
"""

from pathlib import Path
from typing import List, Optional
from collections import defaultdict
import pretty_midi


class PlayabilityFilter:
    """
    Transform full instrumental MIDI into playable piano arrangement.

    Use case: Creating playable backing tracks where completeness matters
    more than note-perfect accuracy.
    """

    def __init__(
        self,
        max_polyphony: int = 8,
        melody_priority: bool = True,
        bass_priority: bool = True,
        max_duration_high: float = 2.0,  # Above C5 (MIDI 72)
        max_duration_mid: float = 3.5,   # C3-C5 (MIDI 48-72)
        max_duration_low: float = 5.0,   # Below C3 (MIDI 48)
        repeated_note_threshold_ms: int = 150,
        velocity_threshold: int = 25,
        duration_threshold: float = 0.08
    ):
        """
        Initialize playability filter.

        Args:
            max_polyphony: Maximum simultaneous notes (default 8, playable by human hands)
            melody_priority: Keep highest notes when reducing polyphony
            bass_priority: Keep lowest notes when reducing polyphony
            max_duration_high: Max duration for notes above C5 (fast decay)
            max_duration_mid: Max duration for notes C3-C5 (medium decay)
            max_duration_low: Max duration for notes below C3 (slow decay)
            repeated_note_threshold_ms: Remove same pitch within this window
            velocity_threshold: Minimum velocity to keep note
            duration_threshold: Minimum duration in seconds to keep note
        """
        self.max_polyphony = max_polyphony
        self.melody_priority = melody_priority
        self.bass_priority = bass_priority
        self.max_duration_high = max_duration_high
        self.max_duration_mid = max_duration_mid
        self.max_duration_low = max_duration_low
        self.repeated_note_threshold_ms = repeated_note_threshold_ms
        self.velocity_threshold = velocity_threshold
        self.duration_threshold = duration_threshold

    def filter_midi(
        self,
        midi_path: Path,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Apply all playability filters to MIDI file.

        Filter order matters:
        1. Basic filtering (velocity, duration) - removes noise
        2. Repeated note filtering - removes guitar strums
        3. Duration limiting by register - piano-like decay
        4. Polyphony reduction - ensures playability (most aggressive, applied last)

        Args:
            midi_path: Input MIDI file
            output_path: Output path (default: input_path with _playable suffix)

        Returns:
            Path to filtered MIDI file
        """
        pm = pretty_midi.PrettyMIDI(str(midi_path))

        total_before = sum(len(inst.notes) for inst in pm.instruments if not inst.is_drum)

        for inst in pm.instruments:
            if inst.is_drum:
                continue

            # Step 1: Basic filtering
            inst.notes = self._filter_basic(inst.notes)

            # Step 2: Remove repeated notes
            inst.notes = self._filter_repeated_notes(inst.notes)

            # Step 3: Limit duration by register
            inst.notes = self._limit_duration_by_register(inst.notes)

            # Step 4: Reduce polyphony (most aggressive)
            inst.notes = self._reduce_polyphony(inst.notes)

        total_after = sum(len(inst.notes) for inst in pm.instruments if not inst.is_drum)

        if output_path is None:
            output_path = midi_path.with_stem(f"{midi_path.stem}_playable")

        pm.write(str(output_path))

        retention = (total_after / total_before * 100) if total_before > 0 else 100
        print(f"   Playability filtering: {total_before} → {total_after} notes "
              f"({retention:.1f}% retained)")

        return output_path

    def _filter_basic(self, notes: List[pretty_midi.Note]) -> List[pretty_midi.Note]:
        """
        Filter by velocity and minimum duration.

        Removes:
        - Very quiet notes (likely bleed/noise)
        - Very short notes (likely false positives)
        """
        return [
            n for n in notes
            if n.velocity >= self.velocity_threshold
            and (n.end - n.start) >= self.duration_threshold
        ]

    def _filter_repeated_notes(
        self,
        notes: List[pretty_midi.Note]
    ) -> List[pretty_midi.Note]:
        """
        Remove same pitch repeated within threshold window.

        This filters out guitar strumming artifacts where the same pitch
        appears multiple times in quick succession (impossible on piano).

        Keeps the loudest note in each group of repeated notes.
        """
        if not notes:
            return notes

        threshold_sec = self.repeated_note_threshold_ms / 1000.0

        # Group notes by pitch
        by_pitch = defaultdict(list)
        for note in notes:
            by_pitch[note.pitch].append(note)

        filtered = []

        for pitch, pitch_notes in by_pitch.items():
            # Sort by onset time
            pitch_notes.sort(key=lambda n: n.start)

            i = 0
            while i < len(pitch_notes):
                current = pitch_notes[i]

                # Collect all notes within threshold
                group = [current]
                j = i + 1
                while j < len(pitch_notes):
                    if pitch_notes[j].start - current.start < threshold_sec:
                        group.append(pitch_notes[j])
                        j += 1
                    else:
                        break

                # Keep the loudest note in the group
                best = max(group, key=lambda n: n.velocity)
                filtered.append(best)
                i = j

        return sorted(filtered, key=lambda n: n.start)

    def _limit_duration_by_register(
        self,
        notes: List[pretty_midi.Note]
    ) -> List[pretty_midi.Note]:
        """
        Cap note duration based on register.

        Piano notes naturally decay faster in higher registers:
        - High register (above C5): ~2 seconds
        - Mid register (C3-C5): ~3.5 seconds
        - Low register (below C3): ~5 seconds

        Guitar/strings/pads often have much longer sustains that don't
        translate well to piano notation.
        """
        for note in notes:
            duration = note.end - note.start

            if note.pitch >= 72:  # Above C5
                max_dur = self.max_duration_high
            elif note.pitch >= 48:  # C3-C5
                max_dur = self.max_duration_mid
            else:  # Below C3
                max_dur = self.max_duration_low

            if duration > max_dur:
                note.end = note.start + max_dur

        return notes

    def _reduce_polyphony(
        self,
        notes: List[pretty_midi.Note]
    ) -> List[pretty_midi.Note]:
        """
        Reduce simultaneous notes to max_polyphony.

        Priority (when reducing):
        1. Keep highest note (melody) if melody_priority=True
        2. Keep lowest note (bass) if bass_priority=True
        3. Fill remaining slots with highest velocity notes

        Uses onset-based grouping (30ms tolerance) to identify
        simultaneous note clusters.
        """
        if not notes:
            return notes

        sorted_notes = sorted(notes, key=lambda n: n.start)
        onset_tolerance = 0.03  # 30ms

        # Group notes by onset time
        onset_groups = []
        current_group = []
        current_time = -1

        for note in sorted_notes:
            if current_time < 0 or note.start - current_time > onset_tolerance:
                if current_group:
                    onset_groups.append(current_group)
                current_group = [note]
                current_time = note.start
            else:
                current_group.append(note)

        if current_group:
            onset_groups.append(current_group)

        # Reduce each group to max_polyphony
        filtered = []

        for group in onset_groups:
            if len(group) <= self.max_polyphony:
                filtered.extend(group)
                continue

            # Apply priority selection
            keep = []
            remaining = list(group)

            # Priority 1: Keep melody (highest pitch)
            if self.melody_priority and remaining:
                melody = max(remaining, key=lambda n: n.pitch)
                keep.append(melody)
                remaining.remove(melody)

            # Priority 2: Keep bass (lowest pitch)
            if self.bass_priority and remaining:
                bass = min(remaining, key=lambda n: n.pitch)
                keep.append(bass)
                remaining.remove(bass)

            # Priority 3: Fill with highest velocity
            slots_left = self.max_polyphony - len(keep)
            if slots_left > 0 and remaining:
                remaining.sort(key=lambda n: n.velocity, reverse=True)
                keep.extend(remaining[:slots_left])

            filtered.extend(keep)

        return filtered


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Playability Filter")
    parser.add_argument("midi_file", type=str, help="Path to MIDI file")
    parser.add_argument("--output", type=str, default=None,
                       help="Output MIDI file path")
    parser.add_argument("--max-polyphony", type=int, default=8,
                       help="Maximum simultaneous notes")
    parser.add_argument("--velocity-threshold", type=int, default=25,
                       help="Minimum velocity to keep (0-127)")
    parser.add_argument("--duration-threshold", type=float, default=0.08,
                       help="Minimum duration in seconds")
    parser.add_argument("--repeated-note-threshold", type=int, default=150,
                       help="Remove same pitch within this window (ms)")
    args = parser.parse_args()

    filter = PlayabilityFilter(
        max_polyphony=args.max_polyphony,
        velocity_threshold=args.velocity_threshold,
        duration_threshold=args.duration_threshold,
        repeated_note_threshold_ms=args.repeated_note_threshold
    )

    midi_path = Path(args.midi_file)
    output_path = Path(args.output) if args.output else None

    filtered_path = filter.filter_midi(midi_path, output_path=output_path)

    print(f"\n✓ Playable MIDI saved: {filtered_path}")
