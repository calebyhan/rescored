"""
MAESTRO Dataset Builder for BiLSTM Training

Prepares training data by:
1. Generating ensemble predictions for MAESTRO audio files
2. Converting predictions and ground truth to piano rolls
3. Saving as .npz files for efficient loading during training

This is a preprocessing step that needs to be run once before training.
"""

from pathlib import Path
from typing import Tuple, Optional
import numpy as np
from tqdm import tqdm
import pretty_midi
import argparse


def midi_to_piano_roll(midi_path: Path, fps: int = 100) -> np.ndarray:
    """
    Convert MIDI to onset piano roll.

    Args:
        midi_path: Path to MIDI file
        fps: Frames per second

    Returns:
        Piano roll array (time, 88) with binary onsets
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))

    # Get duration
    duration = pm.get_end_time()
    n_frames = int(duration * fps) + 1

    # Initialize piano roll (88 keys: A0-C8)
    piano_roll = np.zeros((n_frames, 88), dtype=np.float32)

    # Fill onsets
    for instrument in pm.instruments:
        if instrument.is_drum:
            continue

        for note in instrument.notes:
            onset_frame = int(note.start * fps)
            if onset_frame < n_frames:
                pitch_idx = note.pitch - 21  # A0 = 21
                if 0 <= pitch_idx < 88:
                    piano_roll[onset_frame, pitch_idx] = 1.0

    return piano_roll


def prepare_maestro_dataset(
    maestro_root: Path,
    output_dir: Path,
    ensemble_transcriber,
    split: str = 'train',
    max_items: Optional[int] = None,
    fps: int = 100
):
    """
    Prepare MAESTRO dataset for BiLSTM training.

    Args:
        maestro_root: Root directory of MAESTRO dataset
        output_dir: Directory to save processed .npz files
        ensemble_transcriber: EnsembleTranscriber instance for generating predictions
        split: Dataset split ('train', 'validation', 'test')
        max_items: Maximum items to process (for testing)
        fps: Frames per second for piano roll
    """
    from backend.evaluation.benchmark_datasets import MAESTRODataset

    # Load MAESTRO dataset
    dataset = MAESTRODataset(maestro_root)
    pairs = dataset.get_split(split, max_items)

    print(f"\n{'=' * 70}")
    print(f"Preparing {split} split for BiLSTM training")
    print(f"{'=' * 70}")
    print(f"MAESTRO root: {maestro_root}")
    print(f"Output dir: {output_dir}")
    print(f"Items to process: {len(pairs)}")
    print(f"FPS: {fps}")
    print(f"{'=' * 70}\n")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Create temp directory for ensemble predictions
    temp_dir = output_dir / "temp_ensemble"
    temp_dir.mkdir(exist_ok=True)

    # Process each audio/MIDI pair
    processed = 0
    skipped = 0

    for audio_path, gt_midi_path in tqdm(pairs, desc=f"Processing {split}"):
        try:
            # Check if already processed
            output_path = output_dir / f"{audio_path.stem}.npz"
            if output_path.exists():
                print(f"  ⏭  Skipping (already processed): {audio_path.name}")
                processed += 1
                continue

            # Generate ensemble prediction
            print(f"\n  Transcribing: {audio_path.name}")
            ensemble_midi = ensemble_transcriber.transcribe(audio_path, temp_dir)

            # Convert to piano rolls
            ensemble_roll = midi_to_piano_roll(ensemble_midi, fps)
            gt_roll = midi_to_piano_roll(gt_midi_path, fps)

            # Ensure same length (truncate or pad to match)
            min_len = min(len(ensemble_roll), len(gt_roll))
            max_len = max(len(ensemble_roll), len(gt_roll))

            # Truncate to minimum length (simpler than padding)
            ensemble_roll = ensemble_roll[:min_len]
            gt_roll = gt_roll[:min_len]

            # Save as .npz
            np.savez_compressed(
                output_path,
                ensemble_roll=ensemble_roll,
                ground_truth_roll=gt_roll,
                audio_filename=audio_path.name,
                duration=min_len / fps
            )

            print(f"  ✓ Saved: {output_path.name} ({min_len} frames, {min_len/fps:.1f}s)")
            processed += 1

        except Exception as e:
            print(f"  ✗ Error processing {audio_path.name}: {e}")
            skipped += 1
            continue

    print(f"\n{'=' * 70}")
    print(f"Dataset preparation complete!")
    print(f"{'=' * 70}")
    print(f"Processed: {processed}/{len(pairs)}")
    print(f"Skipped: {skipped}")
    print(f"Output directory: {output_dir}")
    print(f"{'=' * 70}\n")

    # Clean up temp directory
    import shutil
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def main():
    """CLI for dataset preparation."""
    parser = argparse.ArgumentParser(description="Prepare MAESTRO dataset for BiLSTM training")

    parser.add_argument(
        '--maestro-root',
        type=str,
        required=True,
        help='Root directory of MAESTRO dataset'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        required=True,
        help='Output directory for processed .npz files'
    )

    parser.add_argument(
        '--split',
        type=str,
        default='train',
        choices=['train', 'validation', 'test'],
        help='Dataset split to process'
    )

    parser.add_argument(
        '--max-items',
        type=int,
        default=None,
        help='Maximum items to process (for testing)'
    )

    parser.add_argument(
        '--fps',
        type=int,
        default=100,
        help='Frames per second for piano roll'
    )

    args = parser.parse_args()

    # Import ensemble transcriber
    from backend.ensemble_transcriber import EnsembleTranscriber
    from backend.yourmt3_wrapper import YourMT3Transcriber
    from backend.bytedance_wrapper import ByteDanceTranscriber
    from backend.app_config import settings

    # Initialize transcribers
    print("Initializing transcription models...")
    yourmt3 = YourMT3Transcriber(
        model_name="YPTF.MoE+Multi (noPS)",
        device=settings.yourmt3_device
    )

    bytedance = ByteDanceTranscriber(
        device=settings.yourmt3_device
    )

    ensemble = EnsembleTranscriber(
        yourmt3_transcriber=yourmt3,
        bytedance_transcriber=bytedance,
        voting_strategy=settings.ensemble_voting_strategy,
        onset_tolerance_ms=settings.ensemble_onset_tolerance_ms,
        confidence_threshold=settings.ensemble_confidence_threshold,
        use_bytedance_confidence=settings.use_bytedance_confidence
    )

    # Prepare dataset
    prepare_maestro_dataset(
        maestro_root=Path(args.maestro_root),
        output_dir=Path(args.output_dir),
        ensemble_transcriber=ensemble,
        split=args.split,
        max_items=args.max_items,
        fps=args.fps
    )


if __name__ == "__main__":
    main()
