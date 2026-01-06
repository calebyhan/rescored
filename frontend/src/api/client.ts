/**
 * API client for Rescored backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE_URL = API_BASE_URL.replace('http', 'ws');

export interface TranscribeRequest {
  youtube_url: string;
  options?: {
    instruments: string[];
  };
}

export interface TranscribeResponse {
  job_id: string;
  status: string;
  created_at: string;
  estimated_duration_seconds: number;
  websocket_url: string;
}

export interface JobStatus {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
  current_stage: string | null;
  status_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  error: { message: string; retryable: boolean } | null;
  result_url: string | null;
}

export interface ProgressUpdate {
  type: 'progress' | 'completed' | 'error' | 'heartbeat';
  job_id: string;
  progress?: number;
  stage?: string;
  message?: string;
  result_url?: string;
  error?: { message: string; retryable: boolean };
  timestamp: string;
}

export class RescoredAPI {
  private baseURL = API_BASE_URL;
  private wsBaseURL = WS_BASE_URL;

  async submitJob(youtubeURL: string, options?: { instruments?: string[]; vocalInstrument?: number }): Promise<TranscribeResponse> {
    const response = await fetch(`${this.baseURL}/api/v1/transcribe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        youtube_url: youtubeURL,
        options: options ?? { instruments: ['piano'] },
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to submit job');
    }

    return response.json();
  }

  async submitFileJob(file: File, options?: { instruments?: string[]; vocalInstrument?: number }): Promise<TranscribeResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('instruments', JSON.stringify(options?.instruments ?? ['piano']));
    if (options?.vocalInstrument !== undefined) {
      formData.append('vocal_instrument', options.vocalInstrument.toString());
    }

    const response = await fetch(`${this.baseURL}/api/v1/transcribe/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to submit file');
    }

    return response.json();
  }

  async getJobStatus(jobId: string): Promise<JobStatus> {
    const response = await fetch(`${this.baseURL}/api/v1/jobs/${jobId}`);

    if (!response.ok) {
      throw new Error('Failed to fetch job status');
    }

    return response.json();
  }

  async getScore(jobId: string): Promise<string> {
    const response = await fetch(`${this.baseURL}/api/v1/scores/${jobId}`);

    if (!response.ok) {
      throw new Error('Failed to fetch score');
    }

    return response.text();
  }

  connectWebSocket(
    jobId: string,
    onMessage: (update: ProgressUpdate) => void,
    onError?: (error: Event) => void,
    onClose?: () => void
  ): WebSocket {
    const ws = new WebSocket(`${this.wsBaseURL}/api/v1/jobs/${jobId}/stream`);

    ws.onmessage = (event) => {
      const update: ProgressUpdate = JSON.parse(event.data);
      onMessage(update);

      // Send pong for heartbeat
      if (update.type === 'heartbeat') {
        ws.send(JSON.stringify({ type: 'pong', timestamp: new Date().toISOString() }));
      }
    };

    if (onError) {
      ws.onerror = onError;
    }

    if (onClose) {
      ws.onclose = onClose;
    }

    return ws;
  }

  getScoreURL(jobId: string): string {
    return `${this.baseURL}/api/v1/scores/${jobId}`;
  }
}

export const api = new RescoredAPI();

// Compatibility function wrappers for tests
export async function submitTranscription(
  youtubeURL: string,
  options?: { instruments?: string[] }
) {
  // Delegate to class method; include options if provided
  return api.submitJob(youtubeURL, options);
}

export async function getJobStatus(jobId: string) {
  return api.getJobStatus(jobId);
}

export async function downloadScore(jobId: string) {
  return api.getScore(jobId);
}

export async function getMidiFile(jobId: string): Promise<ArrayBuffer> {
  const response = await fetch(`${API_BASE_URL}/api/v1/scores/${jobId}/midi`);

  if (!response.ok) {
    throw new Error('Failed to fetch MIDI file');
  }

  return response.arrayBuffer();
}

export interface ScoreMetadata {
  tempo: number;
  key_signature: string;
  time_signature: { numerator: number; denominator: number };
}

export async function getMetadata(jobId: string): Promise<ScoreMetadata> {
  const response = await fetch(`${API_BASE_URL}/api/v1/scores/${jobId}/metadata`);

  if (!response.ok) {
    throw new Error('Failed to fetch metadata');
  }

  return response.json();
}
