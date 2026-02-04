/**
 * Main application component.
 */
import { useState } from 'react';
import { LoadingScreen } from './components/LoadingScreen';
import { JobSubmission } from './components/JobSubmission';
import { ScoreEditor } from './components/ScoreEditor';
import { DevHeader } from './components/DevHeader';
import './App.css';

// Temporary dev mode toggle - set to false to disable
const DEV_MODE = true;

// Sample job ID from completed backend job (has piano + vocals)
const SAMPLE_JOB_ID = 'e0cc1572-7935-4cb7-8e99-ba0b4c15cf38';

function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [devView, setDevView] = useState<'loading' | 'submission' | 'editor'>('loading');

  const handleLoadingComplete = () => {
    setIsLoading(false);
  };

  const handleJobComplete = (jobId: string) => {
    setCurrentJobId(jobId);
  };

  const handleReset = () => {
    setCurrentJobId(null);
  };

  // Dev mode handlers
  const handleShowLoading = () => {
    setDevView('loading');
    setIsLoading(true);
    setCurrentJobId(null);
  };

  const handleShowSubmission = () => {
    setDevView('submission');
    setIsLoading(false);
    setCurrentJobId(null);
  };

  const handleShowEditor = () => {
    setDevView('editor');
    setIsLoading(false);
    setCurrentJobId(SAMPLE_JOB_ID);
  };

  // Determine current view for dev header
  const getCurrentView = () => {
    if (DEV_MODE) {
      return devView;
    }
    if (isLoading) return 'loading';
    if (!currentJobId) return 'submission';
    return 'editor';
  };

  return (
    <>
      {DEV_MODE && (
        <DevHeader
          onShowLoading={handleShowLoading}
          onShowSubmission={handleShowSubmission}
          onShowEditor={handleShowEditor}
          currentView={getCurrentView()}
        />
      )}
      <div className={`app ${DEV_MODE ? 'with-dev-header' : ''}`}>
        {/* Dev mode: use devView to control display */}
        {DEV_MODE ? (
          <>
            {devView === 'loading' && <LoadingScreen onComplete={handleLoadingComplete} />}
            {devView === 'submission' && <JobSubmission onComplete={handleJobComplete} />}
            {devView === 'editor' && currentJobId && (
              <div>
                <button className="back-button" onClick={handleReset}>
                  ← New Transcription
                </button>
                <ScoreEditor jobId={currentJobId} />
              </div>
            )}
          </>
        ) : (
          /* Production mode: use normal flow */
          <>
            {isLoading && <LoadingScreen onComplete={handleLoadingComplete} />}
            {!currentJobId ? (
              <JobSubmission onComplete={handleJobComplete} />
            ) : (
              <div>
                <button className="back-button" onClick={handleReset}>
                  ← New Transcription
                </button>
                <ScoreEditor jobId={currentJobId} />
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}

export default App;
