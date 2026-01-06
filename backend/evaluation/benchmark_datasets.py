"""
Benchmark Dataset Loaders

Provides utilities for loading standard benchmark datasets:
- MAESTRO: Piano performance dataset with aligned MIDI
- Custom YouTube test set (if available)
"""

from pathlib import Path
from typing import List, Tuple, Optional, Dict
import json


class MAESTRODataset:
    """
    MAESTRO dataset loader.

    MAESTRO (MIDI and Audio Edited for Synchronous TRacks and Organization)
    is a dataset of ~200 hours of virtuosic piano performances with aligned MIDI.

    Dataset: https://magenta.tensorflow.org/datasets/maestro
    """

    def __init__(self, maestro_root: Path, version: str = "v3.0.0"):
        """
        Initialize MAESTRO dataset.

        Args:
            maestro_root: Root directory of MAESTRO dataset
            version: MAESTRO version (default: v3.0.0)
        """
        self.maestro_root = Path(maestro_root)
        self.version = version

        # Load metadata
        self.metadata_path = self.maestro_root / f"maestro-{version}.json"
        self.metadata = self._load_metadata()

        print(f"MAESTRO {version} loaded:")
        print(f"  Root: {self.maestro_root}")
        print(f"  Total recordings: {len(self.metadata)}")
        print(f"  Train split: {self.count_split('train')}")
        print(f"  Validation split: {self.count_split('validation')}")
        print(f"  Test split: {self.count_split('test')}")

    def _load_metadata(self) -> List[Dict]:
        """Load MAESTRO metadata JSON."""
        if not self.metadata_path.exists():
            raise FileNotFoundError(
                f"MAESTRO metadata not found: {self.metadata_path}\n"
                f"Please download MAESTRO dataset from: "
                f"https://magenta.tensorflow.org/datasets/maestro"
            )

        with open(self.metadata_path, 'r') as f:
            data = json.load(f)

        return data

    def count_split(self, split: str) -> int:
        """Count recordings in a split."""
        return sum(1 for item in self.metadata if item['split'] == split)

    def get_split(
        self,
        split: str = 'test',
        max_items: Optional[int] = None
    ) -> List[Tuple[Path, Path]]:
        """
        Get audio/MIDI pairs for a split.

        Args:
            split: 'train', 'validation', or 'test'
            max_items: Maximum number of items to return (for quick testing)

        Returns:
            List of (audio_path, midi_path) tuples
        """
        pairs = []

        for item in self.metadata:
            if item['split'] != split:
                continue

            audio_path = self.maestro_root / item['audio_filename']
            midi_path = self.maestro_root / item['midi_filename']

            # Verify files exist
            if not audio_path.exists():
                print(f"Warning: Audio file not found: {audio_path}")
                continue

            if not midi_path.exists():
                print(f"Warning: MIDI file not found: {midi_path}")
                continue

            pairs.append((audio_path, midi_path))

            if max_items and len(pairs) >= max_items:
                break

        return pairs

    def get_test_subset(self, n: int = 10) -> List[Tuple[Path, Path]]:
        """
        Get small test subset for quick evaluation.

        Args:
            n: Number of test examples

        Returns:
            List of (audio_path, midi_path) tuples
        """
        return self.get_split('test', max_items=n)


class CustomBenchmark:
    """
    Custom benchmark dataset (e.g., YouTube piano videos).

    Assumes directory structure:
    benchmark_root/
      audio/
        track1.wav
        track2.wav
      ground_truth/
        track1.mid
        track2.mid
    """

    def __init__(self, benchmark_root: Path):
        """
        Initialize custom benchmark.

        Args:
            benchmark_root: Root directory with audio/ and ground_truth/ subdirs
        """
        self.benchmark_root = Path(benchmark_root)
        self.audio_dir = self.benchmark_root / "audio"
        self.ground_truth_dir = self.benchmark_root / "ground_truth"

        # Verify structure
        if not self.audio_dir.exists():
            raise FileNotFoundError(f"Audio directory not found: {self.audio_dir}")

        if not self.ground_truth_dir.exists():
            raise FileNotFoundError(f"Ground truth directory not found: {self.ground_truth_dir}")

        # Load pairs
        self.pairs = self._load_pairs()

        print(f"Custom benchmark loaded:")
        print(f"  Root: {self.benchmark_root}")
        print(f"  Total recordings: {len(self.pairs)}")

    def _load_pairs(self) -> List[Tuple[Path, Path]]:
        """Load audio/MIDI pairs."""
        pairs = []

        # Find all audio files
        for audio_path in sorted(self.audio_dir.glob("*.wav")):
            # Look for corresponding MIDI file
            midi_path = self.ground_truth_dir / f"{audio_path.stem}.mid"

            if not midi_path.exists():
                # Try .midi extension
                midi_path = self.ground_truth_dir / f"{audio_path.stem}.midi"

            if not midi_path.exists():
                print(f"Warning: No ground truth for {audio_path.name}")
                continue

            pairs.append((audio_path, midi_path))

        return pairs

    def get_all(self) -> List[Tuple[Path, Path]]:
        """Get all audio/MIDI pairs."""
        return self.pairs


def load_benchmark_dataset(
    dataset_name: str = "maestro",
    dataset_root: Optional[Path] = None,
    split: str = "test",
    max_items: Optional[int] = None
) -> List[Tuple[Path, Path]]:
    """
    Load benchmark dataset with automatic detection.

    Args:
        dataset_name: 'maestro' or 'custom'
        dataset_root: Root directory of dataset
        split: Dataset split (for MAESTRO)
        max_items: Maximum items to load

    Returns:
        List of (audio_path, ground_truth_midi) tuples
    """
    if dataset_root is None:
        # Try default locations
        default_locations = [
            Path("data/maestro-v3.0.0"),
            Path("/tmp/maestro-v3.0.0"),
            Path.home() / "data/maestro-v3.0.0"
        ]

        for location in default_locations:
            if location.exists():
                dataset_root = location
                break

        if dataset_root is None:
            raise FileNotFoundError(
                f"Dataset not found. Tried: {default_locations}\n"
                f"Please download MAESTRO from: https://magenta.tensorflow.org/datasets/maestro"
            )

    if dataset_name == "maestro":
        dataset = MAESTRODataset(dataset_root)
        return dataset.get_split(split, max_items)
    elif dataset_name == "custom":
        dataset = CustomBenchmark(dataset_root)
        return dataset.get_all()
    else:
        raise ValueError(f"Unknown dataset: {dataset_name}")


if __name__ == "__main__":
    """Test dataset loaders."""
    print("Testing Benchmark Dataset Loaders\n")

    # Test MAESTRO loader (if available)
    try:
        dataset = load_benchmark_dataset("maestro", max_items=5)
        print(f"\n✓ MAESTRO test subset loaded: {len(dataset)} examples")

        for i, (audio, midi) in enumerate(dataset[:3], 1):
            print(f"  {i}. Audio: {audio.name}")
            print(f"     MIDI:  {midi.name}")

    except FileNotFoundError as e:
        print(f"\n⚠ MAESTRO not found: {e}")
        print("  To use MAESTRO, download from:")
        print("  https://magenta.tensorflow.org/datasets/maestro")

    print("\n✓ Dataset loaders ready")
