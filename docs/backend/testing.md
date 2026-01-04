# Backend Testing Guide

## Overview

The backend test suite ensures the reliability of the audio processing pipeline, API endpoints, Celery tasks, and utility functions. All tests are written using pytest and can be run locally or in CI/CD pipelines.

## Test Structure

```
backend/tests/
├── conftest.py              # Shared fixtures and test configuration
├── test_api.py             # API endpoint tests (21 tests)
├── test_pipeline.py        # Pipeline component tests (14 tests)
├── test_tasks.py           # Celery task tests (9 tests)
└── test_utils.py           # Utility function tests (15 tests)
```

**Total: 59 tests, 27% code coverage**

## Running Tests

### Quick Start

```bash
cd backend
source .venv/bin/activate

# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_api.py

# Run specific test
pytest tests/test_api.py::TestRootEndpoint::test_root

# Run with verbose output
pytest -v

# Run with short traceback on failures
pytest --tb=short
```

### Test Categories

**API Tests** (`test_api.py`):
- Root endpoint
- Health check (Redis connectivity)
- Transcription submission (validation, rate limiting)
- Job status queries
- Score/MIDI downloads

**Pipeline Tests** (`test_pipeline.py`):
- Function imports and callability
- Pipeline class instantiation
- Required method availability
- Progress callback functionality

**Task Tests** (`test_tasks.py`):
- Celery task execution
- Progress updates
- Error handling and retries
- Job not found scenarios
- Temp file cleanup

**Utility Tests** (`test_utils.py`):
- YouTube URL validation
- Video availability checks
- Error handling for invalid inputs

## Writing Tests

### Test Fixtures

Common fixtures are defined in `conftest.py`:

```python
# Temporary storage directory
def temp_storage_dir():
    """Create temporary storage directory for tests."""

# Mock Redis client
def mock_redis():
    """Mock Redis client for testing."""

# FastAPI test client
def test_client(mock_redis, temp_storage_dir):
    """Create FastAPI test client with mocked dependencies."""

# Sample job data
def sample_job_id():
    """Generate a sample job ID for testing."""

def sample_job_data(sample_job_id):
    """Sample job data for testing."""

# Sample media files
def sample_audio_file(temp_storage_dir):
    """Create a sample WAV file for testing."""

def sample_midi_file(temp_storage_dir):
    """Create a sample MIDI file for testing."""

def sample_musicxml_content():
    """Sample MusicXML content for testing."""
```

### Example Test

```python
import pytest
from unittest.mock import patch, MagicMock

class TestTranscriptionPipeline:
    """Test the transcription pipeline."""

    @patch('pipeline.TranscriptionPipeline')
    def test_pipeline_runs_successfully(
        self,
        mock_pipeline,
        temp_storage_dir
    ):
        """Test successful pipeline execution."""
        # Setup mock
        mock_instance = MagicMock()
        mock_instance.run.return_value = str(temp_storage_dir / "output.musicxml")
        mock_pipeline.return_value = mock_instance

        # Execute
        result = mock_instance.run()

        # Assert
        assert result.endswith("output.musicxml")
        mock_instance.run.assert_called_once()
```

### Mocking Best Practices

**1. Mock External Dependencies**

Always mock:
- Redis connections
- File system operations (when testing logic, not I/O)
- External API calls (yt-dlp, YourMT3+ service)
- Time-dependent operations

**2. Use Proper Patch Targets**

Patch at the point of import, not the definition:

```python
# CORRECT - patch where it's imported
@patch('main.validate_youtube_url')

# WRONG - patch at definition
@patch('app_utils.validate_youtube_url')
```

**3. Create Real Files for Integration Tests**

When testing file operations, create real temp files:

```python
def test_midi_processing(temp_storage_dir):
    midi_file = temp_storage_dir / "test.mid"
    midi_file.write_bytes(b"MThd...")  # Create real file
    result = process_midi(midi_file)
    assert result.exists()
```

## Test Coverage

Current coverage by module:

| Module | Coverage | Notes |
|--------|----------|-------|
| app_config.py | 92% | Configuration loading |
| app_utils.py | 100% | URL validation, video checks |
| main.py | 55% | API endpoints (some error paths untested) |
| tasks.py | 91% | Celery task execution |
| pipeline.py | 5% | Needs integration tests with real ML models |
| tests/*.py | 100% | Test code itself |

**Note**: Low pipeline.py coverage is expected since it requires ML models and GPU. Integration tests should be run separately with real hardware.

## Continuous Integration

### GitHub Actions Example

```yaml
name: Backend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python 3.10
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run tests
        run: |
          cd backend
          pytest --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml
```

## Common Testing Patterns

### Testing API Endpoints

```python
def test_submit_transcription(test_client, mock_redis):
    """Test transcription submission."""
    response = test_client.post(
        "/api/v1/transcribe",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    )
    assert response.status_code == 201
    assert "job_id" in response.json()
```

### Testing Celery Tasks

```python
@patch('tasks.TranscriptionPipeline')
@patch('tasks.redis_client')
def test_task_execution(mock_redis, mock_pipeline):
    """Test Celery task executes successfully."""
    from tasks import process_transcription_task

    # Setup
    mock_redis.hgetall.return_value = {
        'job_id': 'test-123',
        'youtube_url': 'https://youtube.com/watch?v=test'
    }

    # Execute
    process_transcription_task('test-123')

    # Verify
    assert mock_pipeline.called
```

### Testing File Operations

```python
def test_file_cleanup(temp_storage_dir):
    """Test temporary files are cleaned up."""
    temp_file = temp_storage_dir / "temp.wav"
    temp_file.write_bytes(b"test")

    cleanup_temp_files(temp_storage_dir)

    assert not temp_file.exists()
```

## Troubleshooting Tests

### Common Issues

**1. Import Errors**

```bash
# Make sure you're in the venv
source .venv/bin/activate

# Verify pytest is installed
pytest --version
```

**2. Redis Connection Errors**

Tests mock Redis by default. If you see connection errors:

```python
# Check conftest.py has mock_redis fixture
# Ensure test uses the fixture:
def test_something(mock_redis):  # Add this parameter
    ...
```

**3. File Permission Errors**

Temp directories should be writable:

```python
# Use the temp_storage_dir fixture
def test_something(temp_storage_dir):
    file_path = temp_storage_dir / "test.txt"
    file_path.write_text("content")
```

**4. Async Test Errors**

For async tests, use pytest-asyncio:

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

## Test Performance

**Running all tests**: ~5-10 seconds
- API tests: ~2 seconds
- Pipeline tests: <1 second
- Task tests: ~2 seconds
- Utils tests: <1 second

**Tips for faster tests**:
- Mock expensive operations (ML inference, file I/O)
- Use `pytest -n auto` for parallel execution (requires pytest-xdist)
- Run specific test files during development

## Future Improvements

**Needed Tests**:
1. Integration tests with real YourMT3+ model
2. End-to-end tests with actual YouTube videos
3. Performance benchmarks
4. Load testing for concurrent jobs
5. WebSocket connection tests
6. MIDI quantization edge cases
7. MusicXML generation validation

**Coverage Goals**:
- Increase pipeline.py to 40% (integration tests)
- Increase main.py to 80% (all error paths)
- Add performance regression tests

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
