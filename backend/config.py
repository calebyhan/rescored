"""Configuration module for Rescored backend."""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings."""

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"

    # Storage Configuration
    storage_path: Path = Path("/tmp/rescored")

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Worker Configuration
    gpu_enabled: bool = True
    max_video_duration: int = 900  # 15 minutes

    # Transcription Configuration (basic-pitch)
    onset_threshold: float = 0.3  # Note onset confidence (0-1). Lower = more notes detected, better for soft piano
    frame_threshold: float = 0.3  # Frame activation threshold (0-1)
    minimum_note_length: int = 127  # Minimum note samples (~58ms at 44.1kHz)

    # Tempo Detection Configuration
    tempo_detection_duration: int = 60  # Seconds of audio to analyze
    tempo_confidence_threshold: float = 0.5  # Min confidence to use detected tempo

    # Time Signature Detection Configuration
    time_sig_confidence_threshold: float = 0.6  # Min confidence to use detected time sig

    # Key Detection Configuration
    key_confidence_threshold: float = 0.7  # Min confidence to use detected key

    # Note Merging Configuration
    note_merge_gap_threshold: int = 150  # Max gap in ms to merge consecutive notes (increased to catch quantized gaps)

    # Measure Normalization Configuration
    fast_tempo_threshold: int = 140  # BPM threshold for 32nd note quantization

    # Grand Staff Configuration
    enable_grand_staff: bool = True  # Split piano into treble + bass clefs
    middle_c_split: int = 60  # MIDI note number for staff split (60 = Middle C)

    # CORS Configuration
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

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
