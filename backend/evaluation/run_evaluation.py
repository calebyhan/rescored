"""
Run Evaluation Script

Evaluates Phase 1 improvements on MAESTRO dataset.
Compares:
- Baseline: Ensemble without confidence filtering or TTA
- Phase 1.1: Ensemble with confidence filtering
- Phase 1.2: Ensemble with confidence filtering + TTA

Usage:
    python -m backend.evaluation.run_evaluation --dataset maestro --max-items 10
"""

import argparse
from pathlib import Path
import sys

from backend.app_config import Settings
from backend.pipeline import TranscriptionPipeline
from backend.evaluation.evaluator import TranscriptionEvaluator


def create_transcriber(config: Settings, use_tta: bool = False):
    """
    Create transcriber function from pipeline.

    Args:
        config: Settings object
        use_tta: Enable TTA

    Returns:
        Transcriber function compatible with evaluator
    """
    def transcribe(audio_path: Path, output_dir: Path) -> Path:
        """Transcribe audio and return MIDI path."""
        # Override TTA setting
        config.enable_tta = use_tta

        # Create pipeline
        pipeline = TranscriptionPipeline(config)

        # Simplified pipeline for evaluation:
        # 1. Preprocess audio (optional)
        # 2. Separate sources (get piano stem)
        # 3. Transcribe with ensemble (+TTA if enabled)

        try:
            # Preprocess
            if config.enable_audio_preprocessing:
                processed_audio = pipeline.preprocess_audio(audio_path)
            else:
                processed_audio = audio_path

            # Source separation
            stems = pipeline.separate_sources(processed_audio)

            # Select piano stem (or 'other' if no dedicated piano)
            piano_stem = stems.get('piano') or stems.get('other')

            if piano_stem is None or not piano_stem.exists():
                raise ValueError("No piano/other stem found in separation output")

            # Transcribe
            midi_path = pipeline.transcribe_with_ensemble(piano_stem)

            # Copy to output dir
            final_path = output_dir / midi_path.name
            import shutil
            shutil.copy(midi_path, final_path)

            return final_path

        except Exception as e:
            print(f"Error in transcription pipeline: {e}")
            raise

    return transcribe


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Phase 1 improvements on benchmark dataset"
    )

    parser.add_argument(
        '--dataset',
        type=str,
        default='maestro',
        choices=['maestro', 'custom'],
        help='Benchmark dataset to use'
    )

    parser.add_argument(
        '--dataset-root',
        type=str,
        default=None,
        help='Root directory of dataset (auto-detected if not provided)'
    )

    parser.add_argument(
        '--split',
        type=str,
        default='test',
        choices=['train', 'validation', 'test'],
        help='Dataset split (for MAESTRO)'
    )

    parser.add_argument(
        '--max-items',
        type=int,
        default=None,
        help='Maximum items to evaluate (for quick testing)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='/tmp/rescored_evaluation',
        help='Output directory for results'
    )

    parser.add_argument(
        '--models',
        type=str,
        nargs='+',
        default=['baseline', 'phase1.1', 'phase1.2'],
        choices=['baseline', 'phase1.1', 'phase1.2', 'all'],
        help='Models to evaluate'
    )

    args = parser.parse_args()

    # Convert paths
    dataset_root = Path(args.dataset_root) if args.dataset_root else None
    output_dir = Path(args.output_dir)

    # Create evaluator
    print("\n" + "=" * 80)
    print("PHASE 1 EVALUATION - Rescored Transcription Accuracy")
    print("=" * 80 + "\n")

    evaluator = TranscriptionEvaluator(
        dataset=args.dataset,
        dataset_root=dataset_root,
        split=args.split,
        max_items=args.max_items
    )

    # Build model configurations
    models = {}

    if 'all' in args.models:
        args.models = ['baseline', 'phase1.1', 'phase1.2']

    # Baseline: No confidence filtering, no TTA
    if 'baseline' in args.models:
        config_baseline = Settings()
        config_baseline.use_bytedance_confidence = False  # Disable Phase 1.1
        config_baseline.enable_tta = False  # Disable Phase 1.2

        models['baseline'] = create_transcriber(config_baseline, use_tta=False)

    # Phase 1.1: Confidence filtering enabled
    if 'phase1.1' in args.models:
        config_phase1_1 = Settings()
        config_phase1_1.use_bytedance_confidence = True  # Enable Phase 1.1
        config_phase1_1.enable_tta = False  # Disable Phase 1.2

        models['phase1.1_confidence'] = create_transcriber(config_phase1_1, use_tta=False)

    # Phase 1.2: Confidence filtering + TTA
    if 'phase1.2' in args.models:
        config_phase1_2 = Settings()
        config_phase1_2.use_bytedance_confidence = True  # Enable Phase 1.1
        config_phase1_2.enable_tta = True  # Enable Phase 1.2

        models['phase1.2_confidence_tta'] = create_transcriber(config_phase1_2, use_tta=True)

    # Run comparison
    print(f"\nEvaluating {len(models)} configurations:\n")
    for model_name in models.keys():
        print(f"  - {model_name}")
    print()

    all_results = evaluator.compare_models(models, output_dir=output_dir)

    # Save results
    results_dir = output_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    for model_name, results in all_results.items():
        results_path = results_dir / f"{model_name}_results.json"
        evaluator.save_results(results, results_path)

    print(f"\n✓ Evaluation complete!")
    print(f"Results saved to: {results_dir}")

    # Print final summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    evaluator.print_comparison(all_results)


if __name__ == "__main__":
    main()
