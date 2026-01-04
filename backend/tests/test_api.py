"""Integration tests for FastAPI endpoints."""
import pytest
from unittest.mock import patch, MagicMock
import json


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root(self, test_client):
        """Test root endpoint returns API info."""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Rescored API"
        assert data["version"] == "1.0.0"
        assert data["docs"] == "/docs"


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check_healthy(self, test_client, mock_redis):
        """Test health check when all services are healthy."""
        mock_redis.ping.return_value = True

        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis"] == "healthy"

    def test_health_check_redis_down(self, test_client, mock_redis):
        """Test health check when Redis is down."""
        mock_redis.ping.side_effect = Exception("Connection failed")

        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["redis"] == "unhealthy"


class TestTranscribeEndpoint:
    """Test transcription submission endpoint."""

    @patch('main.process_transcription_task')
    @patch('app_utils.check_video_availability')
    @patch('main.validate_youtube_url')
    def test_submit_valid_transcription(
        self,
        mock_validate,
        mock_check_availability,
        mock_task,
        test_client,
        mock_redis
    ):
        """Test submitting valid transcription request."""
        mock_validate.return_value = (True, "dQw4w9WgXcQ")
        mock_check_availability.return_value = {
            'available': True,
            'info': {'duration': 180}
        }
        mock_task.delay.return_value = MagicMock(id="task-id")

        response = test_client.post(
            "/api/v1/transcribe",
            json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        )

        assert response.status_code == 201
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert "websocket_url" in data
        assert data["estimated_duration_seconds"] == 120

        # Verify Redis was called to store job
        assert mock_redis.hset.called

        # Verify Celery task was queued
        assert mock_task.delay.called

    @patch('main.validate_youtube_url')
    def test_submit_invalid_url(self, mock_validate, test_client):
        """Test submitting invalid YouTube URL."""
        mock_validate.return_value = (False, "Invalid YouTube URL format")

        response = test_client.post(
            "/api/v1/transcribe",
            json={"youtube_url": "https://invalid.com/video"}
        )

        assert response.status_code == 400
        assert "Invalid YouTube URL format" in response.json()["detail"]

    @patch('main.validate_youtube_url')
    @patch('main.check_video_availability')
    def test_submit_unavailable_video(
        self,
        mock_check_availability,
        mock_validate,
        test_client
    ):
        """Test submitting unavailable video."""
        mock_validate.return_value = (True, "dQw4w9WgXcQ")
        mock_check_availability.return_value = {
            'available': False,
            'reason': 'Video too long (max 15 minutes)'
        }

        response = test_client.post(
            "/api/v1/transcribe",
            json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        )

        assert response.status_code == 422
        assert "too long" in response.json()["detail"]

    @patch('main.validate_youtube_url')
    @patch('main.check_video_availability')
    def test_submit_with_options(
        self,
        mock_check_availability,
        mock_validate,
        test_client,
        mock_redis
    ):
        """Test submitting transcription with custom options."""
        mock_validate.return_value = (True, "dQw4w9WgXcQ")
        mock_check_availability.return_value = {'available': True, 'info': {}}

        with patch('main.process_transcription_task') as mock_task:
            response = test_client.post(
                "/api/v1/transcribe",
                json={
                    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "options": {"instruments": ["piano", "guitar"]}
                }
            )

            assert response.status_code == 201


class TestRateLimiting:
    """Test rate limiting middleware."""

    @patch('main.validate_youtube_url')
    @patch('main.check_video_availability')
    @patch('main.process_transcription_task')
    def test_rate_limit_enforced(
        self,
        mock_task,
        mock_check_availability,
        mock_validate,
        test_client,
        mock_redis
    ):
        """Test that rate limit is enforced after 10 requests."""
        mock_validate.return_value = (True, "dQw4w9WgXcQ")
        mock_check_availability.return_value = {'available': True, 'info': {}}
        mock_task.delay.return_value = MagicMock(id="task-id")

        # Mock Redis counter for rate limiting
        mock_redis.get.return_value = "10"  # Already at limit

        response = test_client.post(
            "/api/v1/transcribe",
            json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        )

        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]

    @patch('main.validate_youtube_url')
    @patch('main.check_video_availability')
    @patch('main.process_transcription_task')
    def test_rate_limit_under_limit(
        self,
        mock_task,
        mock_check_availability,
        mock_validate,
        test_client,
        mock_redis
    ):
        """Test that requests under limit succeed."""
        mock_validate.return_value = (True, "dQw4w9WgXcQ")
        mock_check_availability.return_value = {'available': True, 'info': {}}
        mock_task.delay.return_value = MagicMock(id="task-id")

        # Mock Redis counter for rate limiting (under limit)
        mock_redis.get.return_value = "5"  # 5 out of 10

        response = test_client.post(
            "/api/v1/transcribe",
            json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        )

        assert response.status_code == 201  # Request succeeds
        assert mock_redis.pipeline.called  # Counter incremented


