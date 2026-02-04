import React from 'react';
import './Footer.css';

export const Footer: React.FC = () => {
  return (
    <footer className="app-footer">
      <div className="footer-content">
        <a
          href="https://github.com/calebyhan/rescored"
          target="_blank"
          rel="noopener noreferrer"
          className="footer-github"
        >
          View on GitHub →
        </a>
      </div>
    </footer>
  );
};
