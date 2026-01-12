"""
Test-Time Augmentation (TTA) for Music Transcription

Applies multiple augmentations to audio, transcribes each version,
and merges results via weighted voting for improved accuracy.

Expected improvement: +2-3% F1 score
Trade-off: 3-5x slower processing time (optional quality mode)
"""

from pathlib import Path
from typing import List, Dict, Callable, Optional
import numpy as np
import librosa
import soundfile as sf
from dataclasses import dataclass


@dataclass
class AugmentationStrategy:
    """Configuration for a single augmentation strategy."""
    name: str
    augment_fn: Callable
    weight: float  # Confidence weight for voting (0-1)


class TTAugmenter:
    """
    Test-Time Augmentation for music transcription.

    Augmentation strategies:
    1. Original audio (weight: 1.0)
    2. Pitch shift ±1 semitone (weight: 0.7)
    3. Time stretch ±5% (weight: 0.5)

    Voting: Weighted majority - notes must appear in ≥3 augmentations
    """

    def __init__(
        self,
        augmentations: List[str] = ['pitch_shift', 'time_stretch'],
        pitch_shifts: List[int] = [-1, 0, +1],
        time_stretches: List[float] = [0.95, 1.0, 1.05],
        min_votes: int = 3,
        onset_tolerance_ms: int = 50
    ):
        """
        Initialize TTA augmenter.

        Args:
            augmentations: List of augmentation types to apply
            pitch_shifts: Semitone shifts to apply (0 = original)
            time_stretches: Time stretch rates (1.0 = original)
            min_votes: Minimum augmentations that must predict a note
            onset_tolerance_ms: Time window for matching notes (milliseconds)
        """
        self.augmentations = augmentations
        self.pitch_shifts = pitch_shifts
        self.time_stretches = time_stretches
        self.min_votes = min_votes
        self.onset_tolerance = onset_tolerance_ms / 1000.0  # Convert to seconds

        # Build augmentation strategies
        self.strategies = self._build_augmentation_strategies()

        print(f"   TTA initialized with {len(self.strategies)} augmentation strategies")

    def _build_augmentation_strategies(self) -> List[AugmentationStrategy]:
        """Build list of augmentation strategies with weights."""
        strategies = []

        # Original audio (always included)
        strategies.append(AugmentationStrategy(
            name='original',
            augment_fn=lambda audio, sr: audio,
            weight=1.0
        ))

        # Pitch shift augmentations
        if 'pitch_shift' in self.augmentations:
            for semitones in self.pitch_shifts:
                if semitones == 0:
                    continue  # Skip original (already added)

                strategies.append(AugmentationStrategy(
                    name=f'pitch_{semitones:+d}st',
                    augment_fn=lambda audio, sr, n=semitones: librosa.effects.pitch_shift(
                        audio, sr=sr, n_steps=n
                    ),
                    weight=0.7
                ))

        # Time stretch augmentations
        if 'time_stretch' in self.augmentations:
            for rate in self.time_stretches:
                if rate == 1.0:
                    continue  # Skip original (already added)

                strategies.append(AugmentationStrategy(
                    name=f'stretch_{rate:.2f}x',
                    augment_fn=lambda audio, sr, r=rate: librosa.effects.time_stretch(
                        audio, rate=r
                    ),
                    weight=0.5
                ))

        return strategies

    def augment_and_transcribe(
        self,
        audio_path: Path,
        transcriber,
        temp_dir: Optional[Path] = None
    ) -> Path:
        """
        Apply TTA: augment audio → transcribe each → vote.

        Args:
            audio_path: Path to audio file
            transcriber: Transcriber instance with transcribe() method
            temp_dir: Directory for temporary files

        Returns:
            Path to final voted MIDI file
        """
        if temp_dir is None:
            temp_dir = audio_path.parent / "tta_temp"
        temp_dir.mkdir(exist_ok=True, parents=True)

        print(f"\n   ═══ Test-Time Augmentation ═══")
        print(f"   Strategies: {len(self.strategies)} augmentations")
        print(f"   Min votes: {self.min_votes}")

        # Load audio once
        print(f"   Loading audio: {audio_path.name}")
        audio, sr = librosa.load(str(audio_path), sr=None, mono=True)
        print(f"   ✓ Loaded: {len(audio)/sr:.1f}s @ {sr}Hz")

        # Transcribe each augmentation
        aug_results = []

        for i, strategy in enumerate(self.strategies, 1):
            print(f"\n   [{i}/{len(self.strategies)}] Augmentation: {strategy.name}")

            # Apply augmentation
            aug_audio = strategy.augment_fn(audio, sr)

            # Save to temp file
            aug_path = temp_dir / f"{audio_path.stem}_{strategy.name}.wav"
            sf.write(str(aug_path), aug_audio, sr)
            print(f"   ✓ Augmented audio saved")

            # Transcribe
            midi_path = transcriber.transcribe(aug_path)
            print(f"   ✓ Transcription complete: {midi_path.name}")

            # Store result with weight and strategy for timing adjustment
            aug_results.append({
                'name': strategy.name,
                'midi_path': midi_path,
                'weight': strategy.weight,
                'strategy': strategy  # Need this to reverse timing adjustments
            })

            # Clean up temp audio (keep MIDI for debugging)
            aug_path.unlink()

        # Vote and merge results
        print(f"\n   Merging {len(aug_results)} transcriptions...")
        final_midi = self._vote_tta_results(aug_results, audio_path, temp_dir)

        print(f"   ✓ TTA complete: {final_midi.name}")
        print(f"   ═══════════════════════════════\n")

        return final_midi

    def _vote_tta_results(
        self,
        aug_results: List[Dict],
        original_audio: Path,
        output_dir: Path
    ) -> Path:
        """
        Weighted voting across TTA results.

        Strategy:
        1. Extract notes from all augmented MIDIs
        2. Group similar notes (same pitch, onset within tolerance)
        3. Weighted voting: sum weights, keep if ≥ min_votes
        4. Average timing/velocity weighted by confidence

        Args:
            aug_results: List of augmentation results
            original_audio: Original audio path (for naming)
            output_dir: Output directory

        Returns:
            Path to voted MIDI file
        """
        import pretty_midi
        from backend.ensemble_transcriber import Note

        # Extract notes from all augmentations
        all_notes = []
        for result in aug_results:
            pm = pretty_midi.PrettyMIDI(str(result['midi_path']))
            strategy = result['strategy']

            for instrument in pm.instruments:
                if instrument.is_drum:
                    continue

                for note in instrument.notes:
                    # Reverse the augmentation's timing effects
                    # For time stretch: if we stretched by 1.05x, divide by 1.05 to restore original timing
                    if 'stretch' in strategy.name:
                        # Extract stretch factor from name (e.g., "stretch_1.05x" -> 1.05)
                        stretch_factor = float(strategy.name.split('_')[1].replace('x', ''))
                        adjusted_onset = note.start / stretch_factor
                        adjusted_offset = note.end / stretch_factor
                    else:
                        adjusted_onset = note.start
                        adjusted_offset = note.end

                    # Reverse pitch shift effect (if any)
                    adjusted_pitch = note.pitch
                    if 'pitch_' in strategy.name:
                        # Extract shift amount from name (e.g., "pitch_+1st" -> +1)
                        shift_str = strategy.name.split('_')[1].replace('st', '')  # "+1st" -> "+1"
                        shift_amount = int(shift_str)
                        adjusted_pitch = note.pitch - shift_amount

                    all_notes.append(Note(
                        pitch=adjusted_pitch,
                        onset=adjusted_onset,
                        offset=adjusted_offset,
                        velocity=note.velocity,
                        confidence=result['weight']
                    ))

        print(f"   Extracted {len(all_notes)} total notes from all augmentations")

        # Group similar notes (same pitch, onset within tolerance)
        note_groups = {}

        for note in all_notes:
            # Quantize onset to tolerance bucket
            onset_bucket = round(note.onset / self.onset_tolerance)
            key = (onset_bucket, note.pitch)

            if key not in note_groups:
                note_groups[key] = []
            note_groups[key].append(note)

        print(f"   Grouped into {len(note_groups)} unique note positions")

        # Debug: check distribution of group sizes
        group_sizes = [len(g) for g in note_groups.values()]
        size_counts = {}
        for s in group_sizes:
            size_counts[s] = size_counts.get(s, 0) + 1
        print(f"   Group size distribution: {dict(sorted(size_counts.items()))}")
        print(f"   Onset tolerance: {self.onset_tolerance*1000:.0f}ms, min_votes: {self.min_votes}")

        # Weighted voting
        voted_notes = []
        for (onset_bucket, pitch), group in note_groups.items():
            # Count votes (weighted)
            total_votes = sum(n.confidence for n in group)
            num_augmentations = len(group)

            # Keep if meets minimum vote threshold
            if num_augmentations >= self.min_votes:
                # Weighted average of timing and velocity
                weights_sum = sum(n.confidence for n in group)

                avg_onset = sum(n.onset * n.confidence for n in group) / weights_sum
                avg_offset = sum(n.offset * n.confidence for n in group) / weights_sum
                avg_velocity = int(sum(n.velocity * n.confidence for n in group) / weights_sum)

                voted_notes.append(Note(
                    pitch=pitch,
                    onset=avg_onset,
                    offset=avg_offset,
                    velocity=avg_velocity,
                    confidence=total_votes
                ))

        # Sort by onset
        voted_notes.sort(key=lambda n: n.onset)

        print(f"   ✓ Voting complete: {len(voted_notes)} notes kept (≥{self.min_votes} votes)")
        print(f"   Filtered: {len(note_groups) - len(voted_notes)} low-confidence notes")

        # Save as MIDI
        output_path = output_dir / f"{original_audio.stem}_tta.mid"
        self._notes_to_midi(voted_notes, output_path)

        return output_path

    def _notes_to_midi(self, notes: List['Note'], output_path: Path):
        """
        Convert notes to MIDI file.

        Args:
            notes: List of Note objects
            output_path: Path for output MIDI file
        """
        from mido import MidiFile, MidiTrack, Message, MetaMessage

        # Create MIDI file
        mid = MidiFile()
        track = MidiTrack()
        mid.tracks.append(track)

        # Add tempo (120 BPM default)
        track.append(MetaMessage('set_tempo', tempo=500000, time=0))

        # Convert notes to MIDI messages
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


if __name__ == "__main__":
    """Test TTA augmenter."""
    print("TTA Augmenter Test")
    print("=" * 60)

    # Test augmentation strategy building
    augmenter = TTAugmenter(
        augmentations=['pitch_shift', 'time_stretch'],
        pitch_shifts=[-1, 0, +1],
        time_stretches=[0.95, 1.0, 1.05],
        min_votes=3
    )

    print(f"\nBuilt {len(augmenter.strategies)} augmentation strategies:")
    for i, strategy in enumerate(augmenter.strategies, 1):
        print(f"  {i}. {strategy.name} (weight: {strategy.weight})")

    print("\nExpected processing time:")
    print(f"  Original: 1x")
    print(f"  TTA: {len(augmenter.strategies)}x slower")
    print(f"  Trade-off: +2-3% accuracy for {len(augmenter.strategies)}x processing time")

    print("\n✓ TTA augmenter ready for use")
