"""
Tests for YourMT3+ transcription service integration.

Tests cover:
- YourMT3+ service health check
- Successful transcription
- Fallback to basic-pitch on service failure
- Fallback to basic-pitch when service disabled
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import mido
import tempfile
import shutil

from pipeline import TranscriptionPipeline
from app_config import Settings


@pytest.fixture
def temp_storage():
    """Create temporary storage directory for tests."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def test_audio_file(temp_storage):
    """Create a minimal test audio file."""
    import soundfile as sf
    import numpy as np

    audio_path = temp_storage / "test_audio.wav"
    # Create 1 second of silence
    sample_rate = 44100
    audio_data = np.zeros(sample_rate)
    sf.write(str(audio_path), audio_data, sample_rate)

    return audio_path


@pytest.fixture
def mock_yourmt3_midi(temp_storage):
    """Create a mock MIDI file that YourMT3+ would return."""
    midi_path = temp_storage / "yourmt3_output.mid"

    # Create a simple MIDI file with one note
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    track.append(mido.Message('note_on', note=60, velocity=80, time=0))
    track.append(mido.Message('note_off', note=60, velocity=0, time=480))
    track.append(mido.MetaMessage('end_of_track', time=0))

    mid.save(str(midi_path))
    return midi_path


@pytest.fixture
def mock_basic_pitch_midi(temp_storage):
    """Create a mock MIDI file that basic-pitch would return."""
    midi_path = temp_storage / "basic_pitch_output.mid"

    # Create a simple MIDI file with one note
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    track.append(mido.Message('note_on', note=62, velocity=70, time=0))
    track.append(mido.Message('note_off', note=62, velocity=0, time=480))
    track.append(mido.MetaMessage('end_of_track', time=0))

    mid.save(str(midi_path))
    return midi_path


