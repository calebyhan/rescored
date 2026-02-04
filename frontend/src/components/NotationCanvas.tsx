/**
 * VexFlow notation rendering component.
 *
 * Supports grand staff (treble + bass clefs) for piano.
 */
import { useEffect, useRef } from 'react';
import { Renderer, Stave, StaveNote, Voice, Formatter, Accidental, StaveConnector } from 'vexflow';
import { useNotationStore } from '../store/notation';
import type { Note, Part } from '../store/notation';
import './NotationCanvas.css';

interface NotationCanvasProps {
  showControls?: boolean;
  interactive?: boolean;
  onNoteSelect?: (id: string, shiftKey?: boolean) => void;
  selectedNotes?: string[];
  showMeasureNumbers?: boolean;
  width?: number;
  height?: number;
  currentTool?: string;
}

export function NotationCanvas({ showControls, interactive, onNoteSelect, selectedNotes, showMeasureNumbers, width, height, currentTool }: NotationCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const score = useNotationStore((state) => state.score);
  const playingNoteIds = useNotationStore((state) => state.playingNoteIds);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear previous render
    containerRef.current.innerHTML = '';

    if (!score || !score.parts.length) {
      return;
    }

    const measuresPerRow = 4;
    const staveWidth = 240;
    const staveHeight = 100; // Height for one staff
    const partSpacing = 20; // Spacing between parts within a system
    const systemSpacing = 40; // Extra spacing between systems (rows)
    const numMeasures = score.parts[0]?.measures.length || 0;
    const numRows = Math.ceil(numMeasures / measuresPerRow);

    // Group parts by instrument (for combined "All Instruments" view)
    const instrumentGroups = groupPartsByInstrument(score.parts);

    // Calculate height needed for one system (row of measures)
    // Each system contains all parts stacked vertically
    let systemHeight = systemSpacing; // Top margin
    instrumentGroups.forEach(parts => {
      if (parts.length >= 2 && arePartsFromSameInstrument(parts)) {
        // Grand staff: two staves close together
        systemHeight += staveHeight + partSpacing + staveHeight + partSpacing;
      } else {
        // Single staff for each part
        parts.forEach(() => {
          systemHeight += staveHeight + partSpacing;
        });
      }
    });

    const totalHeight = systemHeight * numRows + 100;

    // Create renderer
    const renderer = new Renderer(containerRef.current, Renderer.Backends.SVG);
    renderer.resize(width || (measuresPerRow * staveWidth + 20), height || totalHeight);
    const context = renderer.getContext();

    // Render measure-by-measure with all instruments aligned vertically
    for (let measureIdx = 0; measureIdx < numMeasures; measureIdx++) {
      const row = Math.floor(measureIdx / measuresPerRow);
      const col = measureIdx % measuresPerRow;
      const x = 10 + col * staveWidth;
      let yOffset = systemSpacing + row * systemHeight;

      // Render all instrument groups for this measure
      instrumentGroups.forEach((parts, groupIdx) => {
        if (parts.length >= 2 && arePartsFromSameInstrument(parts)) {
          // Grand staff (treble + bass) for piano
          const { trebleStave, bassStave } = renderGrandStaffMeasure(
            context,
            parts,
            measureIdx,
            col,
            row,
            x,
            yOffset,
            staveWidth,
            staveHeight,
            partSpacing,
            score,
            containerRef.current
          );
          yOffset += staveHeight + partSpacing + staveHeight + partSpacing;
        } else {
          // Single staff for each part
          parts.forEach(part => {
            renderSingleStaffMeasure(
              context,
              part,
              measureIdx,
              col,
              row,
              x,
              yOffset,
              staveWidth,
              staveHeight,
              score,
              containerRef.current
            );
            yOffset += staveHeight + partSpacing;
          });
        }
      });
    }
  }, [score]);

  // Highlight playing notes
  useEffect(() => {
    if (!containerRef.current) return;

    // Remove all previous highlights
    const allNotes = containerRef.current.querySelectorAll('.vf-stavenote');
    allNotes.forEach((noteEl) => {
      noteEl.classList.remove('playing');
    });

    // If no notes are playing, we're done
    if (playingNoteIds.length === 0) return;

    // IMPROVED: Highlight by exact note ID
    playingNoteIds.forEach((noteId) => {
      // Find SVG element with matching note ID
      // Note: For chords, data-note-id contains comma-separated IDs
      const noteElements = containerRef.current?.querySelectorAll('.vf-stavenote[data-note-id]');
      noteElements?.forEach((noteElement) => {
        const dataIds = noteElement.getAttribute('data-note-id');
        if (dataIds && dataIds.split(',').includes(noteId)) {
          noteElement.classList.add('playing');
        }
      });
    });
  }, [playingNoteIds]);

  // Highlight selected notes
  useEffect(() => {
    if (!containerRef.current) return;

    // Remove all previous selections
    const allNotes = containerRef.current.querySelectorAll('.vf-stavenote');
    allNotes.forEach((noteEl) => {
      noteEl.classList.remove('selected');
    });

    // If no notes are selected, we're done
    if (!selectedNotes || selectedNotes.length === 0) return;

    // Highlight selected notes
    selectedNotes.forEach((noteId) => {
      const noteElements = containerRef.current?.querySelectorAll('.vf-stavenote[data-note-id]');
      noteElements?.forEach((noteElement) => {
        const dataIds = noteElement.getAttribute('data-note-id');
        if (dataIds && dataIds.split(',').includes(noteId)) {
          noteElement.classList.add('selected');
        }
      });
    });
  }, [selectedNotes]);

  // Add click handlers for interactive mode
  useEffect(() => {
    if (!containerRef.current || !interactive || !onNoteSelect) return;

    const noteElements = containerRef.current.querySelectorAll('.vf-stavenote[data-note-id]');

    const handleNoteClick = (event: Event) => {
      const mouseEvent = event as MouseEvent;
      const target = event.currentTarget as SVGElement;
      const dataIds = target.getAttribute('data-note-id');

      if (dataIds) {
        // For chords (comma-separated IDs), select all notes in the chord
        const noteIds = dataIds.split(',');
        noteIds.forEach(id => onNoteSelect(id, mouseEvent.shiftKey));
      }
    };

    // Attach click handlers and set cursor style
    noteElements.forEach((elem) => {
      elem.addEventListener('click', handleNoteClick);
      (elem as SVGElement).style.cursor = 'pointer';
    });

    // Cleanup function to remove event listeners
    return () => {
      noteElements.forEach((elem) => {
        elem.removeEventListener('click', handleNoteClick);
        (elem as SVGElement).style.cursor = '';
      });
    };
  }, [score, interactive, onNoteSelect]); // Re-run when score changes

  // Add note mode: click on staff to add notes
  useEffect(() => {
    if (!containerRef.current || !interactive) return;

    const { currentTool } = useNotationStore.getState();
    if (currentTool !== 'add') return;

    const handleStaffClick = (event: MouseEvent) => {
      const target = event.target as SVGElement;

      // Ignore clicks on existing notes
      if (target.closest('.vf-stavenote')) {
        return;
      }

      const svg = containerRef.current?.querySelector('svg');
      if (!svg) return;

      const rect = svg.getBoundingClientRect();
      const x = event.clientX - rect.left - 10;
      const y = event.clientY - rect.top;

      const { score, currentDuration, addNote, activeInstrument } = useNotationStore.getState();
      if (!score) return;

      // Convert position to measure/pitch
      const noteInfo = positionToNoteInfo(x, y, score, activeInstrument);
      if (!noteInfo) return;

      const { measureId, pitch, startTime } = noteInfo;

      // Create new note
      const newNote: Note = {
        id: `note-${Date.now()}-${Math.random()}`,
        pitch: pitch,
        duration: currentDuration || 'quarter',
        octave: parseInt(pitch.slice(-1)),
        dotted: false,
        isRest: false,
        startTime: startTime,
      };

      addNote(measureId, newNote);
    };

    const svg = containerRef.current?.querySelector('svg');
    if (svg) {
      svg.addEventListener('click', handleStaffClick);
      return () => svg.removeEventListener('click', handleStaffClick);
    }
  }, [score, interactive, currentTool]);

  return (
    <div className="notation-canvas-wrapper">
      {currentTool === 'add' && (
        <div className="add-mode-indicator">
          Add Mode (A) - Click staff to add notes
        </div>
      )}
      {showControls && (
        <div className="controls">
          <button aria-label="Zoom In">+</button>
          <button aria-label="Zoom Out">-</button>
        </div>
      )}
      <div
        ref={containerRef}
        className={`notation-canvas ${currentTool === 'add' ? 'add-mode' : ''}`}
      />
    </div>
  );
}

