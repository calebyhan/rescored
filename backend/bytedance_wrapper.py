"""
ByteDance Piano Transcription Wrapper

Provides a clean interface to ByteDance's high-accuracy piano transcription model.
Trained on MAESTRO dataset with CNN + BiGRU architecture.

Model: https://github.com/bytedance/piano_transcription
Paper: "High-resolution Piano Transcription with Pedals by Regressing Onsets and Offsets Times"
"""

from pathlib import Path
from typing import Optional, Dict
import torch
import numpy as np


class ByteDanceTranscriber:
    """
    Wrapper for ByteDance piano transcription model.

    Characteristics:
    - High accuracy on piano-only audio (~90% F1 score on MAESTRO)
    - Outputs onset/offset probabilities with confidence scores
    - Trained specifically for piano (not general-purpose)
    - Includes pedal transcription (sustain, soft, sostenuto)

    Performance:
    - GPU: ~15-30s per 3-min song
    - CPU: ~2-5 min per 3-min song
    """

    def __init__(
        self,
        device: Optional[str] = None,
        checkpoint: Optional[str] = None
    ):
        """
        Initialize ByteDance transcription model.

        Args:
            device: Torch device ('cuda', 'mps', 'cpu'). Auto-detected if None.
            checkpoint: Model checkpoint path (optional - will auto-download if None)
        """
        # Import here to avoid dependency issues if not installed
        try:
            from piano_transcription_inference import PianoTranscription, sample_rate
        except ImportError as e:
            raise ImportError(
                "ByteDance piano transcription requires: pip install piano-transcription-inference"
            ) from e

        # Auto-detect device
        if device is None:
            if torch.cuda.is_available():
                device = 'cuda'
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = 'mps'
            else:
                device = 'cpu'

        self.device = device
        self.sample_rate = sample_rate

        print(f"   Initializing ByteDance piano transcription on {device}")

        # Load model
        # If checkpoint is None, PianoTranscription will auto-download the default model
        self.model = PianoTranscription(
            device=device,
            checkpoint_path=checkpoint  # None means auto-download
        )

        print(f"   ✓ ByteDance model loaded")

    def transcribe_audio(
        self,
        audio_path: Path,
        output_dir: Optional[Path] = None
    ) -> Path:
        """
        Transcribe audio to MIDI using ByteDance model.

        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            output_dir: Directory for output MIDI file. Defaults to audio directory.

        Returns:
            Path to generated MIDI file
        """
        from piano_transcription_inference import load_audio

        # Set output directory
        if output_dir is None:
            output_dir = audio_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Output MIDI path
        midi_path = output_dir / f"{audio_path.stem}_bytedance.mid"

        print(f"   Transcribing with ByteDance: {audio_path.name}")

        # Load audio
        (audio, _) = load_audio(
            str(audio_path),
            sr=self.sample_rate,
            mono=True
        )

        # Transcribe
        # ByteDance outputs:
        # - MIDI file with notes and pedal events
        # - onset_roll: Frame-level onset probabilities (can be used for confidence)
        # - offset_roll: Frame-level offset probabilities
        # - velocity_roll: Frame-level velocity predictions
        # - pedal_roll: Frame-level pedal predictions (sustain, soft, sostenuto)

        transcription_result = self.model.transcribe(
            audio,
            str(midi_path)
        )

        print(f"   ✓ ByteDance transcription complete: {midi_path.name}")

        return midi_path

    def transcribe_with_confidence(
        self,
        audio_path: Path,
        output_dir: Optional[Path] = None
    ) -> Dict:
        """
        Transcribe audio and return MIDI path + confidence scores.

        Args:
            audio_path: Path to audio file
            output_dir: Directory for output MIDI file

        Returns:
            Dict with keys:
            - 'midi_path': Path to MIDI file
            - 'onset_confidence': Frame-level onset probabilities
            - 'offset_confidence': Frame-level offset probabilities
            - 'velocity_confidence': Frame-level velocity predictions
        """
        from piano_transcription_inference import load_audio
        import pretty_midi

        # Set output directory
        if output_dir is None:
            output_dir = audio_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        midi_path = output_dir / f"{audio_path.stem}_bytedance.mid"

        # Load audio
        (audio, _) = load_audio(
            str(audio_path),
            sr=self.sample_rate,
            mono=True
        )

        # Transcribe and get full output
        print(f"   Transcribing with ByteDance (with confidence): {audio_path.name}")

        transcription_result = self.model.transcribe(
            audio,
            str(midi_path)
        )

        # Extract note-level confidence scores from frame-level predictions
        # transcription_result is a dict with:
        # - onset_roll: (frames, 88) - probability of note onset at each frame
        # - offset_roll: (frames, 88) - probability of note offset
        # - velocity_roll: (frames, 88) - predicted velocity

        # Load generated MIDI to map confidence to notes
        pm = pretty_midi.PrettyMIDI(str(midi_path))

        # Extract note-level confidence from frame-level predictions
        note_confidences = self._extract_note_confidences_from_rolls(
            pm,
            transcription_result.get('onset_roll'),
            transcription_result.get('offset_roll')
        )

        return {
            'midi_path': midi_path,
            'note_confidences': note_confidences,
            'raw_onset_roll': transcription_result.get('onset_roll'),
            'raw_offset_roll': transcription_result.get('offset_roll'),
            'raw_velocity_roll': transcription_result.get('velocity_roll')
        }

    def _extract_note_confidences_from_rolls(
        self,
        pm: 'pretty_midi.PrettyMIDI',
        onset_roll: np.ndarray,
        offset_roll: np.ndarray
    ) -> list:
        """
        Extract note-level confidence scores from frame-level predictions.

        Args:
            pm: PrettyMIDI object with notes
            onset_roll: (frames, 88) onset probabilities from ByteDance
            offset_roll: (frames, 88) offset probabilities from ByteDance

        Returns:
            List of dicts with note info and confidence scores
        """
        note_confidences = []

        # ByteDance frame rate: 100 FPS (frames per second)
        frames_per_second = 100

        for instrument in pm.instruments:
            if instrument.is_drum:
                continue

            for note in instrument.notes:
                # Map MIDI pitch to piano roll index (A0=21 → index 0)
                piano_idx = note.pitch - 21

                # Skip if pitch is out of piano range
                if not (0 <= piano_idx < 88):
                    continue

                # Extract onset confidence
                onset_frame = int(note.start * frames_per_second)
                onset_frame = max(0, min(onset_frame, onset_roll.shape[0] - 1))

                # Get confidence window (±2 frames around onset for robustness)
                onset_window_start = max(0, onset_frame - 2)
                onset_window_end = min(onset_roll.shape[0], onset_frame + 3)
                onset_window = onset_roll[onset_window_start:onset_window_end, piano_idx]
                onset_conf = float(np.max(onset_window)) if len(onset_window) > 0 else 0.5

                # Extract offset confidence
                offset_frame = int(note.end * frames_per_second)
                offset_frame = max(0, min(offset_frame, offset_roll.shape[0] - 1))

                # Get confidence window (±2 frames around offset)
                offset_window_start = max(0, offset_frame - 2)
                offset_window_end = min(offset_roll.shape[0], offset_frame + 3)
                offset_window = offset_roll[offset_window_start:offset_window_end, piano_idx]
                offset_conf = float(np.max(offset_window)) if len(offset_window) > 0 else 0.5

                # Combined confidence (geometric mean favors consistency)
                # Geometric mean penalizes low scores more than arithmetic mean
                combined_confidence = float(np.sqrt(onset_conf * offset_conf))

                note_confidences.append({
                    'pitch': note.pitch,
                    'onset': note.start,
                    'offset': note.end,
                    'velocity': note.velocity,
                    'onset_confidence': onset_conf,
                    'offset_confidence': offset_conf,
                    'confidence': combined_confidence
                })

        return note_confidences


if __name__ == "__main__":
    # Test the transcriber
    import argparse

    parser = argparse.ArgumentParser(description="Test ByteDance Piano Transcription")
    parser.add_argument("audio_file", type=str, help="Path to audio file")
    parser.add_argument("--output", type=str, default="./output_midi",
                       help="Output directory for MIDI")
    parser.add_argument("--device", type=str, default=None,
                       choices=['cuda', 'mps', 'cpu'],
                       help="Device to use (auto-detected if not specified)")
    args = parser.parse_args()

    transcriber = ByteDanceTranscriber(device=args.device)
    audio_path = Path(args.audio_file)
    output_dir = Path(args.output)

    # Transcribe
    midi_path = transcriber.transcribe_audio(audio_path, output_dir)
    print(f"\n✓ Transcription complete: {midi_path}")
