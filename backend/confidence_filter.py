"""
Confidence-Based MIDI Filtering

Filters out low-confidence notes from transcription output to reduce false positives.

Expected Impact: +1-3% precision improvement
"""

from pathlib import Path
from typing import Dict, Optional
import pretty_midi


class ConfidenceFilter:
    """
    Filter MIDI notes based on confidence scores.

    Removes low-confidence notes that are likely false positives from the
    transcription model. Works with confidence scores if available, or uses
    heuristics based on note characteristics.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        velocity_threshold: int = 20,
        duration_threshold: float = 0.05
    ):
        """
        Initialize confidence filter.

        Args:
            confidence_threshold: Minimum confidence score to keep note (0-1)
            velocity_threshold: Minimum velocity to keep note (0-127)
            duration_threshold: Minimum duration in seconds to keep note
        """
        self.confidence_threshold = confidence_threshold
        self.velocity_threshold = velocity_threshold
        self.duration_threshold = duration_threshold

    def filter_midi_by_confidence(
        self,
        midi_path: Path,
        confidence_scores: Optional[Dict] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Filter MIDI notes based on confidence scores or heuristics.

        Args:
            midi_path: Input MIDI file
            confidence_scores: Optional dict mapping (onset_time, pitch) -> confidence
            output_path: Output path (default: input_path with _filtered suffix)

        Returns:
            Path to filtered MIDI file
        """
        # Load MIDI
        pm = pretty_midi.PrettyMIDI(str(midi_path))

        # Create new MIDI with filtered notes
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

            for note in inst.notes:
                total_notes += 1

                # Get confidence score if available
                if confidence_scores is not None:
                    # Find closest note in confidence scores
                    confidence = self._get_note_confidence(
                        note,
                        confidence_scores
                    )
                else:
                    # Use heuristic confidence based on note characteristics
                    confidence = self._estimate_confidence(note)

                # Filter based on confidence and other thresholds
                if self._should_keep_note(note, confidence):
                    filtered_inst.notes.append(note)
                    kept_notes += 1

            filtered_pm.instruments.append(filtered_inst)

        # Set output path
        if output_path is None:
            output_path = midi_path.with_stem(f"{midi_path.stem}_filtered")

        # Save filtered MIDI
        filtered_pm.write(str(output_path))

        removed = total_notes - kept_notes
        print(f"   Confidence filtering: kept {kept_notes}/{total_notes} notes (removed {removed})")

        return output_path

    def _get_note_confidence(
        self,
        note: pretty_midi.Note,
        confidence_scores: Dict
    ) -> float:
        """
        Get confidence score for a note from the confidence scores dict.

        Args:
            note: Note to get confidence for
            confidence_scores: Dict mapping (onset_time, pitch) -> confidence

        Returns:
            Confidence score (0-1), or 1.0 if not found
        """
        # Try exact match
        key = (note.start, note.pitch)
        if key in confidence_scores:
            return confidence_scores[key]

        # Try approximate match (within 50ms)
        tolerance = 0.05
        for (onset, pitch), confidence in confidence_scores.items():
            if pitch == note.pitch and abs(onset - note.start) < tolerance:
                return confidence

        # Default to high confidence if not found (don't filter)
        return 1.0

    def _estimate_confidence(self, note: pretty_midi.Note) -> float:
        """
        Estimate confidence based on note characteristics (heuristic).

        Heuristics:
        - Very short notes (< 50ms) → likely false positives → low confidence
        - Very quiet notes (velocity < 20) → likely noise → low confidence
        - Normal duration + reasonable velocity → high confidence

        Args:
            note: Note to estimate confidence for

        Returns:
            Estimated confidence (0-1)
        """
        confidence = 1.0

        # Duration-based confidence
        duration = note.end - note.start
        if duration < 0.05:  # < 50ms
            confidence *= 0.3
        elif duration < 0.1:  # < 100ms
            confidence *= 0.6

        # Velocity-based confidence
        if note.velocity < 20:
            confidence *= 0.2
        elif note.velocity < 40:
            confidence *= 0.5

        return confidence

    def _should_keep_note(
        self,
        note: pretty_midi.Note,
        confidence: float
    ) -> bool:
        """
        Determine whether to keep a note based on confidence and thresholds.

        Args:
            note: Note to evaluate
            confidence: Confidence score for the note

        Returns:
            True if note should be kept, False otherwise
        """
        # Check confidence threshold
        if confidence < self.confidence_threshold:
            return False

        # Check velocity threshold
        if note.velocity < self.velocity_threshold:
            return False

        # Check duration threshold
        duration = note.end - note.start
        if duration < self.duration_threshold:
            return False

        return True


if __name__ == "__main__":
    # Test the confidence filter
    import argparse

    parser = argparse.ArgumentParser(description="Test Confidence Filter")
    parser.add_argument("midi_file", type=str, help="Path to MIDI file")
    parser.add_argument("--output", type=str, default=None,
                       help="Output MIDI file path")
    parser.add_argument("--confidence-threshold", type=float, default=0.3,
                       help="Confidence threshold (0-1)")
    parser.add_argument("--velocity-threshold", type=int, default=20,
                       help="Velocity threshold (0-127)")
    parser.add_argument("--duration-threshold", type=float, default=0.05,
                       help="Duration threshold in seconds")
    args = parser.parse_args()

    filter = ConfidenceFilter(
        confidence_threshold=args.confidence_threshold,
        velocity_threshold=args.velocity_threshold,
        duration_threshold=args.duration_threshold
    )

    midi_path = Path(args.midi_file)
    output_path = Path(args.output) if args.output else None

    # Filter MIDI
    filtered_path = filter.filter_midi_by_confidence(
        midi_path,
        confidence_scores=None,  # Use heuristics
        output_path=output_path
    )

    print(f"\n✓ Filtered MIDI saved: {filtered_path}")
