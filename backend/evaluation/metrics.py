"""
Transcription accuracy metrics for piano transcription evaluation.

Implements F1 score, precision, recall, and timing accuracy for comparing
predicted MIDI against ground truth MIDI files.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np
from mido import MidiFile
import pretty_midi


@dataclass
class Note:
    """Represents a musical note with timing and pitch information."""
    pitch: int  # MIDI pitch (0-127)
    onset: float  # Start time in seconds
    offset: float  # End time in seconds
    velocity: int = 64  # Note velocity (0-127)

    @property
    def duration(self) -> float:
        """Note duration in seconds."""
        return self.offset - self.onset


@dataclass
class TranscriptionMetrics:
    """Container for transcription evaluation metrics."""
    precision: float  # True positives / (True positives + False positives)
    recall: float  # True positives / (True positives + False negatives)
    f1_score: float  # Harmonic mean of precision and recall
    onset_mae: float  # Mean absolute error for note onsets (seconds)
    pitch_accuracy: float  # Percentage of correct pitches (given correct onset)
    true_positives: int
    false_positives: int
    false_negatives: int

    def __str__(self) -> str:
        """Human-readable metrics summary."""
        return (
            f"F1 Score: {self.f1_score:.3f}\n"
            f"Precision: {self.precision:.3f}\n"
            f"Recall: {self.recall:.3f}\n"
            f"Onset MAE: {self.onset_mae*1000:.1f}ms\n"
            f"Pitch Accuracy: {self.pitch_accuracy:.3f}\n"
            f"TP: {self.true_positives}, FP: {self.false_positives}, FN: {self.false_negatives}"
        )


def extract_notes_from_midi(midi_path: Path) -> List[Note]:
    """
    Extract notes from a MIDI file using pretty_midi.

    Args:
        midi_path: Path to MIDI file

    Returns:
        List of Note objects sorted by onset time
    """
    try:
        pm = pretty_midi.PrettyMIDI(str(midi_path))
    except Exception as e:
        raise ValueError(f"Failed to load MIDI file {midi_path}: {e}")

    notes = []
    for instrument in pm.instruments:
        # Skip drum tracks
        if instrument.is_drum:
            continue

        for note in instrument.notes:
            notes.append(Note(
                pitch=note.pitch,
                onset=note.start,
                offset=note.end,
                velocity=note.velocity
            ))

    # Sort by onset time
    notes.sort(key=lambda n: n.onset)
    return notes


def match_notes(
    predicted_notes: List[Note],
    ground_truth_notes: List[Note],
    onset_tolerance: float = 0.05,  # 50ms
    pitch_tolerance: int = 0  # Exact pitch match
) -> Tuple[List[Tuple[Note, Note]], List[Note], List[Note]]:
    """
    Match predicted notes to ground truth notes using onset and pitch tolerance.

    Uses greedy matching: for each ground truth note, find the closest predicted
    note within tolerance. A predicted note can only match one ground truth note.

    Args:
        predicted_notes: List of predicted notes
        ground_truth_notes: List of ground truth notes
        onset_tolerance: Maximum time difference (seconds) to consider a match
        pitch_tolerance: Maximum pitch difference (semitones) to consider a match

    Returns:
        Tuple of (matches, false_positives, false_negatives) where:
        - matches: List of (predicted_note, ground_truth_note) pairs
        - false_positives: Predicted notes with no match
        - false_negatives: Ground truth notes with no match
    """
    matches = []
    matched_pred_indices = set()
    unmatched_gt = []

    # For each ground truth note, find best matching predicted note
    for gt_note in ground_truth_notes:
        best_match_idx = None
        best_onset_diff = float('inf')

        for i, pred_note in enumerate(predicted_notes):
            if i in matched_pred_indices:
                continue  # Already matched

            # Check pitch tolerance
            pitch_diff = abs(pred_note.pitch - gt_note.pitch)
            if pitch_diff > pitch_tolerance:
                continue

            # Check onset tolerance
            onset_diff = abs(pred_note.onset - gt_note.onset)
            if onset_diff <= onset_tolerance and onset_diff < best_onset_diff:
                best_match_idx = i
                best_onset_diff = onset_diff

        if best_match_idx is not None:
            matches.append((predicted_notes[best_match_idx], gt_note))
            matched_pred_indices.add(best_match_idx)
        else:
            unmatched_gt.append(gt_note)

    # Unmatched predicted notes are false positives
    false_positives = [
        note for i, note in enumerate(predicted_notes)
        if i not in matched_pred_indices
    ]

    return matches, false_positives, unmatched_gt


def calculate_metrics(
    predicted_midi: Path,
    ground_truth_midi: Path,
    onset_tolerance: float = 0.05,  # 50ms
    pitch_tolerance: int = 0  # Exact pitch
) -> TranscriptionMetrics:
    """
    Calculate transcription accuracy metrics by comparing predicted vs ground truth MIDI.

    Args:
        predicted_midi: Path to predicted MIDI file
        ground_truth_midi: Path to ground truth MIDI file
        onset_tolerance: Maximum onset time difference for matching (seconds)
        pitch_tolerance: Maximum pitch difference for matching (semitones)

    Returns:
        TranscriptionMetrics object with all evaluation metrics
    """
    # Extract notes from both files
    pred_notes = extract_notes_from_midi(predicted_midi)
    gt_notes = extract_notes_from_midi(ground_truth_midi)

    if len(gt_notes) == 0:
        raise ValueError(f"Ground truth MIDI has no notes: {ground_truth_midi}")

    # Match notes
    matches, false_positives, false_negatives = match_notes(
        pred_notes, gt_notes, onset_tolerance, pitch_tolerance
    )

    # Calculate counts
    true_positives = len(matches)
    num_false_positives = len(false_positives)
    num_false_negatives = len(false_negatives)

    # Calculate precision and recall
    precision = true_positives / (true_positives + num_false_positives) if (true_positives + num_false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + num_false_negatives) if (true_positives + num_false_negatives) > 0 else 0.0

    # Calculate F1 score
    f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Calculate onset MAE (only for matched notes)
    if len(matches) > 0:
        onset_errors = [abs(pred.onset - gt.onset) for pred, gt in matches]
        onset_mae = np.mean(onset_errors)
    else:
        onset_mae = float('inf')

    # Calculate pitch accuracy (for matched notes)
    if len(matches) > 0:
        pitch_correct = sum(1 for pred, gt in matches if pred.pitch == gt.pitch)
        pitch_accuracy = pitch_correct / len(matches)
    else:
        pitch_accuracy = 0.0

    return TranscriptionMetrics(
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        onset_mae=onset_mae,
        pitch_accuracy=pitch_accuracy,
        true_positives=true_positives,
        false_positives=num_false_positives,
        false_negatives=num_false_negatives
    )


def calculate_metrics_by_difficulty(
    predicted_midi: Path,
    ground_truth_midi: Path,
    onset_tolerance: float = 0.05
) -> dict:
    """
    Calculate metrics at multiple onset tolerances to assess difficulty.

    Stricter tolerances (20ms) test timing accuracy for simple music.
    Looser tolerances (100ms) are more forgiving for complex/fast passages.

    Args:
        predicted_midi: Path to predicted MIDI file
        ground_truth_midi: Path to ground truth MIDI file
        onset_tolerance: Default onset tolerance (seconds)

    Returns:
        Dictionary with metrics at different tolerance levels
    """
    tolerances = {
        'strict': 0.02,    # 20ms - for simple piano melodies
        'default': 0.05,   # 50ms - standard evaluation
        'lenient': 0.10    # 100ms - for fast/complex passages
    }

    results = {}
    for name, tol in tolerances.items():
        try:
            metrics = calculate_metrics(predicted_midi, ground_truth_midi, onset_tolerance=tol)
            results[name] = metrics
        except Exception as e:
            print(f"Warning: Failed to calculate {name} metrics: {e}")
            results[name] = None

    return results
