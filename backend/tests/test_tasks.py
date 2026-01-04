"""Tests for Celery tasks."""
import pytest
from unittest.mock import patch, MagicMock, call
import json


class TestProcessTranscriptionTask:
    """Test the main Celery transcription task."""

    @patch('tasks.shutil.copy')
    @patch('tasks.TranscriptionPipeline')
    @patch('tasks.redis_client')
    def test_task_success(self, mock_redis, mock_pipeline_class, mock_copy, sample_job_id, temp_storage_dir):
        """Test successful task execution."""
        from tasks import process_transcription_task

        # Mock job data in Redis - all string values
        job_data = {
            'job_id': str(sample_job_id),
            'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'video_id': 'dQw4w9WgXcQ',
            'options': '{"instruments": ["piano"]}'
        }
        mock_redis.hgetall.return_value = job_data

        # Ensure pipeline method returns None
        mock_redis.pipeline.return_value.__enter__.return_value = mock_redis

        # Create actual files so they exist
        (temp_storage_dir / "output.musicxml").write_text("<?xml version='1.0'?><score-partwise></score-partwise>")
        (temp_storage_dir / "output.mid").write_bytes(b"MThd")

        # Mock successful pipeline instance
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = str(temp_storage_dir / "output.musicxml")
        mock_pipeline.final_midi_path = temp_storage_dir / "output.mid"
        mock_pipeline.metadata = {
            "tempo": 120.0,
            "time_signature": {"numerator": 4, "denominator": 4},
            "key_signature": "C"
        }
        mock_pipeline_class.return_value = mock_pipeline

        # Execute task
        process_transcription_task(sample_job_id)

        # Verify pipeline ran
        mock_pipeline.run.assert_called_once()

        # Verify progress updates were published
        assert mock_redis.publish.call_count > 0

        # Verify final status was set to completed
        completed_calls = [
            call for call in mock_redis.hset.call_args_list
            if 'completed' in str(call)
        ]
        assert len(completed_calls) > 0

    @patch('tasks.shutil.copy')
    @patch('tasks.TranscriptionPipeline')
    @patch('tasks.redis_client')
    def test_task_failure(self, mock_redis, mock_pipeline_class, mock_copy, sample_job_id):
        """Test task execution with pipeline failure."""
        from tasks import process_transcription_task
        from celery.exceptions import Retry

        job_data = {
            'job_id': sample_job_id,
            'youtube_url': 'https://www.youtube.com/watch?v=invalid',
            'video_id': 'invalid',
            'options': '{}'
        }
        mock_redis.hgetall.return_value = job_data

        # Mock failed pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = RuntimeError("Download failed")
        mock_pipeline_class.return_value = mock_pipeline

        # Execute task - should raise Retry due to Celery's retry mechanism
        with pytest.raises((Retry, RuntimeError)):
            process_transcription_task(sample_job_id)

        # Verify error was stored in Redis before retry
        error_calls = [
            call for call in mock_redis.hset.call_args_list
            if 'error' in str(call)
        ]
        assert len(error_calls) > 0

    @patch('tasks.shutil.copy')
    @patch('tasks.TranscriptionPipeline')
    @patch('tasks.redis_client')
    def test_task_progress_updates(self, mock_redis, mock_pipeline_class, mock_copy, sample_job_id, temp_storage_dir):
        """Test that task publishes progress updates."""
        from tasks import process_transcription_task

        job_data = {
            'job_id': str(sample_job_id),
            'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'video_id': 'dQw4w9WgXcQ',
            'options': '{}'
        }
        mock_redis.hgetall.return_value = job_data

        # Create actual files so they exist
        (temp_storage_dir / "output.musicxml").write_text("<?xml version='1.0'?><score-partwise></score-partwise>")
        (temp_storage_dir / "output.mid").write_bytes(b"MThd")

        # Ensure pipeline method returns None
        mock_redis.pipeline.return_value.__enter__.return_value = mock_redis

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = str(temp_storage_dir / "output.musicxml")
        mock_pipeline.final_midi_path = temp_storage_dir / "output.mid"
        mock_pipeline.metadata = {
            "tempo": 120.0,
            "time_signature": {"numerator": 4, "denominator": 4},
            "key_signature": "C"
        }
        mock_pipeline_class.return_value = mock_pipeline

        process_transcription_task(sample_job_id)

        # Verify completion message was published
        publish_calls = mock_redis.publish.call_args_list
        assert len(publish_calls) >= 1  # At least completion message

        # Verify final publish call contains completion info
        final_call = publish_calls[-1]
        channel, message = final_call[0]
        assert channel == f"job:{sample_job_id}:updates"
        update_data = json.loads(message)
        assert 'type' in update_data
        assert update_data['type'] == 'completed'

    @patch('tasks.redis_client')
    def test_task_job_not_found(self, mock_redis, sample_job_id):
        """Test task execution when job doesn't exist."""
        from tasks import process_transcription_task

        mock_redis.hgetall.return_value = {}

        with pytest.raises(ValueError) as exc_info:
            process_transcription_task(sample_job_id)

        assert "Job not found" in str(exc_info.value)

    @patch('tasks.shutil.copy')
    @patch('tasks.TranscriptionPipeline')
    @patch('tasks.redis_client')
    def test_task_retry_on_network_error(self, mock_redis, mock_pipeline_class, mock_copy, sample_job_id):
        """Test task retry logic for transient errors."""
        from tasks import process_transcription_task
        from celery.exceptions import Retry

        job_data = {
            'job_id': sample_job_id,
            'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'video_id': 'dQw4w9WgXcQ',
            'options': '{}'
        }
        mock_redis.hgetall.return_value = job_data

        # Mock transient network error
        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = ConnectionError("Network timeout")
        mock_pipeline_class.return_value = mock_pipeline

        with pytest.raises((Retry, ConnectionError)):
            process_transcription_task(sample_job_id)


