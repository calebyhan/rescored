# Interactive Notation Editor

## Overview

The editor allows users to modify transcribed notation directly in the browser: add/delete notes, change durations, transpose passages, and adjust musical parameters.

## MVP Editor Features

### Phase 1 (Minimum Viable Product)
- **Add Note**: Click on staff to add new note
- **Delete Note**: Click note + Delete key or right-click → Delete
- **Move Note**: Drag note vertically to change pitch
- **Change Duration**: Select note, press number key (1=whole, 2=half, 4=quarter, 8=eighth)

### Phase 2 (Future)
- Copy/paste, multi-select
- Transpose selection
- Add articulations (staccato, accents)
- Lyrics, dynamics
- Undo/redo stack

---

## State Management

### Notation State Structure

```typescript
interface NotationState {
  score: {
    id: string;
    title: string;
    composer: string;
    key: string;  // e.g., "C", "Gm"
    timeSignature: string;  // e.g., "4/4"
    tempo: number;  // BPM
    measures: Measure[];
  };
  selectedNoteIds: string[];
  clipboard: Note[] | null;
  history: NotationState[];  // For undo/redo
  historyIndex: number;
}

interface Measure {
  id: string;
  number: number;
  notes: Note[];
}

interface Note {
  id: string;
  pitch: string;  // e.g., "C4", "F#5"
  duration: string;  // "whole", "half", "quarter", "eighth", "16th"
  octave: number;
  dotted: boolean;
  accidental?: 'sharp' | 'flat' | 'natural';
}
```

### Zustand Store

```typescript
import create from 'zustand';

interface NotationStore extends NotationState {
  // Actions
  addNote: (measureId: string, note: Note) => void;
  deleteNote: (noteId: string) => void;
  updateNote: (noteId: string, changes: Partial<Note>) => void;
  selectNote: (noteId: string) => void;
  deselectAll: () => void;
  undo: () => void;
  redo: () => void;
}

export const useNotationStore = create<NotationStore>((set, get) => ({
  score: { /* initial state */ },
  selectedNoteIds: [],
  clipboard: null,
  history: [],
  historyIndex: -1,

  addNote: (measureId, note) => set(state => {
    const measure = state.score.measures.find(m => m.id === measureId);
    if (!measure) return state;

    return {
      score: {
        ...state.score,
        measures: state.score.measures.map(m =>
          m.id === measureId
            ? { ...m, notes: [...m.notes, note].sort(byTimestamp) }
            : m
        ),
      },
    };
  }),

  deleteNote: (noteId) => set(state => ({
    score: {
      ...state.score,
      measures: state.score.measures.map(m => ({
        ...m,
        notes: m.notes.filter(n => n.id !== noteId),
      })),
    },
  })),

  updateNote: (noteId, changes) => set(state => ({
    score: {
      ...state.score,
      measures: state.score.measures.map(m => ({
        ...m,
        notes: m.notes.map(n =>
          n.id === noteId ? { ...n, ...changes } : n
        ),
      })),
    },
  })),

  selectNote: (noteId) => set({ selectedNoteIds: [noteId] }),
  deselectAll: () => set({ selectedNoteIds: [] }),

  undo: () => {
    const { history, historyIndex } = get();
    if (historyIndex > 0) {
      set(history[historyIndex - 1]);
      set({ historyIndex: historyIndex - 1 });
    }
  },

  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex < history.length - 1) {
      set(history[historyIndex + 1]);
      set({ historyIndex: historyIndex + 1 });
    }
  },
}));
```

---

## Edit Operations

### 1. Add Note

**User Action**: Click on staff at desired pitch/time

```typescript
function handleStaffClick(event: MouseEvent, staveElement: SVGElement) {
  // Get click position relative to stave
  const rect = staveElement.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;

  // Convert Y position to pitch
  const pitch = yPositionToPitch(y, stave.clef);

  // Convert X position to time (measure + beat)
  const { measureId, beat } = xPositionToTime(x, stave.width);

  // Create new note
  const newNote: Note = {
    id: generateId(),
    pitch: pitch,
    duration: currentDuration,  // From toolbar
    octave: parseInt(pitch.slice(-1)),
    dotted: false,
  };

  // Add to state
  useNotationStore.getState().addNote(measureId, newNote);
}

function yPositionToPitch(y: number, clef: 'treble' | 'bass'): string {
  // Map Y pixel to line/space on staff
  // Treble clef: E5 (top line) to F4 (bottom line)
  // Each line/space is ~10px
  const lineHeight = 10;
  const pitches = clef === 'treble'
    ? ['F5', 'E5', 'D5', 'C5', 'B4', 'A4', 'G4', 'F4', 'E4']
    : ['A3', 'G3', 'F3', 'E3', 'D3', 'C3', 'B2', 'A2', 'G2'];

  const index = Math.floor(y / lineHeight);
  return pitches[index] || 'C4';
}
```

---

### 2. Delete Note

**User Action**: Select note, press Delete key

```typescript
useEffect(() => {
  function handleKeyDown(event: KeyboardEvent) {
    const { selectedNoteIds, deleteNote } = useNotationStore.getState();

    if (event.key === 'Delete' || event.key === 'Backspace') {
      selectedNoteIds.forEach(id => deleteNote(id));
    }
  }

  window.addEventListener('keydown', handleKeyDown);
  return () => window.removeEventListener('keydown', handleKeyDown);
}, []);
```

---

### 3. Move Note (Change Pitch)

**User Action**: Drag note vertically

