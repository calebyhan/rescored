"""Configuration module for Rescored backend."""
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List
import torch


def _detect_device() -> str:
    """Auto-detect best available device for YourMT3+."""
    if torch.cuda.is_available():
        return "cuda"
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return "mps"
    else:
        return "cpu"


class Settings(BaseSettings):
    """Application settings."""

    # Redis Configuration (uses fakeredis on HF Spaces/development)
    use_fake_redis: bool = False  # Set to False in production with real Redis
    redis_url: str = "redis://localhost:6379/0"

    # Storage Configuration
    storage_path: Path = Path("/tmp/rescored")

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Worker Configuration
    gpu_enabled: bool = True
    max_video_duration: int = 900  # 15 minutes

    # Transcription Configuration (deprecated - kept for API compatibility)
    # These were used by basic-pitch, which has been removed in favor of YourMT3+
    onset_threshold: float = 0.3  # Deprecated
    frame_threshold: float = 0.3  # Deprecated
    minimum_note_length: int = 58  # Deprecated
    minimum_frequency_hz: float = 65.0  # Deprecated
    maximum_frequency_hz: float | None = None  # Deprecated

    # Tempo Detection Configuration
    tempo_detection_duration: int = 60  # Seconds of audio to analyze
    tempo_confidence_threshold: float = 0.5  # Min confidence to use detected tempo

    # Time Signature Detection Configuration
    time_sig_confidence_threshold: float = 0.6  # Min confidence to use detected time sig

    # Key Detection Configuration
    key_confidence_threshold: float = 0.7  # Min confidence to use detected key

    # Note Merging Configuration (DISABLED - basic-pitch handles continuity)
    # note_merge_gap_threshold: int = 150  # REMOVED - merging destroys rhythm

    # Measure Normalization Configuration
    fast_tempo_threshold: int = 140  # BPM threshold for 32nd note quantization

    # Envelope Analysis Configuration
    velocity_decay_threshold: float = 0.7  # Velocity ratio for detecting decay (new/old)
    sustain_artifact_gap_ms: int = 500  # Max gap to consider as sustain tail
    min_velocity_similarity: int = 15  # Min velocity diff for intentional repeat
    irregular_timing_threshold: float = 0.3  # CV threshold for timing irregularity

    # Tempo-Adaptive Thresholds
    slow_tempo_threshold: int = 80  # BPM threshold for slow music
    adaptive_thresholds_enabled: bool = True  # Feature flag

    # Feature Flags
    enable_envelope_analysis: bool = True
    enable_tie_notation: bool = True  # Deprecated (was only used by old generate_musicxml)

    # Phase 2: Zero-Tradeoff Solutions
    # Essentia replaces madmom for numpy 2.x compatibility (professional-grade tempo/beat detection)
    use_essentia_tempo_detection: bool = True  # Use Essentia RhythmExtractor2013 (replaces madmom)
    use_madmom_tempo_detection: bool = False  # DISABLED: madmom incompatible with numpy 2.x
    use_beat_synchronous_quantization: bool = False  # TODO: Implement with Essentia beats

    # Transcription Service Configuration
    use_yourmt3_transcription: bool = True  # Deprecated (always True now - YourMT3+ is only transcriber)
    transcription_service_url: str = "http://localhost:8000"  # Main API URL (YourMT3+ integrated)
    transcription_service_timeout: int = 300  # Timeout for transcription requests (seconds)
    yourmt3_device: str = _detect_device()  # Auto-detect device: 'cuda' (NVIDIA), 'mps' (Apple Silicon), or 'cpu'

    # Source Separation Configuration
    use_two_stage_separation: bool = True  # Use BS-RoFormer + Demucs for better quality (vs Demucs only)
    transcribe_vocals: bool = True  # Transcribe vocal melody as violin
    vocal_instrument: int = 40  # MIDI program number for vocals (40=Violin, 73=Flute, 65=Alto Sax)
    use_6stem_demucs: bool = True  # Use 6-stem Demucs (piano, guitar, drums, bass, other) vs 4-stem

    # Ensemble Transcription Configuration
    use_ensemble_transcription: bool = True  # Use ensemble of YourMT3+ and ByteDance for higher accuracy
    use_bytedance_only: bool = False  # Use ByteDance only (no ensemble, no YourMT3+) - for Phase 1.3c evaluation
    use_yourmt3_ensemble: bool = True  # Include YourMT3+ in ensemble
    use_bytedance_ensemble: bool = True  # Include ByteDance piano transcription in ensemble
    ensemble_voting_strategy: str = "weighted"  # Voting strategy: weighted, intersection, union, majority
    ensemble_onset_tolerance_ms: int = 50  # Time window for matching notes (milliseconds)
    ensemble_confidence_threshold: float = 0.25  # Minimum confidence for weighted voting (lowered to keep more ByteDance low-confidence notes)
    use_asymmetric_thresholds: bool = True  # Use different weights and thresholds per model
    yourmt3_model_weight: float = 0.45  # YourMT3+ weight in ensemble (generalist, no confidence scores)
    bytedance_model_weight: float = 0.55  # ByteDance weight in ensemble (piano specialist, has confidence scores)
    bytedance_min_notes_threshold: int = 50  # Minimum notes for ByteDance to be considered valid (fallback to YourMT3+ only if below)
    bytedance_note_ratio_threshold: float = 0.2  # Minimum ByteDance/YourMT3+ note ratio (warn if catastrophic failure)
    enable_stem_quality_validation: bool = True  # Validate piano stem quality before ByteDance (RMS energy, spectral centroid)

    # Phase 1.1: Enhanced Confidence Filtering
    use_bytedance_confidence: bool = True  # Use ByteDance frame-level confidence scores (onset_roll/offset_roll)
    confidence_aggregation: str = "geometric_mean"  # How to combine onset and offset confidence
    confidence_window_frames: int = 5  # ±2 frames around onset/offset for confidence extraction

    # Phase 1.2: Test-Time Augmentation (TTA)
    enable_tta: bool = False  # OFF by default (user opts in for quality mode - 3-5x slower)
    tta_augmentations: List[str] = ['pitch_shift', 'time_stretch']  # Augmentation types
    tta_pitch_shifts: List[int] = [-1, 0, +1]  # Semitone shifts (0 = original)
    tta_time_stretches: List[float] = [0.95, 1.0, 1.05]  # Time stretch rates (1.0 = original)
    tta_min_votes: int = 2  # Minimum augmentations that must predict a note (reduced from 3)
    tta_onset_tolerance_ms: int = 50  # Time window for matching notes across augmentations

    # Phase 1.3: BiLSTM Refinement
    enable_bilstm_refinement: bool = True  # BiLSTM trained - ready for evaluation
    bilstm_checkpoint_path: Path = Path("refinement/checkpoints/bilstm_best.pt")
    bilstm_fps: int = 100  # Frames per second for piano roll conversion
    bilstm_threshold: float = 0.5  # Onset probability threshold

    # Audio Preprocessing Configuration
    enable_audio_preprocessing: bool = True  # Preprocess audio before separation/transcription
    enable_audio_denoising: bool = True  # Remove background noise and artifacts
    enable_audio_normalization: bool = True  # Normalize volume to consistent level
    enable_highpass_filter: bool = True  # Remove low-frequency rumble (<30Hz)

    # Post-Processing Filters (Phase 4)
    enable_confidence_filtering: bool = False  # Filter low-confidence notes (reduces false positives)
    confidence_threshold: float = 0.3  # Minimum confidence to keep note (0-1)
    velocity_threshold: int = 20  # Minimum velocity to keep note (0-127)
    min_note_duration: float = 0.05  # Minimum note duration in seconds

    enable_key_aware_filtering: bool = False  # Filter isolated out-of-key notes (reduces false positives)
    allow_chromatic_passing_tones: bool = True  # Keep brief chromatic notes (jazz, classical)
    isolation_threshold: float = 0.5  # Time threshold (seconds) to consider note isolated

    # Grand Staff Configuration
    enable_grand_staff: bool = True  # Split piano into treble + bass clefs
    middle_c_split: int = 60  # MIDI note number for staff split (60 = Middle C)

    # Polyphonic Detection Configuration
    polyphonic_range_threshold: int = 24  # Semitone range threshold for polyphonic detection
    note_merge_gap_ms: int = 150  # Max gap (ms) for merging consecutive notes of same pitch
    onset_tolerance_ticks: int = 10  # MIDI ticks tolerance for grouping simultaneous notes

    # MusicXML Generation Configuration
    bucketing_resolution_qn: float = 0.005  # Quarter note resolution for deduplication bucketing
    measure_duration_tolerance_qn: float = 0.15  # Tolerance for measure duration matching
    minimum_note_duration_qn: float = 0.0625  # Minimum note duration (64th note)

    # CORS Configuration
    # Default supports local dev + Vercel + HF Spaces
    # Format: comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173,http://localhost:3000,https://localhost,https://*.vercel.app,https://*.hf.space"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins as list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def temp_audio_path(self) -> Path:
        """Temporary audio storage path."""
        path = self.storage_path / "temp_audio"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def outputs_path(self) -> Path:
        """Output files storage path."""
        path = self.storage_path / "outputs"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
