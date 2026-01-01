"""
YourMT3 Transcription Wrapper

This module provides a simplified interface to the YourMT3+ model for
music transcription. It wraps the HuggingFace Spaces implementation
to provide a clean API for transcription services.

Based on: https://huggingface.co/spaces/mimbres/YourMT3
"""

import sys
import os
from pathlib import Path
from typing import Optional

# Add paths for imports
_base_dir = Path(__file__).parent
sys.path.insert(0, str(_base_dir / "ymt" / "yourmt3_core"))  # For model_helper
sys.path.insert(0, str(_base_dir / "ymt" / "yourmt3_core" / "amt" / "src"))  # For model/utils

import torch
import torchaudio

class YourMT3Transcriber:
    """
    Wrapper class for YourMT3+ music transcription model.

    This class handles model loading and provides a simple transcribe() method
    for converting audio files to MIDI.
    """

    def __init__(
        self,
        model_name: str = "YPTF.MoE+Multi (noPS)",
        device: Optional[str] = None,
        checkpoint_dir: Optional[Path] = None
    ):
        """
        Initialize the YourMT3 transcriber.

        Args:
            model_name: Model variant to use. Options:
                - "YMT3+"
                - "YPTF+Single (noPS)"
                - "YPTF+Multi (PS)"
                - "YPTF.MoE+Multi (noPS)" (default, best quality)
                - "YPTF.MoE+Multi (PS)"
            device: Device to run on ('cuda', 'cpu', or None for auto-detect)
            checkpoint_dir: Directory containing model checkpoints
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.checkpoint_dir = checkpoint_dir or Path(__file__).parent / "ymt" / "yourmt3_core" / "logs" / "2024"

        print(f"Initializing YourMT3+ ({model_name}) on {self.device}")
        print(f"Checkpoint dir: {self.checkpoint_dir}")

        # Import after path setup
        try:
            from model_helper import load_model_checkpoint
            self._load_model_checkpoint = load_model_checkpoint
        except ImportError as e:
            raise RuntimeError(
                f"Failed to import YourMT3 model helpers: {e}\n"
                f"Make sure the amt/src directory is properly set up in yourmt3_core/"
            )

        # Load model
        self.model = self._load_model(model_name)

    def _get_model_args(self, model_name: str) -> list:
        """Get command-line arguments for model loading."""
        project = '2024'
        # Use float16 for GPU devices (CUDA/MPS) for better performance and lower memory
        precision = '16' if self.device in ['cuda', 'mps'] else '32'

        if model_name == "YMT3+":
            checkpoint = "notask_all_cross_v6_xk2_amp0811_gm_ext_plus_nops_b72@model.ckpt"
            args = [checkpoint, '-p', project, '-pr', precision]
        elif model_name == "YPTF+Single (noPS)":
            checkpoint = "ptf_all_cross_rebal5_mirst_xk2_edr005_attend_c_full_plus_b100@model.ckpt"
            args = [checkpoint, '-p', project, '-enc', 'perceiver-tf', '-ac', 'spec',
                    '-hop', '300', '-atc', '1', '-pr', precision]
        elif model_name == "YPTF+Multi (PS)":
            checkpoint = "mc13_256_all_cross_v6_xk5_amp0811_edr005_attend_c_full_plus_2psn_nl26_sb_b26r_800k@model.ckpt"
            args = [checkpoint, '-p', project, '-tk', 'mc13_full_plus_256',
                    '-dec', 'multi-t5', '-nl', '26', '-enc', 'perceiver-tf',
                    '-ac', 'spec', '-hop', '300', '-atc', '1', '-pr', precision]
        elif model_name == "YPTF.MoE+Multi (noPS)":
            checkpoint = "mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops@last.ckpt"
            args = [checkpoint, '-p', project, '-tk', 'mc13_full_plus_256', '-dec', 'multi-t5',
                    '-nl', '26', '-enc', 'perceiver-tf', '-sqr', '1', '-ff', 'moe',
                    '-wf', '4', '-nmoe', '8', '-kmoe', '2', '-act', 'silu', '-epe', 'rope',
                    '-rp', '1', '-ac', 'spec', '-hop', '300', '-atc', '1', '-pr', precision]
        elif model_name == "YPTF.MoE+Multi (PS)":
            checkpoint = "mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b80_ps2@model.ckpt"
            args = [checkpoint, '-p', project, '-tk', 'mc13_full_plus_256', '-dec', 'multi-t5',
                    '-nl', '26', '-enc', 'perceiver-tf', '-sqr', '1', '-ff', 'moe',
                    '-wf', '4', '-nmoe', '8', '-kmoe', '2', '-act', 'silu', '-epe', 'rope',
                    '-rp', '1', '-ac', 'spec', '-hop', '300', '-atc', '1', '-pr', precision]
        else:
            raise ValueError(f"Unknown model name: {model_name}")

        return args

    def _load_model(self, model_name: str):
        """Load the YourMT3 model checkpoint."""
        args = self._get_model_args(model_name)

        print(f"Loading model with args: {' '.join(args)}")

        # YourMT3 expects to be run from amt/src directory for checkpoint paths
        # Save current directory and temporarily change to amt/src
        original_cwd = os.getcwd()
        amt_src_dir = _base_dir / "ymt" / "yourmt3_core" / "amt" / "src"

        try:
            os.chdir(str(amt_src_dir))

            # Load on CPU first, then move to target device
            model = self._load_model_checkpoint(args=args, device="cpu")
            model.to(self.device)
            model.eval()
        finally:
            # Always restore original directory
            os.chdir(original_cwd)

        # Enable optimizations for inference
        if hasattr(torch, 'set_float32_matmul_precision'):
            torch.set_float32_matmul_precision('high')  # Use TF32 on Ampere GPUs

        # Disable gradient computation for inference (reduces memory)
        for param in model.parameters():
            param.requires_grad = False

        print(f"Model loaded successfully on {self.device}")
        return model

    def transcribe_audio(self, audio_path: Path, output_dir: Optional[Path] = None) -> Path:
        """
        Transcribe an audio file to MIDI.

        Args:
            audio_path: Path to input audio file (WAV, MP3, etc.)
            output_dir: Directory to save MIDI output (default: current directory)

        Returns:
            Path to the generated MIDI file

        Raises:
            FileNotFoundError: If audio_path doesn't exist
            RuntimeError: If transcription fails
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        output_dir = Path(output_dir) if output_dir else Path("./")
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Transcribing: {audio_path}")

        try:
            # Import transcribe function
            from model_helper import transcribe

            # Prepare audio info dict (as expected by transcribe function)
            audio_info = {
                'filepath': str(audio_path),
                'track_name': audio_path.stem
            }

            # Run transcription
            midi_path = transcribe(self.model, audio_info)
            midi_path = Path(midi_path)

            # Move to output directory if needed
            if midi_path.parent != output_dir:
                final_path = output_dir / midi_path.name
                midi_path.rename(final_path)
                midi_path = final_path

            print(f"Transcription complete: {midi_path}")
            return midi_path

        except Exception as e:
            raise RuntimeError(f"Transcription failed: {e}")


if __name__ == "__main__":
    # Test the transcriber
    import argparse

    parser = argparse.ArgumentParser(description="Test YourMT3 Transcriber")
    parser.add_argument("audio_file", type=str, help="Path to audio file")
    parser.add_argument("--model", type=str, default="YPTF.MoE+Multi (noPS)",
                       help="Model variant to use")
    parser.add_argument("--output", type=str, default="./output",
                       help="Output directory for MIDI files")
    args = parser.parse_args()

    # Initialize transcriber
    transcriber = YourMT3Transcriber(model_name=args.model)

    # Transcribe audio
    midi_path = transcriber.transcribe_audio(
        audio_path=Path(args.audio_file),
        output_dir=Path(args.output)
    )

    print(f"MIDI saved to: {midi_path}")