export default NotationCanvas;

/**
 * Group parts by instrument for "All Instruments" view
 * Returns an array of part groups, where each group represents one instrument
 */
function groupPartsByInstrument(parts: Part[]): Part[][] {
  // For combined score with multiple instruments, group by instrument name
  const groups = new Map<string, Part[]>();

  for (const part of parts) {
    // Extract instrument name from part name (e.g., "Piano - Right Hand" -> "Piano")
    const instrumentName = part.name.split(' - ')[0] || part.name;

    if (!groups.has(instrumentName)) {
      groups.set(instrumentName, []);
    }
    groups.get(instrumentName)!.push(part);
  }

  return Array.from(groups.values());
}

/**
 * Check if parts are from the same instrument (for grand staff detection)
 */
function arePartsFromSameInstrument(parts: Part[]): boolean {
  if (parts.length < 2) return false;

  // Check if all parts have the same instrument prefix
  const firstInstrument = parts[0].name.split(' - ')[0];
  return parts.every(part => part.name.startsWith(firstInstrument));
}

/**
 * Convert key signature from music21 format (e.g., "A major", "F# minor")
 * to VexFlow format (e.g., "A", "F#")
 */
function convertKeySignature(key: string): string {
  if (!key) return 'C';
  // Remove " major" or " minor" suffix
  return key.replace(/ major| minor/gi, '').trim();
}

