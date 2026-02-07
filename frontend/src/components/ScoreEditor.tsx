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
import { DurationButton } from './DurationButton';
import './ScoreEditor.css';

interface ScoreEditorProps {
  jobId: string;
  onBack?: () => void;
}

export function ScoreEditor({ jobId, onBack }: ScoreEditorProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [instruments, setInstruments] = useState<string[]>([]);

  const loadFromMidi = useNotationStore((state) => state.loadFromMidi);
  const activeInstrument = useNotationStore((state) => state.activeInstrument);
  const setActiveInstrument = useNotationStore((state) => state.setActiveInstrument);
  const score = useNotationStore((state) => state.score);
  const setTempo = useNotationStore((state) => state.setTempo);
  const selectNote = useNotationStore((state) => state.selectNote);
  const deselectAll = useNotationStore((state) => state.deselectAll);
  const selectedNoteIds = useNotationStore((state) => state.selectedNoteIds);
  const updateNote = useNotationStore((state) => state.updateNote);
  const currentDuration = useNotationStore((state) => state.currentDuration);
  const setCurrentDuration = useNotationStore((state) => state.setCurrentDuration);
  const currentTool = useNotationStore((state) => state.currentTool);

  // Undo/Redo
  const undo = useNotationStore((state) => state.undo);
  const redo = useNotationStore((state) => state.redo);
  const canUndo = useNotationStore((state) => state.canUndo);
  const canRedo = useNotationStore((state) => state.canRedo);

  // Copy/Paste
  const copyNotes = useNotationStore((state) => state.copyNotes);
  const pasteNotes = useNotationStore((state) => state.pasteNotes);
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

  // Consolidated keyboard shortcuts handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const cmdOrCtrl = isMac ? e.metaKey : e.ctrlKey;

      // Get latest state values for editing operations
      const { selectedNoteIds, deleteNote, updateNote } = useNotationStore.getState();

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
      // Paste (Ctrl+V) - paste to first selected note's measure
      else if (cmdOrCtrl && e.key === 'v' && selectedNoteIds.length > 0 && hasClipboard()) {
        e.preventDefault();
        const { score } = useNotationStore.getState();
        if (!score) return;

        const firstNoteId = selectedNoteIds[0];
        const measureId = findMeasureIdByNoteId(score, firstNoteId);

        if (measureId) {
          pasteNotes(measureId);
        }
      }
      // Pitch editing (only if notes are selected)
      else if (selectedNoteIds.length > 0 && e.key === 'ArrowUp') {
        e.preventDefault();
        handlePitchUp();
      } else if (selectedNoteIds.length > 0 && e.key === 'ArrowDown') {
        e.preventDefault();
        handlePitchDown();
      }
      // Delete key - remove selected notes
      else if (e.key === 'Delete' && selectedNoteIds.length > 0) {
        selectedNoteIds.forEach(id => deleteNote(id));
        deselectAll();
        e.preventDefault();
      }
      // Number keys 1-8 - change note duration
      else if (e.key >= '1' && e.key <= '8' && selectedNoteIds.length > 0) {
        const durations = ['whole', 'half', 'quarter', 'eighth', '16th', '32nd', '64th', '128th'];
        const newDuration = durations[parseInt(e.key) - 1];
        selectedNoteIds.forEach(id => updateNote(id, { duration: newDuration }));
        e.preventDefault();
      }
      // Accidental keys - enharmonic conversion
      else if (selectedNoteIds.length > 0 && (e.key === '#' || e.key === 'b' || e.key === 'n')) {
        e.preventDefault();

        const accidentalType: 'sharp' | 'flat' | 'natural' =
          e.key === '#' ? 'sharp' : e.key === 'b' ? 'flat' : 'natural';

        selectedNoteIds.forEach(id => {
          const note = findNoteById(score, id);
          if (note && !note.isRest) {
            const newPitch = applyEnharmonic(note.pitch, accidentalType);
            const accidental = accidentalType === 'natural' ? undefined : accidentalType;
            updateNote(id, { pitch: newPitch, accidental });
          }
        });
      }
      // 'A' key - toggle add note mode
      else if (e.key === 'a' || e.key === 'A') {
        e.preventDefault();
        const { currentTool, setCurrentTool } = useNotationStore.getState();
        setCurrentTool(currentTool === 'add' ? 'select' : 'add');
      }
      // Escape key - deselect all notes
      else if (e.key === 'Escape' && selectedNoteIds.length > 0) {
        deselectAll();
        e.preventDefault();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo, canUndo, canRedo, handlePitchUp, handlePitchDown, copyNotes]);

  const loadScore = async () => {
    try {
      setLoading(true);
      setError(null);

      console.log('[ScoreEditor] Starting to load score for job:', jobId);

      // Get job status to find which instruments were transcribed
      const jobStatus = await getJobStatus(jobId);
      console.log('[ScoreEditor] Job status:', jobStatus);

      // Parse instruments from backend (graceful degradation if not available)
      // Backend will eventually return: jobStatus.instruments = ['piano', 'vocals', 'drums']
      const transcribedInstruments = (jobStatus as any).instruments || ['piano'];
      console.log('[ScoreEditor] Transcribed instruments:', transcribedInstruments);
      setInstruments(transcribedInstruments);

      // Fetch metadata once (shared across all instruments)
      const metadata = await getMetadata(jobId);
      console.log('[ScoreEditor] Metadata:', metadata);

      // Load MIDI files for each instrument
      for (const instrument of transcribedInstruments) {
        console.log(`[ScoreEditor] Loading MIDI for ${instrument}...`);

        try {
          // Per-instrument MIDI endpoint (backward compatible)
          const midiData = await getMidiFile(jobId, instrument);
          console.log(`[ScoreEditor] Got MIDI data for ${instrument}, size:`, midiData.byteLength);

          await loadFromMidi(instrument, midiData, {
            tempo: metadata.tempo,
            keySignature: metadata.key_signature,
            timeSignature: metadata.time_signature,
          });

          console.log(`[ScoreEditor] Successfully loaded ${instrument}`);
        } catch (err) {
          console.error(`[ScoreEditor] Failed to load ${instrument}:`, err);
          throw new Error(`Failed to load ${instrument}: ${err instanceof Error ? err.message : 'Unknown error'}`);
        }
      }

      // Wait for store to fully update
      await new Promise(resolve => setTimeout(resolve, 100));

      // Verify all instruments were loaded successfully
      const { scores, availableInstruments } = useNotationStore.getState();
      console.log('[ScoreEditor] Loaded instruments:', availableInstruments);
      console.log('[ScoreEditor] Available scores:', Array.from(scores.keys()));

      // Validate that all instruments were loaded
      if (availableInstruments.length === 0) {
        throw new Error('No instruments were loaded successfully');
      }

      if (availableInstruments.length !== transcribedInstruments.length) {
        console.warn('[ScoreEditor] Mismatch: expected', transcribedInstruments, 'but got', availableInstruments);
      }

      // Set "all" as active if multiple instruments, otherwise first instrument
      if (transcribedInstruments.length > 1 && availableInstruments.length > 1) {
        console.log('[ScoreEditor] Setting active instrument to "all"');
        setActiveInstrument('all');
      } else if (availableInstruments.length > 0) {
        const firstInstrument = availableInstruments[0];
        console.log('[ScoreEditor] Setting active instrument to', firstInstrument);
        setActiveInstrument(firstInstrument);
      } else {
        throw new Error('No instruments available to display');
      }

      console.log('[ScoreEditor] Load complete!');
      setLoading(false);
    } catch (err) {
      console.error('[ScoreEditor] Failed to load score:', err);
      setError(err instanceof Error ? err.message : 'Failed to load score');
      setLoading(false);
    }
  };


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

  // Defensive check: ensure we have a valid score
  if (!score || !score.parts || score.parts.length === 0) {
    console.error('[ScoreEditor] Invalid score state:', { score, activeInstrument, instruments });
    return (
      <div className="score-editor error">
        <h2>Invalid Score</h2>
        <p>The score could not be loaded properly. Active instrument: {activeInstrument}</p>
        <p>Available instruments: {instruments.join(', ')}</p>
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
          {onBack && (
            <button className="back-button-inline" onClick={onBack}>
              ← New Transcription
            </button>
          )}
        </div>

        <div className="editor-sidebar-content">
          {/* Instruments */}
          {instruments.length > 1 && (
            <div className="sidebar-section">
              <h3 className="sidebar-section-title">Instruments</h3>
              <div className="sidebar-instrument-tabs">
                <button
                  key="all"
                  className={`sidebar-instrument-tab ${activeInstrument === 'all' ? 'active' : ''}`}
                  onClick={() => setActiveInstrument('all')}
                >
                  All Instruments
                </button>
                {instruments.map((instrument) => (
                  <button
                    key={instrument}
                    className={`sidebar-instrument-tab ${activeInstrument === instrument ? 'active' : ''}`}
                    onClick={() => setActiveInstrument(instrument)}
                  >
                    {capitalizeFirst(instrument)}
                  </button>
                ))}
              </div>
            </div>
          )}

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
              <p style={{ margin: '0 0 0.5rem 0' }}>• Shift+Click for multi-select</p>
              <p style={{ margin: '0 0 0.5rem 0' }}>• Delete key to remove notes</p>
              <p style={{ margin: '0 0 0.5rem 0' }}>• Arrow keys for pitch</p>
              <p style={{ margin: '0 0 0.5rem 0' }}>• #, b, n for accidentals</p>
              <p style={{ margin: '0' }}>• Ctrl+C/V to copy/paste</p>
            </div>
          </div>
        </div>

        {/* Actions Footer */}
        <div className="sidebar-actions">
          {activeInstrument !== 'all' && (
            <button onClick={handleExportMIDI} className="primary">
              Export {capitalizeFirst(activeInstrument)} (MIDI)
            </button>
          )}
          {instruments.length > 1 && (
            <button onClick={handleExportAllInstruments} className={activeInstrument === 'all' ? 'primary' : ''}>
              Export All Instruments (MIDI)
            </button>
          )}
          {activeInstrument === 'all' && instruments.length === 1 && (
            <button onClick={handleExportMIDI} className="primary">
              Export MIDI
            </button>
          )}
        </div>
      </aside>

      {/* Right Main Area - Notation Canvas */}
      <main className="editor-main">
        {/* Unified Control Bar */}
        <div className="unified-control-bar">
          {/* Left: Undo/Redo */}
          <div className="control-section left">
            <button
              onClick={() => undo()}
              disabled={!canUndo()}
              className="control-button"
              title="Undo (Ctrl+Z)"
            >
              ↶
            </button>
            <button
              onClick={() => redo()}
              disabled={!canRedo()}
              className="control-button"
              title="Redo (Ctrl+Y)"
            >
              ↷
            </button>
          </div>

          {/* Middle: Music Editing */}
          <div className="control-section middle">
            {selectedNoteIds.length > 0 && (
              <>
                <button
                  onClick={() => copyNotes()}
                  className="control-button"
                  title="Copy (Ctrl+C)"
                >
                  Copy
                </button>
                <button
                  onClick={handlePitchUp}
                  className="control-button"
                  title="Increase Pitch (↑)"
                >
                  ↑
                </button>
                <button
                  onClick={handlePitchDown}
                  className="control-button"
                  title="Decrease Pitch (↓)"
                >
                  ↓
                </button>
                <div className="control-divider"></div>
              </>
            )}

            {/* Duration Palette */}
            <div className="duration-palette-inline">
              <DurationButton
                duration="whole"
                isActive={currentDuration === 'whole'}
                onClick={() => setCurrentDuration('whole')}
                title="Whole Note"
              />
              <DurationButton
                duration="half"
                isActive={currentDuration === 'half'}
                onClick={() => setCurrentDuration('half')}
                title="Half Note"
              />
              <DurationButton
                duration="quarter"
                isActive={currentDuration === 'quarter'}
                onClick={() => setCurrentDuration('quarter')}
                title="Quarter Note"
              />
              <DurationButton
                duration="eighth"
                isActive={currentDuration === 'eighth'}
                onClick={() => setCurrentDuration('eighth')}
                title="Eighth Note"
              />
              <DurationButton
                duration="16th"
                isActive={currentDuration === '16th'}
                onClick={() => setCurrentDuration('16th')}
                title="16th Note"
              />
              <DurationButton
                duration="32nd"
                isActive={currentDuration === '32nd'}
                onClick={() => setCurrentDuration('32nd')}
                title="32nd Note"
              />
            </div>
          </div>

          {/* Right: Playback + Tempo */}
          <div className="control-section right">
            <PlaybackControls />
          </div>
        </div>

        <div className="editor-main-content">
          <NotationCanvas
            interactive={true}
            onNoteSelect={(noteId, shiftKey) => {
              if (shiftKey) {
                // Multi-select: toggle in/out
                selectNote(noteId);
              } else {
                // Single-select: replace selection
                deselectAll();
                selectNote(noteId);
              }
            }}
            selectedNotes={selectedNoteIds}
            currentTool={currentTool}
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

// Find which measure contains a given note ID
function findMeasureIdByNoteId(score: any, noteId: string): string | null {
  for (const part of score.parts) {
    for (const measure of part.measures) {
      if (measure.notes.some((n: any) => n.id === noteId)) {
        return measure.id;
      }
    }
  }

  // Fallback: check legacy measures
  for (const measure of score.measures || []) {
    if (measure.notes.some((n: any) => n.id === noteId)) {
      return measure.id;
    }
  }

  return null;
}

// Apply enharmonic conversion to a pitch
function applyEnharmonic(pitch: string, accidentalType: 'sharp' | 'flat' | 'natural'): string {
  const match = pitch.match(/^([A-G][#b]?)(\d+)$/);
  if (!match) return pitch;

  const [, noteClass, octave] = match;

  const enharmonicMap: Record<string, Record<string, string>> = {
    'C': { 'sharp': 'C#', 'flat': 'Db', 'natural': 'C' },
    'C#': { 'sharp': 'C#', 'flat': 'Db', 'natural': 'C' },
    'Db': { 'sharp': 'C#', 'flat': 'Db', 'natural': 'D' },
    'D': { 'sharp': 'D#', 'flat': 'Eb', 'natural': 'D' },
    'D#': { 'sharp': 'D#', 'flat': 'Eb', 'natural': 'D' },
    'Eb': { 'sharp': 'D#', 'flat': 'Eb', 'natural': 'E' },
    'E': { 'sharp': 'F', 'flat': 'E', 'natural': 'E' },
    'F': { 'sharp': 'F#', 'flat': 'F', 'natural': 'F' },
    'F#': { 'sharp': 'F#', 'flat': 'Gb', 'natural': 'F' },
    'Gb': { 'sharp': 'F#', 'flat': 'Gb', 'natural': 'G' },
    'G': { 'sharp': 'G#', 'flat': 'Ab', 'natural': 'G' },
    'G#': { 'sharp': 'G#', 'flat': 'Ab', 'natural': 'G' },
    'Ab': { 'sharp': 'G#', 'flat': 'Ab', 'natural': 'A' },
    'A': { 'sharp': 'A#', 'flat': 'Bb', 'natural': 'A' },
    'A#': { 'sharp': 'A#', 'flat': 'Bb', 'natural': 'A' },
    'Bb': { 'sharp': 'A#', 'flat': 'Bb', 'natural': 'B' },
    'B': { 'sharp': 'C', 'flat': 'B', 'natural': 'B' },
  };

  const newNoteClass = enharmonicMap[noteClass]?.[accidentalType] || noteClass;

  // Handle octave changes (B# → C, Cb → B)
  let newOctave = octave;
  if (noteClass === 'B' && accidentalType === 'sharp') {
    newOctave = String(parseInt(octave) + 1); // B# → C in next octave
  } else if (noteClass === 'C' && accidentalType === 'flat') {
    newOctave = String(parseInt(octave) - 1); // Cb → B in previous octave
  }

  return newNoteClass + newOctave;
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
