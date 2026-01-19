"""
BiLSTM Refinement Model

Uses bidirectional LSTM to refine ensemble transcription predictions.
Corrects isolated errors by capturing temporal patterns in note sequences.

Expected improvement: +1-2% F1
Training time: 8-12 hours on single GPU
Dataset: MAESTRO (paired ensemble predictions + ground truth)
"""

from pathlib import Path
from typing import Optional
import numpy as np
import torch
import torch.nn as nn
import pretty_midi


class BiLSTMRefiner(nn.Module):
    """
    BiLSTM refinement network for piano transcription.

    Architecture:
    - Input: Piano roll from ensemble (time × 88 keys)
    - BiLSTM: 2 layers, 256 hidden units, bidirectional
    - Attention: Multi-head self-attention for long-range dependencies
    - Output: Refined piano roll (corrected onset probabilities)

    Improvements:
    - Corrects isolated false positives (single erroneous notes)
    - Fixes timing errors (onset/offset misalignment)
    - Smooths note sequences based on musical context
    """

    def __init__(
        self,
        input_dim: int = 88,  # Piano keys (A0-C8)
        hidden_dim: int = 256,
        num_layers: int = 2,
        dropout: float = 0.2,
        use_attention: bool = True
    ):
        """
        Initialize BiLSTM refiner.

        Args:
            input_dim: Number of piano keys (default: 88)
            hidden_dim: LSTM hidden dimension
            num_layers: Number of LSTM layers
            dropout: Dropout probability
            use_attention: Use self-attention mechanism
        """
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.use_attention = use_attention

        # Bidirectional LSTM for temporal modeling
        self.bilstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0
        )

        # Multi-head self-attention (optional, improves long-range dependencies)
        if use_attention:
            self.attention = nn.MultiheadAttention(
                embed_dim=hidden_dim * 2,  # Bidirectional doubles the dimension
                num_heads=4,
                dropout=dropout,
                batch_first=True
            )

        # Output projection
        self.output_layer = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, input_dim),
            nn.Sigmoid()  # Output onset probabilities [0, 1]
        )

    def forward(self, piano_roll: torch.Tensor) -> torch.Tensor:
        """
        Forward pass: refine piano roll predictions.

        Args:
            piano_roll: (batch, time, 88) onset probabilities from ensemble

        Returns:
            refined_roll: (batch, time, 88) refined onset probabilities
        """
        # BiLSTM encoding (captures temporal context)
        lstm_out, _ = self.bilstm(piano_roll)

        # Self-attention (captures long-range dependencies, e.g., repeated phrases)
        if self.use_attention:
            attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        else:
            attn_out = lstm_out

        # Output projection (refined probabilities)
        refined = self.output_layer(attn_out)

        return refined


