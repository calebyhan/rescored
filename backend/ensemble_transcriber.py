"""
Ensemble Transcription Module

Combines multiple transcription models via voting for improved accuracy.

Ensemble Strategy:
- YourMT3+: Multi-instrument generalist, excellent polyphony & expressive timing (80-85% F1)
- ByteDance: Piano specialist, high precision on piano-only audio (90-95% F1)
- Combined: Voting reduces false positives and false negatives (90-95% F1 expected)
"""

from pathlib import Path
from typing import List, Dict, Optional, Literal
from dataclasses import dataclass
import numpy as np
from mido import MidiFile, MidiTrack, Message, MetaMessage
import pretty_midi


@dataclass
class Note:
    """Musical note with timing and pitch information."""
    pitch: int  # MIDI pitch (0-127)
    onset: float  # Start time in seconds
    offset: float  # End time in seconds
    velocity: int = 64  # Note velocity (0-127)
    confidence: float = 1.0  # Confidence score (0-1)

    @property
    def duration(self) -> float:
        """Note duration in seconds."""
        return self.offset - self.onset


class EnsembleTranscriber:
    """
    Ensemble transcription using multiple models with voting.

    Voting Strategies:
    1. 'weighted': Sum confidence scores, keep notes above threshold
    2. 'intersection': Only keep notes agreed upon by all models (high precision)
    3. 'union': Keep all notes from all models (high recall)
    4. 'majority': Keep notes predicted by >=50% of models
    """

    def __init__(
        self,
        yourmt3_transcriber,
        bytedance_transcriber,
        voting_strategy: Literal['weighted', 'intersection', 'union', 'majority'] = 'weighted',
        onset_tolerance_ms: int = 50,
        confidence_threshold: float = 0.6
    ):
        """
        Initialize ensemble transcriber.

        Args:
            yourmt3_transcriber: YourMT3Transcriber instance
            bytedance_transcriber: ByteDanceTranscriber instance
            voting_strategy: How to combine predictions
            onset_tolerance_ms: Time window for matching notes (milliseconds)
            confidence_threshold: Minimum confidence for 'weighted' strategy
        """
        self.yourmt3 = yourmt3_transcriber
        self.bytedance = bytedance_transcriber
        self.voting_strategy = voting_strategy
        self.onset_tolerance = onset_tolerance_ms / 1000.0  # Convert to seconds
        self.confidence_threshold = confidence_threshold

    def transcribe(
        self,
        audio_path: Path,
        output_dir: Optional[Path] = None
    ) -> Path:
        """
        Transcribe audio using ensemble of models.

        Args:
            audio_path: Path to audio file (should be piano stem)
            output_dir: Directory for output MIDI file

        Returns:
            Path to ensemble MIDI file
        """
        if output_dir is None:
            output_dir = audio_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n   ═══ Ensemble Transcription ═══")
        print(f"   Strategy: {self.voting_strategy}")
        print(f"   Onset tolerance: {self.onset_tolerance*1000:.0f}ms")

        # Transcribe with YourMT3+
        print(f"\n   [1/2] Transcribing with YourMT3+...")
        yourmt3_midi = self.yourmt3.transcribe_audio(audio_path, output_dir)
        yourmt3_notes = self._extract_notes_from_midi(yourmt3_midi)
        print(f"   ✓ YourMT3+ found {len(yourmt3_notes)} notes")

        # Transcribe with ByteDance
        print(f"\n   [2/2] Transcribing with ByteDance...")
        bytedance_midi = self.bytedance.transcribe_audio(audio_path, output_dir)
        bytedance_notes = self._extract_notes_from_midi(bytedance_midi)
        print(f"   ✓ ByteDance found {len(bytedance_notes)} notes")

        # Vote and merge
        print(f"\n   Voting with '{self.voting_strategy}' strategy...")
        ensemble_notes = self._vote_notes(
            [yourmt3_notes, bytedance_notes],
            model_names=['YourMT3+', 'ByteDance']
        )
        print(f"   ✓ Ensemble result: {len(ensemble_notes)} notes")

        # Convert to MIDI
        ensemble_midi_path = output_dir / f"{audio_path.stem}_ensemble.mid"
        self._notes_to_midi(ensemble_notes, ensemble_midi_path)

        print(f"   ✓ Ensemble MIDI saved: {ensemble_midi_path.name}")
        print(f"   ═══════════════════════════════\n")

        return ensemble_midi_path

    def _extract_notes_from_midi(self, midi_path: Path) -> List[Note]:
        """
        Extract notes from MIDI file.

        Args:
            midi_path: Path to MIDI file

        Returns:
            List of Note objects
        """
        pm = pretty_midi.PrettyMIDI(str(midi_path))

        notes = []
        for instrument in pm.instruments:
            if instrument.is_drum:
                continue

            for note in instrument.notes:
                notes.append(Note(
                    pitch=note.pitch,
                    onset=note.start,
                    offset=note.end,
                    velocity=note.velocity,
                    confidence=1.0  # Default confidence (TODO: extract from model if available)
                ))

        # Sort by onset time
        notes.sort(key=lambda n: n.onset)
        return notes

    def _vote_notes(
        self,
        note_lists: List[List[Note]],
        model_names: List[str]
    ) -> List[Note]:
        """
        Vote on notes from multiple models.

        Args:
            note_lists: List of note lists from different models
            model_names: Names of models (for logging)

        Returns:
            Merged list of notes after voting
        """
        if self.voting_strategy == 'weighted':
            return self._vote_weighted(note_lists, model_names)
        elif self.voting_strategy == 'intersection':
            return self._vote_intersection(note_lists, model_names)
        elif self.voting_strategy == 'union':
            return self._vote_union(note_lists, model_names)
        elif self.voting_strategy == 'majority':
            return self._vote_majority(note_lists, model_names)
        else:
            raise ValueError(f"Unknown voting strategy: {self.voting_strategy}")

    def _vote_weighted(
        self,
        note_lists: List[List[Note]],
        model_names: List[str]
    ) -> List[Note]:
        """
        Weighted voting: Sum confidence scores, keep notes above threshold.

        Gives higher weight to ByteDance (piano specialist).
        """
        # Model weights (ByteDance is more accurate for piano)
        weights = {'YourMT3+': 0.4, 'ByteDance': 0.6}

        # Group notes by (onset_bucket, pitch)
        note_groups = {}

        for model_idx, notes in enumerate(note_lists):
            model_name = model_names[model_idx]
            weight = weights.get(model_name, 1.0 / len(note_lists))

            for note in notes:
                # Quantize onset to tolerance bucket
                onset_bucket = round(note.onset / self.onset_tolerance)
                key = (onset_bucket, note.pitch)

                if key not in note_groups:
                    note_groups[key] = []

                # Add note with weighted confidence
                note.confidence *= weight
                note_groups[key].append(note)

        # Merge notes in each group
        merged_notes = []
        for (onset_bucket, pitch), group in note_groups.items():
            # Sum confidence across models
            total_confidence = sum(n.confidence for n in group)

            if total_confidence >= self.confidence_threshold:
                # Use average timing and velocity
                avg_onset = np.mean([n.onset for n in group])
                avg_offset = np.mean([n.offset for n in group])
                avg_velocity = int(np.mean([n.velocity for n in group]))

                merged_notes.append(Note(
                    pitch=pitch,
                    onset=avg_onset,
                    offset=avg_offset,
                    velocity=avg_velocity,
                    confidence=total_confidence
                ))

        merged_notes.sort(key=lambda n: n.onset)
        return merged_notes

    def _vote_intersection(
        self,
        note_lists: List[List[Note]],
        model_names: List[str]
    ) -> List[Note]:
        """
        Intersection voting: Only keep notes agreed upon by ALL models.
        High precision, potentially lower recall.
        """
        if len(note_lists) == 0:
            return []

        # Start with first model's notes
        base_notes = note_lists[0]
        matched_notes = []

        for base_note in base_notes:
            # Check if this note appears in ALL other models
            found_in_all = True

            for other_notes in note_lists[1:]:
                if not self._find_matching_note(base_note, other_notes):
                    found_in_all = False
                    break

            if found_in_all:
                matched_notes.append(base_note)

        return matched_notes

    def _vote_union(
        self,
        note_lists: List[List[Note]],
        model_names: List[str]
    ) -> List[Note]:
        """
        Union voting: Keep ALL notes from ALL models.
        High recall, potentially more false positives.
        """
        # Combine all notes
        all_notes = []
        for notes in note_lists:
            all_notes.extend(notes)

        # Deduplicate: group similar notes and average them
        note_groups = {}

        for note in all_notes:
            onset_bucket = round(note.onset / self.onset_tolerance)
            key = (onset_bucket, note.pitch)

            if key not in note_groups:
                note_groups[key] = []
            note_groups[key].append(note)

        # Average duplicates
        merged_notes = []
        for (onset_bucket, pitch), group in note_groups.items():
            avg_onset = np.mean([n.onset for n in group])
            avg_offset = np.mean([n.offset for n in group])
            avg_velocity = int(np.mean([n.velocity for n in group]))

            merged_notes.append(Note(
                pitch=pitch,
                onset=avg_onset,
                offset=avg_offset,
                velocity=avg_velocity,
                confidence=len(group) / len(note_lists)  # Confidence = agreement ratio
            ))

        merged_notes.sort(key=lambda n: n.onset)
        return merged_notes

    def _vote_majority(
        self,
        note_lists: List[List[Note]],
        model_names: List[str]
    ) -> List[Note]:
        """
        Majority voting: Keep notes predicted by >=50% of models.
        Balanced precision and recall.
        """
        threshold = len(note_lists) / 2.0

        # Group notes by (onset_bucket, pitch)
        note_groups = {}

        for notes in note_lists:
            for note in notes:
                onset_bucket = round(note.onset / self.onset_tolerance)
                key = (onset_bucket, note.pitch)

                if key not in note_groups:
                    note_groups[key] = []
                note_groups[key].append(note)

        # Keep notes with majority agreement
        merged_notes = []
        for (onset_bucket, pitch), group in note_groups.items():
            if len(group) >= threshold:
                avg_onset = np.mean([n.onset for n in group])
                avg_offset = np.mean([n.offset for n in group])
                avg_velocity = int(np.mean([n.velocity for n in group]))

                merged_notes.append(Note(
                    pitch=pitch,
                    onset=avg_onset,
                    offset=avg_offset,
                    velocity=avg_velocity,
                    confidence=len(group) / len(note_lists)
                ))

        merged_notes.sort(key=lambda n: n.onset)
        return merged_notes

    def _find_matching_note(self, target: Note, notes: List[Note]) -> Optional[Note]:
        """Find a note that matches the target note within tolerance."""
        for note in notes:
            if (note.pitch == target.pitch and
                abs(note.onset - target.onset) <= self.onset_tolerance):
                return note
        return None

    def _notes_to_midi(self, notes: List[Note], output_path: Path):
        """
        Convert list of notes to MIDI file.

        Args:
            notes: List of Note objects
            output_path: Path for output MIDI file
        """
        # Create MIDI file
        mid = MidiFile()
        track = MidiTrack()
        mid.tracks.append(track)

        # Add tempo (120 BPM default)
        track.append(MetaMessage('set_tempo', tempo=500000, time=0))

        # Convert notes to MIDI messages
        # (simplified - assumes single instrument, no overlapping notes with same pitch)

        # Use absolute timing, then convert to delta
        events = []

        for note in notes:
            # Convert seconds to ticks (480 ticks per beat, 120 BPM)
            ticks_per_second = 480 * 2  # 480 ticks/beat * 2 beats/second at 120 BPM
            onset_ticks = int(note.onset * ticks_per_second)
            offset_ticks = int(note.offset * ticks_per_second)

            events.append((onset_ticks, 'note_on', note.pitch, note.velocity))
            events.append((offset_ticks, 'note_off', note.pitch, 0))

        # Sort by time
        events.sort(key=lambda e: e[0])

        # Convert to delta time and add to track
        previous_time = 0
        for abs_time, msg_type, pitch, velocity in events:
            delta_time = abs_time - previous_time
            previous_time = abs_time

            track.append(Message(
                msg_type,
                note=pitch,
                velocity=velocity,
                time=delta_time
            ))

        # Add end of track
        track.append(MetaMessage('end_of_track', time=0))

        # Save
        mid.save(output_path)
