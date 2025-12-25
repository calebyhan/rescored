# Backend Testing Guide

Comprehensive guide for testing the Rescored backend.

## Table of Contents

- [Setup](#setup)
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Writing Tests](#writing-tests)
- [Testing Patterns](#testing-patterns)
- [Troubleshooting](#troubleshooting)

## Setup

### Install Test Dependencies

```bash
cd backend
pip install -r requirements-test.txt
```

This installs:
- `pytest`: Test framework
- `pytest-asyncio`: Async test support
- `pytest-cov`: Coverage reporting
- `pytest-mock`: Enhanced mocking
- `httpx`: HTTP testing client

### Configuration

Test configuration is in `pytest.ini`:

```ini
[pytest]
testpaths = tests
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow-running tests
    gpu: Tests requiring GPU
    network: Tests requiring network
```

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific file
pytest tests/test_utils.py

# Run specific test
pytest tests/test_utils.py::TestValidateYouTubeURL::test_valid_watch_url

# Run by marker
pytest -m unit
pytest -m "unit and not slow"
```

### Watch Mode

Use `pytest-watch` for continuous testing:

```bash
pip install pytest-watch
ptw  # Runs tests on file changes
```

### Coverage Reports

```bash
# Terminal report
pytest --cov --cov-report=term-missing

# HTML report
pytest --cov --cov-report=html
open htmlcov/index.html

# Both
pytest --cov --cov-report=term-missing --cov-report=html
```

## Test Structure

### Test Files

Each module has a corresponding test file:

- `utils.py` → `tests/test_utils.py`
- `pipeline.py` → `tests/test_pipeline.py`
- `main.py` → `tests/test_api.py`
- `tasks.py` → `tests/test_tasks.py`

### Test Organization

Group related tests in classes:

```python
class TestValidateYouTubeURL:
    """Test YouTube URL validation."""

    def test_valid_watch_url(self):
        """Test standard youtube.com/watch URL."""
        is_valid, video_id = validate_youtube_url("https://www.youtube.com/watch?v=...")
        assert is_valid is True
        assert video_id == "..."

    def test_invalid_domain(self):
        """Test URL from wrong domain."""
        is_valid, error = validate_youtube_url("https://vimeo.com/12345")
        assert is_valid is False
```

## Writing Tests

### Basic Test Template

```python
import pytest
from module_name import function_to_test

class TestFunctionName:
    """Test suite for function_name."""

    def test_happy_path(self):
        """Test normal successful execution."""
        result = function_to_test(valid_input)
        assert result == expected_output

    def test_edge_case(self):
        """Test boundary condition."""
        result = function_to_test(edge_case_input)
        assert result == expected_edge_output

    def test_error_handling(self):
        """Test error is raised for invalid input."""
        with pytest.raises(ValueError) as exc_info:
            function_to_test(invalid_input)
        assert "expected error message" in str(exc_info.value)
```

### Using Fixtures

Fixtures provide reusable test data:

```python
@pytest.fixture
def sample_audio_file(temp_storage_dir):
    """Create a sample WAV file for testing."""
    import numpy as np
    import soundfile as sf

    sample_rate = 44100
    duration = 1.0
    samples = np.zeros(int(sample_rate * duration), dtype=np.float32)

    audio_path = temp_storage_dir / "test_audio.wav"
    sf.write(str(audio_path), samples, sample_rate)

    return audio_path

def test_using_fixture(sample_audio_file):
    """Test that uses the fixture."""
    assert sample_audio_file.exists()
    assert sample_audio_file.suffix == ".wav"
```

### Mocking External Dependencies

#### Mock yt-dlp

```python
from unittest.mock import patch, MagicMock

@patch('pipeline.yt_dlp.YoutubeDL')
def test_download_audio(mock_ydl_class, temp_storage_dir):
    """Test audio download with mocked yt-dlp."""
    mock_ydl = MagicMock()
    mock_ydl_class.return_value.__enter__.return_value = mock_ydl

    result = download_audio("https://youtube.com/watch?v=...", temp_storage_dir)

    assert result.exists()
    mock_ydl.download.assert_called_once()
```

#### Mock Redis

```python
@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = MagicMock(spec=Redis)
    redis_mock.ping.return_value = True
    redis_mock.hgetall.return_value = {}
    return redis_mock

def test_with_redis(mock_redis):
    """Test function that uses Redis."""
    # Redis is mocked, no real connection needed
    mock_redis.hset("key", "field", "value")
    assert mock_redis.hset.called
```

#### Mock ML Models

```python
@patch('pipeline.basic_pitch.inference.predict')
def test_transcribe_audio(mock_predict, sample_audio_file, temp_storage_dir):
    """Test transcription with mocked ML model."""
    # Mock model output
    mock_predict.return_value = (
        np.zeros((100, 88)),  # note activations
        np.zeros((100, 88)),  # onsets
        np.zeros((100, 1))    # contours
    )

    result = transcribe_audio(sample_audio_file, temp_storage_dir)

    assert result.exists()
    assert result.suffix == ".mid"
```

## Testing Patterns

### Testing API Endpoints

```python
from fastapi.testclient import TestClient

def test_submit_transcription(test_client, mock_redis):
    """Test transcription submission endpoint."""
    response = test_client.post(
        "/api/v1/transcribe",
        json={"youtube_url": "https://www.youtube.com/watch?v=..."}
    )

    assert response.status_code == 201
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
```

### Testing Async Functions

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_operation()
    assert result == expected_value
```

### Testing WebSocket Connections

```python
def test_websocket(test_client, sample_job_id):
    """Test WebSocket connection."""
    with test_client.websocket_connect(f"/api/v1/jobs/{sample_job_id}/stream") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "progress"
        assert "job_id" in data
```

### Testing Error Scenarios

```python
def test_video_too_long(test_client):
    """Test error handling for videos exceeding duration limit."""
    with patch('utils.check_video_availability') as mock_check:
        mock_check.return_value = {
            'available': False,
            'reason': 'Video too long (max 15 minutes)'
        }

        response = test_client.post(
            "/api/v1/transcribe",
            json={"youtube_url": "https://www.youtube.com/watch?v=long"}
        )

        assert response.status_code == 422
        assert "too long" in response.json()["detail"]
```

### Testing Retries

```python
def test_retry_on_network_error():
    """Test that function retries on network error."""
    mock_func = MagicMock()
    mock_func.side_effect = [
        ConnectionError("Network timeout"),  # First call fails
        ConnectionError("Network timeout"),  # Second call fails
        {"success": True}                     # Third call succeeds
    ]

    # Function should retry and eventually succeed
    result = function_with_retry(mock_func)
    assert result == {"success": True}
    assert mock_func.call_count == 3
```

### Parametrized Tests

Test multiple inputs efficiently:

```python
@pytest.mark.parametrize("url,expected_valid,expected_id", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True, "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", True, "dQw4w9WgXcQ"),
    ("https://vimeo.com/12345", False, None),
    ("not-a-url", False, None),
])
def test_url_validation(url, expected_valid, expected_id):
    """Test URL validation with multiple inputs."""
    is_valid, result = validate_youtube_url(url)
    assert is_valid == expected_valid
    if expected_valid:
        assert result == expected_id
```

## Testing Pipeline Stages

### Audio Download

```python
@patch('pipeline.yt_dlp.YoutubeDL')
def test_download_audio_success(mock_ydl_class, temp_storage_dir):
    """Test successful audio download."""
    mock_ydl = MagicMock()
    mock_ydl_class.return_value.__enter__.return_value = mock_ydl

    result = download_audio("https://youtube.com/watch?v=...", temp_storage_dir)

    assert result.exists()
    assert result.suffix == ".wav"
```

### Source Separation

```python
@patch('pipeline.demucs.separate.main')
def test_separate_sources(mock_demucs, sample_audio_file, temp_storage_dir):
    """Test source separation."""
    # Create mock output files
    stems_dir = temp_storage_dir / "htdemucs" / "test_audio"
    stems_dir.mkdir(parents=True)
    for stem in ["drums", "bass", "vocals", "other"]:
        (stems_dir / f"{stem}.wav").touch()

    result = separate_sources(sample_audio_file, temp_storage_dir)

    assert all(stem in result for stem in ["drums", "bass", "vocals", "other"])
    assert all(path.exists() for path in result.values())
```

### Transcription

```python
@patch('pipeline.basic_pitch.inference.predict')
def test_transcribe_audio(mock_predict, sample_audio_file, temp_storage_dir):
    """Test audio transcription."""
    mock_predict.return_value = (
        np.random.rand(100, 88),
        np.random.rand(100, 88),
        np.random.rand(100, 1)
    )

    result = transcribe_audio(sample_audio_file, temp_storage_dir)

    assert result.exists()
    assert result.suffix == ".mid"
```

### MusicXML Generation

```python
@patch('pipeline.music21.converter.parse')
def test_generate_musicxml(mock_parse, sample_midi_file, temp_storage_dir):
    """Test MusicXML generation."""
    mock_score = MagicMock()
    mock_parse.return_value = mock_score

    result = generate_musicxml(sample_midi_file, temp_storage_dir)

    assert result.exists()
    assert result.suffix == ".musicxml"
    mock_score.write.assert_called_once()
```

## Troubleshooting

### Common Issues

**Import Errors**

```bash
# Ensure backend directory is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

**Redis Connection Errors**

```python
# Always mock Redis in tests unless testing Redis specifically
@pytest.fixture(autouse=True)
def mock_redis():
    with patch('main.redis_client') as mock:
        yield mock
```

**File Permission Errors**

```python
# Always use temp directories
@pytest.fixture
def temp_storage_dir():
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)
```

**GPU Not Available**

```python
# Mark GPU tests and skip if unavailable
@pytest.mark.gpu
@pytest.mark.skipif(not torch.cuda.is_available(), reason="GPU not available")
def test_gpu_processing():
    ...
```

### Debugging Failed Tests

```bash
# Show print statements
pytest -s

# Verbose output
pytest -vv

# Drop into debugger on failure
pytest --pdb

# Run only failed tests
pytest --lf
```

### Performance Issues

```bash
# Identify slow tests
pytest --durations=10

# Run tests in parallel
pytest -n auto  # Requires pytest-xdist
```

## Best Practices

1. **Mock external dependencies**: Don't make real API calls, network requests, or ML inferences
2. **Use fixtures**: Share common setup code across tests
3. **Test edge cases**: Empty inputs, None values, boundary conditions
4. **Clean up resources**: Always clean up temp files, connections
5. **Keep tests independent**: Tests should not depend on each other
6. **Write descriptive names**: Test names should explain what they verify
7. **Test one thing**: Each test should verify one specific behavior
8. **Use markers**: Tag tests by type (unit, integration, slow, gpu)

## Example Test File

Complete example showing best practices:

```python
"""Tests for audio processing pipeline."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
from pipeline import download_audio, separate_sources, transcribe_audio


class TestAudioDownload:
    """Test audio download stage."""

    @patch('pipeline.yt_dlp.YoutubeDL')
    def test_success(self, mock_ydl_class, temp_storage_dir):
        """Test successful audio download."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = download_audio("https://youtube.com/watch?v=test", temp_storage_dir)

        assert result.exists()
        assert result.suffix == ".wav"
        mock_ydl.download.assert_called_once()

    @patch('pipeline.yt_dlp.YoutubeDL')
    def test_network_error(self, mock_ydl_class, temp_storage_dir):
        """Test handling of network error."""
        import yt_dlp
        mock_ydl = MagicMock()
        mock_ydl.download.side_effect = yt_dlp.utils.DownloadError("Network error")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        with pytest.raises(Exception) as exc_info:
            download_audio("https://youtube.com/watch?v=test", temp_storage_dir)

        assert "Network error" in str(exc_info.value)
```
