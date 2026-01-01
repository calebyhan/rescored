"""
Download and prepare MAESTRO dataset subset for benchmarking.

MAESTRO (MIDI and Audio Edited for Synchronous TRacks and Organization) is a
dataset of ~200 hours of piano performances with aligned MIDI.

We'll download a curated subset for testing:
- Simple pieces (easy difficulty)
- Classical pieces (Chopin, Bach - medium/hard)
- Varied tempo and complexity

Dataset info: https://magenta.tensorflow.org/datasets/maestro
"""

import json
import subprocess
from pathlib import Path
from typing import List
import urllib.request
import zipfile
import shutil

from evaluation.benchmark import TestCase, save_test_cases_to_json


# Curated subset of MAESTRO for testing
# Format: (year, split, filename_prefix, genre, difficulty)
MAESTRO_SUBSET = [
    # Easy - Simple classical pieces
    ("2004", "test", "MIDI-Unprocessed_SMF_02_R1_2004_01-05_ORIG_MID--AUDIO_02_R1_2004_03_Track03_wav", "classical", "easy"),
    ("2004", "test", "MIDI-Unprocessed_SMF_02_R1_2004_01-05_ORIG_MID--AUDIO_02_R1_2004_05_Track05_wav", "classical", "easy"),

    # Medium - Chopin, moderate tempo
    ("2004", "test", "MIDI-Unprocessed_XP_14_R1_2004_01-04_ORIG_MID--AUDIO_14_R1_2004_04_Track04_wav", "classical", "medium"),
    ("2006", "test", "MIDI-Unprocessed_07_R1_2006_01-09_ORIG_MID--AUDIO_07_R1_2006_04_Track04_wav", "classical", "medium"),
    ("2008", "test", "MIDI-Unprocessed_11_R1_2008_01-04_ORIG_MID--AUDIO_11_R1_2008_02_Track02_wav", "classical", "medium"),

    # Hard - Fast passages, complex harmony
    ("2009", "test", "MIDI-Unprocessed_16_R1_2009_01-04_ORIG_MID--AUDIO_16_R1_2009_16_R1_2009_02_WAV", "classical", "hard"),
    ("2011", "test", "MIDI-Unprocessed_03_R1_2011_MID--AUDIO_03_R1_2011_03_R1_2011_02_WAV", "classical", "hard"),
    ("2013", "test", "MIDI-Unprocessed_20_R1_2013_MID--AUDIO_20_R1_2013_20_R1_2013_02_WAV", "classical", "hard"),
]


