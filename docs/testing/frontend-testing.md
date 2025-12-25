# Frontend Testing Guide

Comprehensive guide for testing the Rescored frontend.

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
cd frontend
npm install
```

Test dependencies (already in `package.json`):
- `vitest`: Test framework
- `@testing-library/react`: React testing utilities
- `@testing-library/user-event`: User interaction simulation
- `@testing-library/jest-dom`: DOM matchers
- `jsdom`: DOM implementation for Node.js
- `@vitest/ui`: Interactive test UI
- `@vitest/coverage-v8`: Coverage reporting

### Configuration

Test configuration is in `vitest.config.ts`:

```typescript
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
    },
  },
});
```

## Running Tests

### Basic Commands

```bash
# Run all tests
npm test

# Run in watch mode
npm test -- --watch

# Run with UI
npm run test:ui

# Run with coverage
npm run test:coverage

# Run specific file
npm test -- src/tests/api/client.test.ts

# Run tests matching pattern
npm test -- --grep "JobSubmission"
```

### Watch Mode

Watch mode automatically re-runs tests when files change:

```bash
npm test -- --watch

# Watch specific file
npm test -- --watch src/tests/components/NotationCanvas.test.tsx
```

### Coverage Reports

```bash
# Generate coverage report
npm run test:coverage

# Open HTML report
open coverage/index.html
```

## Test Structure

### Test Files

Component tests live alongside components or in `src/tests/`:

```
frontend/src/
├── components/
│   ├── JobSubmission.tsx
│   └── JobSubmission.test.tsx      # Option 1: Co-located
├── tests/
│   ├── setup.ts                     # Test configuration
│   ├── fixtures.ts                  # Shared test data
│   ├── components/
│   │   └── JobSubmission.test.tsx  # Option 2: Separate directory
│   └── api/
│       └── client.test.ts
```

### Test Organization

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import Component from './Component';

describe('Component', () => {
  beforeEach(() => {
    // Setup before each test
  });

  describe('Rendering', () => {
    it('should render correctly', () => {
      // Test rendering
    });
  });

  describe('Interactions', () => {
    it('should handle user input', async () => {
      // Test interactions
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty state', () => {
      // Test edge cases
    });
  });
});
```

## Writing Tests

### Basic Component Test

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MyComponent from './MyComponent';