/**
 * Render a single measure of grand staff with treble and bass clefs connected by brace
 */
function renderGrandStaffMeasure(
  context: any,
  parts: Part[],
  measureIdx: number,
  col: number,
  row: number,
  x: number,
  yOffset: number,
  staveWidth: number,
  staveHeight: number,
  partSpacing: number,
  score: any,
  containerRef?: HTMLDivElement | null
): { trebleStave: Stave; bassStave: Stave } {
  const treblePart = parts[0]; // Treble clef (right hand)
  const bassPart = parts[1];   // Bass clef (left hand)

  const yTreble = yOffset;
  const yBass = yTreble + staveHeight + partSpacing;

  // Create treble stave
  const trebleStave = new Stave(x, yTreble, staveWidth);
  if (col === 0) {
    trebleStave.addClef('treble');
    trebleStave.addTimeSignature(score.timeSignature);
    const vexflowKey = convertKeySignature(score.key);
    if (vexflowKey && vexflowKey !== 'C') {
      trebleStave.addKeySignature(vexflowKey);
    }
    // Add instrument label on first system
    if (row === 0) {
      const instrumentName = treblePart.name.split(' - ')[0] || 'Piano';
      trebleStave.setText(instrumentName, 3, { shift_x: -60, shift_y: 0 });
    }
  }
  trebleStave.setContext(context).draw();

  // Create bass stave
  const bassStave = new Stave(x, yBass, staveWidth);
  if (col === 0) {
    bassStave.addClef('bass');
    bassStave.addTimeSignature(score.timeSignature);
    const vexflowKey = convertKeySignature(score.key);
    if (vexflowKey && vexflowKey !== 'C') {
      bassStave.addKeySignature(vexflowKey);
    }
  }
  bassStave.setContext(context).draw();

  // Connect staves with brace (only at start of each system)
  if (col === 0) {
    const connector = new StaveConnector(trebleStave, bassStave);
    connector.setType(StaveConnector.type.BRACE);
    connector.setContext(context).draw();

    // Also add a line connector
    const lineConnector = new StaveConnector(trebleStave, bassStave);
    lineConnector.setType(StaveConnector.type.SINGLE_LEFT);
    lineConnector.setContext(context).draw();
  }

  // Render notes for both staves
  if (treblePart.measures[measureIdx]?.notes.length > 0) {
    renderMeasureNotes(context, trebleStave, treblePart.measures[measureIdx].notes, score.timeSignature, containerRef);
  }

  if (bassPart.measures[measureIdx]?.notes.length > 0) {
    renderMeasureNotes(context, bassStave, bassPart.measures[measureIdx].notes, score.timeSignature, containerRef);
  }

  return { trebleStave, bassStave };
}

/**
 * Render a single measure of a single staff
 */
