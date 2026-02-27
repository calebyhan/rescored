/**
 * Score header component displaying metadata with editable tempo.
 * Shows title, composer, tempo (click-to-edit), key signature, and time signature.
 */
import { useState } from 'react';
import './ScoreHeader.css';

interface ScoreHeaderProps {
  title: string;
  composer: string;
  tempo: number;
  keySignature: string;
  timeSignature: string;
  onTempoChange: (tempo: number) => void;
}

export function ScoreHeader({
  title,
  composer,
  tempo,
  keySignature,
  timeSignature,
  onTempoChange,
}: ScoreHeaderProps) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState<number>(0);

  const handleTempoClick = () => {
    setTempValue(tempo);
    setEditing(true);
  };

  const handleTempoSave = () => {
    // Validate range: 40-240 BPM
    if (tempValue >= 40 && tempValue <= 240) {
      onTempoChange(tempValue);
      setEditing(false);
    } else {
      // Invalid value - revert
      setTempValue(tempo);
      setEditing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleTempoSave();
    } else if (e.key === 'Escape') {
      setTempValue(tempo);
      setEditing(false);
    }
  };

  return (
    <div className="score-header">
      <div className="header-top">
        <h2 className="score-title">{title}</h2>
        {composer && <p className="score-composer">{composer}</p>}
      </div>

      <div className="metadata-row">
        <div
          className="tempo-display"
          role="button"
          tabIndex={0}
          onClick={handleTempoClick}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleTempoClick(); }}
          title="Click to edit tempo"
        >
          {editing ? (
            <input
              type="number"
              value={tempValue}
              onChange={(e) => setTempValue(parseInt(e.target.value) || 120)}
              onBlur={handleTempoSave}
              onKeyDown={handleKeyDown}
              min={40}
              max={240}
              className="tempo-input"
            />
          ) : (
            <span>♩ = {tempo}</span>
          )}
        </div>

        <div className="metadata-divider">|</div>

        <div className="key-display">
          <span className="metadata-label">Key:</span> {keySignature}
        </div>

        <div className="metadata-divider">|</div>

        <div className="time-display">
          <span className="metadata-label">Time:</span> {timeSignature}
        </div>
      </div>
    </div>
  );
}