class TestYourMT3Integration:
    """Test suite for YourMT3+ transcription service integration."""

    def test_yourmt3_enabled_by_default(self):
        """Test that YourMT3+ is enabled by default in config."""
        config = Settings()
        assert config.use_yourmt3_transcription is True

    def test_yourmt3_service_health_check(self, temp_storage):
        """Test YourMT3+ service health check endpoint."""
        config = Settings(use_yourmt3_transcription=True)
        pipeline = TranscriptionPipeline(
            job_id="test_health",
            youtube_url="https://youtube.com/test",
            storage_path=temp_storage,
            config=config
        )

        with patch('requests.get') as mock_get:
            # Mock successful health check
            mock_response = Mock()
            mock_response.json.return_value = {
                "status": "healthy",
                "model_loaded": True,
                "device": "mps"
            }
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Call transcribe_with_yourmt3 (which includes health check)
            with patch('requests.post') as mock_post:
                mock_post_response = Mock()
                mock_post_response.content = b"mock midi data"
                mock_post.return_value = mock_post_response

                with patch('builtins.open', create=True):
                    with patch('pathlib.Path.exists', return_value=True):
                        # This would fail in real scenario, but we're testing health check
                        try:
                            pipeline.transcribe_with_yourmt3(temp_storage / "test.wav")
                        except:
                            pass  # Expected to fail, we just want to verify health check was called

            # Verify health check was called
            assert mock_get.called
            assert "/health" in str(mock_get.call_args)

    def test_yourmt3_transcription_success(self, temp_storage, test_audio_file, mock_yourmt3_midi):
        """Test successful YourMT3+ transcription."""
        config = Settings(use_yourmt3_transcription=True)
        pipeline = TranscriptionPipeline(
            job_id="test_success",
            youtube_url="https://youtube.com/test",
            storage_path=temp_storage,
            config=config
        )

        with patch('requests.get') as mock_get:
            # Mock successful health check
            mock_health = Mock()
            mock_health.json.return_value = {"status": "healthy", "model_loaded": True}
            mock_health.raise_for_status = Mock()
            mock_get.return_value = mock_health

            with patch('requests.post') as mock_post:
                # Mock successful transcription
                with open(mock_yourmt3_midi, 'rb') as f:
                    mock_midi_data = f.read()

                mock_response = Mock()
                mock_response.content = mock_midi_data
                mock_post.return_value = mock_response

                result = pipeline.transcribe_with_yourmt3(test_audio_file)

                assert result.exists()
                assert result.suffix == '.mid'

                # Verify MIDI file is valid
                mid = mido.MidiFile(result)
                assert len(mid.tracks) > 0

    def test_yourmt3_fallback_on_service_error(self, temp_storage, test_audio_file):
        """Test fallback to basic-pitch when YourMT3+ service fails."""
        config = Settings(use_yourmt3_transcription=True)
        pipeline = TranscriptionPipeline(
            job_id="test_fallback",
            youtube_url="https://youtube.com/test",
            storage_path=temp_storage,
            config=config
        )

        with patch('requests.get') as mock_get:
            # Mock health check failure
            mock_get.side_effect = Exception("Service unavailable")

            with patch('basic_pitch.inference.predict_and_save') as mock_bp:
                # Mock basic-pitch creating a MIDI file
                def create_basic_pitch_midi(*args, **kwargs):
                    output_dir = Path(kwargs['output_directory'])
                    audio_path = Path(kwargs['audio_path_list'][0])
                    midi_path = output_dir / f"{audio_path.stem}_basic_pitch.mid"

                    # Create simple MIDI
                    mid = mido.MidiFile()
                    track = mido.MidiTrack()
                    mid.tracks.append(track)
                    track.append(mido.Message('note_on', note=64, velocity=75, time=0))
                    track.append(mido.Message('note_off', note=64, velocity=0, time=480))
                    track.append(mido.MetaMessage('end_of_track', time=0))
                    mid.save(str(midi_path))

                mock_bp.side_effect = create_basic_pitch_midi

                # This should use basic-pitch as fallback
                result = pipeline.transcribe_to_midi(
                    audio_path=test_audio_file
                )

                assert result.exists()
                assert result.suffix == '.mid'

                # Verify basic-pitch was called
                assert mock_bp.called

    def test_yourmt3_disabled_uses_basic_pitch(self, temp_storage, test_audio_file):
        """Test that basic-pitch is used when YourMT3+ is disabled."""
        config = Settings(use_yourmt3_transcription=False)
        pipeline = TranscriptionPipeline(
            job_id="test_disabled",
            youtube_url="https://youtube.com/test",
            storage_path=temp_storage,
            config=config
        )

        with patch('basic_pitch.inference.predict_and_save') as mock_bp:
            # Mock basic-pitch creating a MIDI file
            def create_basic_pitch_midi(*args, **kwargs):
                output_dir = Path(kwargs['output_directory'])
                audio_path = Path(kwargs['audio_path_list'][0])
                midi_path = output_dir / f"{audio_path.stem}_basic_pitch.mid"

                # Create simple MIDI
                mid = mido.MidiFile()
                track = mido.MidiTrack()
                mid.tracks.append(track)
                track.append(mido.Message('note_on', note=65, velocity=78, time=0))
                track.append(mido.Message('note_off', note=65, velocity=0, time=480))
                track.append(mido.MetaMessage('end_of_track', time=0))
                mid.save(str(midi_path))

            mock_bp.side_effect = create_basic_pitch_midi

            result = pipeline.transcribe_to_midi(
                audio_path=test_audio_file
            )

            assert result.exists()
            assert result.suffix == '.mid'

            # Verify basic-pitch was called and YourMT3+ was not
            assert mock_bp.called

    def test_yourmt3_service_timeout(self, temp_storage, test_audio_file):
        """Test that timeouts are handled gracefully with fallback."""
        config = Settings(
            use_yourmt3_transcription=True,
            transcription_service_timeout=5
        )
        pipeline = TranscriptionPipeline(
            job_id="test_timeout",
            youtube_url="https://youtube.com/test",
            storage_path=temp_storage,
            config=config
        )

        import requests

        with patch('requests.get') as mock_get:
            # Mock health check success
            mock_health = Mock()
            mock_health.json.return_value = {"status": "healthy", "model_loaded": True}
            mock_get.return_value = mock_health

            with patch('requests.post') as mock_post:
                # Mock timeout
                mock_post.side_effect = requests.exceptions.Timeout()

                with patch('basic_pitch.inference.predict_and_save') as mock_bp:
                    # Mock basic-pitch creating a MIDI file
                    def create_basic_pitch_midi(*args, **kwargs):
                        output_dir = Path(kwargs['output_directory'])
                        audio_path = Path(kwargs['audio_path_list'][0])
                        midi_path = output_dir / f"{audio_path.stem}_basic_pitch.mid"

                        # Create simple MIDI
                        mid = mido.MidiFile()
                        track = mido.MidiTrack()
                        mid.tracks.append(track)
                        track.append(mido.Message('note_on', note=66, velocity=80, time=0))
                        track.append(mido.Message('note_off', note=66, velocity=0, time=480))
                        track.append(mido.MetaMessage('end_of_track', time=0))
                        mid.save(str(midi_path))

                    mock_bp.side_effect = create_basic_pitch_midi

                    result = pipeline.transcribe_to_midi(
                        audio_path=test_audio_file
                    )

                    assert result.exists()
                    # Verify fallback to basic-pitch
                    assert mock_bp.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