function renderSingleStaffMeasure(
  context: any,
  part: Part,
  measureIdx: number,
  col: number,
  row: number,
  x: number,
  yOffset: number,
  staveWidth: number,
  staveHeight: number,
  score: any,
  containerRef?: HTMLDivElement | null
): Stave {
  const measure = part.measures[measureIdx];
  const stave = new Stave(x, yOffset, staveWidth);

  if (col === 0) {
    stave.addClef(part.clef);
    stave.addTimeSignature(score.timeSignature);
    const vexflowKey = convertKeySignature(score.key);
    if (vexflowKey && vexflowKey !== 'C') {
      stave.addKeySignature(vexflowKey);
    }
    // Add instrument label on first system
    if (row === 0) {
      stave.setText(part.name || 'Instrument', 3, { shift_x: -60, shift_y: 0 });
    }
  }

  stave.setContext(context).draw();

  if (measure?.notes.length > 0) {
    renderMeasureNotes(context, stave, measure.notes, score.timeSignature, containerRef);
  }

  return stave;
}

/**
 * Render notes for a single measure, handling chords properly
 */
function renderMeasureNotes(
  context: any,
  stave: Stave,
  notes: Note[],
  timeSignature: string,
  containerRef?: HTMLDivElement | null
): void {
  try {
    // Group notes by chordId (trust the parser's chord grouping from MIDI)
    // This is more accurate than re-detecting chords by duration
    const noteGroups: Record<string, Note[]> = notes.reduce((groups, note) => {
      const groupId = note.chordId || `single-${note.id}`;
      if (!groups[groupId]) groups[groupId] = [];
      groups[groupId].push(note);
      return groups;
    }, {} as Record<string, Note[]>);

    // Convert each group to VexFlow note
    const vexNotes: StaveNote[] = [];
    for (const group of Object.values(noteGroups)) {
      try {
        if (group[0].isRest) {
          // Rests are always single
          vexNotes.push(convertToVexNote(group[0]));
        } else if (group.length === 1) {
          // Single note
          vexNotes.push(convertToVexNote(group[0]));
        } else {
          // Chord (multiple notes with same chordId)
          vexNotes.push(convertToVexChord(group));
        }
      } catch (err) {
        // Skip invalid note/chord
        console.warn('Failed to convert note/chord:', err);
      }
    }

    // Handle empty measures by rendering a whole rest
    if (vexNotes.length === 0) {
      const [beats, beatValue] = timeSignature.split('/').map(Number);
      // Use whole rest for 4/4, half rest for 2/4, etc.
      const restDuration = beats >= 4 ? 'w' : beats >= 2 ? 'h' : 'q';

      const wholeRest = new StaveNote({
        keys: ['b/4'],
        duration: restDuration + 'r',
      });

      const voice = new Voice({ num_beats: beats, beat_value: beatValue });
      voice.setMode(Voice.Mode.SOFT);
      voice.addTickables([wholeRest]);

      const formatter = new Formatter();
      formatter.joinVoices([voice]).format([voice], stave.getWidth() - 20);
      voice.draw(context, stave);
      return;
    }

    // Create voice - use SOFT mode for now to handle incomplete measures gracefully
    const [beats, beatValue] = timeSignature.split('/').map(Number);
    const voice = new Voice({
      num_beats: beats,
      beat_value: beatValue,
    });
    voice.setMode(Voice.Mode.SOFT);
    voice.addTickables(vexNotes);

    // Format and draw
    const formatter = new Formatter();
    formatter.joinVoices([voice]).format([voice], stave.getWidth() - 20);
    voice.draw(context, stave);

    // Attach note IDs to SVG elements for accurate playback highlighting
    if (containerRef) {
      const svgNotes = containerRef.querySelectorAll('.vf-stavenote');
      const tickables = voice.getTickables();

      // Map note group indices to actual note IDs
      let noteGroupIndex = 0;
      for (const group of Object.values(noteGroups)) {
        const svgElement = svgNotes[svgNotes.length - tickables.length + noteGroupIndex];
        if (svgElement && group.length > 0) {
          // For chords, store all note IDs (comma-separated)
          const noteIds = group.map(n => n.id).join(',');
          svgElement.setAttribute('data-note-id', noteIds);
        }
        noteGroupIndex++;
      }
    }
  } catch (error) {
    // Silently skip measures that fail to render
    console.warn('Failed to render measure:', error);
  }
}

