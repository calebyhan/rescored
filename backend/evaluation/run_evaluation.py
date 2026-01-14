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

        # Create pipeline with dummy job_id and youtube_url (not needed for evaluation)
        job_id = f"eval_{audio_path.stem}"
        pipeline = TranscriptionPipeline(
            job_id=job_id,
            youtube_url="",  # Not needed for evaluation
            storage_path=output_dir,
            config=config
        )

        # Simplified pipeline for evaluation:
        # MAESTRO is already solo piano, so skip source separation

        try:
            # For MAESTRO: Audio is already piano-only, transcribe directly
            # Skip preprocessing and source separation
            midi_path = pipeline.transcribe_with_ensemble(audio_path)

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
        default=['baseline', 'phase1.1', 'phase1.3'],
        choices=['baseline', 'phase1.1', 'phase1.2', 'phase1.3', 'phase1.3b', 'phase1.3c', 'phase1.4', 'all'],
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
        args.models = ['baseline', 'phase1.1', 'phase1.2', 'phase1.3', 'phase1.3b', 'phase1.3c', 'phase1.4']

    # Baseline: No confidence filtering, no TTA, no BiLSTM
    if 'baseline' in args.models:
        config_baseline = Settings()
        config_baseline.use_bytedance_confidence = False  # Disable Phase 1.1
        config_baseline.enable_tta = False  # Disable Phase 1.2
        config_baseline.enable_bilstm_refinement = False  # Disable Phase 1.3

        models['baseline'] = create_transcriber(config_baseline, use_tta=False)

    # Phase 1.1: Confidence filtering enabled
    if 'phase1.1' in args.models:
        config_phase1_1 = Settings()
        config_phase1_1.use_bytedance_confidence = True  # Enable Phase 1.1
        config_phase1_1.enable_tta = False  # Disable Phase 1.2
        config_phase1_1.enable_bilstm_refinement = False  # Disable Phase 1.3

        models['phase1.1_confidence'] = create_transcriber(config_phase1_1, use_tta=False)

    # Phase 1.2: Confidence filtering + TTA
    if 'phase1.2' in args.models:
        config_phase1_2 = Settings()
        config_phase1_2.use_bytedance_confidence = True  # Enable Phase 1.1
        config_phase1_2.enable_tta = True  # Enable Phase 1.2
        config_phase1_2.enable_bilstm_refinement = False  # Disable Phase 1.3

        models['phase1.2_confidence_tta'] = create_transcriber(config_phase1_2, use_tta=True)

    # Phase 1.3: Confidence filtering + BiLSTM refinement
    if 'phase1.3' in args.models:
        config_phase1_3 = Settings()
        config_phase1_3.use_bytedance_confidence = True  # Enable Phase 1.1
        config_phase1_3.enable_tta = False  # Disable Phase 1.2
        config_phase1_3.enable_bilstm_refinement = True  # Enable Phase 1.3

        models['phase1.3_confidence_bilstm'] = create_transcriber(config_phase1_3, use_tta=False)

    # Phase 1.3b: BiLSTM only (no ensemble, no confidence filtering)
    if 'phase1.3b' in args.models:
        config_phase1_3b = Settings()
        config_phase1_3b.use_ensemble_transcription = False  # Disable ensemble (YourMT3+ only)
        config_phase1_3b.use_bytedance_confidence = False  # Disable Phase 1.1
        config_phase1_3b.enable_tta = False  # Disable Phase 1.2
        config_phase1_3b.enable_bilstm_refinement = True  # Enable Phase 1.3

        models['phase1.3b_bilstm_only'] = create_transcriber(config_phase1_3b, use_tta=False)

    # Phase 1.3c: ByteDance + BiLSTM (no ensemble, ByteDance only with BiLSTM refinement)
    if 'phase1.3c' in args.models:
        config_phase1_3c = Settings()
        config_phase1_3c.use_ensemble_transcription = False  # Disable ensemble (ByteDance only)
        config_phase1_3c.use_bytedance_only = True  # Use ByteDance instead of YourMT3+
        config_phase1_3c.use_bytedance_confidence = False  # Disable confidence filtering (not needed for single model)
        config_phase1_3c.enable_tta = False  # Disable Phase 1.2
        config_phase1_3c.enable_bilstm_refinement = True  # Enable Phase 1.3

        models['phase1.3c_bytedance_bilstm'] = create_transcriber(config_phase1_3c, use_tta=False)

    # Phase 1.4: Confidence filtering + TTA + BiLSTM (full pipeline)
    if 'phase1.4' in args.models:
        config_phase1_4 = Settings()
        config_phase1_4.use_bytedance_confidence = True  # Enable Phase 1.1
        config_phase1_4.enable_tta = True  # Enable Phase 1.2
        config_phase1_4.enable_bilstm_refinement = True  # Enable Phase 1.3

        models['phase1.4_confidence_tta_bilstm'] = create_transcriber(config_phase1_4, use_tta=True)

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
