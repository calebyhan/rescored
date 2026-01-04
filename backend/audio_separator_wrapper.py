"""
Audio Separator Wrapper

Provides a clean interface to audio-separator library for 2-stage source separation:
1. BS-RoFormer: Remove vocals (SOTA vocal/instrumental separation)
2. Demucs: Separate instrumental into piano/guitar/bass/drums/other

Based on: https://github.com/nomadkaraoke/python-audio-separator
"""

from pathlib import Path
from typing import Dict, Optional
import subprocess
import shutil
import sys


class AudioSeparator:
    """
    Wrapper for audio-separator with support for multiple separation strategies.

    Separation strategies:
    1. Two-stage (vocal removal + instrument separation)
    2. Direct piano isolation (Demucs 6-stem)
    3. Legacy Demucs 4-stem (backwards compatibility)
    """

    def __init__(self, model_dir: Optional[Path] = None):
        """
        Initialize audio separator.

        Args:
            model_dir: Directory to store downloaded models (default: ~/.audio-separator/)
        """
        self.model_dir = model_dir or Path.home() / ".audio-separator"
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def separate_vocals(
        self,
        audio_path: Path,
        output_dir: Path,
        model: str = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
    ) -> Dict[str, Path]:
        """
        Separate vocals from instrumental using BS-RoFormer (SOTA).

        Args:
            audio_path: Input audio file
            output_dir: Directory for output stems
            model: BS-RoFormer model to use (default: best quality)

        Returns:
            Dict with keys: 'vocals', 'instrumental'
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use audio-separator CLI - find it relative to Python executable
        python_bin = Path(sys.executable)
        venv_bin = python_bin.parent
        audio_separator_bin = venv_bin / "audio-separator"

        # Fall back to PATH if not in venv
        if not audio_separator_bin.exists():
            audio_separator_bin = shutil.which("audio-separator") or "audio-separator"
        else:
            audio_separator_bin = str(audio_separator_bin)

        # Convert to absolute path for audio-separator
        audio_path_abs = audio_path.resolve()

        cmd = [
            audio_separator_bin,
            str(audio_path_abs),
            "-m", model,
            "--output_dir", str(output_dir.resolve()),
            "--output_format", "WAV"
        ]

        if self.model_dir:
            cmd.extend(["--model_file_dir", str(self.model_dir)])

        result = subprocess.run(cmd, capture_output=True, text=True)

        # Debug: print stdout/stderr to see what happened
        print(f"   [DEBUG] audio-separator return code: {result.returncode}")
        if result.stdout:
            print(f"   [DEBUG] stdout: {result.stdout[-1000:]}")
        if result.stderr:
            print(f"   [DEBUG] stderr: {result.stderr[-1000:]}")

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            raise RuntimeError(f"BS-RoFormer vocal separation failed: {error_msg}")

        # audio-separator creates files with model name appended
        # Pattern: filename_(Vocals)_modelname.wav or filename_(Vocals).wav

        # Check what files were actually created
        if output_dir.exists():
            actual_files = list(output_dir.glob("*.wav"))
            print(f"   [DEBUG] Files created in {output_dir}: {[f.name for f in actual_files]}")

            # Find vocals and instrumental files by pattern matching
            vocals_files = [f for f in actual_files if "Vocal" in f.name]
            instrumental_files = [f for f in actual_files if "Instrumental" in f.name]

            if vocals_files and instrumental_files:
                vocals_path = vocals_files[0]
                instrumental_path = instrumental_files[0]
                print(f"   ✓ Found vocals: {vocals_path.name}")
                print(f"   ✓ Found instrumental: {instrumental_path.name}")
            else:
                raise RuntimeError(f"Could not find output files. Found: {[f.name for f in actual_files]}")
        else:
            raise RuntimeError(f"Output directory {output_dir} does not exist")

        return {
            'vocals': vocals_path,
            'instrumental': instrumental_path
        }

    def separate_instruments_demucs(
        self,
        audio_path: Path,
        output_dir: Path,
        stems: int = 6
    ) -> Dict[str, Path]:
        """
        Separate instrumental audio into individual instruments using Demucs.

        Args:
            audio_path: Input audio file (should be instrumental, vocals already removed)
            output_dir: Directory for output stems
            stems: Number of stems (4 or 6)
                4-stem: vocals, drums, bass, other
                6-stem: vocals, drums, bass, guitar, piano, other

        Returns:
            Dict with stem names as keys and paths as values
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use Demucs directly for instrument separation
        model = "htdemucs_6s" if stems == 6 else "htdemucs"

        # Find demucs binary relative to Python executable
        python_bin = Path(sys.executable)
        venv_bin = python_bin.parent
        demucs_bin = venv_bin / "demucs"

        # Fall back to PATH if not in venv
        if not demucs_bin.exists():
            demucs_bin = shutil.which("demucs") or "demucs"
        else:
            demucs_bin = str(demucs_bin)

        # Convert to absolute path for demucs
        audio_path_abs = audio_path.resolve()

        cmd = [
            demucs_bin,
            "-n", model,
            "-o", str(output_dir.resolve()),
            str(audio_path_abs)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            raise RuntimeError(f"Demucs instrument separation failed: {error_msg}")

        # Demucs creates: output_dir/model_name/audio_stem/*.wav
        demucs_output = output_dir / model / audio_path.stem

        if stems == 6:
            stem_files = {
                'vocals': demucs_output / "vocals.wav",
                'drums': demucs_output / "drums.wav",
                'bass': demucs_output / "bass.wav",
                'guitar': demucs_output / "guitar.wav",
                'piano': demucs_output / "piano.wav",
                'other': demucs_output / "other.wav",
            }
        else:
            stem_files = {
                'vocals': demucs_output / "vocals.wav",
                'drums': demucs_output / "drums.wav",
                'bass': demucs_output / "bass.wav",
                'other': demucs_output / "other.wav",
            }

        # Verify all expected stems exist
        missing = [name for name, path in stem_files.items() if not path.exists()]
        if missing:
            raise RuntimeError(f"Missing expected stems: {missing}")

        return stem_files

    def two_stage_separation(
        self,
        audio_path: Path,
        output_dir: Path,
        instrument_stems: int = 6
    ) -> Dict[str, Path]:
        """
        Two-stage separation for optimal quality:
        1. Remove vocals with BS-RoFormer (SOTA vocal separation)
        2. Separate clean instrumental with Demucs 6-stem (piano, guitar, drums, bass, other)

        Args:
            audio_path: Input audio file
            output_dir: Directory for output stems
            instrument_stems: Number of instrument stems (4 or 6)

        Returns:
            Dict with all stems: vocals, piano, guitar, drums, bass, other
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Stage 1: Remove vocals with BS-RoFormer
        print("   Stage 1: Separating vocals with BS-RoFormer...")
        vocal_dir = output_dir / "stage1_vocals"
        vocal_stems = self.separate_vocals(audio_path, vocal_dir)

        # Stage 2: Separate instrumental with Demucs
        print(f"   Stage 2: Separating instruments with Demucs {instrument_stems}-stem...")
        instrument_dir = output_dir / "stage2_instruments"
        instrument_stems_dict = self.separate_instruments_demucs(
            vocal_stems['instrumental'],
            instrument_dir,
            stems=instrument_stems
        )

        # Combine results (vocals from stage 1, instruments from stage 2)
        all_stems = {
            'vocals': vocal_stems['vocals'],  # From BS-RoFormer (clean)
        }

        # Add all instrument stems except the duplicate vocals stem from Demucs
        for name, path in instrument_stems_dict.items():
            if name != 'vocals':  # Skip Demucs vocals (we have better ones from BS-RoFormer)
                all_stems[name] = path

        print(f"   ✓ 2-stage separation complete: {list(all_stems.keys())}")

        return all_stems


if __name__ == "__main__":
    # Test the separator
    import argparse

    parser = argparse.ArgumentParser(description="Test Audio Separator")
    parser.add_argument("audio_file", type=str, help="Path to audio file")
    parser.add_argument("--output", type=str, default="./output_stems",
                       help="Output directory for stems")
    parser.add_argument("--mode", type=str, default="two-stage",
                       choices=["vocals", "instruments", "two-stage"],
                       help="Separation mode")
    args = parser.parse_args()

    separator = AudioSeparator()
    audio_path = Path(args.audio_file)
    output_dir = Path(args.output)

    if args.mode == "vocals":
        stems = separator.separate_vocals(audio_path, output_dir)
        print(f"Vocal separation complete:")
        for name, path in stems.items():
            print(f"  {name}: {path}")

    elif args.mode == "instruments":
        stems = separator.separate_instruments_demucs(audio_path, output_dir, stems=6)
        print(f"Instrument separation complete:")
        for name, path in stems.items():
            print(f"  {name}: {path}")

    elif args.mode == "two-stage":
        stems = separator.two_stage_separation(audio_path, output_dir, instrument_stems=6)
        print(f"2-stage separation complete:")
        for name, path in stems.items():
            print(f"  {name}: {path}")