class TestJobStatusEndpoint:
    """Test job status endpoint."""

    def test_get_existing_job_status(self, test_client, mock_redis, sample_job_data):
        """Test getting status of existing job."""
        mock_redis.hgetall.return_value = sample_job_data

        response = test_client.get(f"/api/v1/jobs/{sample_job_data['job_id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == sample_job_data["job_id"]
        assert data["status"] == "queued"
        assert data["progress"] == 0
        assert data["current_stage"] == "queued"

    def test_get_nonexistent_job(self, test_client, mock_redis):
        """Test getting status of nonexistent job."""
        mock_redis.hgetall.return_value = {}

        response = test_client.get("/api/v1/jobs/nonexistent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_completed_job_status(self, test_client, mock_redis, sample_job_data):
        """Test getting status of completed job."""
        completed_job = {**sample_job_data, "status": "completed", "progress": 100}
        mock_redis.hgetall.return_value = completed_job

        response = test_client.get(f"/api/v1/jobs/{sample_job_data['job_id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["result_url"] is not None

    def test_get_failed_job_status(self, test_client, mock_redis, sample_job_data):
        """Test getting status of failed job."""
        error_data = {"message": "Transcription failed", "stage": "audio_download"}
        failed_job = {
            **sample_job_data,
            "status": "failed",
            "error": json.dumps(error_data)
        }
        mock_redis.hgetall.return_value = failed_job

        response = test_client.get(f"/api/v1/jobs/{sample_job_data['job_id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] is not None
        assert data["error"]["message"] == "Transcription failed"


class TestScoreDownloadEndpoint:
    """Test score download endpoint."""

    def test_download_completed_score(
        self,
        test_client,
        mock_redis,
        sample_job_data,
        temp_storage_dir,
        sample_musicxml_content
    ):
        """Test downloading a completed score."""
        # Create a real MusicXML file
        score_path = temp_storage_dir / "score.musicxml"
        score_path.write_text(sample_musicxml_content)

        completed_job = {
            **sample_job_data,
            "status": "completed",
            "output_path": str(score_path)
        }
        mock_redis.hgetall.return_value = completed_job

        response = test_client.get(f"/api/v1/scores/{sample_job_data['job_id']}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.recordare.musicxml+xml"
        assert "score-partwise" in response.text

    def test_download_nonexistent_job(self, test_client, mock_redis):
        """Test downloading score for nonexistent job."""
        mock_redis.hgetall.return_value = {}

        response = test_client.get("/api/v1/scores/nonexistent-id")

        assert response.status_code == 404

    def test_download_incomplete_job(self, test_client, mock_redis, sample_job_data):
        """Test downloading score for incomplete job."""
        mock_redis.hgetall.return_value = sample_job_data  # Still queued

        response = test_client.get(f"/api/v1/scores/{sample_job_data['job_id']}")

        assert response.status_code == 404
        assert "not available" in response.json()["detail"]

    def test_download_missing_file(self, test_client, mock_redis, sample_job_data):
        """Test downloading score when file is missing."""
        completed_job = {
            **sample_job_data,
            "status": "completed",
            "output_path": "/nonexistent/path/score.musicxml"
        }
        mock_redis.hgetall.return_value = completed_job

        response = test_client.get(f"/api/v1/scores/{sample_job_data['job_id']}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestMIDIDownloadEndpoint:
    """Test MIDI download endpoint."""

    def test_download_completed_midi(self, test_client, sample_job_id, tmp_path, mock_redis):
        """Test downloading MIDI from completed job."""
        # Create a dummy MIDI file
        midi_file = tmp_path / "test.mid"
        midi_file.write_bytes(b"MIDI_DATA")

        # Set job as completed with MIDI path
        mock_redis.hgetall.return_value = {
            "status": "completed",
            "midi_path": str(midi_file)
        }

        response = test_client.get(f"/api/v1/scores/{sample_job_id}/midi")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/midi"
        assert response.content == b"MIDI_DATA"

    def test_download_nonexistent_job_midi(self, test_client, mock_redis):
        """Test downloading MIDI from nonexistent job."""
        mock_redis.hgetall.return_value = {}

        response = test_client.get("/api/v1/scores/nonexistent/midi")

        assert response.status_code == 404
        assert "not available" in response.json()["detail"]

    def test_download_incomplete_job_midi(self, test_client, sample_job_id, mock_redis):
        """Test downloading MIDI from incomplete job."""
        mock_redis.hgetall.return_value = {"status": "processing"}

        response = test_client.get(f"/api/v1/scores/{sample_job_id}/midi")

        assert response.status_code == 404

    def test_download_missing_midi_file(self, test_client, sample_job_id, mock_redis):
        """Test downloading when MIDI file doesn't exist."""
        mock_redis.hgetall.return_value = {
            "status": "completed",
            "midi_path": "/nonexistent/path.mid"
        }

        response = test_client.get(f"/api/v1/scores/{sample_job_id}/midi")

        assert response.status_code == 404
        assert "file not found" in response.json()["detail"].lower()
