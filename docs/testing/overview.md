# Testing Guide

Complete testing guide for the Rescored project.

## Quick Start

### Backend Tests

```bash
cd backend
pip install -r requirements-test.txt
pytest --cov
```

### Frontend Tests

```bash
cd frontend
npm install
npm test
```

## Testing Philosophy

Rescored follows these testing principles:

1. **Test behavior, not implementation** - Verify what the code does, not how
2. **Write tests that give confidence** - Focus on high-value tests that catch real bugs
3. **Keep tests maintainable** - Tests should be easy to understand and modify
4. **Test at the right level** - Unit tests for logic, integration tests for workflows
5. **Fast feedback loops** - Tests should run quickly to enable rapid development

## Test Suites

### Backend Test Suite (`backend/tests/`)

- **Unit Tests** (`test_utils.py`) - URL validation, video availability checks
- **API Tests** (`test_api.py`) - FastAPI endpoints, WebSocket connections
- **Pipeline Tests** (`test_pipeline.py`) - Audio processing, transcription, MusicXML generation
- **Task Tests** (`test_tasks.py`) - Celery workers, job processing, progress updates

**Features**: Mocked external dependencies (yt-dlp, Redis, ML models), temporary file handling, parametrized tests, coverage reporting

### Frontend Test Suite (`frontend/src/tests/`)

- **API Client Tests** (`api/client.test.ts`) - HTTP requests, WebSocket connections
- **Component Tests** (`components/`) - JobSubmission, NotationCanvas, PlaybackControls
- **Store Tests** (`store/useScoreStore.test.ts`) - Zustand state management

**Features**: React Testing Library, user event simulation, mocked VexFlow and Tone.js, coverage reporting

## Coverage Goals

| Component | Target | Priority |
|-----------|--------|----------|
| Backend Utils | 90%+ | High |
| Backend Pipeline | 85%+ | Critical |
| Backend API | 80%+ | High |
| Frontend API Client | 85%+ | Critical |
| Frontend Components | 75%+ | High |
| Frontend Store | 80%+ | High |

## Running Tests

### Backend

```bash
# Run all tests
pytest

# With coverage
pytest --cov --cov-report=html

# Specific tests
pytest tests/test_utils.py
pytest tests/test_utils.py::TestValidateYouTubeURL::test_valid_watch_url

# By category
pytest -m unit              # Only unit tests
pytest -m integration       # Only integration tests
pytest -m "not slow"        # Exclude slow tests
pytest -m "not gpu"         # Exclude GPU tests

# Debugging
pytest -vv                  # Verbose output
pytest -s                   # Show print statements
pytest --pdb                # Drop into debugger on failure
pytest --lf                 # Run last failed tests
```

### Frontend

```bash
# Run all tests
npm test

# Watch mode
npm test -- --watch

# With UI
npm run test:ui

# With coverage
npm run test:coverage

# Specific tests
npm test -- src/tests/api/client.test.ts
npm test -- --grep "JobSubmission"
```

## Test Structure

### Backend

```
backend/tests/
├── conftest.py           # Shared fixtures (temp dirs, mock Redis, sample files)
├── test_utils.py         # Utility function tests
├── test_api.py           # API endpoint tests
├── test_pipeline.py      # Audio processing tests
└── test_tasks.py         # Celery task tests
```

### Frontend

```
frontend/src/tests/
├── setup.ts              # Test configuration (mocks for VexFlow, Tone.js, WebSocket)
├── fixtures.ts           # Shared test data (MusicXML, job responses, etc.)
├── api/client.test.ts
├── components/
│   ├── JobSubmission.test.tsx
│   ├── NotationCanvas.test.tsx
│   └── PlaybackControls.test.tsx
└── store/useScoreStore.test.ts
```

## Common Patterns

### Backend Testing

```python
# Mock external services
@patch('pipeline.yt_dlp.YoutubeDL')
def test_download_audio(mock_ydl_class, temp_storage_dir):
    mock_ydl = MagicMock()
    mock_ydl_class.return_value.__enter__.return_value = mock_ydl

    result = download_audio("https://youtube.com/...", temp_storage_dir)

    assert result.exists()
    assert result.suffix == ".wav"

# Test API endpoints
def test_submit_transcription(test_client):
    response = test_client.post(
        "/api/v1/transcribe",
        json={"youtube_url": "https://www.youtube.com/watch?v=..."}
    )

    assert response.status_code == 201
    assert "job_id" in response.json()

# Parametrized tests
@pytest.mark.parametrize("url,expected_valid", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
    ("https://vimeo.com/12345", False),
])
def test_url_validation(url, expected_valid):
    is_valid, _ = validate_youtube_url(url)
    assert is_valid == expected_valid
```

