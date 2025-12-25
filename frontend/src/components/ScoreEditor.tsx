/**
 * Main score editor component integrating notation, playback, and export.
 */
import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useNotationStore } from '../store/notation';
import { NotationCanvas } from './NotationCanvas';
import { PlaybackControls } from './PlaybackControls';
import './ScoreEditor.css';

interface ScoreEditorProps {
  jobId: string;
}

export function ScoreEditor({ jobId }: ScoreEditorProps) {
  const [musicXML, setMusicXML] = useState('');
  const [loading, setLoading] = useState(true);
  const loadFromMusicXML = useNotationStore((state) => state.loadFromMusicXML);

  useEffect(() => {
    loadScore();
  }, [jobId]);

  const loadScore = async () => {
    try {
      const xml = await api.getScore(jobId);
      setMusicXML(xml);
      loadFromMusicXML(xml);
      setLoading(false);
    } catch (err) {
      console.error('Failed to load score:', err);
      setLoading(false);
    }
  };

  const handleExportMusicXML = () => {
    const blob = new Blob([musicXML], {
      type: 'application/vnd.recordare.musicxml+xml',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `score_${jobId}.musicxml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportMIDI = () => {
    alert('MIDI export not yet implemented');
  };

  if (loading) {
    return <div className="score-editor loading">Loading score...</div>;
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

      <NotationCanvas musicXML={musicXML} />

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
