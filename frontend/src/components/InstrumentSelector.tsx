/**
 * Multi-instrument selector for choosing which instruments to transcribe.
 */
import { useState } from 'react';
import './InstrumentSelector.css';

export interface Instrument {
  id: string;
  label: string;
}

const INSTRUMENTS: Instrument[] = [
  { id: 'piano', label: 'Piano' },
  { id: 'vocals', label: 'Vocals' },
  { id: 'drums', label: 'Drums' },
  { id: 'bass', label: 'Bass' },
  { id: 'guitar', label: 'Guitar' },
  { id: 'other', label: 'Other Instruments' }
];

export const VOCAL_INSTRUMENTS = [
  { id: 'violin', label: 'Violin', program: 40 },
  { id: 'flute', label: 'Flute', program: 73 },
  { id: 'clarinet', label: 'Clarinet', program: 71 },
  { id: 'saxophone', label: 'Saxophone', program: 64 },
  { id: 'trumpet', label: 'Trumpet', program: 56 },
  { id: 'voice', label: 'Singing Voice', program: 65 },
];

interface InstrumentSelectorProps {
  selectedInstruments: string[];
  onChange: (instruments: string[]) => void;
  vocalInstrument?: string;
  onVocalInstrumentChange?: (instrument: string) => void;
}

export function InstrumentSelector({
  selectedInstruments,
  onChange,
  vocalInstrument = 'violin',
  onVocalInstrumentChange
}: InstrumentSelectorProps) {
  const handleToggle = (instrumentId: string) => {
    const isSelected = selectedInstruments.includes(instrumentId);

    if (isSelected) {
      // Don't allow deselecting if it's the only selected instrument
      if (selectedInstruments.length === 1) {
        return;
      }
      const newInstruments = selectedInstruments.filter(id => id !== instrumentId);
      console.log('[DEBUG] InstrumentSelector: Removing', instrumentId, '-> New list:', newInstruments);
      onChange(newInstruments);
    } else {
      const newInstruments = [...selectedInstruments, instrumentId];
      console.log('[DEBUG] InstrumentSelector: Adding', instrumentId, '-> New list:', newInstruments);
      onChange(newInstruments);
    }
  };

  const vocalsSelected = selectedInstruments.includes('vocals');

  return (
    <div className="instrument-selector">
      <span className="selector-label">Select Instruments:</span>
      <div className="instrument-grid">
        {INSTRUMENTS.map(instrument => (
          <button
            key={instrument.id}
            type="button"
            className={`instrument-button ${selectedInstruments.includes(instrument.id) ? 'selected' : ''}`}
            onClick={() => handleToggle(instrument.id)}
            aria-pressed={selectedInstruments.includes(instrument.id)}
          >
            <span className="instrument-label">{instrument.label}</span>
          </button>
        ))}
      </div>

      {vocalsSelected && onVocalInstrumentChange && (
        <div className="vocal-instrument-selector">
          <label htmlFor="vocal-instrument">Transcribe vocals as:</label>
          <select
            id="vocal-instrument"
            value={vocalInstrument}
            onChange={(e) => onVocalInstrumentChange(e.target.value)}
          >
            {VOCAL_INSTRUMENTS.map(inst => (
              <option key={inst.id} value={inst.id}>
                {inst.label}
              </option>
            ))}
          </select>
        </div>
      )}

      <p className="selector-hint">
        Select at least one instrument to transcribe
      </p>
    </div>
  );
}

export default InstrumentSelector;
