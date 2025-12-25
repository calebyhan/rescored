#!/usr/bin/env python3
"""
Test different Demucs models to find the best source separation.

Usage (from backend directory):
    python scripts/test_demucs_models.py <audio_path>

Example:
    python scripts/test_demucs_models.py /tmp/rescored/temp/test_e2e/audio.wav
"""
import sys
from pathlib import Path
import subprocess
import soundfile as sf
import numpy as np
import tempfile
import shutil


def test_demucs_model(audio_path: Path, model_name: str, stems: str = None):
    """Test a specific Demucs model."""
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print(f"{'='*60}")

    # Create temp directory for this test
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Build command
        cmd = ["demucs", "--model", model_name, "-o", str(temp_path), str(audio_path)]

        if stems:
            cmd.extend(["--two-stems", stems])

        print(f"Command: {' '.join(cmd)}")
        print("Running... (this may take a minute)")

        # Run Demucs
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                print(f"❌ Failed: {result.stderr[:500]}")
                return None

            # Find output directory
            model_output_dir = temp_path / model_name / audio_path.stem

            if not model_output_dir.exists():
                print(f"❌ Output directory not found: {model_output_dir}")
                return None

            # Analyze stems
            print("\nStem Analysis:")
            original_data, sr = sf.read(audio_path)
            original_energy = np.sum(original_data**2)

            stem_energies = {}

            for stem_file in sorted(model_output_dir.glob("*.wav")):
                stem_name = stem_file.stem
                stem_data, _ = sf.read(stem_file)
                stem_energy = np.sum(stem_data**2)
                stem_rms = np.sqrt(np.mean(stem_data**2))

                percentage = (stem_energy / original_energy) * 100
                stem_energies[stem_name] = (stem_energy, stem_rms, percentage)

                print(f"  {stem_name:15s}: {percentage:5.1f}% energy, RMS: {stem_rms:.3f}")

            # Find best stem for piano/melodic content
            # Usually 'other', 'piano', or 'other' in 2-stem
            print("\nBest stem for piano:")

            if 'piano' in stem_energies:
                best_stem = 'piano'
                print(f"  ✓ Dedicated 'piano' stem found")
            elif 'other' in stem_energies:
                best_stem = 'other'
                print(f"  ✓ Using 'other' stem")
            else:
                # Find stem with most energy
                best_stem = max(stem_energies.items(), key=lambda x: x[1][0])[0]
                print(f"  → Using '{best_stem}' (highest energy)")

            energy, rms, percentage = stem_energies[best_stem]
            print(f"  Energy: {percentage:.1f}%, RMS: {rms:.3f}")

            if percentage < 15:
                print(f"  ⚠️  Very low energy - may not work well")
            elif percentage < 25:
                print(f"  ⚠️  Low energy - borderline")
            else:
                print(f"  ✓ Good energy level")

            return {
                'model': model_name,
                'best_stem': best_stem,
                'energy_percentage': percentage,
                'rms': rms,
                'all_stems': stem_energies
            }

        except subprocess.TimeoutExpired:
            print(f"❌ Timeout after 5 minutes")
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_demucs_models.py <audio_path>")
        print("\nExample:")
        print("  python scripts/test_demucs_models.py /tmp/rescored/temp/test_e2e/audio.wav")
        sys.exit(1)

    audio_path = Path(sys.argv[1])

    if not audio_path.exists():
        print(f"Error: Audio file not found: {audio_path}")
        sys.exit(1)

    print("=" * 60)
    print("DEMUCS MODEL COMPARISON")
    print("=" * 60)
    print(f"Audio file: {audio_path}")
    print(f"Duration: ~{sf.info(audio_path).duration:.1f}s")

    # Test different models
    results = []

    # Test 1: Current model (htdemucs 2-stem)
    print("\n\n" + "="*60)
    print("TEST 1: htdemucs (2-stem: other)")
    print("="*60)
    result = test_demucs_model(audio_path, "htdemucs", stems="other")
    if result:
        results.append(result)

    # Test 2: htdemucs_6s (6-stem with dedicated piano)
    print("\n\n" + "="*60)
    print("TEST 2: htdemucs_6s (6-stem with piano)")
    print("="*60)
    result = test_demucs_model(audio_path, "htdemucs_6s")
    if result:
        results.append(result)

    # Test 3: htdemucs full 4-stem
    print("\n\n" + "="*60)
    print("TEST 3: htdemucs (4-stem)")
    print("="*60)
    result = test_demucs_model(audio_path, "htdemucs")
    if result:
        results.append(result)

    # Summary
    print("\n\n" + "="*60)
    print("SUMMARY & RECOMMENDATIONS")
    print("="*60)

    if not results:
        print("No successful tests!")
        sys.exit(1)

    # Sort by energy percentage
    results.sort(key=lambda x: x['energy_percentage'], reverse=True)

    print("\nRanking (by piano/melodic energy):")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['model']:20s} - {result['best_stem']:10s} - "
              f"{result['energy_percentage']:5.1f}% energy, RMS: {result['rms']:.3f}")

    best_result = results[0]
    print(f"\n✓ RECOMMENDED: Use {best_result['model']} with '{best_result['best_stem']}' stem")

    if best_result['energy_percentage'] < 20:
        print("\n⚠️  WARNING: Even the best model has low energy (<20%)")
        print("   This suggests:")
        print("   - The audio may not have much piano/melodic content")
        print("   - The piano may be heavily mixed with other instruments")
        print("   - You may need to try a different test video")

    print("\nTo update pipeline.py:")
    if best_result['model'] == 'htdemucs_6s':
        print(f"  1. Change line ~98: --two-stems=other → remove this flag")
        print(f"  2. Change line ~96: demucs_output / 'htdemucs_6s' / audio_path.stem")
        print(f"  3. Use stem: {best_result['best_stem']}.wav")
    elif best_result['model'] == 'htdemucs' and '--two-stems' not in str(best_result):
        print(f"  1. Change line ~98: --two-stems=other → remove this flag")
        print(f"  2. Use stem: {best_result['best_stem']}.wav")

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