class TestProgressCallback:
    """Test progress callback functionality."""

    @patch('tasks.redis_client')
    def test_update_progress(self, mock_redis, sample_job_id):
        """Test progress update function."""
        from tasks import update_progress

        update_progress(sample_job_id, 50, "transcription", "Transcribing audio...")

        # Verify Redis was updated
        mock_redis.hset.assert_called()
        call_args = mock_redis.hset.call_args[0]
        assert call_args[0] == f"job:{sample_job_id}"

        # Verify WebSocket message was published
        mock_redis.publish.assert_called()
        channel, message = mock_redis.publish.call_args[0]
        assert channel == f"job:{sample_job_id}:updates"

        update_data = json.loads(message)
        assert update_data['progress'] == 50
        assert update_data['stage'] == "transcription"
        assert update_data['message'] == "Transcribing audio..."

    @patch('tasks.redis_client')
    def test_multiple_progress_updates(self, mock_redis, sample_job_id):
        """Test sequence of progress updates."""
        from tasks import update_progress

        stages = [
            (5, "download", "Downloading audio"),
            (25, "separation", "Separating audio sources"),
            (60, "transcription", "Transcribing to MIDI"),
            (90, "musicxml", "Generating MusicXML"),
            (100, "completed", "Processing complete")
        ]

        for progress, stage, message in stages:
            update_progress(sample_job_id, progress, stage, message)

        # Should have 5 updates
        assert mock_redis.hset.call_count == 5
        assert mock_redis.publish.call_count == 5


class TestCleanup:
    """Test cleanup of temporary files."""

    @patch('tasks.shutil.rmtree')
    def test_cleanup_temp_files(self, mock_rmtree, sample_job_id, temp_storage_dir):
        """Test cleanup of temporary files after job completion."""
        from tasks import cleanup_temp_files

        # Create the temp directory so cleanup will attempt to remove it
        temp_dir = temp_storage_dir / "temp" / sample_job_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        cleanup_temp_files(sample_job_id, storage_path=temp_storage_dir)

        # Verify temp directory was removed
        mock_rmtree.assert_called()

    def test_cleanup_preserves_output(self, sample_job_id, temp_storage_dir):
        """Test that cleanup preserves final output files."""
        from tasks import cleanup_temp_files

        # Create a temp directory with files
        temp_dir = temp_storage_dir / "temp" / sample_job_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Create temp files
        (temp_dir / "temp_audio.wav").touch()
        (temp_dir / "temp_midi.mid").touch()

        # Create output files
        outputs_dir = temp_storage_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        output_files = [
            outputs_dir / "output.musicxml",
            outputs_dir / "output.mid"
        ]

        for f in output_files:
            f.touch()

        # Run cleanup
        cleanup_temp_files(sample_job_id, storage_path=temp_storage_dir)

        # Verify temp directory was removed
        assert not temp_dir.exists()
        
        # Verify output files still exist
        for f in output_files:
            assert f.exists()
