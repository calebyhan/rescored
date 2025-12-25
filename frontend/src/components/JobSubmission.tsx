/**
 * Job submission form with progress tracking.
 */
import { useState } from 'react';
import { submitTranscription } from '../api/client';
import './JobSubmission.css';

interface JobSubmissionProps {
  onComplete?: (jobId: string) => void;
  onJobSubmitted?: (response: any) => void;
}

export function JobSubmission({ onComplete, onJobSubmitted }: JobSubmissionProps) {
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [status, setStatus] = useState<'idle' | 'submitting' | 'failed'>('idle');
  const [error, setError] = useState<string | null>(null);

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
    const validation = validateUrl(youtubeUrl);
    if (validation) {
      setError(validation);
      return;
    }
    setStatus('submitting');

    try {
      const response = await submitTranscription(youtubeUrl, { instruments: ['piano'] });
      setYoutubeUrl('');
      if (onJobSubmitted) onJobSubmitted(response);
      if (onComplete) onComplete(response.job_id);

      // Reset to idle so the form stays usable after submissions in tests.
      setStatus('idle');
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
          <div className="form-group">
            <label htmlFor="youtube-url">YouTube URL:</label>
            <input
              id="youtube-url"
              type="text"
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              placeholder="YouTube URL"
              required
              onBlur={() => {
                const validation = validateUrl(youtubeUrl);
                if (validation) setError(validation);
              }}
            />
          </div>
          <button type="submit" disabled={status === 'submitting'}>Transcribe</button>
          {status === 'submitting' && <div>Submitting...</div>}
          {error && <div role="alert">{error}</div>}
        </form>
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
