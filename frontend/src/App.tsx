/**
 * Main application component.
 */
import { useState } from 'react';
import { JobSubmission } from './components/JobSubmission';
import { ScoreEditor } from './components/ScoreEditor';
import './App.css';

function App() {
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);

  const handleJobComplete = (jobId: string) => {
    setCurrentJobId(jobId);
  };

  const handleReset = () => {
    setCurrentJobId(null);
  };

  return (
    <div className="app">
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
    </div>
  );
}

export default App;
