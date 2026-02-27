import React, { useEffect, useState } from 'react';
import './LoadingScreen.css';

interface LoadingScreenProps {
  onComplete?: () => void;
  duration?: number; // Total animation duration in ms
}

const WORD_LETTERS = 'rescored'.split('').map((letter, index) => ({
  letter,
  key: `letter-${index}`,
  delay: `${index * 0.1}s`,
}));
const UNDERLINE_DELAY = `${WORD_LETTERS.length * 0.1}s`;
const SUBTITLE_DELAY = `${WORD_LETTERS.length * 0.1 + 0.3}s`;

export const LoadingScreen: React.FC<LoadingScreenProps> = ({
  onComplete,
  duration = 2500
}) => {
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsComplete(true), duration);
    return () => clearTimeout(timer);
  }, [duration]);

  // Call onComplete 300ms after animation finishes to let the exit animation play
  useEffect(() => {
    if (!isComplete || !onComplete) return;
    const timer = setTimeout(onComplete, 300);
    return () => clearTimeout(timer);
  }, [isComplete, onComplete]);

  return (
    <div className={`loading-screen ${isComplete ? 'complete' : ''}`}>
      <div className="loading-content">
        <h1 className="loading-title">
          {WORD_LETTERS.map(({ letter, key, delay }) => (
            <span
              key={key}
              className="loading-letter"
              style={{ animationDelay: delay }}
            >
              {letter}
            </span>
          ))}
        </h1>
        <div
          className="loading-underline"
          style={{ animationDelay: UNDERLINE_DELAY }}
        />
        <p
          className="loading-subtitle"
          style={{ animationDelay: SUBTITLE_DELAY }}
        >
          AI Music Transcription
        </p>
      </div>
    </div>
  );
};
