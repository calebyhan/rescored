/**
 * Job submission form with progress tracking.
 */
import { useState, useRef, useEffect, useReducer } from 'react';
import { api } from '../api/client';
import type { ProgressUpdate } from '../api/client';
import { InstrumentSelector, VOCAL_INSTRUMENTS } from './InstrumentSelector';
import { Footer } from './Footer';
import './JobSubmission.css';

interface FormState {
  youtubeUrl: string;
  uploadMode: 'url' | 'file';
  selectedFile: File | null;
}

type FormAction =
  | { type: 'SET_URL'; url: string }
  | { type: 'SET_MODE'; mode: 'url' | 'file' }
  | { type: 'SET_FILE'; file: File | null }
  | { type: 'RESET_FORM' };

const initialFormState: FormState = { youtubeUrl: '', uploadMode: 'url', selectedFile: null };

function formReducer(state: FormState, action: FormAction): FormState {
  switch (action.type) {
    case 'SET_URL': return { ...state, youtubeUrl: action.url };
    case 'SET_MODE': return { ...state, uploadMode: action.mode };
    case 'SET_FILE': return { ...state, selectedFile: action.file };
    case 'RESET_FORM': return initialFormState;
    default: return state;
  }
}

type JobStatus = 'idle' | 'submitting' | 'processing' | 'failed';

interface JobState {
  status: JobStatus;
  error: string | null;
  progress: number;
  progressMessage: string;
}

type JobAction =
  | { type: 'SUBMIT' }
  | { type: 'START_PROCESSING' }
  | { type: 'PROGRESS'; progress: number; message: string }
  | { type: 'COMPLETE' }
  | { type: 'ERROR'; error: string }
  | { type: 'SET_ERROR'; error: string | null }
  | { type: 'RESET' };

const initialJobState: JobState = { status: 'idle', error: null, progress: 0, progressMessage: '' };

function jobReducer(state: JobState, action: JobAction): JobState {
  switch (action.type) {
    case 'SUBMIT': return { ...state, status: 'submitting', error: null };
    case 'START_PROCESSING': return { ...state, status: 'processing', progress: 0, progressMessage: 'Starting transcription...' };
    case 'PROGRESS': return { ...state, progress: action.progress, progressMessage: action.message };
    case 'COMPLETE': return { ...state, status: 'idle', progress: 100, progressMessage: 'Transcription complete!' };
    case 'ERROR': return { ...state, status: 'failed', error: action.error };
    case 'SET_ERROR': return { ...state, error: action.error };
    case 'RESET': return initialJobState;
    default: return state;
  }
}

interface JobSubmissionProps {
  onComplete?: (jobId: string) => void;
  onJobSubmitted?: (response: any) => void;
}

