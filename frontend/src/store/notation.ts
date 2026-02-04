/**
 * Zustand store for notation state management.
 * Supports multi-instrument transcription.
 */
import { create } from 'zustand';
import { parseMidiFile, assignChordIds } from '../utils/midi-parser';

export interface Note {
  id: string;
  pitch: string; // e.g., "C4", "F#5", or empty string for rests
  duration: string; // "whole", "half", "quarter", "eighth", "16th"
  octave: number;
  startTime: number;
  dotted: boolean;
  accidental?: 'sharp' | 'flat' | 'natural';
  isRest: boolean;
  chordId?: string; // Group chord notes together (notes with same chordId are rendered as single VexFlow chord)
}

export interface Measure {
  id: string;
  number: number;
  notes: Note[];
}

export interface Part {
  id: string;
  name: string; // "Piano Right Hand", "Piano Left Hand"
  clef: 'treble' | 'bass';
  measures: Measure[];
}

export interface Score {
  id: string;
  title: string;
  composer: string;
  key: string; // e.g., "C", "Gm"
  timeSignature: string; // e.g., "4/4"
  tempo: number; // BPM
  parts: Part[]; // Support multiple parts for grand staff
  measures: Measure[]; // Legacy: for backward compatibility, use parts[0].measures
}

// Snapshot of score state for undo/redo
interface HistorySnapshot {
  scores: Map<string, Score>;
  activeInstrument: string;
  timestamp: number;
}

interface NotationState {
  // Multi-instrument support
  scores: Map<string, Score>; // instrument -> Score
  activeInstrument: string; // Currently viewing instrument (e.g., 'piano', 'vocals')
  availableInstruments: string[]; // All transcribed instruments

  // Legacy single-score access (for backward compatibility)
  score: Score | null;

  selectedNoteIds: string[];
  currentTool: 'select' | 'add' | 'delete';
  currentDuration: string;
  currentPitch: string; // For adding notes (e.g., "C4")
  playingNoteIds: string[]; // Notes currently being played (for visual feedback)

  // Undo/Redo history
  history: HistorySnapshot[];
  historyIndex: number; // Current position in history (-1 = no history)
  maxHistorySize: number;

  // Clipboard for copy/paste
  clipboard: Note[];

  // Actions
  loadFromMidi: (
    instrument: string,
    midiData: ArrayBuffer,
    metadata?: {
      tempo?: number;
      keySignature?: string;
      timeSignature?: { numerator: number; denominator: number };
    }
  ) => Promise<void>;
  setActiveInstrument: (instrument: string) => void;
  setTempo: (tempo: number) => void;
  addNote: (measureId: string, note: Note) => void;
  deleteNote: (noteId: string) => void;
  updateNote: (noteId: string, changes: Partial<Note>) => void;
  selectNote: (noteId: string) => void;
  deselectAll: () => void;
  setCurrentTool: (tool: 'select' | 'add' | 'delete') => void;
  setCurrentDuration: (duration: string) => void;
  setCurrentPitch: (pitch: string) => void;
  setPlayingNoteIds: (noteIds: string[]) => void;

  // Undo/Redo actions
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;

  // Copy/Paste actions
  copyNotes: () => void;
  pasteNotes: (measureId: string) => void;
  hasClipboard: () => boolean;

  // Measure operations
  insertMeasure: (afterMeasureId: string) => void;
  deleteMeasure: (measureId: string) => void;
}

// Helper function to deep clone scores Map
const cloneScoresMap = (scores: Map<string, Score>): Map<string, Score> => {
  const cloned = new Map<string, Score>();
  scores.forEach((score, instrument) => {
    cloned.set(instrument, JSON.parse(JSON.stringify(score)));
  });
  return cloned;
};

