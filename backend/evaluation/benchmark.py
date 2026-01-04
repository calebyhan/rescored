"""
Benchmark runner for evaluating transcription accuracy on test datasets.

Supports MAESTRO dataset and custom test videos with ground truth MIDI.
"""

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
import sys

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from evaluation.metrics import calculate_metrics, TranscriptionMetrics


@dataclass
class TestCase:
    """Represents a single test case for benchmarking."""
    name: str  # Descriptive name (e.g., "Chopin_Nocturne_Op9_No2")
    audio_path: Path  # Path to audio file (WAV/MP3)
    ground_truth_midi: Optional[Path] = None  # Path to ground truth MIDI file (None for manual review)
    genre: str = "classical"  # Genre: classical, pop, jazz, simple
    difficulty: str = "medium"  # Difficulty: easy, medium, hard
    duration: Optional[float] = None  # Duration in seconds

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'audio_path': str(self.audio_path),
            'ground_truth_midi': str(self.ground_truth_midi) if self.ground_truth_midi else None,
            'genre': self.genre,
            'difficulty': self.difficulty,
            'duration': self.duration
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TestCase':
        """Create TestCase from dictionary."""
        ground_truth = data.get('ground_truth_midi')
        return cls(
            name=data['name'],
            audio_path=Path(data['audio_path']),
            ground_truth_midi=Path(ground_truth) if ground_truth else None,
            genre=data.get('genre', 'classical'),
            difficulty=data.get('difficulty', 'medium'),
            duration=data.get('duration')
        )


@dataclass
class BenchmarkResult:
    """Results for a single test case."""
    test_case_name: str
    genre: str
    difficulty: str
    metrics: TranscriptionMetrics
    processing_time: float  # Time taken to transcribe (seconds)
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'test_case': self.test_case_name,
            'genre': self.genre,
            'difficulty': self.difficulty,
            'f1_score': self.metrics.f1_score,
            'precision': self.metrics.precision,
            'recall': self.metrics.recall,
            'onset_mae': self.metrics.onset_mae,
            'pitch_accuracy': self.metrics.pitch_accuracy,
            'true_positives': self.metrics.true_positives,
            'false_positives': self.metrics.false_positives,
            'false_negatives': self.metrics.false_negatives,
            'processing_time': self.processing_time,
            'success': self.success,
            'error': self.error_message
        }


