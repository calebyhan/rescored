/**
 * Zustand store for notation state management.
 */
import { create } from 'zustand';
import { parseMusicXML } from '../utils/musicxml-parser';
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
  score: Score | null;
  selectedNoteIds: string[];
  currentTool: 'select' | 'add' | 'delete';
  currentDuration: string;
  playingNoteIds: string[]; // Notes currently being played (for visual feedback)

  // Actions
  loadFromMusicXML: (xml: string) => void;
  loadFromMidi: (
    midiData: ArrayBuffer,
    metadata?: {
      tempo?: number;
      keySignature?: string;
      timeSignature?: { numerator: number; denominator: number };
    }
  ) => Promise<void>;
  exportToMusicXML: () => string;
  addNote: (measureId: string, note: Note) => void;
  deleteNote: (noteId: string) => void;
  updateNote: (noteId: string, changes: Partial<Note>) => void;
  selectNote: (noteId: string) => void;
  deselectAll: () => void;
  setCurrentTool: (tool: 'select' | 'add' | 'delete') => void;
  setCurrentDuration: (duration: string) => void;
  setPlayingNoteIds: (noteIds: string[]) => void;
}

export const useNotationStore = create<NotationState>((set, _get) => ({
  score: null,
  selectedNoteIds: [],
  currentTool: 'select',
  currentDuration: 'quarter',
  playingNoteIds: [],

  loadFromMusicXML: (xml: string) => {
    try {
      const score = parseMusicXML(xml);
      set({ score });
    } catch (error) {
      console.error('Failed to parse MusicXML:', error);
      // Fallback to empty score
      set({
        score: {
          id: 'score-1',
          title: 'Transcribed Score',
          composer: 'Unknown',
          key: 'C',
          timeSignature: '4/4',
          tempo: 120,
          parts: [],
          measures: [],
        },
      });
    }
  },

  loadFromMidi: async (midiData, metadata) => {
    try {
      let score = await parseMidiFile(midiData, {
        tempo: metadata?.tempo,
        timeSignature: metadata?.timeSignature,
        keySignature: metadata?.keySignature,
        splitAtMiddleC: true,
        middleCNote: 60,
      });

      // Assign chord IDs to simultaneous notes
      score = assignChordIds(score);

      set({ score });
    } catch (error) {
      console.error('Failed to parse MIDI:', error);
      // Fallback to empty score
      set({
        score: {
          id: 'score-1',
          title: 'Transcribed Score',
          composer: 'YourMT3+',
          key: metadata?.keySignature || 'C',
          timeSignature: metadata?.timeSignature
            ? `${metadata.timeSignature.numerator}/${metadata.timeSignature.denominator}`
            : '4/4',
          tempo: metadata?.tempo || 120,
          parts: [],
          measures: [],
        },
      });
    }
  },

  exportToMusicXML: () => {
    // TODO: Implement MusicXML generation
    return '<?xml version="1.0"?><score-partwise></score-partwise>';
  },

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

  selectNote: (noteId) => set({ selectedNoteIds: [noteId] }),

  deselectAll: () => set({ selectedNoteIds: [] }),

  setCurrentTool: (tool) => set({ currentTool: tool }),

  setCurrentDuration: (duration) => set({ currentDuration: duration }),

  setPlayingNoteIds: (noteIds) => set({ playingNoteIds: noteIds }),
}));
