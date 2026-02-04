import React, { useEffect, useState } from 'react';
import './LoadingScreen.css';

interface LoadingScreenProps {
  onComplete?: () => void;
  duration?: number; // Total animation duration in ms
}

export const LoadingScreen: React.FC<LoadingScreenProps> = ({
  onComplete,
  duration = 2500
}) => {
  const [isComplete, setIsComplete] = useState(false);
  const word = 'rescored';

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsComplete(true);
      if (onComplete) {
        // Small delay before calling onComplete to let the animation finish
        setTimeout(onComplete, 300);
      }
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onComplete]);

  return (
    <div className={`loading-screen ${isComplete ? 'complete' : ''}`}>
      <div className="loading-content">
        <h1 className="loading-title">
          {word.split('').map((letter, index) => (
            <span
              key={index}
              className="loading-letter"
              style={{
                animationDelay: `${index * 0.1}s`,
              }}
            >
              {letter}
            </span>
          ))}
        </h1>
        <div
          className="loading-underline"
          style={{
            animationDelay: `${word.length * 0.1}s`,
          }}
        />
        <p
          className="loading-subtitle"
          style={{
            animationDelay: `${word.length * 0.1 + 0.3}s`,
          }}
        >
          AI Music Transcription
        </p>
      </div>
    </div>
  );
};
