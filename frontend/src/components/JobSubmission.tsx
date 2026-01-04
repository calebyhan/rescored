/**
 * Job submission form with progress tracking.
 */
import { useState, useRef, useEffect } from 'react';
import { api } from '../api/client';
import type { ProgressUpdate } from '../api/client';
import { InstrumentSelector } from './InstrumentSelector';
import './JobSubmission.css';

interface JobSubmissionProps {
  onComplete?: (jobId: string) => void;
  onJobSubmitted?: (response: any) => void;
}

export function JobSubmission({ onComplete, onJobSubmitted }: JobSubmissionProps) {
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [selectedInstruments, setSelectedInstruments] = useState<string[]>(['piano']);
  const [status, setStatus] = useState<'idle' | 'submitting' | 'processing' | 'failed'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const wsRef = useRef<WebSocket | null>(null);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const validateUrl = (value: string): string | null => {
    try {
      const u = new URL(value);
      if (!/^(www\.)?youtube\.com$|^(www\.)?youtu\.be$/.test(u.hostname)) {
        return 'Please enter a YouTube link';
      }
      return null;
    } catch {
      return 'Invalid URL';
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate URL
    const validation = validateUrl(youtubeUrl);
    if (validation) {
      setError(validation);
      return;
    }

    // Validate at least one instrument is selected
    if (selectedInstruments.length === 0) {
      setError('Please select at least one instrument');
      return;
    }

    setStatus('submitting');

    try {
      const response = await api.submitJob(youtubeUrl, { instruments: selectedInstruments });
      setYoutubeUrl('');
      if (onJobSubmitted) onJobSubmitted(response);

      // Switch to processing status and connect WebSocket
      setStatus('processing');
      setProgress(0);
      setProgressMessage('Starting transcription...');

      // Connect WebSocket for progress updates
      wsRef.current = api.connectWebSocket(
        response.job_id,
        (update: ProgressUpdate) => {
          if (update.type === 'progress') {
            setProgress(update.progress || 0);
            setProgressMessage(update.message || `Processing: ${update.stage}`);
          } else if (update.type === 'completed') {
            setProgress(100);
            setProgressMessage('Transcription complete!');
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
            // Wait a moment to show completion, then switch to editor
            setTimeout(() => {
              if (onComplete) onComplete(response.job_id);
              setStatus('idle');
            }, 500);
          } else if (update.type === 'error') {
            setStatus('failed');
            setError(update.error?.message || 'Transcription failed');
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
          }
        },
        (error) => {
          console.error('WebSocket error:', error);
          setStatus('failed');
          setError('Connection error. Please try again.');
        }
      );

      // Poll for progress updates as fallback (in case WebSocket misses early updates)
      const pollInterval = setInterval(async () => {
        try {
          const jobStatus = await api.getJobStatus(response.job_id);
          setProgress(jobStatus.progress);
          setProgressMessage(jobStatus.status_message || 'Processing...');

          if (jobStatus.status === 'completed') {
            clearInterval(pollInterval);
            setProgress(100);
            setProgressMessage('Transcription complete!');
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
            setTimeout(() => {
              if (onComplete) onComplete(response.job_id);
              setStatus('idle');
            }, 500);
          } else if (jobStatus.status === 'failed') {
            clearInterval(pollInterval);
            setStatus('failed');
            setError(jobStatus.error?.message || 'Transcription failed');
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      }, 1000); // Poll every second

      // Store interval ID for cleanup
      const currentInterval = pollInterval;
      return () => {
        clearInterval(currentInterval);
        if (wsRef.current) {
          wsRef.current.close();
        }
      };
    } catch (err) {
      setStatus('failed');
      setError(err instanceof Error ? err.message : 'Failed to submit job');
      return;
    }
  };

  return (
    <div className="job-submission">
      <h1>Rescored - AI Music Transcription</h1>
      <p>Convert YouTube videos to editable sheet music</p>

      {(status === 'idle' || status === 'submitting') && (
        <form onSubmit={handleSubmit}>
          <InstrumentSelector
            selectedInstruments={selectedInstruments}
            onChange={setSelectedInstruments}
          />

          <div className="form-group">
            <label htmlFor="youtube-url">YouTube URL:</label>
            <input
              id="youtube-url"
              type="text"
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              required
              onBlur={() => {
                const validation = validateUrl(youtubeUrl);
                if (validation) setError(validation);
              }}
            />
          </div>
          <button type="submit" disabled={status === 'submitting'}>Transcribe</button>
          {status === 'submitting' && <div>Submitting...</div>}
          {error && <div role="alert" className="error-alert">{error}</div>}
        </form>
      )}

      {status === 'processing' && (
        <div className="progress-container">
          <h2>Transcribing...</h2>
          <div className="progress-bar-container">
            <div className="progress-bar" style={{ width: `${progress}%` }} />
          </div>
          <p className="progress-message">{progress}% - {progressMessage}</p>
          <p className="progress-info">
            This may take 1-2 minutes. Please don't close this window.
          </p>
        </div>
      )}

      {status === 'failed' && (
        <div className="error-message">
          <h2>✗ Transcription Failed</h2>
          <p>{error}</p>
          <button onClick={() => setStatus('idle')}>Try Again</button>
        </div>
      )}
    </div>
  );
}

export default JobSubmission;
