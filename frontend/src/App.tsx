/**
 * Main application component.
 */
import { useState, useEffect } from 'react';
import { LoadingScreen } from './components/LoadingScreen';
import { JobSubmission } from './components/JobSubmission';
import { ScoreEditor } from './components/ScoreEditor';
import { ProductionWarning } from './components/ProductionWarning';
import './App.css';

const PRODUCTION_WARNING_DISMISSED_KEY = 'rescored-production-warning-dismissed';

function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [showProductionWarning, setShowProductionWarning] = useState(false);

  const isProduction = import.meta.env.MODE === 'production';

  useEffect(() => {
    // Check if user has already dismissed the warning
    const hasBeenDismissed = localStorage.getItem(PRODUCTION_WARNING_DISMISSED_KEY) === 'true';

    // Only show warning in production mode if not previously dismissed
    if (isProduction && !hasBeenDismissed && !isLoading) {
      setShowProductionWarning(true);
    }
  }, [isProduction, isLoading]);

  const handleLoadingComplete = () => {
    setIsLoading(false);
  };

  const handleCloseProductionWarning = () => {
    localStorage.setItem(PRODUCTION_WARNING_DISMISSED_KEY, 'true');
    setShowProductionWarning(false);
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
      {showProductionWarning && <ProductionWarning onClose={handleCloseProductionWarning} />}
      {!currentJobId ? (
        <JobSubmission onComplete={handleJobComplete} />
      ) : (
        <ScoreEditor jobId={currentJobId} onBack={handleReset} />
      )}
    </div>
  );
}

export default App;
