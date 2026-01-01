/**
 * Main score editor component integrating notation, playback, and export.
 */
import { useState, useEffect } from 'react';
import { getMidiFile, getMetadata } from '../api/client';
import { useNotationStore } from '../store/notation';
import { NotationCanvas } from './NotationCanvas';
import { PlaybackControls } from './PlaybackControls';
import './ScoreEditor.css';

interface ScoreEditorProps {
  jobId: string;
}

export function ScoreEditor({ jobId }: ScoreEditorProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadFromMidi = useNotationStore((state) => state.loadFromMidi);

  useEffect(() => {
    loadScore();
  }, [jobId]);

  const loadScore = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch MIDI file and metadata in parallel
      const [midiData, metadata] = await Promise.all([
        getMidiFile(jobId),
        getMetadata(jobId),
      ]);

      // Load MIDI into notation store
      await loadFromMidi(midiData, {
        tempo: metadata.tempo,
        keySignature: metadata.key_signature,
        timeSignature: metadata.time_signature,
      });

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
          <button onClick={handleExportMusicXML}>Export MusicXML</button>
          <button onClick={handleExportMIDI}>Export MIDI</button>
        </div>
      </div>

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
