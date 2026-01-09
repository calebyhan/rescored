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
  playingNoteIds: string[]; // Notes currently being played (for visual feedback)

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
  setPlayingNoteIds: (noteIds: string[]) => void;
}

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
  playingNoteIds: [],

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

      // Update tempo in active score
      const updatedScore = { ...state.score, tempo };

      // Update in scores map
      const newScores = new Map(state.scores);
      newScores.set(state.activeInstrument, updatedScore);

      return {
        score: updatedScore,
        scores: newScores,
      };
    }),

  addNote: (measureId, note) =>
    set((state) => {
      if (!state.score) return state;

      return {
        score: {
          ...state.score,
          measures: state.score.measures.map((m) =>
            m.id === measureId
              ? { ...m, notes: [...m.notes, note].sort((a, b) => a.startTime - b.startTime) }
              : m
          ),
        },
      };
    }),

  deleteNote: (noteId) =>
    set((state) => {
      if (!state.score) return state;

      return {
        score: {
          ...state.score,
          measures: state.score.measures.map((m) => ({
            ...m,
            notes: m.notes.filter((n) => n.id !== noteId),
          })),
        },
      };
    }),

  updateNote: (noteId, changes) =>
    set((state) => {
      if (!state.score) return state;

      return {
        score: {
          ...state.score,
          measures: state.score.measures.map((m) => ({
            ...m,
            notes: m.notes.map((n) => (n.id === noteId ? { ...n, ...changes } : n)),
          })),
        },
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

  setPlayingNoteIds: (noteIds) => set({ playingNoteIds: noteIds }),
}));
