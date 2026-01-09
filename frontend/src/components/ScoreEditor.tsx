/**
 * Main score editor component integrating notation, playback, and export.
 * Supports multi-instrument transcription.
 */
import { useState, useEffect, useCallback } from 'react';
import { getMidiFile, getMetadata, getJobStatus } from '../api/client';
import { useNotationStore } from '../store/notation';
import { NotationCanvas } from './NotationCanvas';
import { PlaybackControls } from './PlaybackControls';
import { InstrumentTabs } from './InstrumentTabs';
import { ScoreHeader } from './ScoreHeader';
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
  const score = useNotationStore((state) => state.score);
  const setTempo = useNotationStore((state) => state.setTempo);
  const selectNote = useNotationStore((state) => state.selectNote);
  const selectedNoteIds = useNotationStore((state) => state.selectedNoteIds);
  const updateNote = useNotationStore((state) => state.updateNote);

  // Undo/Redo
  const undo = useNotationStore((state) => state.undo);
  const redo = useNotationStore((state) => state.redo);
  const canUndo = useNotationStore((state) => state.canUndo);
  const canRedo = useNotationStore((state) => state.canRedo);

  // Copy/Paste
  const copyNotes = useNotationStore((state) => state.copyNotes);
  const hasClipboard = useNotationStore((state) => state.hasClipboard);

  // Pitch editing functions (must be defined before useEffect that uses them)
  const handlePitchUp = useCallback(() => {
    if (!score) return;
    selectedNoteIds.forEach((noteId) => {
      const note = findNoteById(score, noteId);
      if (note && !note.isRest) {
        const newPitch = transposePitch(note.pitch, 1); // +1 semitone
        if (newPitch) {
          updateNote(noteId, { pitch: newPitch });
        }
      }
    });
  }, [score, selectedNoteIds, updateNote]);

  const handlePitchDown = useCallback(() => {
    if (!score) return;
    selectedNoteIds.forEach((noteId) => {
      const note = findNoteById(score, noteId);
      if (note && !note.isRest) {
        const newPitch = transposePitch(note.pitch, -1); // -1 semitone
        if (newPitch) {
          updateNote(noteId, { pitch: newPitch });
        }
      }
    });
  }, [score, selectedNoteIds, updateNote]);

  useEffect(() => {
    loadScore();
  }, [jobId]);

  // Keyboard shortcuts for undo/redo and pitch editing
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const cmdOrCtrl = isMac ? e.metaKey : e.ctrlKey;

      // Undo/Redo
      if (cmdOrCtrl && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        if (canUndo()) undo();
      } else if (cmdOrCtrl && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        if (canRedo()) redo();
      }
      // Copy (only if notes are selected)
      else if (cmdOrCtrl && e.key === 'c' && selectedNoteIds.length > 0) {
        e.preventDefault();
        copyNotes();
      }
      // Pitch editing (only if notes are selected)
      else if (selectedNoteIds.length > 0 && e.key === 'ArrowUp') {
        e.preventDefault();
        handlePitchUp();
      } else if (selectedNoteIds.length > 0 && e.key === 'ArrowDown') {
        e.preventDefault();
        handlePitchDown();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo, canUndo, canRedo, selectedNoteIds, handlePitchUp, handlePitchDown, copyNotes]);

  const loadScore = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get job status to find which instruments were transcribed
      const jobStatus = await getJobStatus(jobId);

      // Parse instruments from backend (graceful degradation if not available)
      // Backend will eventually return: jobStatus.instruments = ['piano', 'vocals', 'drums']
      const transcribedInstruments = (jobStatus as any).instruments || ['piano'];
      setInstruments(transcribedInstruments);

      // Fetch metadata once (shared across all instruments)
      const metadata = await getMetadata(jobId);

      // Load MIDI files for each instrument
      for (const instrument of transcribedInstruments) {
        // Per-instrument MIDI endpoint (backward compatible)
        const midiData = await getMidiFile(jobId, instrument);

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

  // Keyboard handlers for editing
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Get latest state values
      const { selectedNoteIds, deleteNote, updateNote, deselectAll } = useNotationStore.getState();

      // Delete key - remove selected notes
      if (e.key === 'Delete' && selectedNoteIds.length > 0) {
        selectedNoteIds.forEach(id => deleteNote(id));
        deselectAll();
        e.preventDefault(); // Prevent default browser behavior
      }

      // Number keys 1-8 - change note duration
      if (e.key >= '1' && e.key <= '8' && selectedNoteIds.length > 0) {
        const durations = ['whole', 'half', 'quarter', 'eighth', '16th', '32nd', '64th', '128th'];
        const newDuration = durations[parseInt(e.key) - 1];
        selectedNoteIds.forEach(id => updateNote(id, { duration: newDuration }));
        e.preventDefault();
      }

      // Escape key - deselect all notes
      if (e.key === 'Escape' && selectedNoteIds.length > 0) {
        deselectAll();
        e.preventDefault();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []); // Empty deps - uses getState() for latest values

  const handleExportMIDI = async () => {
    try {
      // Export the current edited score (not the original MIDI from backend)
      if (!score) {
        alert('No score loaded');
        return;
      }

      // Generate MIDI from current score state (includes all edits)
      const { generateMidiFromScore } = await import('../utils/midi-exporter');
      const midiData = generateMidiFromScore(score);

      // Download the MIDI file
      const blob = new Blob([midiData.buffer as ArrayBuffer], { type: 'audio/midi' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `score_${activeInstrument}_edited.mid`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export MIDI:', err);
      alert('Failed to export MIDI file');
    }
  };

  const handleExportAllInstruments = async () => {
    try {
      const { scores, availableInstruments } = useNotationStore.getState();
      const { generateMidiFromScore } = await import('../utils/midi-exporter');

      // Export each instrument separately
      for (const instrument of availableInstruments) {
        const instrumentScore = scores.get(instrument);
        if (!instrumentScore) continue;

        const midiData = generateMidiFromScore(instrumentScore);
        const blob = new Blob([midiData.buffer as ArrayBuffer], { type: 'audio/midi' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `score_${instrument}_edited.mid`;
        a.click();
        URL.revokeObjectURL(url);

        // Small delay between downloads to prevent browser blocking
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    } catch (err) {
      console.error('Failed to export all instruments:', err);
      alert('Failed to export MIDI files');
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
      {/* Left Sidebar - Controls & Metadata */}
      <aside className="editor-sidebar">
        <div className="editor-sidebar-header">
          <h2>Score Editor</h2>
          <div className="subtitle">Edit and export your transcription</div>
        </div>

        <div className="editor-sidebar-content">
          {/* Score Info */}
          {score && (
            <div className="sidebar-section">
              <h3 className="sidebar-section-title">Score Info</h3>
              <div className="sidebar-score-header">
                <h4 className="sidebar-score-title">{score.title}</h4>
                {score.composer && <p className="sidebar-score-composer">{score.composer}</p>}
              </div>
              <div className="sidebar-metadata">
                <div className="metadata-item">
                  <span className="metadata-label">Tempo</span>
                  <span className="metadata-value">♩ = {score.tempo}</span>
                </div>
                <div className="metadata-item">
                  <span className="metadata-label">Key</span>
                  <span className="metadata-value">{score.key}</span>
                </div>
                <div className="metadata-item">
                  <span className="metadata-label">Time</span>
                  <span className="metadata-value">{score.timeSignature}</span>
                </div>
              </div>
            </div>
          )}

          {/* Instruments */}
          {instruments.length > 1 && (
            <div className="sidebar-section">
              <h3 className="sidebar-section-title">Instruments</h3>
              <div className="sidebar-instrument-tabs">
                {instruments.map((instrument) => (
                  <button
                    key={instrument}
                    className={`sidebar-instrument-tab ${activeInstrument === instrument ? 'active' : ''}`}
                    onClick={() => setActiveInstrument(instrument)}
                  >
                    {getInstrumentIcon(instrument)} {capitalizeFirst(instrument)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Playback */}
          <div className="sidebar-section">
            <h3 className="sidebar-section-title">Playback</h3>
            <PlaybackControls />
          </div>

          {/* Quick Add Note */}
          <div className="sidebar-section">
            <h3 className="sidebar-section-title">Quick Add</h3>
            <div style={{ fontSize: '0.875rem', color: '#4b5563' }}>
              <p style={{ margin: '0 0 0.5rem 0' }}>Press 'A' key to enable Add Mode</p>
              <p style={{ margin: '0', color: '#9ca3af', fontSize: '0.8rem' }}>
                Then click on staff to add notes
              </p>
            </div>
          </div>

          {/* Quick Tips */}
          <div className="sidebar-section">
            <h3 className="sidebar-section-title">Quick Tips</h3>
            <div style={{ fontSize: '0.875rem', color: '#6b7280', lineHeight: '1.5' }}>
              <p style={{ margin: '0 0 0.5rem 0' }}>• Click notes to select</p>
              <p style={{ margin: '0 0 0.5rem 0' }}>• Press Delete to remove</p>
              <p style={{ margin: '0 0 0.5rem 0' }}>• Press 1-8 for duration</p>
              <p style={{ margin: '0' }}>• Space to play/pause</p>
            </div>
          </div>
        </div>

        {/* Actions Footer */}
        <div className="sidebar-actions">
          <button onClick={handleExportMIDI} className="primary">
            Export Current Instrument (MIDI)
          </button>
          {instruments.length > 1 && (
            <button onClick={handleExportAllInstruments}>
              Export All Instruments
            </button>
          )}
          <button className="secondary">Export MusicXML (Soon)</button>
        </div>
      </aside>

      {/* Right Main Area - Notation Canvas */}
      <main className="editor-main">
        {/* Toolbar */}
        <div className="editor-toolbar">
          <div className="toolbar-group">
            <button
              onClick={() => undo()}
              disabled={!canUndo()}
              className="toolbar-button"
              title="Undo (Ctrl+Z)"
            >
              ↶ Undo
            </button>
            <button
              onClick={() => redo()}
              disabled={!canRedo()}
              className="toolbar-button"
              title="Redo (Ctrl+Y)"
            >
              ↷ Redo
            </button>
          </div>

          {selectedNoteIds.length > 0 && (
            <>
              <div className="toolbar-group">
                <button
                  onClick={() => copyNotes()}
                  className="toolbar-button"
                  title="Copy (Ctrl+C)"
                >
                  📋 Copy
                </button>
              </div>

              <div className="toolbar-group">
                <button
                  onClick={handlePitchUp}
                  className="toolbar-button"
                  title="Increase Pitch (↑)"
                >
                  ↑ Pitch Up
                </button>
                <button
                  onClick={handlePitchDown}
                  className="toolbar-button"
                  title="Decrease Pitch (↓)"
                >
                  ↓ Pitch Down
                </button>
              </div>
            </>
          )}
        </div>

        <div className="editor-main-content">
          <NotationCanvas
            interactive={true}
            onNoteSelect={(noteId) => selectNote(noteId)}
            selectedNotes={selectedNoteIds}
          />
        </div>
      </main>
    </div>
  );
}

// Helper functions

// Find note by ID in score
function findNoteById(score: any, noteId: string): any | null {
  for (const part of score.parts) {
    for (const measure of part.measures) {
      const note = measure.notes.find((n: any) => n.id === noteId);
      if (note) return note;
    }
  }
  // Fallback: check legacy measures array
  for (const measure of score.measures || []) {
    const note = measure.notes.find((n: any) => n.id === noteId);
    if (note) return note;
  }
  return null;
}

// Transpose pitch by semitones
function transposePitch(pitch: string, semitones: number): string | null {
  const match = pitch.match(/^([A-G])([#b]?)(\d+)$/);
  if (!match) return null;

  const [, noteName, accidental, octaveStr] = match;
  const octave = parseInt(octaveStr);

  // Map note names to MIDI numbers within an octave
  const noteMap: Record<string, number> = {
    'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
  };

  // Calculate current MIDI number
  let midiNumber = (octave + 1) * 12 + noteMap[noteName];
  if (accidental === '#') midiNumber += 1;
  if (accidental === 'b') midiNumber -= 1;

  // Apply transposition
  midiNumber += semitones;

  // Clamp to valid MIDI range (0-127)
  if (midiNumber < 0 || midiNumber > 127) return null;

  // Convert back to pitch string
  const newOctave = Math.floor(midiNumber / 12) - 1;
  const pitchClass = midiNumber % 12;

  // Map pitch class to note name (prefer naturals, then sharps)
  const pitchClassMap: Record<number, string> = {
    0: 'C', 1: 'C#', 2: 'D', 3: 'D#', 4: 'E', 5: 'F',
    6: 'F#', 7: 'G', 8: 'G#', 9: 'A', 10: 'A#', 11: 'B'
  };

  return pitchClassMap[pitchClass] + newOctave;
}

function getInstrumentIcon(instrument: string): string {
  const icons: Record<string, string> = {
    piano: '🎹',
    vocals: '🎤',
    drums: '🥁',
    bass: '🎸',
    guitar: '🎸',
    other: '🎵',
  };
  return icons[instrument] || '🎵';
}

function capitalizeFirst(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}
