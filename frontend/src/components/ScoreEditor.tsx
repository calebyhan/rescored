/**
 * Main score editor component integrating notation, playback, and export.
 * Supports multi-instrument transcription.
 */
import { useState, useEffect } from 'react';
import { getMidiFile, getMetadata, getJobStatus } from '../api/client';
import { useNotationStore } from '../store/notation';
import { NotationCanvas } from './NotationCanvas';
import { PlaybackControls } from './PlaybackControls';
import { InstrumentTabs } from './InstrumentTabs';
import './ScoreEditor.css';

interface ScoreEditorProps {
  jobId: string;
}

export function ScoreEditor({ jobId }: ScoreEditorProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [instruments, setInstruments] = useState<string[]>([]);

  const loadFromMidi = useNotationStore((state) => state.loadFromMidi);
  const activeInstrument = useNotationStore((state) => state.activeInstrument);
  const setActiveInstrument = useNotationStore((state) => state.setActiveInstrument);

  useEffect(() => {
    loadScore();
  }, [jobId]);

  const loadScore = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get job status to find which instruments were transcribed
      const jobStatus = await getJobStatus(jobId);

      // For now, assume piano is the default instrument (backend doesn't yet return instruments list)
      // TODO: Update when backend API returns instruments list in job status
      const transcribedInstruments = ['piano'];
      setInstruments(transcribedInstruments);

      // Fetch metadata once (shared across all instruments)
      const metadata = await getMetadata(jobId);

      // Load MIDI files for each instrument
      for (const instrument of transcribedInstruments) {
        // For MVP, backend only supports piano (single stem)
        // In the future, this will fetch per-instrument MIDI: `/api/v1/scores/${jobId}/midi/${instrument}`
        const midiData = await getMidiFile(jobId);

        await loadFromMidi(instrument, midiData, {
          tempo: metadata.tempo,
          keySignature: metadata.key_signature,
          timeSignature: metadata.time_signature,
        });
      }

      // Set first instrument as active
      if (transcribedInstruments.length > 0) {
        setActiveInstrument(transcribedInstruments[0]);
      }

      setLoading(false);
    } catch (err) {
      console.error('Failed to load score:', err);
      setError(err instanceof Error ? err.message : 'Failed to load score');
      setLoading(false);
    }
  };

  const handleExportMusicXML = () => {
    // TODO: Generate MusicXML from edited score state
    alert('MusicXML export coming soon - will generate from your edited notation');
  };

  const handleExportMIDI = async () => {
    try {
      // Download the original MIDI file
      const midiData = await getMidiFile(jobId);
      const blob = new Blob([midiData], { type: 'audio/midi' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `score_${jobId}.mid`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export MIDI:', err);
      alert('Failed to export MIDI file');
    }
  };

  if (loading) {
    return <div className="score-editor loading">Loading score...</div>;
  }

  if (error) {
    return (
      <div className="score-editor error">
        <h2>Error Loading Score</h2>
        <p>{error}</p>
        <button onClick={loadScore}>Retry</button>
      </div>
    );
  }

  return (
    <div className="score-editor">
      <div className="editor-toolbar">
        <h2>Score Editor</h2>
        <div className="toolbar-actions">
          <button onClick={handleExportMIDI}>Export MIDI</button>
        </div>
      </div>

      <InstrumentTabs
        instruments={instruments}
        activeInstrument={activeInstrument}
        onInstrumentChange={setActiveInstrument}
      />

      <PlaybackControls />

      <NotationCanvas />

      <div className="editor-instructions">
        <h3>Editing Instructions (MVP)</h3>
        <ul>
          <li>Click notes to select them</li>
          <li>Press Delete to remove selected notes</li>
          <li>Press 1-8 to change note duration</li>
          <li>Full editing features coming soon...</li>
        </ul>
      </div>
    </div>
  );
}