class BiLSTMRefinementPipeline:
    """
    Wrapper for loading and applying BiLSTM refinement to MIDI files.

    Usage:
        refiner = BiLSTMRefinementPipeline(checkpoint_path)
        refined_midi = refiner.refine_midi(ensemble_midi_path)
    """

    def __init__(
        self,
        checkpoint_path: Path,
        device: Optional[str] = None,
        fps: int = 100  # Frames per second for piano roll
    ):
        """
        Initialize refinement pipeline.

        Args:
            checkpoint_path: Path to trained BiLSTM checkpoint
            device: Device to use ('cuda', 'mps', 'cpu'). Auto-detected if None.
            fps: Frames per second for piano roll conversion
        """
        # Auto-detect device
        if device is None:
            if torch.cuda.is_available():
                device = 'cuda'
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = 'mps'
            else:
                device = 'cpu'

        self.device = device
        self.fps = fps

        # Load model (use_attention=False to match training checkpoint)
        self.model = BiLSTMRefiner(use_attention=False).to(device)

        if checkpoint_path.exists():
            print(f"   Loading BiLSTM checkpoint: {checkpoint_path.name}")
            state_dict = torch.load(checkpoint_path, map_location=device)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            print(f"   ✓ BiLSTM model loaded on {device}")
        else:
            print(f"   ⚠ Warning: Checkpoint not found: {checkpoint_path}")
            print(f"   BiLSTM refinement will be skipped")
            self.model = None

    def refine_midi(
        self,
        midi_path: Path,
        output_dir: Optional[Path] = None,
        threshold: float = 0.5
    ) -> Path:
        """
        Refine MIDI file using BiLSTM.

        Args:
            midi_path: Path to ensemble MIDI output
            output_dir: Directory for refined MIDI (default: same as input)
            threshold: Onset probability threshold for refined output

        Returns:
            Path to refined MIDI file
        """
        if self.model is None:
            print("   ⚠ BiLSTM model not loaded, returning original MIDI")
            return midi_path

        if output_dir is None:
            output_dir = midi_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Convert MIDI to piano roll
        piano_roll = self._midi_to_piano_roll(midi_path)

        # Run BiLSTM refinement
        # For long sequences, process in chunks to avoid cuDNN memory issues
        max_chunk_length = 30000  # ~5 minutes at 100 FPS, safe for GPU memory
        overlap = 1000  # Overlap between chunks for smooth transitions

        with torch.no_grad():
            if len(piano_roll) <= max_chunk_length:
                # Short sequence - process directly
                piano_roll_tensor = torch.from_numpy(piano_roll).float().contiguous()
                piano_roll_tensor = piano_roll_tensor.unsqueeze(0).to(self.device)
                refined_tensor = self.model(piano_roll_tensor)
                refined_roll = refined_tensor.squeeze(0).cpu().numpy()
            else:
                # Long sequence - process in overlapping chunks
                refined_roll = np.zeros_like(piano_roll)
                weights = np.zeros(len(piano_roll))  # For blending overlapping regions

                for start in range(0, len(piano_roll), max_chunk_length - overlap):
                    end = min(start + max_chunk_length, len(piano_roll))
                    chunk = piano_roll[start:end]

                    chunk_tensor = torch.from_numpy(chunk).float().contiguous()
                    chunk_tensor = chunk_tensor.unsqueeze(0).to(self.device)
                    refined_chunk = self.model(chunk_tensor).squeeze(0).cpu().numpy()

                    # Blend overlapping regions using linear ramp
                    chunk_weights = np.ones(len(refined_chunk))
                    if start > 0:
                        # Ramp up at the beginning of non-first chunks
                        ramp_length = min(overlap, len(refined_chunk))
                        chunk_weights[:ramp_length] = np.linspace(0, 1, ramp_length)
                    if end < len(piano_roll):
                        # Ramp down at the end of non-last chunks
                        ramp_length = min(overlap, len(refined_chunk))
                        chunk_weights[-ramp_length:] = np.linspace(1, 0, ramp_length)

                    refined_roll[start:end] += refined_chunk * chunk_weights[:, np.newaxis]
                    weights[start:end] += chunk_weights

                # Normalize by weights
                weights = np.maximum(weights, 1e-8)  # Avoid division by zero
                refined_roll = refined_roll / weights[:, np.newaxis]

        # Convert back to MIDI
        refined_path = output_dir / f"{midi_path.stem}_bilstm.mid"
        self._piano_roll_to_midi(refined_roll, midi_path, refined_path, threshold)

        return refined_path

    def _midi_to_piano_roll(self, midi_path: Path) -> np.ndarray:
        """
        Convert MIDI to onset piano roll.

        Args:
            midi_path: Path to MIDI file

        Returns:
            Piano roll array (time, 88) with onset probabilities
        """
        pm = pretty_midi.PrettyMIDI(str(midi_path))

        # Get duration
        duration = pm.get_end_time()
        n_frames = int(duration * self.fps) + 1

        # Initialize piano roll (88 keys)
        piano_roll = np.zeros((n_frames, 88), dtype=np.float32)

        # Fill onsets (binary for now, could use velocity in future)
        for instrument in pm.instruments:
            if instrument.is_drum:
                continue

            for note in instrument.notes:
                onset_frame = int(note.start * self.fps)
                if onset_frame < n_frames:
                    pitch_idx = note.pitch - 21  # A0 = 21
                    if 0 <= pitch_idx < 88:
                        piano_roll[onset_frame, pitch_idx] = 1.0

        return piano_roll

    def _piano_roll_to_midi(
        self,
        refined_roll: np.ndarray,
        original_midi: Path,
        output_path: Path,
        threshold: float
    ):
        """
        Convert refined piano roll back to MIDI.

        Uses original MIDI for timing/velocity information where available.

        Args:
            refined_roll: Refined onset probabilities (time, 88)
            original_midi: Original MIDI file for reference
            output_path: Path to save refined MIDI
            threshold: Onset probability threshold
        """
        # Load original MIDI for reference
        pm_orig = pretty_midi.PrettyMIDI(str(original_midi))

        # Create new MIDI
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)  # Piano

        # Detect onsets from refined roll
        for pitch_idx in range(88):
            pitch = pitch_idx + 21  # A0 = 21

            # Find frames where onset probability > threshold
            pitch_roll = refined_roll[:, pitch_idx]
            onset_frames = np.where(pitch_roll > threshold)[0]

            # Group consecutive frames (to avoid duplicate notes)
            if len(onset_frames) == 0:
                continue

            # Find peaks (local maxima) to avoid duplicates
            peaks = []
            for i in range(len(onset_frames)):
                frame = onset_frames[i]

                # Check if this is a local maximum
                is_peak = True
                for j in range(max(0, frame - 2), min(len(refined_roll), frame + 3)):
                    if j != frame and refined_roll[j, pitch_idx] >= refined_roll[frame, pitch_idx]:
                        is_peak = False
                        break

                if is_peak:
                    peaks.append(frame)

            # Create notes from peaks
            for onset_frame in peaks:
                onset_time = onset_frame / self.fps

                # Try to find corresponding note in original MIDI for velocity/offset
                orig_note = self._find_closest_note(pm_orig, pitch, onset_time)

                if orig_note:
                    # Use original note's velocity and duration
                    velocity = orig_note.velocity
                    offset_time = orig_note.end
                else:
                    # Default values
                    velocity = 80
                    # Estimate offset (next onset or fixed duration)
                    next_onsets = [f for f in peaks if f > onset_frame]
                    if next_onsets:
                        offset_frame = next_onsets[0]
                    else:
                        offset_frame = min(onset_frame + int(0.5 * self.fps), len(refined_roll) - 1)
                    offset_time = offset_frame / self.fps

                # Add note
                note = pretty_midi.Note(
                    velocity=velocity,
                    pitch=pitch,
                    start=onset_time,
                    end=offset_time
                )
                instrument.notes.append(note)

        pm.instruments.append(instrument)
        pm.write(str(output_path))

    def _find_closest_note(
        self,
        midi: pretty_midi.PrettyMIDI,
        pitch: int,
        onset_time: float,
        tolerance: float = 0.1  # 100ms tolerance
    ) -> Optional[pretty_midi.Note]:
        """Find the closest note in original MIDI."""
        for instrument in midi.instruments:
            if instrument.is_drum:
                continue

            for note in instrument.notes:
                if note.pitch == pitch and abs(note.start - onset_time) < tolerance:
                    return note

        return None


