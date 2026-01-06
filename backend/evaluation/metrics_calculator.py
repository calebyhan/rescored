"""
Metrics Calculator using mir_eval

Computes standard music information retrieval metrics for transcription evaluation.
Uses mir_eval library for consistent, reproducible metrics.
"""

from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import pretty_midi


class MirEvalMetrics:
    """
    Calculate transcription metrics using mir_eval.

    Metrics computed:
    - Note F1 (onset): Primary metric
    - Note F1 with offset: Secondary metric
    - Precision, Recall
    - Onset/offset tolerances configurable
    """

    def __init__(
        self,
        onset_tolerance: float = 0.05,  # 50ms
        offset_tolerance: float = 0.05,
        offset_min_tolerance: float = 0.05
    ):
        """
        Initialize metrics calculator.

        Args:
            onset_tolerance: Onset tolerance in seconds (default: 50ms)
            offset_tolerance: Offset tolerance in seconds (default: 50ms)
            offset_min_tolerance: Minimum offset tolerance (default: 50ms)
        """
        try:
            import mir_eval
            self.mir_eval = mir_eval
        except ImportError:
            raise ImportError(
                "mir_eval is required for evaluation. Install with: pip install mir_eval"
            )

        self.onset_tolerance = onset_tolerance
        self.offset_tolerance = offset_tolerance
        self.offset_min_tolerance = offset_min_tolerance

    def compute(
        self,
        prediction_midi: Path,
        ground_truth_midi: Path
    ) -> Dict[str, float]:
        """
        Compute all metrics for a prediction vs ground truth.

        Args:
            prediction_midi: Path to predicted MIDI file
            ground_truth_midi: Path to ground truth MIDI file

        Returns:
            Dict with metric names and values
        """
        # Extract note arrays
        pred_intervals, pred_pitches = self._midi_to_note_arrays(prediction_midi)
        gt_intervals, gt_pitches = self._midi_to_note_arrays(ground_truth_midi)

        # Compute onset-only metrics
        # mir_eval returns tuple: (precision, recall, f1, overlap_ratio)
        onset_precision, onset_recall, onset_f1, _ = \
            self.mir_eval.transcription.precision_recall_f1_overlap(
                ref_intervals=gt_intervals,
                ref_pitches=gt_pitches,
                est_intervals=pred_intervals,
                est_pitches=pred_pitches,
                onset_tolerance=self.onset_tolerance,
                offset_ratio=None  # Onset-only
            )

        # Compute onset+offset metrics
        offset_precision, offset_recall, offset_f1, _ = \
            self.mir_eval.transcription.precision_recall_f1_overlap(
                ref_intervals=gt_intervals,
                ref_pitches=gt_pitches,
                est_intervals=pred_intervals,
                est_pitches=pred_pitches,
                onset_tolerance=self.onset_tolerance,
                offset_ratio=0.2,  # Offset within 20% of duration
                offset_min_tolerance=self.offset_min_tolerance
            )

        # Return comprehensive metrics
        return {
            # Primary metrics (onset-only)
            'precision': onset_precision,
            'recall': onset_recall,
            'f1': onset_f1,

            # Secondary metrics (onset+offset)
            'precision_with_offset': offset_precision,
            'recall_with_offset': offset_recall,
            'f1_with_offset': offset_f1,

            # Count statistics
            'n_predicted': len(pred_pitches),
            'n_ground_truth': len(gt_pitches),
            'n_true_positives': int(onset_precision * len(pred_pitches)),
            'n_false_positives': int((1 - onset_precision) * len(pred_pitches)),
            'n_false_negatives': int((1 - onset_recall) * len(gt_pitches)),
        }

    def compute_frame_metrics(
        self,
        prediction_midi: Path,
        ground_truth_midi: Path,
        fps: int = 100
    ) -> Dict[str, float]:
        """
        Compute frame-level metrics (continuous evaluation).

        Args:
            prediction_midi: Path to predicted MIDI file
            ground_truth_midi: Path to ground truth MIDI file
            fps: Frames per second (default: 100)

        Returns:
            Dict with frame-level metrics
        """
        # Convert to piano rolls
        pred_roll = self._midi_to_piano_roll(prediction_midi, fps)
        gt_roll = self._midi_to_piano_roll(ground_truth_midi, fps)

        # Ensure same length
        min_len = min(len(pred_roll), len(gt_roll))
        pred_roll = pred_roll[:min_len]
        gt_roll = gt_roll[:min_len]

        # Compute frame-level metrics
        # Flatten to binary (any pitch active at frame)
        pred_frames = (pred_roll.sum(axis=1) > 0).astype(int)
        gt_frames = (gt_roll.sum(axis=1) > 0).astype(int)

        # Compute precision, recall, F1
        tp = np.sum((pred_frames == 1) & (gt_frames == 1))
        fp = np.sum((pred_frames == 1) & (gt_frames == 0))
        fn = np.sum((pred_frames == 0) & (gt_frames == 1))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            'frame_precision': precision,
            'frame_recall': recall,
            'frame_f1': f1
        }

    def _midi_to_note_arrays(
        self,
        midi_path: Path
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert MIDI to note arrays for mir_eval.

        Args:
            midi_path: Path to MIDI file

        Returns:
            Tuple of (intervals, pitches)
            - intervals: (n_notes, 2) array of (onset, offset) in seconds
            - pitches: (n_notes,) array of MIDI pitch numbers
        """
        pm = pretty_midi.PrettyMIDI(str(midi_path))

        intervals = []
        pitches = []

        for instrument in pm.instruments:
            if instrument.is_drum:
                continue

            for note in instrument.notes:
                intervals.append([note.start, note.end])
                pitches.append(note.pitch)

        # Convert to numpy arrays
        if len(intervals) == 0:
            # Empty MIDI - return empty arrays
            intervals = np.zeros((0, 2))
            pitches = np.zeros(0)
        else:
            intervals = np.array(intervals)
            pitches = np.array(pitches)

        return intervals, pitches

    def _midi_to_piano_roll(
        self,
        midi_path: Path,
        fps: int
    ) -> np.ndarray:
        """
        Convert MIDI to piano roll.

        Args:
            midi_path: Path to MIDI file
            fps: Frames per second

        Returns:
            Piano roll array (frames, 88)
        """
        pm = pretty_midi.PrettyMIDI(str(midi_path))

        # Get duration
        duration = pm.get_end_time()
        n_frames = int(duration * fps)

        # Initialize piano roll (88 keys)
        piano_roll = np.zeros((n_frames, 88), dtype=np.float32)

        # Fill frames where notes are active
        for instrument in pm.instruments:
            if instrument.is_drum:
                continue

            for note in instrument.notes:
                # Frame range for this note
                start_frame = int(note.start * fps)
                end_frame = int(note.end * fps)

                # Piano roll index
                pitch_idx = note.pitch - 21  # A0 = 21
                if 0 <= pitch_idx < 88:
                    piano_roll[start_frame:end_frame, pitch_idx] = 1.0

        return piano_roll


def print_metrics_summary(metrics: Dict[str, float], label: str = "Metrics"):
    """
    Pretty-print metrics summary.

    Args:
        metrics: Metrics dict from compute()
        label: Label for this metrics summary
    """
    print(f"\n{'=' * 60}")
    print(f"{label}")
    print(f"{'=' * 60}")

    # Primary metrics
    print(f"\nPrimary Metrics (Onset-only, tolerance={metrics.get('onset_tolerance', 50)}ms):")
    print(f"  Precision: {metrics['precision']:.1%}")
    print(f"  Recall:    {metrics['recall']:.1%}")
    print(f"  F1 Score:  {metrics['f1']:.1%}  ⭐")

    # Secondary metrics
    if 'f1_with_offset' in metrics:
        print(f"\nSecondary Metrics (Onset + Offset):")
        print(f"  Precision: {metrics['precision_with_offset']:.1%}")
        print(f"  Recall:    {metrics['recall_with_offset']:.1%}")
        print(f"  F1 Score:  {metrics['f1_with_offset']:.1%}")

    # Frame metrics
    if 'frame_f1' in metrics:
        print(f"\nFrame Metrics:")
        print(f"  Precision: {metrics['frame_precision']:.1%}")
        print(f"  Recall:    {metrics['frame_recall']:.1%}")
        print(f"  F1 Score:  {metrics['frame_f1']:.1%}")

    # Counts
    print(f"\nCounts:")
    print(f"  Ground Truth Notes: {metrics['n_ground_truth']}")
    print(f"  Predicted Notes:    {metrics['n_predicted']}")
    print(f"  True Positives:     {metrics['n_true_positives']}")
    print(f"  False Positives:    {metrics['n_false_positives']}")
    print(f"  False Negatives:    {metrics['n_false_negatives']}")

    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    """Test metrics calculator with dummy data."""
    import tempfile

    print("Testing MirEvalMetrics Calculator\n")

    # Create dummy MIDI files for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create ground truth MIDI (simple melody)
        gt_pm = pretty_midi.PrettyMIDI()
        gt_instrument = pretty_midi.Instrument(program=0)

        # Add 10 notes
        for i in range(10):
            note = pretty_midi.Note(
                velocity=80,
                pitch=60 + i,
                start=i * 0.5,
                end=(i + 1) * 0.5
            )
            gt_instrument.notes.append(note)

        gt_pm.instruments.append(gt_instrument)
        gt_path = tmpdir / "ground_truth.mid"
        gt_pm.write(str(gt_path))

        # Create prediction MIDI (90% accurate - 1 false positive, 1 false negative)
        pred_pm = pretty_midi.PrettyMIDI()
        pred_instrument = pretty_midi.Instrument(program=0)

        # Add 9 correct notes (skip note 5 - false negative)
        for i in range(10):
            if i == 5:
                continue  # False negative

            note = pretty_midi.Note(
                velocity=75,
                pitch=60 + i,
                start=i * 0.5 + 0.01,  # Slight timing offset
                end=(i + 1) * 0.5
            )
            pred_instrument.notes.append(note)

        # Add 1 false positive
        false_positive = pretty_midi.Note(
            velocity=70,
            pitch=70,
            start=5.5,
            end=6.0
        )
        pred_instrument.notes.append(false_positive)

        pred_pm.instruments.append(pred_instrument)
        pred_path = tmpdir / "prediction.mid"
        pred_pm.write(str(pred_path))

        # Compute metrics
        calculator = MirEvalMetrics(onset_tolerance=0.05)
        metrics = calculator.compute(pred_path, gt_path)

        # Print results
        print_metrics_summary(metrics, "Test Metrics (Expected: ~90% F1)")

        # Verify results
        expected_f1 = 0.9  # 9 true positives, 1 false positive, 1 false negative
        assert abs(metrics['f1'] - expected_f1) < 0.05, \
            f"F1 score {metrics['f1']:.2f} not close to expected {expected_f1:.2f}"

        print("✓ Metrics calculator test passed!")
        print(f"  Expected F1: ~{expected_f1:.1%}")
        print(f"  Actual F1:   {metrics['f1']:.1%}")
