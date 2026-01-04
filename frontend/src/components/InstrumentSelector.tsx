/**
 * Multi-instrument selector for choosing which instruments to transcribe.
 */
import { useState } from 'react';
import './InstrumentSelector.css';

export interface Instrument {
  id: string;
  label: string;
  icon: string;
}

const INSTRUMENTS: Instrument[] = [
  { id: 'piano', label: 'Piano', icon: '🎹' },
  { id: 'vocals', label: 'Vocals (Violin)', icon: '🎤' },
  { id: 'drums', label: 'Drums', icon: '🥁' },
  { id: 'bass', label: 'Bass', icon: '🎸' },
  { id: 'guitar', label: 'Guitar', icon: '🎸' },
  { id: 'other', label: 'Other Instruments', icon: '🎵' }
];

interface InstrumentSelectorProps {
  selectedInstruments: string[];
  onChange: (instruments: string[]) => void;
}

export function InstrumentSelector({ selectedInstruments, onChange }: InstrumentSelectorProps) {
  const handleToggle = (instrumentId: string) => {
    const isSelected = selectedInstruments.includes(instrumentId);

    if (isSelected) {
      // Don't allow deselecting if it's the only selected instrument
      if (selectedInstruments.length === 1) {
        return;
      }
      onChange(selectedInstruments.filter(id => id !== instrumentId));
    } else {
      onChange([...selectedInstruments, instrumentId]);
    }
  };

  return (
    <div className="instrument-selector">
      <label className="selector-label">Select Instruments:</label>
      <div className="instrument-grid">
        {INSTRUMENTS.map(instrument => (
          <button
            key={instrument.id}
            type="button"
            className={`instrument-button ${selectedInstruments.includes(instrument.id) ? 'selected' : ''}`}
            onClick={() => handleToggle(instrument.id)}
            aria-pressed={selectedInstruments.includes(instrument.id)}
          >
            <span className="instrument-icon">{instrument.icon}</span>
            <span className="instrument-label">{instrument.label}</span>
          </button>
        ))}
      </div>
      <p className="selector-hint">
        Select at least one instrument to transcribe
      </p>
    </div>
  );
}

export default InstrumentSelector;
