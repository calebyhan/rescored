import React from 'react';
import './DevHeader.css';

interface DevHeaderProps {
  onShowLoading: () => void;
  onShowSubmission: () => void;
  onShowEditor: () => void;
  currentView: 'loading' | 'submission' | 'editor';
}

export const DevHeader: React.FC<DevHeaderProps> = ({
  onShowLoading,
  onShowSubmission,
  onShowEditor,
  currentView,
}) => {
  return (
    <header className="dev-header">
      <div className="dev-header-content">
        <span className="dev-label">DEV MODE</span>
        <div className="dev-nav">
          <button
            onClick={onShowLoading}
            className={currentView === 'loading' ? 'active' : ''}
          >
            Loading
          </button>
          <button
            onClick={onShowSubmission}
            className={currentView === 'submission' ? 'active' : ''}
          >
            Submission
          </button>
          <button
            onClick={onShowEditor}
            className={currentView === 'editor' ? 'active' : ''}
          >
            Editor
          </button>
        </div>
      </div>
    </header>
  );
};
