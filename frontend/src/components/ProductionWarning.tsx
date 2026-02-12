import React from 'react';
import './ProductionWarning.css';

interface ProductionWarningProps {
  onClose: () => void;
}

export const ProductionWarning: React.FC<ProductionWarningProps> = ({ onClose }) => {
  return (
    <div className="production-warning-overlay" onClick={onClose}>
      <div className="production-warning-modal" onClick={(e) => e.stopPropagation()}>
        <div className="production-warning-header">
          <h2>⚠️ Production Version Notice</h2>
        </div>
        <div className="production-warning-content">
          <p>
            You're using the <strong>production version</strong> of Rescored. Please note:
          </p>
          <ul>
            <li>This version is <strong>not actively maintained</strong></li>
            <li>Processing will be <strong>significantly slower</strong> than local instances</li>
            <li>Limited resources may result in longer wait times</li>
          </ul>
          <p className="production-warning-recommendation">
            For the <strong>best performance and accuracy</strong>, we recommend running Rescored locally:
          </p>
          <a
            href="https://github.com/calebyhan/rescored"
            target="_blank"
            rel="noopener noreferrer"
            className="production-warning-github-link"
          >
            📦 View on GitHub
          </a>
        </div>
        <button className="production-warning-close-btn" onClick={onClose}>
          Got it, continue anyway
        </button>
      </div>
    </div>
  );
};