class TranscriptionBenchmark:
    """
    Benchmark runner for transcription models.

    Evaluates transcription accuracy on a test set and generates reports.
    """

    def __init__(
        self,
        test_cases: List[TestCase],
        output_dir: Path,
        onset_tolerance: float = 0.05
    ):
        """
        Initialize benchmark runner.

        Args:
            test_cases: List of test cases to evaluate
            output_dir: Directory to save results
            onset_tolerance: Onset matching tolerance (seconds)
        """
        self.test_cases = test_cases
        self.output_dir = Path(output_dir)
        self.onset_tolerance = onset_tolerance
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_single_test(
        self,
        test_case: TestCase,
        transcribe_fn,
        output_midi_dir: Path
    ) -> BenchmarkResult:
        """
        Run a single test case.

        Args:
            test_case: Test case to evaluate
            transcribe_fn: Function that takes audio_path and returns MIDI path
            output_midi_dir: Directory to save transcribed MIDI files

        Returns:
            BenchmarkResult with metrics and timing
        """
        print(f"\n{'='*60}")
        print(f"Test: {test_case.name}")
        print(f"Genre: {test_case.genre} | Difficulty: {test_case.difficulty}")
        print(f"{'='*60}")

        try:
            # Transcribe audio
            start_time = time.time()
            predicted_midi = transcribe_fn(test_case.audio_path, output_midi_dir)
            processing_time = time.time() - start_time

            if not predicted_midi.exists():
                raise FileNotFoundError(f"Transcription failed: {predicted_midi} not found")

            print(f"✅ Transcription completed in {processing_time:.1f}s")

            # Calculate metrics only if ground truth is available
            if test_case.ground_truth_midi:
                metrics = calculate_metrics(
                    predicted_midi,
                    test_case.ground_truth_midi,
                    onset_tolerance=self.onset_tolerance
                )

                print(f"\n📊 Results:")
                print(f"   F1 Score: {metrics.f1_score:.3f}")
                print(f"   Precision: {metrics.precision:.3f}")
                print(f"   Recall: {metrics.recall:.3f}")
                print(f"   Onset MAE: {metrics.onset_mae*1000:.1f}ms")
            else:
                # No ground truth - create placeholder metrics for manual review
                print(f"\n📝 No ground truth available - MIDI saved for manual review")
                print(f"   Output: {predicted_midi}")
                metrics = TranscriptionMetrics(
                    precision=0.0, recall=0.0, f1_score=0.0,
                    onset_mae=0.0, pitch_accuracy=0.0,
                    true_positives=0, false_positives=0, false_negatives=0
                )

            return BenchmarkResult(
                test_case_name=test_case.name,
                genre=test_case.genre,
                difficulty=test_case.difficulty,
                metrics=metrics,
                processing_time=processing_time,
                success=True
            )

        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"❌ Test failed: {e}")
            print(f"\nFull traceback:")
            print(error_traceback)

            # Return placeholder metrics for failed test
            return BenchmarkResult(
                test_case_name=test_case.name,
                genre=test_case.genre,
                difficulty=test_case.difficulty,
                metrics=TranscriptionMetrics(
                    precision=0.0, recall=0.0, f1_score=0.0,
                    onset_mae=float('inf'), pitch_accuracy=0.0,
                    true_positives=0, false_positives=0, false_negatives=0
                ),
                processing_time=0.0,
                success=False,
                error_message=str(e)
            )

    def run_benchmark(self, transcribe_fn, model_name: str = "model") -> List[BenchmarkResult]:
        """
        Run full benchmark on all test cases.

        Args:
            transcribe_fn: Function that transcribes audio to MIDI
            model_name: Name of model being tested (for output files)

        Returns:
            List of BenchmarkResult objects
        """
        print(f"\n🎹 Starting Benchmark: {model_name}")
        print(f"📝 Test cases: {len(self.test_cases)}")
        print(f"⏱️  Onset tolerance: {self.onset_tolerance*1000:.0f}ms")

        # Create output directory for transcribed MIDI
        output_midi_dir = self.output_dir / f"{model_name}_midi"
        output_midi_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for i, test_case in enumerate(self.test_cases, 1):
            print(f"\n[{i}/{len(self.test_cases)}]", end=" ")
            result = self.run_single_test(test_case, transcribe_fn, output_midi_dir)
            results.append(result)

        # Save results
        self._save_results(results, model_name)
        self._print_summary(results, model_name)

        return results

    def _save_results(self, results: List[BenchmarkResult], model_name: str):
        """Save benchmark results to JSON and CSV."""
        # JSON format (detailed)
        json_path = self.output_dir / f"{model_name}_results.json"
        with open(json_path, 'w') as f:
            json.dump([r.to_dict() for r in results], f, indent=2)
        print(f"\n💾 Saved detailed results to: {json_path}")

        # CSV format (for spreadsheet analysis)
        csv_path = self.output_dir / f"{model_name}_results.csv"
        df = pd.DataFrame([r.to_dict() for r in results])
        df.to_csv(csv_path, index=False)
        print(f"💾 Saved CSV results to: {csv_path}")

    def _print_summary(self, results: List[BenchmarkResult], model_name: str):
        """Print summary statistics."""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        print(f"\n{'='*60}")
        print(f"📊 BENCHMARK SUMMARY: {model_name}")
        print(f"{'='*60}")
        print(f"Total tests: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")

        if len(successful) == 0:
            print("\n❌ All tests failed!")
            return

        # Overall metrics
        avg_f1 = sum(r.metrics.f1_score for r in successful) / len(successful)
        avg_precision = sum(r.metrics.precision for r in successful) / len(successful)
        avg_recall = sum(r.metrics.recall for r in successful) / len(successful)
        avg_onset_mae = sum(r.metrics.onset_mae for r in successful) / len(successful)
        avg_time = sum(r.processing_time for r in successful) / len(successful)

        print(f"\n📈 Overall Accuracy:")
        print(f"   F1 Score: {avg_f1:.3f}")
        print(f"   Precision: {avg_precision:.3f}")
        print(f"   Recall: {avg_recall:.3f}")
        print(f"   Onset MAE: {avg_onset_mae*1000:.1f}ms")
        print(f"   Avg Processing Time: {avg_time:.1f}s")

        # By genre
        genres = set(r.genre for r in successful)
        print(f"\n📊 By Genre:")
        for genre in sorted(genres):
            genre_results = [r for r in successful if r.genre == genre]
            genre_f1 = sum(r.metrics.f1_score for r in genre_results) / len(genre_results)
            print(f"   {genre.capitalize()}: F1={genre_f1:.3f} ({len(genre_results)} tests)")

        # By difficulty
        difficulties = set(r.difficulty for r in successful)
        print(f"\n📊 By Difficulty:")
        for diff in ['easy', 'medium', 'hard']:
            if diff in difficulties:
                diff_results = [r for r in successful if r.difficulty == diff]
                diff_f1 = sum(r.metrics.f1_score for r in diff_results) / len(diff_results)
                print(f"   {diff.capitalize()}: F1={diff_f1:.3f} ({len(diff_results)} tests)")

        print(f"\n{'='*60}\n")


def load_test_cases_from_json(json_path: Path) -> List[TestCase]:
    """Load test cases from JSON file."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return [TestCase.from_dict(case) for case in data]


def save_test_cases_to_json(test_cases: List[TestCase], json_path: Path):
    """Save test cases to JSON file."""
    with open(json_path, 'w') as f:
        json.dump([tc.to_dict() for tc in test_cases], f, indent=2)
    print(f"💾 Saved {len(test_cases)} test cases to: {json_path}")
