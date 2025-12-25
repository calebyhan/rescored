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
