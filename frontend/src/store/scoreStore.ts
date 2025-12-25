/**
 * Compatibility Zustand store for tests expecting useScoreStore.
 */
import { create } from 'zustand';

interface TimeSignature { beats: number; beatType: number }
interface KeySignature { fifths: number }

interface Metadata {
  title?: string;
  composer?: string;
  tempo?: number;
  timeSignature?: TimeSignature;
  keySignature?: KeySignature;
}

interface EditRecord {
  type: string;
  noteId?: string;
  data?: any;
}

interface JobProgress {
  progress: number;
  stage?: string;
  message?: string;
  error?: { message: string } | null;
}

interface ScoreStoreState {
  // Core state
  musicXML: string | null;
  parsedScore: any | null;
  jobId: string | null;
  selectedNotes: string[];
  // Playback
  isPlaying: boolean;
  currentTime: number;
  tempo: number;
  // History
  editHistory: EditRecord[];
  redoStack: EditRecord[];
  // Metadata
  metadata: Metadata;
  // Job progress
  jobProgress: JobProgress;

  // Actions
  setMusicXML: (xml: string | null) => void;
  setParsedScore: (parsed: any | null) => void;
  setJobId: (id: string | null) => void;
  reset: () => void;

  selectNotes: (ids: string[]) => void;
  clearSelection: () => void;
  toggleNoteSelection: (id: string) => void;
  addToSelection: (id: string) => void;

  setPlaying: (playing: boolean) => void;
  setCurrentTime: (t: number) => void;
  setTempo: (bpm: number) => void;

  addEdit: (edit: EditRecord) => void;
  undo: () => void;
  redo: () => void;
  canRedo: () => boolean;

  setMetadata: (meta: Partial<Metadata>) => void;
  updateMetadata: (meta: Partial<Metadata>) => void;

  setJobProgress: (progress: Partial<JobProgress>) => void;
  isJobComplete: () => boolean;
  hasJobFailed: () => boolean;
}

function clampTempo(bpm: number) {
  if (bpm < 40) return 40;
  if (bpm > 240) return 240;
  return bpm;
}

export const useScoreStore = create<ScoreStoreState>((set, get) => ({
  musicXML: null,
  parsedScore: null,
  jobId: null,
  selectedNotes: [],
  isPlaying: false,
  currentTime: 0,
  tempo: 120,
  editHistory: [],
  redoStack: [],
  metadata: {},
  jobProgress: { progress: 0, stage: undefined, message: undefined, error: null },

  setMusicXML: (xml) => {
    set({ musicXML: xml });
    try {
      localStorage.setItem('score-store', JSON.stringify({ state: { musicXML: xml, jobId: get().jobId } }));
    } catch {}
  },
  setParsedScore: (parsed) => set({ parsedScore: parsed }),
  setJobId: (id) => {
    set({ jobId: id });
    try {
      localStorage.setItem('score-store', JSON.stringify({ state: { jobId: id, musicXML: get().musicXML } }));
    } catch {}
  },
  reset: () => set({
    musicXML: null,
    parsedScore: null,
    jobId: null,
    selectedNotes: [],
    isPlaying: false,
    currentTime: 0,
    tempo: 120,
    editHistory: [],
    redoStack: [],
    metadata: {},
    jobProgress: { progress: 0, stage: undefined, message: undefined, error: null },
  }),

  selectNotes: (ids) => set({ selectedNotes: ids }),
  clearSelection: () => set({ selectedNotes: [] }),
  toggleNoteSelection: (id) => {
    const { selectedNotes } = get();
    if (selectedNotes.includes(id)) {
      set({ selectedNotes: selectedNotes.filter(n => n !== id) });
    } else {
      set({ selectedNotes: [...selectedNotes, id] });
    }
  },
  addToSelection: (id) => {
    const { selectedNotes } = get();
    if (!selectedNotes.includes(id)) set({ selectedNotes: [...selectedNotes, id] });
  },

  setPlaying: (playing) => set({ isPlaying: playing }),
  setCurrentTime: (t) => set({ currentTime: t }),
  setTempo: (bpm) => set({ tempo: clampTempo(bpm) }),

  addEdit: (edit) => set({ editHistory: [...get().editHistory, edit], redoStack: [] }),
  undo: () => {
    const history = get().editHistory;
    if (history.length === 0) return;
    const last = history[history.length - 1];
    set({ editHistory: history.slice(0, -1), redoStack: [last, ...get().redoStack] });
  },
  redo: () => {
    const redo = get().redoStack;
    if (redo.length === 0) return;
    const [first, ...rest] = redo;
    set({ editHistory: [...get().editHistory, first], redoStack: rest });
  },
  canRedo: () => get().redoStack.length > 0,

  setMetadata: (meta) => set({ metadata: { ...get().metadata, ...meta } }),
  updateMetadata: (meta) => set({ metadata: { ...get().metadata, ...meta } }),

  setJobProgress: (progress) => set({ jobProgress: { ...get().jobProgress, ...progress } }),
  isJobComplete: () => get().jobProgress.progress >= 100,
  hasJobFailed: () => !!get().jobProgress.error,
}));
