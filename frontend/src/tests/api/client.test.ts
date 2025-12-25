/**
 * Tests for API client.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { submitTranscription, getJobStatus, downloadScore } from '../../api/client';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('API Client', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  describe('submitTranscription', () => {
    it('should submit a YouTube URL for transcription', async () => {
      const mockResponse = {
        job_id: 'test-job-123',
        status: 'queued',
        created_at: '2025-01-01T00:00:00Z',
        estimated_duration_seconds: 120,
        websocket_url: 'ws://localhost:8000/api/v1/jobs/test-job-123/stream',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => mockResponse,
      });

      const result = await submitTranscription('https://www.youtube.com/watch?v=dQw4w9WgXcQ');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/transcribe'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
          body: expect.stringContaining('youtube_url'),
        })
      );

      expect(result).toEqual(mockResponse);
    });

    it('should handle invalid YouTube URL', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({
          detail: 'Invalid YouTube URL format',
        }),
      });

      await expect(
        submitTranscription('https://invalid.com/video')
      ).rejects.toThrow();
    });

    it('should handle video unavailable error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({
          detail: 'Video too long (max 15 minutes)',
        }),
      });

      await expect(
        submitTranscription('https://www.youtube.com/watch?v=long-video')
      ).rejects.toThrow();
    });

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(
        submitTranscription('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
      ).rejects.toThrow('Network error');
    });

    it('should include custom options', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({}),
      });

      await submitTranscription('https://www.youtube.com/watch?v=dQw4w9WgXcQ', {
        instruments: ['piano', 'guitar'],
      });

      const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(callBody.options).toEqual({ instruments: ['piano', 'guitar'] });
    });
  });

  describe('getJobStatus', () => {
    it('should fetch job status', async () => {
      const mockStatus = {
        job_id: 'test-job-123',
        status: 'processing',
        progress: 50,
        current_stage: 'transcription',
        status_message: 'Transcribing audio',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockStatus,
      });

      const result = await getJobStatus('test-job-123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/jobs/test-job-123')
      );
      expect(result).toEqual(mockStatus);
    });

    it('should handle job not found', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({
          detail: 'Job not found',
        }),
      });

      await expect(getJobStatus('nonexistent-id')).rejects.toThrow();
    });

    it('should handle completed job', async () => {
      const mockStatus = {
        job_id: 'test-job-123',
        status: 'completed',
        progress: 100,
        result_url: '/api/v1/scores/test-job-123',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockStatus,
      });

      const result = await getJobStatus('test-job-123');

      expect(result.status).toBe('completed');
      expect(result.result_url).toBeDefined();
    });

    it('should handle failed job with error details', async () => {
      const mockStatus = {
        job_id: 'test-job-123',
        status: 'failed',
        progress: 25,
        error: {
          message: 'Download failed',
          stage: 'audio_download',
        },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockStatus,
      });

      const result = await getJobStatus('test-job-123');

      expect(result.status).toBe('failed');
      expect(result.error).toBeDefined();
      if (!result.error) throw new Error('Expected error details');
      expect(result.error.message).toBe('Download failed');
    });
  });

  describe('downloadScore', () => {
    it('should download MusicXML score', async () => {
      const mockXML = '<?xml version="1.0"?><score-partwise></score-partwise>';

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: async () => mockXML,
        headers: new Headers({
          'content-type': 'application/vnd.recordare.musicxml+xml',
        }),
      });

      const result = await downloadScore('test-job-123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/scores/test-job-123')
      );
      expect(result).toBe(mockXML);
    });

    it('should handle score not available', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({
          detail: 'Score not available',
        }),
      });

      await expect(downloadScore('test-job-123')).rejects.toThrow();
    });

    it('should handle incomplete job', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({
          detail: 'Score not available',
        }),
      });

      await expect(downloadScore('processing-job')).rejects.toThrow();
    });
  });

  describe('WebSocket connection', () => {
    it('should establish WebSocket connection', () => {
      const mockWS = {
        addEventListener: vi.fn(),
        close: vi.fn(),
        readyState: WebSocket.OPEN,
      };

      global.WebSocket = vi.fn(() => mockWS) as any;

      const ws = new WebSocket('ws://localhost:8000/api/v1/jobs/test-job-123/stream');

      expect(WebSocket).toHaveBeenCalledWith(
        expect.stringContaining('test-job-123')
      );
      expect(ws.readyState).toBe(WebSocket.OPEN);
    });

    it('should handle WebSocket messages', () => {
      const mockWS = {
        addEventListener: vi.fn(),
        close: vi.fn(),
      };

      global.WebSocket = vi.fn(() => mockWS) as any;

      const ws = new WebSocket('ws://localhost:8000/api/v1/jobs/test-job-123/stream');
      const onMessage = vi.fn();
      ws.addEventListener('message', onMessage);

      expect(mockWS.addEventListener).toHaveBeenCalledWith('message', onMessage);
    });

    it('should handle WebSocket errors', () => {
      const mockWS = {
        addEventListener: vi.fn(),
        close: vi.fn(),
      };

      global.WebSocket = vi.fn(() => mockWS) as any;

      const ws = new WebSocket('ws://localhost:8000/api/v1/jobs/test-job-123/stream');
      const onError = vi.fn();
      ws.addEventListener('error', onError);

      expect(mockWS.addEventListener).toHaveBeenCalledWith('error', onError);
    });
  });
});