export function JobSubmission({ onComplete, onJobSubmitted }: JobSubmissionProps) {
  const [formState, formDispatch] = useReducer(formReducer, initialFormState);
  const { youtubeUrl, uploadMode, selectedFile } = formState;
  const [selectedInstruments, setSelectedInstruments] = useState<string[]>(['piano']);
  const [vocalInstrument, setVocalInstrument] = useState('violin');
  const [jobState, dispatch] = useReducer(jobReducer, initialJobState);
  const { status, error, progress, progressMessage } = jobState;
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
    dispatch({ type: 'SET_ERROR', error: null });

    // Validate based on mode
    if (uploadMode === 'url') {
      const validation = validateUrl(youtubeUrl);
      if (validation) {
        dispatch({ type: 'SET_ERROR', error: validation });
        return;
      }
    } else {
      if (!selectedFile) {
        dispatch({ type: 'SET_ERROR', error: 'Please select an audio file' });
        return;
      }
    }

    // Validate at least one instrument is selected
    if (selectedInstruments.length === 0) {
      dispatch({ type: 'SET_ERROR', error: 'Please select at least one instrument' });
      return;
    }

    dispatch({ type: 'SUBMIT' });

    console.log('[DEBUG] About to submit job with instruments:', selectedInstruments);

    // Get the MIDI program number for the selected vocal instrument
    const vocalProgram = VOCAL_INSTRUMENTS.find(v => v.id === vocalInstrument)?.program || 40;

    try {
      const response = uploadMode === 'url'
        ? await api.submitJob(youtubeUrl, { instruments: selectedInstruments, vocalInstrument: vocalProgram })
        : await api.submitFileJob(selectedFile!, { instruments: selectedInstruments, vocalInstrument: vocalProgram });

      formDispatch({ type: 'RESET_FORM' });
      if (onJobSubmitted) onJobSubmitted(response);

      // Switch to processing status and connect WebSocket
      dispatch({ type: 'START_PROCESSING' });

      // Connect WebSocket for progress updates
      wsRef.current = api.connectWebSocket(
        response.job_id,
        (update: ProgressUpdate) => {
          if (update.type === 'progress') {
            dispatch({ type: 'PROGRESS', progress: update.progress || 0, message: update.message || `Processing: ${update.stage}` });
          } else if (update.type === 'completed') {
            dispatch({ type: 'COMPLETE' });
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
            // Wait a moment to show completion, then switch to editor
            setTimeout(() => {
              if (onComplete) onComplete(response.job_id);
              dispatch({ type: 'RESET' });
            }, 500);
          } else if (update.type === 'error') {
            dispatch({ type: 'ERROR', error: update.error?.message || 'Transcription failed' });
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
          }
        },
        (error) => {
          console.error('WebSocket error:', error);
          dispatch({ type: 'ERROR', error: 'Connection error. Please try again.' });
        }
      );

      // Poll for progress updates as fallback (in case WebSocket misses early updates)
      const pollInterval = setInterval(async () => {
        try {
          const jobStatus = await api.getJobStatus(response.job_id);
          dispatch({ type: 'PROGRESS', progress: jobStatus.progress, message: jobStatus.status_message || 'Processing...' });

          if (jobStatus.status === 'completed') {
            clearInterval(pollInterval);
            dispatch({ type: 'COMPLETE' });
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
            setTimeout(() => {
              if (onComplete) onComplete(response.job_id);
              dispatch({ type: 'RESET' });
            }, 500);
          } else if (jobStatus.status === 'failed') {
            clearInterval(pollInterval);
            dispatch({ type: 'ERROR', error: jobStatus.error?.message || 'Transcription failed' });
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
      dispatch({ type: 'ERROR', error: err instanceof Error ? err.message : 'Failed to submit job' });
      return;
    }
  };

  return (
    <div className="job-submission">
      {/* Hero Section - only show when idle */}
      {(status === 'idle' || status === 'submitting') && (
        <div className="hero-section">
          <h1 className="hero-title">rescored</h1>
          <p className="hero-subtitle">AI-powered transcription from YouTube or audio files</p>
        </div>
      )}

      {/* Main Card */}
      {(status === 'idle' || status === 'submitting') && (
        <div className="submission-card">
          <div className="card-header">
            <h2 className="card-title">Start Transcription</h2>
            <p className="card-subtitle">Choose your input method and select instruments to transcribe</p>
          </div>

          <form onSubmit={handleSubmit}>
            <InstrumentSelector
              selectedInstruments={selectedInstruments}
              onChange={setSelectedInstruments}
              vocalInstrument={vocalInstrument}
              onVocalInstrumentChange={setVocalInstrument}
            />

            <div className="form-group">
              <span className="form-label">Input Method</span>
              <div className="upload-mode-selector">
                <button
                  type="button"
                  className={uploadMode === 'url' ? 'active' : ''}
                  onClick={() => {
                    formDispatch({ type: 'SET_MODE', mode: 'url' });
                    dispatch({ type: 'SET_ERROR', error: null });
                  }}
                >
                  YouTube URL
                </button>
                <button
                  type="button"
                  className={uploadMode === 'file' ? 'active' : ''}
                  onClick={() => {
                    formDispatch({ type: 'SET_MODE', mode: 'file' });
                    dispatch({ type: 'SET_ERROR', error: null });
                  }}
                >
                  Upload File
                </button>
              </div>
            </div>

            {uploadMode === 'url' ? (
              <div className="form-group">
                <label htmlFor="youtube-url">YouTube URL</label>
                <input
                  id="youtube-url"
                  type="text"
                  value={youtubeUrl}
                  onChange={(e) => formDispatch({ type: 'SET_URL', url: e.target.value })}
                  placeholder="https://www.youtube.com/watch?v=..."
                  required
                  onBlur={() => {
                    const validation = validateUrl(youtubeUrl);
                    if (validation) dispatch({ type: 'SET_ERROR', error: validation });
                  }}
                />
              </div>
            ) : (
              <div className="form-group">
                <label htmlFor="audio-file">Audio File</label>
                <input
                  id="audio-file"
                  type="file"
                  accept=".wav,.mp3,.flac,.ogg,.m4a,.aac"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      const maxSize = 100 * 1024 * 1024; // 100MB
                      if (file.size > maxSize) {
                        dispatch({ type: 'SET_ERROR', error: 'File too large. Maximum size: 100MB' });
                        formDispatch({ type: 'SET_FILE', file: null });
                      } else {
                        formDispatch({ type: 'SET_FILE', file });
                        dispatch({ type: 'SET_ERROR', error: null });
                      }
                    }
                  }}
                  required
                />
                {selectedFile && (
                  <p className="file-info">
                    📄 {selectedFile.name} • {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                )}
              </div>
            )}

            {error && <div role="alert" className="error-alert">{error}</div>}

            <button type="submit" disabled={status === 'submitting'}>
              {status === 'submitting' ? '⏳ Submitting...' : 'Start Transcription'}
            </button>
          </form>
        </div>
      )}

      {/* Progress View */}
      {status === 'processing' && (
        <div className="submission-card">
          <div className="progress-container">
            <h2>Transcribing Your Music</h2>
            <p className="progress-message">{progressMessage || 'Processing audio...'}</p>

            <div className="progress-bar-container">
              <div className="progress-bar" style={{ width: `${progress}%` }} />
            </div>

            <p className="progress-text">{progress}%</p>

            <p className="progress-info">
              This usually takes 5-15 minutes depending on the length of your audio.
              <br />
              Please keep this window open.
            </p>
          </div>
        </div>
      )}

      {/* Error View */}
      {status === 'failed' && (
        <div className="submission-card">
          <div className="error-message">
            <h2>Transcription Failed</h2>
            <p>{error || 'An unexpected error occurred. Please try again.'}</p>
            <button onClick={() => dispatch({ type: 'RESET' })}>← Try Again</button>
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}

export default JobSubmission;