def download_maestro_subset(
    output_dir: Path,
    version: str = "v3.0.0"
) -> Path:
    """
    Download MAESTRO dataset (full version - 100+ GB).

    Note: This is a large download. For testing, we'll only use a small subset.

    Args:
        output_dir: Directory to save dataset
        version: MAESTRO version to download

    Returns:
        Path to extracted dataset directory
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    maestro_dir = output_dir / f"maestro-{version}"

    if maestro_dir.exists():
        print(f"✅ MAESTRO dataset already exists at: {maestro_dir}")
        return maestro_dir

    # Download URL
    url = f"https://storage.googleapis.com/magentadata/datasets/maestro/{version}/maestro-{version}.zip"
    zip_path = output_dir / f"maestro-{version}.zip"

    print(f"⬇️  Downloading MAESTRO {version} (this may take a while - ~100GB)...")
    print(f"   From: {url}")
    print(f"   To: {zip_path}")
    print("\n   ⚠️  WARNING: This is a LARGE download (100+ GB)!")
    print("   Consider downloading manually and extracting to:", output_dir)

    # For now, we'll skip auto-download and assume user has dataset
    # or provide instructions for manual download
    raise NotImplementedError(
        f"Please download MAESTRO manually from:\n"
        f"  {url}\n"
        f"Extract to: {output_dir}\n"
        f"Or use the maestro-downloader package: pip install maestro-downloader"
    )


def find_maestro_files(
    maestro_dir: Path,
    test_case_prefix: str,
    year: str
) -> tuple:
    """
    Find audio and MIDI files for a MAESTRO test case.

    Args:
        maestro_dir: Path to MAESTRO dataset root
        test_case_prefix: Filename prefix (without extension)
        year: Year subdirectory

    Returns:
        Tuple of (audio_path, midi_path) or (None, None) if not found
    """
    year_dir = maestro_dir / year

    # Look for audio file (.wav)
    audio_path = year_dir / f"{test_case_prefix}.wav"
    if not audio_path.exists():
        # Try alternative naming
        audio_path = year_dir / f"{test_case_prefix}.flac"

    # Look for MIDI file (.midi or .mid)
    midi_path = year_dir / f"{test_case_prefix}.midi"
    if not midi_path.exists():
        midi_path = year_dir / f"{test_case_prefix}.mid"

    if audio_path.exists() and midi_path.exists():
        return audio_path, midi_path

    return None, None


def create_maestro_test_cases(
    maestro_dir: Path,
    subset: List[tuple] = MAESTRO_SUBSET
) -> List[TestCase]:
    """
    Create test cases from MAESTRO dataset subset.

    Args:
        maestro_dir: Path to MAESTRO dataset root
        subset: List of (year, split, prefix, genre, difficulty) tuples

    Returns:
        List of TestCase objects
    """
    test_cases = []

    for year, split, prefix, genre, difficulty in subset:
        audio_path, midi_path = find_maestro_files(maestro_dir, prefix, year)

        if audio_path and midi_path:
            # Extract a readable name from the filename
            name = prefix.split("--")[-1].replace("_", " ").replace(".wav", "")

            test_case = TestCase(
                name=f"MAESTRO_{year}_{name[:50]}",  # Truncate long names
                audio_path=audio_path,
                ground_truth_midi=midi_path,
                genre=genre,
                difficulty=difficulty
            )
            test_cases.append(test_case)
            print(f"✅ Added test case: {test_case.name}")
        else:
            print(f"⚠️  Skipping (files not found): {year}/{prefix}")

    return test_cases


def create_simple_test_cases(output_dir: Path) -> List[TestCase]:
    """
    Create simple test cases for initial testing (without MAESTRO).

    Uses synthesized MIDI or publicly available simple piano pieces.
    Useful for testing the pipeline without downloading MAESTRO.

    Args:
        output_dir: Directory to save test files

    Returns:
        List of TestCase objects
    """
    test_cases = []
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # For now, return empty list with instructions
    print("📝 To use MAESTRO dataset:")
    print("   1. Download MAESTRO v3.0.0 from: https://magenta.tensorflow.org/datasets/maestro")
    print("   2. Extract to a directory (e.g., /tmp/maestro-v3.0.0/)")
    print("   3. Run: prepare_maestro_test_cases('/tmp/maestro-v3.0.0/')")
    print("")
    print("📝 Or create custom test cases with your own audio + MIDI files")

    return test_cases


def prepare_maestro_test_cases(
    maestro_dir: Path,
    output_json: Path
) -> List[TestCase]:
    """
    Main function to prepare MAESTRO test cases and save to JSON.

    Args:
        maestro_dir: Path to MAESTRO dataset root directory
        output_json: Path to save test_videos.json

    Returns:
        List of TestCase objects
    """
    maestro_dir = Path(maestro_dir)

    if not maestro_dir.exists():
        raise FileNotFoundError(
            f"MAESTRO directory not found: {maestro_dir}\n"
            f"Please download and extract MAESTRO dataset first."
        )

    print(f"🎹 Preparing MAESTRO test cases from: {maestro_dir}")

    # Create test cases from subset
    test_cases = create_maestro_test_cases(maestro_dir, MAESTRO_SUBSET)

    if len(test_cases) == 0:
        raise ValueError(
            "No test cases created! Check if MAESTRO directory structure is correct.\n"
            f"Expected structure: {maestro_dir}/YYYY/*.wav and *.midi"
        )

    # Save to JSON
    save_test_cases_to_json(test_cases, output_json)

    print(f"\n✅ Created {len(test_cases)} test cases")
    print(f"   Easy: {sum(1 for tc in test_cases if tc.difficulty == 'easy')}")
    print(f"   Medium: {sum(1 for tc in test_cases if tc.difficulty == 'medium')}")
    print(f"   Hard: {sum(1 for tc in test_cases if tc.difficulty == 'hard')}")

    return test_cases


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare MAESTRO dataset for benchmarking")
    parser.add_argument(
        "--maestro-dir",
        type=Path,
        required=True,
        help="Path to MAESTRO dataset root directory (e.g., /tmp/maestro-v3.0.0)"
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("backend/evaluation/test_videos.json"),
        help="Path to save test cases JSON file"
    )

    args = parser.parse_args()

    test_cases = prepare_maestro_test_cases(args.maestro_dir, args.output_json)

    print(f"\n🎯 Next steps:")
    print(f"   1. Run baseline benchmark:")
    print(f"      python -m evaluation.run_benchmark --model yourmt3")
    print(f"   2. Compare with other models after implementing them")
