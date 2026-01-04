/**
 * Instrument tabs for switching between transcribed instruments.
 */
import './InstrumentTabs.css';

interface InstrumentInfo {
  id: string;
  label: string;
  icon: string;
}

const INSTRUMENT_INFO: Record<string, InstrumentInfo> = {
  piano: { id: 'piano', label: 'Piano', icon: '🎹' },
  vocals: { id: 'vocals', label: 'Vocals', icon: '🎤' },
  drums: { id: 'drums', label: 'Drums', icon: '🥁' },
  bass: { id: 'bass', label: 'Bass', icon: '🎸' },
  guitar: { id: 'guitar', label: 'Guitar', icon: '🎸' },
  other: { id: 'other', label: 'Other', icon: '🎵' },
};

interface InstrumentTabsProps {
  instruments: string[];
  activeInstrument: string;
  onInstrumentChange: (instrument: string) => void;
}

export function InstrumentTabs({ instruments, activeInstrument, onInstrumentChange }: InstrumentTabsProps) {
  if (instruments.length === 0) {
    return null;
  }

  // If only one instrument, show it as a badge instead of tabs
  if (instruments.length === 1) {
    const instrument = instruments[0];
    const info = INSTRUMENT_INFO[instrument] || { id: instrument, label: instrument, icon: '🎵' };
    return (
      <div className="instrument-tabs single">
        <div className="instrument-badge">
          <span className="instrument-icon">{info.icon}</span>
          <span className="instrument-label">{info.label}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="instrument-tabs">
      {instruments.map((instrument) => {
        const info = INSTRUMENT_INFO[instrument] || { id: instrument, label: instrument, icon: '🎵' };
        const isActive = instrument === activeInstrument;

        return (
          <button
            key={instrument}
            className={`instrument-tab ${isActive ? 'active' : ''}`}
            onClick={() => onInstrumentChange(instrument)}
            aria-pressed={isActive}
          >
            <span className="instrument-icon">{info.icon}</span>
            <span className="instrument-label">{info.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export default InstrumentTabs;