if __name__ == "__main__":
    """Test BiLSTM model architecture."""
    print("Testing BiLSTM Refiner Architecture\n")

    # Test model creation
    model = BiLSTMRefiner(
        input_dim=88,
        hidden_dim=256,
        num_layers=2,
        dropout=0.2,
        use_attention=True
    )

    print(f"Model architecture:")
    print(f"  Input: (batch, time, 88)")
    print(f"  BiLSTM: 2 layers × 256 hidden × bidirectional")
    print(f"  Attention: 4-head self-attention")
    print(f"  Output: (batch, time, 88)")
    print()

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print(f"Model parameters:")
    print(f"  Total: {total_params:,}")
    print(f"  Trainable: {trainable_params:,}")
    print()

    # Test forward pass
    batch_size = 4
    time_steps = 1000  # 10 seconds at 100 FPS
    input_roll = torch.randn(batch_size, time_steps, 88)

    print(f"Testing forward pass:")
    print(f"  Input shape: {input_roll.shape}")

    with torch.no_grad():
        output_roll = model(input_roll)

    print(f"  Output shape: {output_roll.shape}")
    print(f"  Output range: [{output_roll.min():.3f}, {output_roll.max():.3f}]")
    print()

    print("✓ BiLSTM refiner architecture test passed!")
    print(f"\nCheckpoint size (estimated): ~{total_params * 4 / 1024 / 1024:.1f} MB")
