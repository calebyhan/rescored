/**
 * Tests for JobSubmission component.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import JobSubmission from '../../components/JobSubmission';
import { sampleJobResponse } from '../fixtures';

// Mock API client
vi.mock('../../api/client', () => ({
  submitTranscription: vi.fn(),
}));

import { submitTranscription } from '../../api/client';

describe('JobSubmission Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render URL input and submit button', () => {
    render(<JobSubmission />);

    expect(screen.getByPlaceholderText(/youtube url/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /transcribe/i })).toBeInTheDocument();
  });

  it('should accept user input', async () => {
    const user = userEvent.setup();
    render(<JobSubmission />);

    const input = screen.getByPlaceholderText(/youtube url/i);
    await user.type(input, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ');

    expect(input).toHaveValue('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
  });

  it('should submit valid YouTube URL', async () => {
    const user = userEvent.setup();
    const mockSubmit = vi.mocked(submitTranscription);
    mockSubmit.mockResolvedValueOnce(sampleJobResponse);

    const onJobSubmitted = vi.fn();
    render(<JobSubmission onJobSubmitted={onJobSubmitted} />);

    const input = screen.getByPlaceholderText(/youtube url/i);
    const button = screen.getByRole('button', { name: /transcribe/i });

    await user.type(input, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    await user.click(button);

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith(
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        expect.any(Object)
      );
      expect(onJobSubmitted).toHaveBeenCalledWith(sampleJobResponse);
    });
  });

  it('should show error for invalid URL', async () => {
    const user = userEvent.setup();
    render(<JobSubmission />);

    const input = screen.getByPlaceholderText(/youtube url/i);
    const button = screen.getByRole('button', { name: /transcribe/i });

    await user.type(input, 'not-a-url');
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/invalid url/i)).toBeInTheDocument();
    });
  });

  it('should show error for non-YouTube URL', async () => {
    const user = userEvent.setup();
    render(<JobSubmission />);

    const input = screen.getByPlaceholderText(/youtube url/i);
    const button = screen.getByRole('button', { name: /transcribe/i });

    await user.type(input, 'https://vimeo.com/12345');
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/youtube url/i)).toBeInTheDocument();
    });
  });

  it('should disable submit button while processing', async () => {
    const user = userEvent.setup();
    const mockSubmit = vi.mocked(submitTranscription);

    // Delay response to test loading state
    mockSubmit.mockImplementationOnce(() =>
      new Promise(resolve => setTimeout(() => resolve(sampleJobResponse), 100))
    );

    render(<JobSubmission />);

    const input = screen.getByPlaceholderText(/youtube url/i);
    const button = screen.getByRole('button', { name: /transcribe/i });

    await user.type(input, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    await user.click(button);

    // Button should be disabled during submission
    expect(button).toBeDisabled();

    await waitFor(() => {
      expect(button).not.toBeDisabled();
    });
  });

  it('should show loading indicator while submitting', async () => {
    const user = userEvent.setup();
    const mockSubmit = vi.mocked(submitTranscription);

    mockSubmit.mockImplementationOnce(() =>
      new Promise(resolve => setTimeout(() => resolve(sampleJobResponse), 100))
    );

    render(<JobSubmission />);

    const input = screen.getByPlaceholderText(/youtube url/i);
    const button = screen.getByRole('button', { name: /transcribe/i });

    await user.type(input, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    await user.click(button);

    expect(screen.getByText(/submitting/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText(/submitting/i)).not.toBeInTheDocument();
    });
  });

  it('should handle API errors', async () => {
    const user = userEvent.setup();
    const mockSubmit = vi.mocked(submitTranscription);
    mockSubmit.mockRejectedValueOnce(new Error('Video too long'));

    render(<JobSubmission />);

    const input = screen.getByPlaceholderText(/youtube url/i);
    const button = screen.getByRole('button', { name: /transcribe/i });

    await user.type(input, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/video too long/i)).toBeInTheDocument();
    });
  });

  it('should clear input after successful submission', async () => {
    const user = userEvent.setup();
    const mockSubmit = vi.mocked(submitTranscription);
    mockSubmit.mockResolvedValueOnce(sampleJobResponse);

    render(<JobSubmission />);

    const input = screen.getByPlaceholderText(/youtube url/i) as HTMLInputElement;
    const button = screen.getByRole('button', { name: /transcribe/i });

    await user.type(input, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    await user.click(button);

    await waitFor(() => {
      expect(input.value).toBe('');
    });
  });

  it('should validate URL format on blur', async () => {
    const user = userEvent.setup();
    render(<JobSubmission />);

    const input = screen.getByPlaceholderText(/youtube url/i);

    await user.type(input, 'invalid-url');
    fireEvent.blur(input);

    await waitFor(() => {
      expect(screen.getByText(/invalid/i)).toBeInTheDocument();
    });
  });

  it('should allow paste from clipboard', async () => {
    const user = userEvent.setup();
    render(<JobSubmission />);

    const input = screen.getByPlaceholderText(/youtube url/i);

    // Simulate paste
    await user.click(input);
    await user.paste('https://www.youtube.com/watch?v=dQw4w9WgXcQ');

    expect(input).toHaveValue('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
  });
});