describe('MyComponent', () => {
  it('should render text', () => {
    render(<MyComponent text="Hello" />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('should handle button click', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();

    render(<MyComponent onClick={handleClick} />);

    const button = screen.getByRole('button');
    await user.click(button);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

### Testing with User Interactions

Use `@testing-library/user-event` for realistic interactions:

```typescript
import userEvent from '@testing-library/user-event';

it('should accept user input', async () => {
  const user = userEvent.setup();
  render(<JobSubmission />);

  const input = screen.getByPlaceholderText(/youtube url/i);

  // Type into input
  await user.type(input, 'https://www.youtube.com/watch?v=...');
  expect(input).toHaveValue('https://www.youtube.com/watch?v=...');

  // Click button
  const button = screen.getByRole('button', { name: /submit/i });
  await user.click(button);

  // Verify action
  await waitFor(() => {
    expect(mockSubmit).toHaveBeenCalled();
  });
});
```

### Testing Async Operations

```typescript
import { waitFor } from '@testing-library/react';

it('should load data', async () => {
  const mockFetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ data: 'test' }),
  });
  global.fetch = mockFetch;

  render(<DataComponent />);

  await waitFor(() => {
    expect(screen.getByText('test')).toBeInTheDocument();
  });
});
```

### Mocking Dependencies

#### Mock API Client

```typescript
vi.mock('../../api/client', () => ({
  submitTranscription: vi.fn(),
  getJobStatus: vi.fn(),
  downloadScore: vi.fn(),
}));

import { submitTranscription } from '../../api/client';

it('should call API', async () => {
  const mockSubmit = vi.mocked(submitTranscription);
  mockSubmit.mockResolvedValue({ job_id: '123', status: 'queued' });

  // Test component that uses submitTranscription
  // ...

  expect(mockSubmit).toHaveBeenCalledWith('https://youtube.com/...');
});
```

#### Mock Zustand Store

```typescript
import { renderHook, act } from '@testing-library/react';
import { useScoreStore } from '../../store/scoreStore';

it('should update store', () => {
  const { result } = renderHook(() => useScoreStore());

  act(() => {
    result.current.setMusicXML('<musicxml>...</musicxml>');
  });

  expect(result.current.musicXML).toBe('<musicxml>...</musicxml>');
});
```

#### Mock VexFlow

```typescript
// In setup.ts
vi.mock('vexflow', () => ({
  Flow: {
    Renderer: vi.fn(() => ({
      resize: vi.fn(),
      getContext: vi.fn(() => ({
        clear: vi.fn(),
        setFont: vi.fn(),
      })),
    })),
    Stave: vi.fn(() => ({
      addClef: vi.fn().mockReturnThis(),
      addTimeSignature: vi.fn().mockReturnThis(),
      setContext: vi.fn().mockReturnThis(),
      draw: vi.fn(),
    })),
  },
}));
```

## Testing Patterns

### Testing Form Submission

```typescript
it('should submit form with valid data', async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn();

  render(<Form onSubmit={onSubmit} />);

  // Fill out form
  await user.type(screen.getByLabelText(/url/i), 'https://youtube.com/...');

  // Submit
  await user.click(screen.getByRole('button', { name: /submit/i }));

  // Verify
  await waitFor(() => {
    expect(onSubmit).toHaveBeenCalledWith({
      url: 'https://youtube.com/...',
    });
  });
});
```

### Testing Error States

```typescript
it('should show error message', async () => {
  const mockFetch = vi.fn().mockRejectedValue(new Error('Network error'));
  global.fetch = mockFetch;

  render(<Component />);

  await waitFor(() => {
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });
});
```

### Testing Loading States

```typescript
it('should show loading indicator', async () => {
  const mockFetch = vi.fn(() =>
    new Promise(resolve => setTimeout(() => resolve({ ok: true }), 100))
  );
  global.fetch = mockFetch;

  render(<Component />);

  // Should show loading
  expect(screen.getByText(/loading/i)).toBeInTheDocument();

  // Should hide loading after data loads
  await waitFor(() => {
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
  });
});
```

### Testing WebSocket Connections

```typescript
it('should handle WebSocket messages', () => {
  const mockWS = {
    addEventListener: vi.fn(),
    send: vi.fn(),
    close: vi.fn(),
  };

  global.WebSocket = vi.fn(() => mockWS) as any;

  render(<WebSocketComponent />);

  // Get message handler
  const messageHandler = mockWS.addEventListener.mock.calls.find(
    call => call[0] === 'message'
  )?.[1];

  // Simulate message
  messageHandler?.({ data: JSON.stringify({ type: 'progress', progress: 50 }) });

  // Verify UI updated
  expect(screen.getByText(/50%/)).toBeInTheDocument();
});
```

### Testing Conditional Rendering

```typescript
it('should render different states', () => {
  const { rerender } = render(<StatusIndicator status="loading" />);
  expect(screen.getByText(/loading/i)).toBeInTheDocument();

  rerender(<StatusIndicator status="success" />);
  expect(screen.getByText(/success/i)).toBeInTheDocument();

  rerender(<StatusIndicator status="error" />);
  expect(screen.getByText(/error/i)).toBeInTheDocument();
});
```

### Testing Canvas/VexFlow Components

```typescript
it('should render notation', () => {
  // Mock canvas context
  const mockContext = {
    fillRect: vi.fn(),
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    stroke: vi.fn(),
  };

  HTMLCanvasElement.prototype.getContext = vi.fn(() => mockContext) as any;

  const { container } = render(<NotationCanvas musicXML={sampleXML} />);

  // Verify canvas or SVG exists
  const canvas = container.querySelector('canvas');
  expect(canvas).toBeInTheDocument();
});
```

### Snapshot Testing

Use snapshots for stable UI components:

```typescript
it('should match snapshot', () => {
  const { container } = render(<StaticComponent />);
  expect(container).toMatchSnapshot();
});
```

**Update snapshots:**
```bash
npm test -- -u
```

## Testing Custom Hooks

```typescript
import { renderHook, act } from '@testing-library/react';
import { useCustomHook } from './useCustomHook';

it('should handle state changes', () => {
  const { result } = renderHook(() => useCustomHook());

  expect(result.current.count).toBe(0);

  act(() => {
    result.current.increment();
  });

  expect(result.current.count).toBe(1);
});
```

## Accessibility Testing

```typescript
it('should be accessible', () => {
  render(<Component />);

  // Check for proper labels
  expect(screen.getByLabelText(/input field/i)).toBeInTheDocument();

  // Check for ARIA attributes
  expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Submit');

  // Check keyboard navigation
  const button = screen.getByRole('button');
  button.focus();
  expect(button).toHaveFocus();
});
```

## Troubleshooting

### Common Issues

**Canvas/VexFlow Errors**

```typescript
// Mock canvas in setup.ts
beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    fillRect: vi.fn(),
    // ... other canvas methods
  })) as any;
});
```

**WebSocket Errors**

```typescript
// Mock WebSocket in setup.ts
global.WebSocket = vi.fn(() => ({
  addEventListener: vi.fn(),
  send: vi.fn(),
  close: vi.fn(),
  readyState: WebSocket.OPEN,
})) as any;
```

**Module Import Errors**

```typescript
// Use vi.mock at top of test file
vi.mock('external-module', () => ({
  default: vi.fn(),
  namedExport: vi.fn(),
}));
```

**Async Test Timeouts**

```typescript
// Increase timeout for slow tests
it('slow test', async () => {
  // ...
}, { timeout: 10000 });
```

### Debugging Tests

```bash
# Run with UI for interactive debugging
npm run test:ui

# Run specific test in watch mode
npm test -- --watch --grep "test name"

# Debug in VS Code
# Add breakpoint and use "Debug Test" code lens
```

### Performance Issues

```bash
# Identify slow tests
npm test -- --reporter=verbose

# Run tests in parallel (default)
npm test

# Run sequentially if needed
npm test -- --no-threads
```

## Best Practices

1. **Test user behavior, not implementation**: Focus on what users see and do
2. **Use accessible queries**: Prefer `getByRole`, `getByLabelText` over `getByTestId`
3. **Avoid testing implementation details**: Don't test internal state or methods
4. **Keep tests simple**: Each test should verify one thing
5. **Use realistic data**: Test with data similar to production
6. **Clean up**: Always clean up side effects (timers, listeners)
7. **Mock external dependencies**: Don't make real API calls or WebSocket connections
8. **Test edge cases**: Empty states, errors, loading states

## Query Priority

Use queries in this order (most preferred first):

1. **Accessible Queries**:
   - `getByRole`
   - `getByLabelText`
   - `getByPlaceholderText`
   - `getByText`

2. **Semantic Queries**:
   - `getByAltText`
   - `getByTitle`

3. **Test IDs** (last resort):
   - `getByTestId`

Example:

```typescript
// Good
const button = screen.getByRole('button', { name: /submit/i });
const input = screen.getByLabelText(/email/i);

// Acceptable
const image = screen.getByAltText('Logo');

// Last resort
const element = screen.getByTestId('custom-element');
```

## Example Test File

Complete example showing best practices:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import JobSubmission from './JobSubmission';

vi.mock('../../api/client', () => ({
  submitTranscription: vi.fn(),
}));

import { submitTranscription } from '../../api/client';

describe('JobSubmission', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render input and button', () => {
      render(<JobSubmission />);

      expect(screen.getByPlaceholderText(/youtube url/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /transcribe/i })).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('should accept and submit valid URL', async () => {
      const user = userEvent.setup();
      const mockSubmit = vi.mocked(submitTranscription);
      mockSubmit.mockResolvedValue({ job_id: '123', status: 'queued' });

      render(<JobSubmission />);

      const input = screen.getByPlaceholderText(/youtube url/i);
      const button = screen.getByRole('button', { name: /transcribe/i });

      await user.type(input, 'https://www.youtube.com/watch?v=...');
      await user.click(button);

      await waitFor(() => {
        expect(mockSubmit).toHaveBeenCalledWith(
          'https://www.youtube.com/watch?v=...',
          expect.any(Object)
        );
      });
    });
  });

  describe('Error Handling', () => {
    it('should show error for invalid URL', async () => {
      const user = userEvent.setup();
      render(<JobSubmission />);

      const input = screen.getByPlaceholderText(/youtube url/i);
      const button = screen.getByRole('button', { name: /transcribe/i });

      await user.type(input, 'invalid-url');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByText(/invalid/i)).toBeInTheDocument();
      });
    });
  });
});
```
