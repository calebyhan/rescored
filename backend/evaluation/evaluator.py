"""
Main Evaluation Orchestrator

Runs transcription evaluation on benchmark datasets and computes metrics.
Supports comparing multiple models/configurations.
"""

from pathlib import Path
from typing import List, Dict, Optional, Callable
import json
from datetime import datetime
from dataclasses import dataclass, asdict
import numpy as np

from backend.evaluation.metrics_calculator import MirEvalMetrics, print_metrics_summary
from backend.evaluation.benchmark_datasets import load_benchmark_dataset


@dataclass
class EvaluationResult:
    """Result from evaluating a single audio file."""
    audio_filename: str
    model_name: str
    metrics: Dict[str, float]
    duration_seconds: float
    error: Optional[str] = None


class TranscriptionEvaluator:
    """
    Evaluate transcription models on benchmark datasets.

    Usage:
        evaluator = TranscriptionEvaluator(dataset='maestro', split='test')
        results = evaluator.evaluate_model(transcriber, model_name='ensemble')
        evaluator.print_summary(results)
    """

    def __init__(
        self,
        dataset: str = 'maestro',
        dataset_root: Optional[Path] = None,
        split: str = 'test',
        max_items: Optional[int] = None,
        onset_tolerance: float = 0.05
    ):
        """
        Initialize evaluator.

        Args:
            dataset: Dataset name ('maestro' or 'custom')
            dataset_root: Root directory of dataset
            split: Dataset split (for MAESTRO: 'train', 'validation', 'test')
            max_items: Maximum items to evaluate (for quick testing)
            onset_tolerance: Onset tolerance for metrics (seconds)
        """
        self.dataset_name = dataset
        self.split = split
        self.onset_tolerance = onset_tolerance

        # Load dataset
        print(f"\nLoading benchmark dataset: {dataset}")
        self.dataset_pairs = load_benchmark_dataset(
            dataset_name=dataset,
            dataset_root=dataset_root,
            split=split,
            max_items=max_items
        )

        print(f"✓ Loaded {len(self.dataset_pairs)} evaluation pairs\n")

        # Initialize metrics calculator
        self.metrics_calculator = MirEvalMetrics(onset_tolerance=onset_tolerance)

    def evaluate_model(
        self,
        transcriber: Callable[[Path, Path], Path],
        model_name: str = "model",
        output_dir: Optional[Path] = None
    ) -> List[EvaluationResult]:
        """
        Evaluate a transcription model on the dataset.

        Args:
            transcriber: Function that takes (audio_path, output_dir) and returns MIDI path
            model_name: Name for this model/configuration
            output_dir: Directory for output MIDI files

        Returns:
            List of EvaluationResult objects
        """
        if output_dir is None:
            output_dir = Path(f"/tmp/evaluation/{model_name}")
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"{'=' * 70}")
        print(f"Evaluating: {model_name}")
        print(f"Dataset: {self.dataset_name} ({self.split} split)")
        print(f"Items: {len(self.dataset_pairs)}")
        print(f"{'=' * 70}\n")

        results = []

        for i, (audio_path, ground_truth_midi) in enumerate(self.dataset_pairs, 1):
            print(f"[{i}/{len(self.dataset_pairs)}] {audio_path.name}")

            try:
                # Transcribe
                import time
                start_time = time.time()

                prediction_midi = transcriber(audio_path, output_dir)

                duration = time.time() - start_time
                print(f"  ✓ Transcription complete ({duration:.1f}s)")

                # Compute metrics
                metrics = self.metrics_calculator.compute(
                    prediction_midi,
                    ground_truth_midi
                )

                metrics['duration_seconds'] = duration

                print(f"  ✓ F1: {metrics['f1']:.1%} "
                      f"(P: {metrics['precision']:.1%}, R: {metrics['recall']:.1%})")

                results.append(EvaluationResult(
                    audio_filename=audio_path.name,
                    model_name=model_name,
                    metrics=metrics,
                    duration_seconds=duration
                ))

            except Exception as e:
                print(f"  ✗ Error: {e}")
                results.append(EvaluationResult(
                    audio_filename=audio_path.name,
                    model_name=model_name,
                    metrics={},
                    duration_seconds=0.0,
                    error=str(e)
                ))

        print(f"\n{'=' * 70}")
        print(f"Evaluation complete: {model_name}")
        print(f"{'=' * 70}\n")

        return results

    def compare_models(
        self,
        models: Dict[str, Callable[[Path, Path], Path]],
        output_dir: Optional[Path] = None
    ) -> Dict[str, List[EvaluationResult]]:
        """
        Compare multiple models on the same dataset.

        Args:
            models: Dict of {model_name: transcriber_function}
            output_dir: Base directory for outputs

        Returns:
            Dict of {model_name: results}
        """
        if output_dir is None:
            output_dir = Path("/tmp/evaluation")

        all_results = {}

        for model_name, transcriber in models.items():
            model_output_dir = output_dir / model_name
            results = self.evaluate_model(transcriber, model_name, model_output_dir)
            all_results[model_name] = results

        # Print comparison
        self.print_comparison(all_results)

        return all_results

    def print_summary(self, results: List[EvaluationResult]):
        """Print summary statistics for evaluation results."""
        # Filter out errors
        valid_results = [r for r in results if r.error is None]

        if len(valid_results) == 0:
            print("No valid results to summarize")
            return

        # Aggregate metrics
        metrics_keys = list(valid_results[0].metrics.keys())

        summary = {
            'model_name': results[0].model_name,
            'n_total': len(results),
            'n_success': len(valid_results),
            'n_errors': len(results) - len(valid_results)
        }

        for key in metrics_keys:
            values = [r.metrics[key] for r in valid_results if key in r.metrics]
            if len(values) > 0:
                summary[f'{key}_mean'] = np.mean(values)
                summary[f'{key}_std'] = np.std(values)
                summary[f'{key}_min'] = np.min(values)
                summary[f'{key}_max'] = np.max(values)

        # Print summary
        print_metrics_summary(
            {
                'precision': summary.get('precision_mean', 0),
                'recall': summary.get('recall_mean', 0),
                'f1': summary.get('f1_mean', 0),
                'precision_with_offset': summary.get('precision_with_offset_mean', 0),
                'recall_with_offset': summary.get('recall_with_offset_mean', 0),
                'f1_with_offset': summary.get('f1_with_offset_mean', 0),
                'n_predicted': int(summary.get('n_predicted_mean', 0)),
                'n_ground_truth': int(summary.get('n_ground_truth_mean', 0)),
                'n_true_positives': int(summary.get('n_true_positives_mean', 0)),
                'n_false_positives': int(summary.get('n_false_positives_mean', 0)),
                'n_false_negatives': int(summary.get('n_false_negatives_mean', 0)),
            },
            label=f"{summary['model_name']} - Summary ({summary['n_success']}/{summary['n_total']} successful)"
        )

        print(f"Timing:")
        if 'duration_seconds_mean' in summary:
            print(f"  Mean duration: {summary['duration_seconds_mean']:.1f}s")
            print(f"  Total duration: {summary['duration_seconds_mean'] * summary['n_total']:.1f}s")

        print(f"\nVariance:")
        print(f"  F1 std dev: {summary.get('f1_std', 0):.1%}")
        print(f"  F1 range: {summary.get('f1_min', 0):.1%} - {summary.get('f1_max', 0):.1%}")

    def print_comparison(self, all_results: Dict[str, List[EvaluationResult]]):
        """Print comparison table for multiple models."""
        print(f"\n{'=' * 80}")
        print("MODEL COMPARISON")
        print(f"{'=' * 80}\n")

        # Compute summary stats for each model
        summaries = []

        for model_name, results in all_results.items():
            valid_results = [r for r in results if r.error is None]

            if len(valid_results) == 0:
                continue

            f1_values = [r.metrics['f1'] for r in valid_results]
            precision_values = [r.metrics['precision'] for r in valid_results]
            recall_values = [r.metrics['recall'] for r in valid_results]

            summaries.append({
                'model': model_name,
                'f1_mean': np.mean(f1_values),
                'f1_std': np.std(f1_values),
                'precision_mean': np.mean(precision_values),
                'recall_mean': np.mean(recall_values),
                'n_success': len(valid_results),
                'n_total': len(results)
            })

        # Sort by F1 score
        summaries.sort(key=lambda x: x['f1_mean'], reverse=True)

        # Print table
        print(f"{'Model':<30} {'F1 Score':<15} {'Precision':<12} {'Recall':<12} {'Success':<10}")
        print(f"{'-' * 80}")

        for summary in summaries:
            print(f"{summary['model']:<30} "
                  f"{summary['f1_mean']:>6.1%} ± {summary['f1_std']:>5.1%}  "
                  f"{summary['precision_mean']:>10.1%}  "
                  f"{summary['recall_mean']:>10.1%}  "
                  f"{summary['n_success']:>3}/{summary['n_total']:<3}")

        print(f"{'-' * 80}")

        # Show improvement
        if len(summaries) >= 2:
            baseline = summaries[-1]['f1_mean']
            best = summaries[0]['f1_mean']
            improvement = best - baseline

            print(f"\nImprovement over baseline ({summaries[-1]['model']}):")
            print(f"  {summaries[0]['model']}: +{improvement:.1%} ({baseline:.1%} → {best:.1%})")

        print(f"\n{'=' * 80}\n")

    def save_results(
        self,
        results: List[EvaluationResult],
        output_path: Path
    ):
        """
        Save evaluation results to JSON.

        Args:
            results: List of evaluation results
            output_path: Path for output JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict
        results_dict = {
            'metadata': {
                'dataset': self.dataset_name,
                'split': self.split,
                'onset_tolerance': self.onset_tolerance,
                'timestamp': datetime.now().isoformat(),
                'n_items': len(results)
            },
            'results': [asdict(r) for r in results]
        }

        with open(output_path, 'w') as f:
            json.dump(results_dict, f, indent=2)

        print(f"✓ Results saved to: {output_path}")


if __name__ == "__main__":
    """Test evaluator with dummy transcriber."""
    import tempfile
    import pretty_midi
    import shutil

    print("Testing TranscriptionEvaluator\n")

    # Create temporary test dataset
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create fake MAESTRO structure
        maestro_dir = tmpdir / "maestro-v3.0.0"
        maestro_dir.mkdir()

        # Create 3 dummy audio/MIDI pairs
        for i in range(3):
            # Create dummy audio (silent WAV)
            audio_path = maestro_dir / f"test_{i}.wav"
            # Just touch the file for testing
            audio_path.touch()

            # Create ground truth MIDI
            pm = pretty_midi.PrettyMIDI()
            instrument = pretty_midi.Instrument(program=0)

            for j in range(5):
                note = pretty_midi.Note(
                    velocity=80,
                    pitch=60 + j,
                    start=j * 0.5,
                    end=(j + 1) * 0.5
                )
                instrument.notes.append(note)

            pm.instruments.append(instrument)
            midi_path = maestro_dir / f"test_{i}.mid"
            pm.write(str(midi_path))

        # Create metadata JSON
        metadata = [
            {
                'audio_filename': f'test_{i}.wav',
                'midi_filename': f'test_{i}.mid',
                'split': 'test'
            }
            for i in range(3)
        ]

        metadata_path = maestro_dir / "maestro-v3.0.0.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

        # Create dummy transcriber (returns ground truth with slight modification)
        def dummy_transcriber(audio_path: Path, output_dir: Path) -> Path:
            """Dummy transcriber that returns slightly modified ground truth."""
            # Find corresponding MIDI
            midi_path = audio_path.with_suffix('.mid')

            # Copy to output dir
            output_path = output_dir / f"{audio_path.stem}_transcribed.mid"
            shutil.copy(midi_path, output_path)

            return output_path

        # Test evaluator
        try:
            evaluator = TranscriptionEvaluator(
                dataset='maestro',
                dataset_root=maestro_dir,
                split='test'
            )

            results = evaluator.evaluate_model(
                dummy_transcriber,
                model_name="dummy_model"
            )

            evaluator.print_summary(results)

            print("\n✓ Evaluator test passed!")

        except Exception as e:
            print(f"\n✗ Evaluator test failed: {e}")
            raise
