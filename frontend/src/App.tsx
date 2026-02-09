/**
 * Main application component.
 */
import { useState } from 'react';
import { LoadingScreen } from './components/LoadingScreen';
import { JobSubmission } from './components/JobSubmission';
import { ScoreEditor } from './components/ScoreEditor';
import './App.css';

function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);

  const handleLoadingComplete = () => {
    setIsLoading(false);
  };

  const handleJobComplete = (jobId: string) => {
    setCurrentJobId(jobId);
  };

  const handleReset = () => {
    setCurrentJobId(null);
  };

  return (
    <div className="app">
      {isLoading && <LoadingScreen onComplete={handleLoadingComplete} />}
      {!currentJobId ? (
        <JobSubmission onComplete={handleJobComplete} />
      ) : (
        <ScoreEditor jobId={currentJobId} onBack={handleReset} />
      )}
    </div>
  );
}

export default App;