// Helper function to create a combined score with all instruments
const createCombinedScore = (scores: Map<string, Score>, instruments: string[]): Score => {
  const allParts: Part[] = [];
  let firstScore: Score | null = null;

  // Collect all parts from all instruments
  for (const instrument of instruments) {
    const score = scores.get(instrument);
    if (!score) continue;

    if (!firstScore) firstScore = score;

    // Add all parts from this instrument with updated names
    for (const part of score.parts) {
      allParts.push({
        ...part,
        id: `${instrument}-${part.id}`,
        name: `${capitalizeFirst(instrument)}${part.name && part.name !== 'Instrument' ? ' - ' + part.name : ''}`,
      });
    }
  }

  // Use metadata from the first score
  return {
    id: 'combined-score',
    title: firstScore?.title || 'Combined Score',
    composer: firstScore?.composer || '',
    key: firstScore?.key || 'C',
    timeSignature: firstScore?.timeSignature || '4/4',
    tempo: firstScore?.tempo || 120,
    parts: allParts,
    measures: [], // Legacy support - use parts instead
  };
};

// Helper function to capitalize first letter
const capitalizeFirst = (str: string): string => {
  return str.charAt(0).toUpperCase() + str.slice(1);
};

// Helper function to extract instrument name from combined score part ID
// Part IDs in combined score are formatted as: "${instrument}-${originalPartId}"
const extractInstrumentFromPartId = (partId: string): string | null => {
  const match = partId.match(/^([^-]+)-/);
  return match ? match[1] : null;
};

// Helper function to find which instrument a measure belongs to in combined score
const findInstrumentForMeasure = (score: Score, measureId: string): string | null => {
  for (const part of score.parts) {
    if (part.measures.some(m => m.id === measureId)) {
      return extractInstrumentFromPartId(part.id);
    }
  }
  return null;
};

// Helper function to find which instrument a note belongs to in combined score
const findInstrumentForNote = (score: Score, noteId: string): string | null => {
  for (const part of score.parts) {
    for (const measure of part.measures) {
      if (measure.notes.some(n => n.id === noteId)) {
        return extractInstrumentFromPartId(part.id);
      }
    }
  }
  return null;
};

// Helper function to save current state to history
const saveToHistory = (state: NotationState): Partial<NotationState> => {
  const snapshot: HistorySnapshot = {
    scores: cloneScoresMap(state.scores),
    activeInstrument: state.activeInstrument,
    timestamp: Date.now(),
  };

  // Truncate future history if we're not at the end
  const newHistory = state.history.slice(0, state.historyIndex + 1);

  // Add new snapshot
  newHistory.push(snapshot);

  // Limit history size
  if (newHistory.length > state.maxHistorySize) {
    newHistory.shift(); // Remove oldest
  }

  return {
    history: newHistory,
    historyIndex: newHistory.length - 1,
  };
};