/**
 * Convert multiple notes to a VexFlow chord
 */
function convertToVexChord(notes: Note[]): StaveNote {
  if (notes.length === 0) {
    throw new Error('Cannot create chord from empty notes array');
  }

  // Map duration to VexFlow codes
  const durationMap: Record<string, string> = {
    'whole': 'w',
    'half': 'h',
    'quarter': 'q',
    'eighth': '8',
    '16th': '16',
    '32nd': '32',
  };

  const vexDuration = durationMap[notes[0].duration] || 'q';
  const duration = notes[0].dotted ? vexDuration + 'd' : vexDuration;

  // Convert all notes to VexFlow keys and collect accidentals
  const keys: string[] = [];
  const accidentals: { index: number; type: string }[] = [];

  for (let i = 0; i < notes.length; i++) {
    const note = notes[i];

    if (!note.pitch || typeof note.pitch !== 'string') {
      continue; // Skip invalid pitches
    }

    // Parse pitch: expect format like "C4", "F#5", "Bb3"
    const pitchMatch = note.pitch.match(/^([A-G])([#b]?)(\d)$/);
    if (!pitchMatch) {
      continue; // Skip invalid format
    }

    const [, letter, accidental, octave] = pitchMatch;

    // Validate octave
    const octaveNum = parseInt(octave);
    if (octaveNum < 0 || octaveNum > 9) {
      continue; // Skip out of range
    }

    // Build VexFlow key (e.g., "c/4")
    const vexKey = letter.toLowerCase() + '/' + octave;
    keys.push(vexKey);

    // Track accidentals
    if (accidental === '#') {
      accidentals.push({ index: i, type: '#' });
    } else if (accidental === 'b') {
      accidentals.push({ index: i, type: 'b' });
    }
  }

  if (keys.length === 0) {
    throw new Error('No valid pitches in chord');
  }

  // Sort keys from lowest to highest (VexFlow requirement for chords)
  keys.sort();

  // Create the chord
  const staveNote = new StaveNote({
    keys,
    duration,
  });

  // Add accidentals to the corresponding keys
  accidentals.forEach(({ index, type }) => {
    staveNote.addModifier(new Accidental(type), index);
  });

  return staveNote;
}

/**
 * Convert our Note format to VexFlow StaveNote (including rests)
 */
function convertToVexNote(note: Note): StaveNote {
  // Map duration to VexFlow codes
  const durationMap: Record<string, string> = {
    'whole': 'w',
    'half': 'h',
    'quarter': 'q',
    'eighth': '8',
    '16th': '16',
    '32nd': '32',
  };

  const vexDuration = durationMap[note.duration] || 'q';
  const duration = note.dotted ? vexDuration + 'd' : vexDuration;

  // Handle rests
  if (note.isRest) {
    return new StaveNote({
      keys: ['b/4'], // Rest position (doesn't matter for rests)
      duration: duration + 'r', // Add 'r' suffix for rest
    });
  }

  // Handle pitched notes
  if (!note.pitch || typeof note.pitch !== 'string') {
    throw new Error(`Invalid pitch: ${note.pitch}`);
  }

  // Parse pitch: expect format like "C4", "F#5", "Bb3"
  const pitchMatch = note.pitch.match(/^([A-G])([#b]?)(\d)$/);
  if (!pitchMatch) {
    throw new Error(`Invalid pitch format: ${note.pitch}`);
  }

  const [, letter, accidental, octave] = pitchMatch;

  // Validate octave
  const octaveNum = parseInt(octave);
  if (octaveNum < 0 || octaveNum > 9) {
    throw new Error(`Octave out of range: ${octave}`);
  }

  // Build VexFlow key (e.g., "c/4")
  const vexKey = letter.toLowerCase() + '/' + octave;

  // Create the note
  const staveNote = new StaveNote({
    keys: [vexKey],
    duration,
  });

  // Add accidental if present
  if (accidental === '#') {
    staveNote.addModifier(new Accidental('#'), 0);
  } else if (accidental === 'b') {
    staveNote.addModifier(new Accidental('b'), 0);
  }

  return staveNote;
}

/**
 * Convert click position to note information
 * Supports both single instrument and "All Instruments" view
 */
function positionToNoteInfo(
  x: number,
  y: number,
  score: any,
  activeInstrument: string
): { measureId: string; pitch: string; startTime: number } | null {
  const measuresPerRow = 4;
  const staveWidth = 240;
  const staveHeight = 100;
  const partSpacing = 20;
  const systemSpacing = 40;

  // Determine column
  const col = Math.floor(x / staveWidth);
  if (col < 0 || col >= measuresPerRow) return null;

  // Determine which system and part
  const numMeasures = score.parts[0]?.measures.length || 0;
  let yOffset = systemSpacing;
  let row = 0;

  // Group parts by instrument (for "All" view)
  const instrumentGroups = groupPartsByInstrument(score.parts);

  for (row = 0; row < Math.ceil(numMeasures / measuresPerRow); row++) {
    let systemHeight = 0;

    // Iterate through instrument groups in this system
    for (const parts of instrumentGroups) {
      if (parts.length >= 2 && arePartsFromSameInstrument(parts)) {
        // Grand staff
        const trebleY = yOffset + systemHeight;
        const bassY = trebleY + staveHeight + partSpacing;

        if (y >= trebleY && y < trebleY + staveHeight) {
          // Clicked on treble staff
          const measureIdx = row * measuresPerRow + col;
          if (measureIdx >= numMeasures) return null;

          const measure = parts[0].measures[measureIdx];
          const pitch = yPositionToPitch(y, trebleY, 'treble');
          const startTime = calculateStartTime(x, col, measureIdx, score.timeSignature);

          return { measureId: measure.id, pitch, startTime };
        } else if (y >= bassY && y < bassY + staveHeight) {
          // Clicked on bass staff
          const measureIdx = row * measuresPerRow + col;
          if (measureIdx >= numMeasures) return null;

          const measure = parts[1].measures[measureIdx];
          const pitch = yPositionToPitch(y, bassY, 'bass');
          const startTime = calculateStartTime(x, col, measureIdx, score.timeSignature);

          return { measureId: measure.id, pitch, startTime };
        }

        systemHeight += staveHeight + partSpacing + staveHeight + partSpacing;
      } else {
        // Single staff for each part
        for (const part of parts) {
          const staveY = yOffset + systemHeight;

          if (y >= staveY && y < staveY + staveHeight) {
            const measureIdx = row * measuresPerRow + col;
            if (measureIdx >= numMeasures) return null;

            const measure = part.measures[measureIdx];
            const pitch = yPositionToPitch(y, staveY, part.clef);
            const startTime = calculateStartTime(x, col, measureIdx, score.timeSignature);

            return { measureId: measure.id, pitch, startTime };
          }

          systemHeight += staveHeight + partSpacing;
        }
      }
    }

    yOffset += systemHeight;
  }

  return null;
}

/**
 * Convert Y position to pitch
 */
function yPositionToPitch(y: number, staveY: number, clef: 'treble' | 'bass'): string {
  const relativeY = y - staveY;
  const lineHeight = 10; // 10px per line/space

  // Staff pitches from top to bottom (includes ledger lines)
  const treblePitches = [
    'C6', 'B5', 'A5', 'G5', 'F5',           // Ledger lines above
    'E5', 'D5', 'C5', 'B4', 'A4', 'G4', 'F4', // Staff
    'E4', 'D4', 'C4', 'B3', 'A3'            // Ledger lines below
  ];

  const bassPitches = [
    'E4', 'D4', 'C4', 'B3', 'A3',           // Ledger lines above
    'G3', 'F3', 'E3', 'D3', 'C3', 'B2', 'A2', // Staff
    'G2', 'F2', 'E2', 'D2', 'C2'            // Ledger lines below
  ];

  const pitches = clef === 'treble' ? treblePitches : bassPitches;
  const index = Math.floor(relativeY / lineHeight);

  // Clamp to valid range
  const clampedIndex = Math.max(0, Math.min(index, pitches.length - 1));
  return pitches[clampedIndex];
}

/**
 * Calculate start time for note based on X position
 */
function calculateStartTime(x: number, col: number, measureIdx: number, timeSignature: string): number {
  const staveWidth = 240;
  const xWithinMeasure = x - (col * staveWidth);
  const beatFraction = Math.max(0, Math.min(1, xWithinMeasure / staveWidth));

  const [beatsPerMeasure] = timeSignature.split('/').map(Number);
  return measureIdx * beatsPerMeasure + (beatFraction * beatsPerMeasure);
}