```typescript
function handleNoteDrag(noteId: string, event: MouseEvent) {
  const startY = event.clientY;
  let currentY = startY;

  function onMouseMove(e: MouseEvent) {
    currentY = e.clientY;
    const deltaY = currentY - startY;

    // Convert delta to semitones (10px per semitone)
    const semitoneShift = Math.round(deltaY / 10);

    // Update note pitch
    const originalNote = findNoteById(noteId);
    const newPitch = transposePitch(originalNote.pitch, semitoneShift);

    useNotationStore.getState().updateNote(noteId, { pitch: newPitch });

    // Re-render VexFlow
    renderNotation();
  }

  function onMouseUp() {
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

function transposePitch(pitch: string, semitones: number): string {
  const pitchMap = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const [note, octaveStr] = [pitch.slice(0, -1), pitch.slice(-1)];
  let octave = parseInt(octaveStr);

  let index = pitchMap.indexOf(note);
  index += semitones;

  // Handle octave wrap
  while (index < 0) {
    index += 12;
    octave--;
  }
  while (index >= 12) {
    index -= 12;
    octave++;
  }

  return `${pitchMap[index]}${octave}`;
}
```

---

### 4. Change Duration

**User Action**: Select note, press number key

```typescript
const durationKeyMap: { [key: string]: string } = {
  '1': 'whole',
  '2': 'half',
  '4': 'quarter',
  '8': 'eighth',
  '6': '16th',  // 6 for 16th note
};

useEffect(() => {
  function handleKeyDown(event: KeyboardEvent) {
    const { selectedNoteIds, updateNote } = useNotationStore.getState();
    const newDuration = durationKeyMap[event.key];

    if (newDuration && selectedNoteIds.length > 0) {
      selectedNoteIds.forEach(id => {
        updateNote(id, { duration: newDuration });
      });

      renderNotation();  // Re-render
    }
  }

  window.addEventListener('keydown', handleKeyDown);
  return () => window.removeEventListener('keydown', handleKeyDown);
}, []);
```

---

## UI Components

### Toolbar

```typescript
export const EditorToolbar: React.FC = () => {
  const [selectedTool, setSelectedTool] = useState<'select' | 'add' | 'delete'>('select');
  const [selectedDuration, setSelectedDuration] = useState<string>('quarter');

  return (
    <div className="editor-toolbar">
      <ToolButton
        icon="cursor"
        active={selectedTool === 'select'}
        onClick={() => setSelectedTool('select')}
        tooltip="Select (V)"
      />
      <ToolButton
        icon="plus"
        active={selectedTool === 'add'}
        onClick={() => setSelectedTool('add')}
        tooltip="Add Note (A)"
      />
      <ToolButton
        icon="trash"
        active={selectedTool === 'delete'}
        onClick={() => setSelectedTool('delete')}
        tooltip="Delete (D)"
      />

      <Divider />

      <DurationSelector value={selectedDuration} onChange={setSelectedDuration} />

      <Divider />

      <ToolButton icon="undo" onClick={() => useNotationStore.getState().undo()} tooltip="Undo (Cmd+Z)" />
      <ToolButton icon="redo" onClick={() => useNotationStore.getState().redo()} tooltip="Redo (Cmd+Shift+Z)" />
    </div>
  );
};
```

### Context Menu (Right-Click)

```typescript
export const NoteContextMenu: React.FC<{ noteId: string, position: { x: number, y: number } }> = ({ noteId, position }) => {
  const { deleteNote, updateNote } = useNotationStore();

  return (
    <Menu style={{ top: position.y, left: position.x }}>
      <MenuItem onClick={() => deleteNote(noteId)}>Delete</MenuItem>
      <MenuItem onClick={() => updateNote(noteId, { dotted: true })}>Add Dot</MenuItem>
      <MenuItem onClick={() => { /* transpose logic */ }}>Transpose...</MenuItem>
    </Menu>
  );
};
```

---

## Keyboard Shortcuts

```typescript
const shortcuts = {
  'v': 'select tool',
  'a': 'add note tool',
  'd': 'delete tool',
  '1-8': 'change duration',
  'Delete': 'delete selected',
  'Cmd+Z': 'undo',
  'Cmd+Shift+Z': 'redo',
  'Cmd+C': 'copy',
  'Cmd+V': 'paste',
  'ArrowUp': 'transpose up',
  'ArrowDown': 'transpose down',
};
```

---

## Undo/Redo Implementation

```typescript
// Save state before every mutation
function saveHistory() {
  const state = useNotationStore.getState();
  const newHistory = state.history.slice(0, state.historyIndex + 1);
  newHistory.push(state);

  set({
    history: newHistory,
    historyIndex: newHistory.length - 1,
  });
}

// Call before mutations
addNote: (measureId, note) => {
  saveHistory();
  // ... perform mutation
}
```

---

## Validation

### Prevent Invalid Edits

```typescript
function validateNote(note: Note, measure: Measure): string | null {
  // Check measure capacity (e.g., 4/4 = 4 beats max)
  const totalBeats = measure.notes.reduce((sum, n) => sum + durationToBeats(n.duration), 0);

  if (totalBeats + durationToBeats(note.duration) > measure.maxBeats) {
    return 'Measure is full';
  }

  // Check pitch range for instrument
  if (!isPitchInRange(note.pitch, 'piano')) {
    return 'Pitch out of range for piano';
  }

  return null;  // Valid
}
```

---

## Next Steps

1. Implement [Playback System](playback.md) to hear edited notation
2. Add advanced features (copy/paste, multi-select)
3. Test editing with complex scores

See [Data Flow](data-flow.md) for how state propagates through the app.
