"""Pytest configuration and fixtures for backend tests."""
import pytest
from pathlib import Path
import tempfile
import shutil
from fastapi.testclient import TestClient
from redis import Redis
from unittest.mock import MagicMock, patch
import uuid


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = MagicMock(spec=Redis)
    redis_mock.ping.return_value = True
    redis_mock.hgetall.return_value = {}
    redis_mock.hset.return_value = True
    redis_mock.pubsub.return_value.subscribe.return_value = None
    return redis_mock


@pytest.fixture
def test_client(mock_redis, temp_storage_dir):
    """Create FastAPI test client with mocked dependencies."""
    with patch('main.redis_client', mock_redis):
        with patch('app_config.settings.storage_path', temp_storage_dir):
            from main import app
            client = TestClient(app)
            yield client


@pytest.fixture
def sample_job_id():
    """Generate a sample job ID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_job_data(sample_job_id):
    """Sample job data for testing."""
    return {
        "job_id": sample_job_id,
        "status": "queued",
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "video_id": "dQw4w9WgXcQ",
        "options": '{"instruments": ["piano"]}',
        "created_at": "2025-01-01T00:00:00",
        "progress": 0,
        "current_stage": "queued",
        "status_message": "Job queued for processing",
    }


@pytest.fixture
def sample_youtube_urls():
    """Collection of sample YouTube URLs for testing."""
    return {
        "valid": [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        ],
        "invalid": [
            "https://example.com/video",
            "not-a-url",
            "https://vimeo.com/12345",
            "https://youtube.com/invalid",
        ]
    }


@pytest.fixture
def mock_yt_dlp_info():
    """Mock yt-dlp video info."""
    return {
        'id': 'dQw4w9WgXcQ',
        'title': 'Test Video',
        'duration': 180,  # 3 minutes
        'age_limit': 0,
        'formats': [
            {'format_id': '140', 'ext': 'wav', 'abr': 128}
        ]
    }


@pytest.fixture
def sample_audio_file(temp_storage_dir):
    """Create a sample WAV file for testing."""
    import numpy as np
    import soundfile as sf

    # Generate 1 second of silence at 44.1kHz
    sample_rate = 44100
    duration = 1.0
    samples = np.zeros(int(sample_rate * duration), dtype=np.float32)

    audio_path = temp_storage_dir / "test_audio.wav"
    sf.write(str(audio_path), samples, sample_rate)

    return audio_path


@pytest.fixture
def sample_midi_file(temp_storage_dir):
    """Create a sample MIDI file for testing."""
    import mido

    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Add some notes (middle C for 1 beat)
    track.append(mido.Message('note_on', note=60, velocity=64, time=0))
    track.append(mido.Message('note_off', note=60, velocity=64, time=480))

    midi_path = temp_storage_dir / "test_midi.mid"
    mid.save(str(midi_path))

    return midi_path


@pytest.fixture
def sample_musicxml_content():
    """Sample MusicXML content for testing."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1">
      <part-name>Piano</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key>
          <fifths>0</fifths>
        </key>
        <time>
          <beats>4</beats>
          <beat-type>4</beat-type>
        </time>
        <clef>
          <sign>G</sign>
          <line>2</line>
        </clef>
      </attributes>
      <note>
        <pitch>
          <step>C</step>
          <octave>4</octave>
        </pitch>
        <duration>4</duration>
        <type>whole</type>
      </note>
    </measure>
  </part>
</score-partwise>'''
