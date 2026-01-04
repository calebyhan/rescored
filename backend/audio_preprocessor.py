"""
Audio Preprocessing Module

Enhances audio quality before source separation and transcription.

Preprocessing Steps:
1. Spectral denoising - Remove background noise and artifacts
2. Peak normalization - Normalize volume to consistent level
3. High-pass filtering - Remove rumble and DC offset
4. Resampling - Ensure consistent sample rate

Target: +2-5% accuracy improvement on noisy/compressed YouTube audio
"""

from pathlib import Path
from typing import Optional
import numpy as np
import librosa
import soundfile as sf


class AudioPreprocessor:
    """
    Audio preprocessing for improving transcription accuracy.

    Mitigates common issues with YouTube audio:
    - Compression artifacts (lossy codecs)
    - Background noise (ambient, microphone noise)
    - Inconsistent levels (quiet vs loud recordings)
    - Low-frequency rumble (not musical, degrades separation)
    """

    def __init__(
        self,
        enable_denoising: bool = True,
        enable_normalization: bool = True,
        enable_highpass: bool = True,
        target_sample_rate: int = 44100
    ):
        """
        Initialize audio preprocessor.

        Args:
            enable_denoising: Enable spectral denoising
            enable_normalization: Enable peak normalization
            enable_highpass: Enable high-pass filter (remove rumble)
            target_sample_rate: Target sample rate (Hz)
        """
        self.enable_denoising = enable_denoising
        self.enable_normalization = enable_normalization
        self.enable_highpass = enable_highpass
        self.target_sample_rate = target_sample_rate

    def preprocess(
        self,
        audio_path: Path,
        output_dir: Optional[Path] = None
    ) -> Path:
        """
        Preprocess audio file for improved transcription quality.

        Args:
            audio_path: Input audio file
            output_dir: Output directory (default: same as input)

        Returns:
            Path to preprocessed audio file
        """
        if output_dir is None:
            output_dir = audio_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{audio_path.stem}_preprocessed.wav"

        print(f"   Preprocessing audio: {audio_path.name}")

        # Load audio (preserve stereo if present)
        y, sr = librosa.load(str(audio_path), sr=None, mono=False)

        # Handle stereo vs mono
        if y.ndim == 2:
            print(f"   Input: stereo, {sr}Hz")
            is_stereo = True
        else:
            print(f"   Input: mono, {sr}Hz")
            is_stereo = False
            y = np.expand_dims(y, axis=0)  # Make it (1, samples) for uniform processing

        # 1. Spectral denoising
        if self.enable_denoising:
            print(f"   Applying spectral denoising...")
            y = self._denoise(y, sr, is_stereo)

        # 2. Peak normalization
        if self.enable_normalization:
            print(f"   Normalizing volume...")
            y = self._normalize(y)

        # 3. High-pass filter (remove rumble <30Hz)
        if self.enable_highpass:
            print(f"   Applying high-pass filter (30Hz cutoff)...")
            y = self._highpass_filter(y, sr)

        # 4. Resample to target sample rate
        if sr != self.target_sample_rate:
            print(f"   Resampling: {sr}Hz → {self.target_sample_rate}Hz")
            y = self._resample(y, sr, self.target_sample_rate)
            sr = self.target_sample_rate

        # Convert back to mono if input was mono
        if not is_stereo:
            y = y[0]  # Remove channel dimension

        # Save preprocessed audio
        sf.write(output_path, y.T if is_stereo else y, sr)
        print(f"   ✓ Preprocessed audio saved: {output_path.name}")

        return output_path

    def _denoise(self, y: np.ndarray, sr: int, is_stereo: bool) -> np.ndarray:
        """
        Apply spectral denoising using noisereduce library.

        Args:
            y: Audio data (channels, samples)
            sr: Sample rate
            is_stereo: Whether audio is stereo

        Returns:
            Denoised audio
        """
        try:
            import noisereduce as nr
        except ImportError:
            print(f"   ⚠ noisereduce not installed, skipping denoising")
            return y

        # Apply denoising per channel
        y_denoised = np.zeros_like(y)

        for ch in range(y.shape[0]):
            y_denoised[ch] = nr.reduce_noise(
                y=y[ch],
                sr=sr,
                stationary=True,  # Assume noise is stationary (consistent background)
                prop_decrease=0.8  # Aggressiveness (0-1, higher = more aggressive)
            )

        return y_denoised

    def _normalize(self, y: np.ndarray, target_db: float = -1.0) -> np.ndarray:
        """
        Normalize audio to target peak level.

        Args:
            y: Audio data
            target_db: Target peak level in dB (default: -1dB = almost full scale)

        Returns:
            Normalized audio
        """
        # Find peak across all channels
        peak = np.abs(y).max()

        if peak == 0:
            return y  # Avoid division by zero

        # Calculate gain to reach target peak
        target_linear = 10 ** (target_db / 20.0)
        gain = target_linear / peak

        return y * gain

    def _highpass_filter(
        self,
        y: np.ndarray,
        sr: int,
        cutoff_hz: float = 30.0
    ) -> np.ndarray:
        """
        Apply high-pass filter to remove low-frequency rumble.

        Args:
            y: Audio data (channels, samples)
            sr: Sample rate
            cutoff_hz: Cutoff frequency (Hz)

        Returns:
            Filtered audio
        """
        from scipy.signal import butter, sosfilt

        # Design 4th-order Butterworth high-pass filter
        sos = butter(4, cutoff_hz, 'hp', fs=sr, output='sos')

        # Apply per channel
        y_filtered = np.zeros_like(y)

        for ch in range(y.shape[0]):
            y_filtered[ch] = sosfilt(sos, y[ch])

        return y_filtered

    def _resample(
        self,
        y: np.ndarray,
        orig_sr: int,
        target_sr: int
    ) -> np.ndarray:
        """
        Resample audio to target sample rate.

        Args:
            y: Audio data (channels, samples)
            orig_sr: Original sample rate
            target_sr: Target sample rate

        Returns:
            Resampled audio
        """
        y_resampled = np.zeros((y.shape[0], int(y.shape[1] * target_sr / orig_sr)))

        for ch in range(y.shape[0]):
            y_resampled[ch] = librosa.resample(
                y[ch],
                orig_sr=orig_sr,
                target_sr=target_sr
            )

        return y_resampled


if __name__ == "__main__":
    # Test the preprocessor
    import argparse

    parser = argparse.ArgumentParser(description="Test Audio Preprocessor")
    parser.add_argument("audio_file", type=str, help="Path to audio file")
    parser.add_argument("--output", type=str, default="./output_audio",
                       help="Output directory for preprocessed audio")
    parser.add_argument("--no-denoise", action="store_true",
                       help="Disable denoising")
    parser.add_argument("--no-normalize", action="store_true",
                       help="Disable normalization")
    parser.add_argument("--no-highpass", action="store_true",
                       help="Disable high-pass filter")
    args = parser.parse_args()

    preprocessor = AudioPreprocessor(
        enable_denoising=not args.no_denoise,
        enable_normalization=not args.no_normalize,
        enable_highpass=not args.no_highpass
    )

    audio_path = Path(args.audio_file)
    output_dir = Path(args.output)

    # Preprocess
    output_path = preprocessor.preprocess(audio_path, output_dir)
    print(f"\n✓ Preprocessing complete: {output_path}")
