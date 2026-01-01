"""
Main script to run transcription benchmarks.

Usage:
    # Prepare MAESTRO test cases (one-time setup)
    python -m evaluation.prepare_maestro --maestro-dir /path/to/maestro-v3.0.0

    # Run baseline benchmark on YourMT3+
    python -m evaluation.run_benchmark --model yourmt3 --test-cases evaluation/test_videos.json

    # Compare with ensemble after Phase 3
    python -m evaluation.run_benchmark --model ensemble --test-cases evaluation/test_videos.json
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path to import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.benchmark import TranscriptionBenchmark, load_test_cases_from_json
from evaluation.metrics import calculate_metrics
from pipeline import TranscriptionPipeline
from app_config import Settings


def transcribe_with_yourmt3(audio_path: Path, output_dir: Path) -> Path:
    """
    Transcribe audio using current YourMT3+ pipeline.

    Args:
        audio_path: Path to input audio file
        output_dir: Directory to save output MIDI

    Returns:
        Path to output MIDI file
    """
    config = Settings()

    # Create a temporary job ID for benchmarking
    import uuid
    job_id = f"benchmark_{uuid.uuid4().hex[:8]}"

    # Initialize pipeline
    pipeline = TranscriptionPipeline(job_id=job_id, config=config)

    # Create temporary output directory
    temp_dir = Path("/tmp/rescored_benchmark") / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Copy audio to temp dir (pipeline expects YouTube audio download)
    import shutil
    temp_audio = temp_dir / "audio.wav"
    shutil.copy(audio_path, temp_audio)

    try:
        # Run source separation
        separated_audio_dir = pipeline.separate_audio(temp_audio)
        piano_stem = separated_audio_dir / "other.wav"

        if not piano_stem.exists():
            raise FileNotFoundError(f"Source separation failed: {piano_stem}")

        # Run transcription
        midi_path = pipeline.transcribe_to_midi(piano_stem)

        # Copy result to output directory
        output_midi = output_dir / f"{audio_path.stem}.mid"
        shutil.copy(midi_path, output_midi)

        return output_midi

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def transcribe_with_ensemble(audio_path: Path, output_dir: Path) -> Path:
    """
    Transcribe audio using ensemble method (Phase 3).

    Note: This will be implemented in Phase 3.

    Args:
        audio_path: Path to input audio file
        output_dir: Directory to save output MIDI

    Returns:
        Path to output MIDI file
    """
    raise NotImplementedError(
        "Ensemble transcription not yet implemented. "
        "This will be available after Phase 3."
    )


def transcribe_with_bytedance(audio_path: Path, output_dir: Path) -> Path:
    """
    Transcribe audio using ByteDance piano model (Phase 2).

    Note: This will be implemented in Phase 2.

    Args:
        audio_path: Path to input audio file
        output_dir: Directory to save output MIDI

    Returns:
        Path to output MIDI file
    """
    raise NotImplementedError(
        "ByteDance transcription not yet implemented. "
        "This will be available after Phase 2."
    )


def main():
    parser = argparse.ArgumentParser(description="Run transcription benchmarks")
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        choices=["yourmt3", "bytedance", "ensemble"],
        help="Model to benchmark"
    )
    parser.add_argument(
        "--test-cases",
        type=Path,
        default=Path("backend/evaluation/test_videos.json"),
        help="Path to test cases JSON file"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backend/evaluation/results"),
        help="Directory to save benchmark results"
    )
    parser.add_argument(
        "--onset-tolerance",
        type=float,
        default=0.05,
        help="Onset matching tolerance in seconds (default: 0.05 = 50ms)"
    )

    args = parser.parse_args()

    # Load test cases
    if not args.test_cases.exists():
        print(f"❌ Test cases file not found: {args.test_cases}")
        print(f"\n📝 First, prepare test cases:")
        print(f"   python -m evaluation.prepare_maestro --maestro-dir /path/to/maestro-v3.0.0")
        sys.exit(1)

    test_cases = load_test_cases_from_json(args.test_cases)
    print(f"✅ Loaded {len(test_cases)} test cases from {args.test_cases}")

    # Select transcription function
    transcribe_fn_map = {
        "yourmt3": transcribe_with_yourmt3,
        "bytedance": transcribe_with_bytedance,
        "ensemble": transcribe_with_ensemble
    }
    transcribe_fn = transcribe_fn_map[args.model]

    # Create benchmark runner
    benchmark = TranscriptionBenchmark(
        test_cases=test_cases,
        output_dir=args.output_dir,
        onset_tolerance=args.onset_tolerance
    )

    # Run benchmark
    results = benchmark.run_benchmark(
        transcribe_fn=transcribe_fn,
        model_name=args.model
    )

    print(f"\n✅ Benchmark complete!")
    print(f"   Results saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