### Frontend Testing

```typescript
// Test components with user interaction
it('should submit form', async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn();

  render(<JobSubmission onSubmit={onSubmit} />);

  const input = screen.getByPlaceholderText(/youtube url/i);
  await user.type(input, 'https://www.youtube.com/watch?v=...');

  const button = screen.getByRole('button', { name: /submit/i });
  await user.click(button);

  await waitFor(() => {
    expect(onSubmit).toHaveBeenCalled();
  });
});

// Mock API calls
vi.mock('../../api/client', () => ({
  submitTranscription: vi.fn(),
}));

it('should call API', async () => {
  const mockSubmit = vi.mocked(submitTranscription);
  mockSubmit.mockResolvedValue({ job_id: '123' });

  // Test component that uses submitTranscription
  // ...
});

// Test store
it('should update store', () => {
  const { result } = renderHook(() => useScoreStore());

  act(() => {
    result.current.setMusicXML('<musicxml>...</musicxml>');
  });

  expect(result.current.musicXML).toBe('<musicxml>...</musicxml>');
});
```

## Mocking Strategy

### Backend
- **External Services**: Mock yt-dlp, Redis, Celery
- **ML Models**: Mock Demucs and basic-pitch for fast tests
- **File System**: Use temporary directories

### Frontend
- **API Calls**: Mock fetch with vitest
- **WebSockets**: Mock WebSocket connections
- **Browser APIs**: Mock Canvas, Audio, localStorage
- **Libraries**: Mock VexFlow, Tone.js

## Best Practices

### General
1. ✅ Write descriptive test names that explain the scenario
2. ✅ Keep tests simple and focused (one thing per test)
3. ✅ Use Arrange-Act-Assert structure
4. ✅ Make tests independent (no shared state)
5. ✅ Clean up resources (files, connections, timers)
6. ✅ Mock external dependencies
7. ✅ Add tests when fixing bugs
8. ✅ Keep test code as clean as production code

### Backend-Specific
- Use pytest fixtures for shared setup
- Mock yt-dlp, Redis, Celery, ML models
- Use temporary directories for file operations
- Mark slow/GPU tests with `@pytest.mark.slow` and `@pytest.mark.gpu`
- Test both success and error paths

### Frontend-Specific
- Test user behavior, not implementation details
- Use accessible queries: `getByRole`, `getByLabelText` (not `getByTestId`)
- Mock API calls and WebSocket connections
- Test loading states and error handling
- Clean up side effects (timers, event listeners)

## Troubleshooting

### Backend

**Import errors**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**Redis connection errors** - Always mock Redis unless testing Redis specifically

**GPU tests failing** - Mark with `@pytest.mark.gpu` and skip if unavailable

### Frontend

**Canvas errors** - Mock canvas context in `setup.ts`

**WebSocket errors** - Mock WebSocket in `setup.ts`

**Module import errors** - Use `vi.mock()` at top of test file

**Async timeouts** - Increase timeout: `it('test', async () => { ... }, { timeout: 10000 })`

## Test Performance

**Benchmarks:**
- Unit tests: < 100ms each
- Full backend suite: < 30 seconds
- Full frontend suite: < 20 seconds

**Optimization:**
- Mock expensive operations (ML inference, network calls)
- Use test markers to skip slow tests during development
- Parallelize tests (pytest-xdist for backend, vitest default)
- Cache expensive fixtures

## CI/CD Integration

Tests run automatically on:
- **Pull Requests** - All tests must pass
- **Main Branch** - Full suite including slow tests
- **Nightly** - Extended test suite with real YouTube videos
- **Pre-release** - E2E tests, performance benchmarks

## Detailed Guides

For detailed information, see:
- **[Backend Testing Guide](./backend-testing.md)** - In-depth backend testing patterns and examples
- **[Frontend Testing Guide](./frontend-testing.md)** - In-depth frontend testing patterns and examples
- **[Test Video Collection](./test-videos.md)** - Curated YouTube videos for testing transcription quality

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