export const useNotationStore = create<NotationState>((set, get) => ({
  // Multi-instrument state
  scores: new Map(),
  activeInstrument: 'piano',
  availableInstruments: [],

  // Legacy single-score (points to active instrument's score)
  score: null,

  selectedNoteIds: [],
  currentTool: 'select',
  currentDuration: 'quarter',
  currentPitch: 'C4',
  playingNoteIds: [],

  // Undo/Redo state
  history: [],
  historyIndex: -1,
  maxHistorySize: 50,

  // Clipboard state
  clipboard: [],

  loadFromMidi: async (instrument, midiData, metadata) => {
    try {
      let score = await parseMidiFile(midiData, {
        tempo: metadata?.tempo,
        timeSignature: metadata?.timeSignature,
        keySignature: metadata?.keySignature,
        splitAtMiddleC: instrument === 'piano', // Only split piano into grand staff
        middleCNote: 60,
      });

      // Assign chord IDs to simultaneous notes
      score = assignChordIds(score);

      // Update scores map
      const state = get();
      const newScores = new Map(state.scores);
      newScores.set(instrument, score);

      // Update available instruments if this is a new one
      const newAvailableInstruments = state.availableInstruments.includes(instrument)
        ? state.availableInstruments
        : [...state.availableInstruments, instrument];

      set({
        scores: newScores,
        availableInstruments: newAvailableInstruments,
        // Update legacy score if this is the active instrument
        score: state.activeInstrument === instrument ? score : state.score,
      });
    } catch (error) {
      console.error('Failed to parse MIDI:', error);
      // Create fallback empty score
      const emptyScore: Score = {
        id: `score-${instrument}`,
        title: 'Transcribed Score',
        composer: 'YourMT3+',
        key: metadata?.keySignature || 'C',
        timeSignature: metadata?.timeSignature
          ? `${metadata.timeSignature.numerator}/${metadata.timeSignature.denominator}`
          : '4/4',
        tempo: metadata?.tempo || 120,
        parts: [],
        measures: [],
      };

      const state = get();
      const newScores = new Map(state.scores);
      newScores.set(instrument, emptyScore);

      const newAvailableInstruments = state.availableInstruments.includes(instrument)
        ? state.availableInstruments
        : [...state.availableInstruments, instrument];

      set({
        scores: newScores,
        availableInstruments: newAvailableInstruments,
        score: state.activeInstrument === instrument ? emptyScore : state.score,
      });
    }
  },

  setActiveInstrument: (instrument) => {
    const state = get();

    // Special case: "all" means show all instruments combined
    if (instrument === 'all' && state.availableInstruments.length > 0) {
      const combinedScore = createCombinedScore(state.scores, state.availableInstruments);
      set({
        activeInstrument: instrument,
        score: combinedScore,
        selectedNoteIds: [], // Clear selection when switching instruments
      });
      return;
    }

    const instrumentScore = state.scores.get(instrument);

    set({
      activeInstrument: instrument,
      score: instrumentScore || null,
      selectedNoteIds: [], // Clear selection when switching instruments
    });
  },

  setTempo: (tempo) =>
    set((state) => {
      if (!state.score) return state;

      // Save current state to history
      const historyUpdate = saveToHistory(state);

      // Update tempo in active score
      const updatedScore = { ...state.score, tempo };

      // Update in scores map
      const newScores = new Map(state.scores);
      newScores.set(state.activeInstrument, updatedScore);

      return {
        ...historyUpdate,
        score: updatedScore,
        scores: newScores,
      };
    }),

  addNote: (measureId, note) =>
    set((state) => {
      if (!state.score) return state;

      // Save current state to history
      const historyUpdate = saveToHistory(state);

      // Update parts structure (primary)
      const updatedParts = state.score.parts.map((part) => ({
        ...part,
        measures: part.measures.map((m) =>
          m.id === measureId
            ? { ...m, notes: [...m.notes, note].sort((a, b) => a.startTime - b.startTime) }
            : m
        ),
      }));

      // Also update legacy measures for backward compatibility (if it exists)
      const updatedMeasures = state.score.measures?.map((m) =>
        m.id === measureId
          ? { ...m, notes: [...m.notes, note].sort((a, b) => a.startTime - b.startTime) }
          : m
      ) || [];

      const updatedScore = {
        ...state.score,
        parts: updatedParts,
        measures: updatedMeasures,
      };

      // Update in scores map
      const newScores = new Map(state.scores);
      newScores.set(state.activeInstrument, updatedScore);

      return {
        ...historyUpdate,
        score: updatedScore,
        scores: newScores,
      };
    }),

  deleteNote: (noteId) =>
    set((state) => {
      if (!state.score) return state;

      // Save current state to history
      const historyUpdate = saveToHistory(state);

      // Special handling for "all" instruments mode
      if (state.activeInstrument === 'all') {
        // Find which instrument this note belongs to
        const targetInstrument = findInstrumentForNote(state.score, noteId);
        if (!targetInstrument) return state;

        // Get the target instrument's score
        const targetScore = state.scores.get(targetInstrument);
        if (!targetScore) return state;

        // Update the target instrument's score
        const updatedTargetParts = targetScore.parts.map((part) => ({
          ...part,
          measures: part.measures.map((m) => ({
            ...m,
            notes: m.notes.filter((n) => n.id !== noteId),
          })),
        }));

        const updatedTargetScore = {
          ...targetScore,
          parts: updatedTargetParts,
          measures: updatedTargetParts[0]?.measures || [],
        };

        // Update the scores map with the modified instrument score
        const newScores = new Map(state.scores);
        newScores.set(targetInstrument, updatedTargetScore);

        // Regenerate combined score
        const newCombinedScore = createCombinedScore(newScores, state.availableInstruments);

        return {
          ...historyUpdate,
          scores: newScores,
          score: newCombinedScore,
        };
      }

      // Normal single-instrument mode
      const updatedParts = state.score.parts.map((part) => ({
        ...part,
        measures: part.measures.map((m) => ({
          ...m,
          notes: m.notes.filter((n) => n.id !== noteId),
        })),
      }));

      const updatedMeasures = state.score.measures?.map((m) => ({
        ...m,
        notes: m.notes.filter((n) => n.id !== noteId),
      })) || [];

      const updatedScore = {
        ...state.score,
        parts: updatedParts,
        measures: updatedMeasures,
      };

      const newScores = new Map(state.scores);
      newScores.set(state.activeInstrument, updatedScore);

      return {
        ...historyUpdate,
        score: updatedScore,
        scores: newScores,
      };
    }),

  updateNote: (noteId, changes) =>
    set((state) => {
      if (!state.score) return state;

      // Save current state to history
      const historyUpdate = saveToHistory(state);

      // Special handling for "all" instruments mode
      if (state.activeInstrument === 'all') {
        // Find which instrument this note belongs to
        const targetInstrument = findInstrumentForNote(state.score, noteId);
        if (!targetInstrument) return state;

        // Get the target instrument's score
        const targetScore = state.scores.get(targetInstrument);
        if (!targetScore) return state;

        // Update the target instrument's score
        const updatedTargetParts = targetScore.parts.map((part) => ({
          ...part,
          measures: part.measures.map((m) => ({
            ...m,
            notes: m.notes.map((n) => (n.id === noteId ? { ...n, ...changes } : n)),
          })),
        }));

        const updatedTargetScore = {
          ...targetScore,
          parts: updatedTargetParts,
          measures: updatedTargetParts[0]?.measures || [],
        };

        // Update the scores map with the modified instrument score
        const newScores = new Map(state.scores);
        newScores.set(targetInstrument, updatedTargetScore);

        // Regenerate combined score
        const newCombinedScore = createCombinedScore(newScores, state.availableInstruments);

        return {
          ...historyUpdate,
          scores: newScores,
          score: newCombinedScore,
        };
      }

      // Normal single-instrument mode
      const updatedParts = state.score.parts.map((part) => ({
        ...part,
        measures: part.measures.map((m) => ({
          ...m,
          notes: m.notes.map((n) => (n.id === noteId ? { ...n, ...changes } : n)),
        })),
      }));

      const updatedMeasures = state.score.measures?.map((m) => ({
        ...m,
        notes: m.notes.map((n) => (n.id === noteId ? { ...n, ...changes } : n)),
      })) || [];

      const updatedScore = {
        ...state.score,
        parts: updatedParts,
        measures: updatedMeasures,
      };

      const newScores = new Map(state.scores);
      newScores.set(state.activeInstrument, updatedScore);

      return {
        ...historyUpdate,
        score: updatedScore,
        scores: newScores,
      };
    }),

  selectNote: (noteId) =>
    set((state) => {
      const isSelected = state.selectedNoteIds.includes(noteId);
      return {
        selectedNoteIds: isSelected
          ? state.selectedNoteIds.filter(id => id !== noteId) // Toggle off if already selected
          : [...state.selectedNoteIds, noteId], // Toggle on if not selected
      };
    }),

  deselectAll: () => set({ selectedNoteIds: [] }),

  setCurrentTool: (tool) => set({ currentTool: tool }),

  setCurrentDuration: (duration) => set({ currentDuration: duration }),

  setCurrentPitch: (pitch) => set({ currentPitch: pitch }),

  setPlayingNoteIds: (noteIds) => set({ playingNoteIds: noteIds }),

  // Undo/Redo implementation
  undo: () =>
    set((state) => {
      if (state.historyIndex <= 0) return state; // Nothing to undo

      const newIndex = state.historyIndex - 1;
      const snapshot = state.history[newIndex];

      // Restore scores from snapshot
      const restoredScores = cloneScoresMap(snapshot.scores);

      return {
        scores: restoredScores,
        activeInstrument: snapshot.activeInstrument,
        score: restoredScores.get(snapshot.activeInstrument) || null,
        historyIndex: newIndex,
        selectedNoteIds: [], // Clear selection on undo
      };
    }),

  redo: () =>
    set((state) => {
      if (state.historyIndex >= state.history.length - 1) return state; // Nothing to redo

      const newIndex = state.historyIndex + 1;
      const snapshot = state.history[newIndex];

      // Restore scores from snapshot
      const restoredScores = cloneScoresMap(snapshot.scores);

      return {
        scores: restoredScores,
        activeInstrument: snapshot.activeInstrument,
        score: restoredScores.get(snapshot.activeInstrument) || null,
        historyIndex: newIndex,
        selectedNoteIds: [], // Clear selection on redo
      };
    }),

  canUndo: () => {
    const state = get();
    return state.historyIndex > 0;
  },

  canRedo: () => {
    const state = get();
    return state.historyIndex < state.history.length - 1;
  },

  // Copy/Paste implementation
  copyNotes: () =>
    set((state) => {
      if (!state.score || state.selectedNoteIds.length === 0) return state;

      // Find and copy selected notes
      const notesToCopy: Note[] = [];
      for (const part of state.score.parts) {
        for (const measure of part.measures) {
          for (const note of measure.notes) {
            if (state.selectedNoteIds.includes(note.id)) {
              // Deep copy note to clipboard
              notesToCopy.push(JSON.parse(JSON.stringify(note)));
            }
          }
        }
      }

      // Fallback: check legacy measures array
      if (notesToCopy.length === 0 && state.score.measures) {
        for (const measure of state.score.measures) {
          for (const note of measure.notes) {
            if (state.selectedNoteIds.includes(note.id)) {
              notesToCopy.push(JSON.parse(JSON.stringify(note)));
            }
          }
        }
      }

      return {
        clipboard: notesToCopy,
      };
    }),

  pasteNotes: (measureId: string) =>
    set((state) => {
      if (!state.score || state.clipboard.length === 0) return state;

      // Save state to history
      const historyUpdate = saveToHistory(state);

      // Find target measure
      let targetMeasure = null;
      let targetPart = null;

      for (const part of state.score.parts) {
        const measure = part.measures.find((m) => m.id === measureId);
        if (measure) {
          targetMeasure = measure;
          targetPart = part;
          break;
        }
      }

      // Fallback: check legacy measures
      if (!targetMeasure && state.score.measures) {
        targetMeasure = state.score.measures.find((m) => m.id === measureId);
      }

      if (!targetMeasure) {
        return state; // Measure not found
      }

      // Generate new IDs and paste notes
      const pastedNotes = state.clipboard.map((note) => ({
        ...note,
        id: `note-${Date.now()}-${Math.random()}`, // Generate unique ID
      }));

      // Add pasted notes to measure (sorted by startTime)
      const updatedNotes = [...targetMeasure.notes, ...pastedNotes].sort(
        (a, b) => a.startTime - b.startTime
      );

      // Update score
      let updatedScore;
      if (targetPart) {
        // Update in parts
        updatedScore = {
          ...state.score,
          parts: state.score.parts.map((part) =>
            part.id === targetPart.id
              ? {
                  ...part,
                  measures: part.measures.map((m) =>
                    m.id === measureId ? { ...m, notes: updatedNotes } : m
                  ),
                }
              : part
          ),
        };
      } else {
        // Update in legacy measures
        updatedScore = {
          ...state.score,
          measures: state.score.measures.map((m) =>
            m.id === measureId ? { ...m, notes: updatedNotes } : m
          ),
        };
      }

      // Update in scores map
      const newScores = new Map(state.scores);
      newScores.set(state.activeInstrument, updatedScore);

      return {
        ...historyUpdate,
        score: updatedScore,
        scores: newScores,
        selectedNoteIds: pastedNotes.map((n) => n.id), // Select pasted notes
      };
    }),

  hasClipboard: () => {
    const state = get();
    return state.clipboard.length > 0;
  },

  // Measure operations
  insertMeasure: (afterMeasureId: string) =>
    set((state) => {
      if (!state.score) return state;

      // Save state to history
      const historyUpdate = saveToHistory(state);

      // Update parts structure (primary)
      let measureIndex = -1;
      const updatedParts = state.score.parts.map((part) => {
        const partMeasureIndex = part.measures.findIndex((m) => m.id === afterMeasureId);
        if (partMeasureIndex !== -1) {
          measureIndex = partMeasureIndex;
        }

        if (partMeasureIndex === -1) return part;

        // Create new empty measure
        const newMeasure: Measure = {
          id: `measure-${part.id}-${Date.now()}`,
          number: partMeasureIndex + 2,
          notes: [],
        };

        // Insert measure and renumber subsequent measures
        return {
          ...part,
          measures: [
            ...part.measures.slice(0, partMeasureIndex + 1),
            newMeasure,
            ...part.measures.slice(partMeasureIndex + 1).map((m, idx) => ({
              ...m,
              number: partMeasureIndex + 3 + idx,
            })),
          ],
        };
      });

      // Also update legacy measures for backward compatibility (if it exists)
      let updatedMeasures = state.score.measures || [];
      if (updatedMeasures.length > 0) {
        const legacyIndex = updatedMeasures.findIndex((m) => m.id === afterMeasureId);
        if (legacyIndex !== -1) {
          const newMeasure: Measure = {
            id: `measure-${Date.now()}`,
            number: legacyIndex + 2,
            notes: [],
          };

          updatedMeasures = [
            ...updatedMeasures.slice(0, legacyIndex + 1),
            newMeasure,
            ...updatedMeasures.slice(legacyIndex + 1).map((m, idx) => ({
              ...m,
              number: legacyIndex + 3 + idx,
            })),
          ];
        }
      }

      const updatedScore = {
        ...state.score,
        parts: updatedParts,
        measures: updatedMeasures,
      };

      // Update in scores map
      const newScores = new Map(state.scores);
      newScores.set(state.activeInstrument, updatedScore);

      return {
        ...historyUpdate,
        score: updatedScore,
        scores: newScores,
      };
    }),

  deleteMeasure: (measureId: string) =>
    set((state) => {
      if (!state.score) return state;

      // Don't delete if it's the only measure in any part
      const hasOnlyOneMeasure = state.score.parts.some((part) => part.measures.length <= 1);
      if (hasOnlyOneMeasure) return state;

      // Save state to history
      const historyUpdate = saveToHistory(state);

      // Update parts structure (primary)
      const updatedParts = state.score.parts.map((part) => ({
        ...part,
        measures: part.measures
          .filter((m) => m.id !== measureId)
          .map((m, idx) => ({
            ...m,
            number: idx + 1,
          })),
      }));

      // Also update legacy measures for backward compatibility (if it exists)
      const updatedMeasures = state.score.measures
        ?.filter((m) => m.id !== measureId)
        .map((m, idx) => ({
          ...m,
          number: idx + 1,
        })) || [];

      const updatedScore = {
        ...state.score,
        parts: updatedParts,
        measures: updatedMeasures,
      };

      // Update in scores map
      const newScores = new Map(state.scores);
      newScores.set(state.activeInstrument, updatedScore);

      return {
        ...historyUpdate,
        score: updatedScore,
        scores: newScores,
      };
    }),
}));
