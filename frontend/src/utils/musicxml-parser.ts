/**
 * Lightweight MusicXML parser for extracting notes and metadata.
 *
 * Supports grand staff with multiple parts (treble + bass for piano).
 */
import type { Note, Score, Measure, Part } from '../store/notation';

interface ParsedNote {
  pitch: string;
  octave: number;
  duration: number; // in divisions
  type: string; // whole, half, quarter, etc.
  accidental?: string;
  dotted: boolean;
  isRest: boolean;
}

export function parseMusicXML(xml: string): Score {
  const parser = new DOMParser();
  const doc = parser.parseFromString(xml, 'text/xml');

  // Extract metadata
  const title = doc.querySelector('movement-title')?.textContent ||
                doc.querySelector('work-title')?.textContent ||
                'Untitled';
  const composer = doc.querySelector('creator[type="composer"]')?.textContent || 'Unknown';

  // Extract key signature
  const fifths = doc.querySelector('key fifths')?.textContent;
  const keyMap: Record<string, string> = {
    '-7': 'Cb', '-6': 'Gb', '-5': 'Db', '-4': 'Ab', '-3': 'Eb', '-2': 'Bb', '-1': 'F',
    '0': 'C', '1': 'G', '2': 'D', '3': 'A', '4': 'E', '5': 'B', '6': 'F#', '7': 'C#'
  };
  const key = fifths ? keyMap[fifths] || 'C' : 'C';

  // Extract time signature
  const beats = doc.querySelector('time beats')?.textContent || '4';
  const beatType = doc.querySelector('time beat-type')?.textContent || '4';
  const timeSignature = `${beats}/${beatType}`;

  // Extract tempo
  let tempo = 120;
  const tempoElement = doc.querySelector('sound[tempo]');
  if (tempoElement) {
    const tempoAttr = tempoElement.getAttribute('tempo');
    if (tempoAttr) {
      tempo = parseInt(tempoAttr);
    }
  }

  // Parse all parts (for grand staff: treble + bass)
  const partElements = doc.querySelectorAll('score-partwise > part');
  const parts: Part[] = [];
  let allMeasures: Measure[] = []; // For backward compatibility

  partElements.forEach((partEl, partIdx) => {
    const partId = partEl.getAttribute('id') || `part-${partIdx}`;

    // Get part name and clef
    const partName = doc.querySelector(`score-part[id="${partId}"] part-name`)?.textContent || `Part ${partIdx + 1}`;

    // Determine clef from first measure
    const firstClefSign = partEl.querySelector('measure clef sign')?.textContent || 'G';
    const clef: 'treble' | 'bass' = firstClefSign === 'F' ? 'bass' : 'treble';

    const measureElements = partEl.querySelectorAll('measure');
    const measures: Measure[] = [];

    measureElements.forEach((measureEl, idx) => {
    const measureNumber = parseInt(measureEl.getAttribute('number') || String(idx + 1));
    const notes: Note[] = [];

    const noteElements = measureEl.querySelectorAll('note');
    let currentChord: Note[] = [];
    let currentChordId: string | null = null;

    noteElements.forEach((noteEl, noteIdx) => {
      const parsedNote = parseNoteElement(noteEl);
      if (!parsedNote) return;

      // Check if this note is part of a chord (simultaneous with previous note)
      const isChordMember = noteEl.querySelector('chord') !== null;

      // Assign chord ID for chord grouping
      if (!isChordMember) {
        // Start new chord group (or single note)
        currentChordId = `chord-${measureNumber}-${noteIdx}`;
      }

      if (parsedNote.isRest) {
        // Flush any pending chord before adding rest
        if (currentChord.length > 0) {
          notes.push(...currentChord);
          currentChord = [];
        }

        // Include rests (rests don't have chordId)
        notes.push({
          id: `note-${measureNumber}-${notes.length}`,
          pitch: '',
          duration: parsedNote.type,
          octave: 0,
          startTime: 0,
          dotted: parsedNote.dotted,
          isRest: true,
          chordId: undefined, // Rests are never part of chords
        });
      } else {
        // Build full pitch string for pitched notes
        const pitchName = parsedNote.pitch +
                         (parsedNote.accidental === 'sharp' ? '#' :
                          parsedNote.accidental === 'flat' ? 'b' : '');
        const fullPitch = pitchName + parsedNote.octave;

        const note: Note = {
          id: `note-${measureNumber}-${notes.length + currentChord.length}`,
          pitch: fullPitch,
          duration: parsedNote.type,
          octave: parsedNote.octave,
          startTime: 0,
          dotted: parsedNote.dotted,
          accidental: parsedNote.accidental as 'sharp' | 'flat' | 'natural' | undefined,
          isRest: false,
          chordId: currentChordId || undefined, // Assign chord ID for grouping
        };

        if (isChordMember) {
          // Add to current chord group
          currentChord.push(note);
        } else {
          // Flush previous chord if any
          if (currentChord.length > 0) {
            notes.push(...currentChord);
            currentChord = [];
          }
          // Start new chord group (or single note)
          currentChord = [note];
        }
      }
    });

    // Flush any remaining chord
    if (currentChord.length > 0) {
      notes.push(...currentChord);
    }

      // Add ALL measures, even if empty (will show as blank measures)
      measures.push({
        id: `part-${partIdx}-measure-${measureNumber}`,
        number: measureNumber,
        notes,
      });
    });

    // Add this part to the parts array
    parts.push({
      id: partId,
      name: partName,
      clef,
      measures,
    });

    // For backward compatibility, use first part's measures
    if (partIdx === 0) {
      allMeasures = measures;
    }
  });

  // If no parts found, return empty score
  if (parts.length === 0) {
    parts.push({
      id: 'part-0',
      name: 'Piano',
      clef: 'treble',
      measures: [],
    });
  }

  return {
    id: 'parsed-score',
    title,
    composer,
    key,
    timeSignature,
    tempo,
    parts,
    measures: allMeasures, // Legacy field for backward compat
  };
}

function parseNoteElement(noteEl: Element): ParsedNote | null {
  const durationEl = noteEl.querySelector('duration');
  const typeEl = noteEl.querySelector('type');

  if (!durationEl || !typeEl) return null;

  // Check if this is a rest
  const isRest = noteEl.querySelector('rest') !== null;

  if (isRest) {
    return {
      pitch: '',
      octave: 0,
      duration: parseInt(durationEl.textContent || '0'),
      type: typeEl.textContent || 'quarter',
      dotted: noteEl.querySelector('dot') !== null,
      isRest: true,
    };
  }

  // Parse pitched note
  const pitchEl = noteEl.querySelector('pitch');
  if (!pitchEl) return null;

  const step = pitchEl.querySelector('step')?.textContent;
  const octave = pitchEl.querySelector('octave')?.textContent;
  const alter = pitchEl.querySelector('alter')?.textContent; // Semantic pitch alteration
  const accidentalEl = noteEl.querySelector('accidental'); // Visual accidental display
  const dotEl = noteEl.querySelector('dot');

  if (!step || !octave) return null;

  // Parse accidental from both <alter> (semantic) and <accidental> (visual) tags
  let accidental: string | undefined;

  // Priority 1: Use <alter> for pitch accuracy (indicates actual pitch)
  if (alter) {
    const alterValue = parseInt(alter);
    if (alterValue === 1) accidental = 'sharp';
    else if (alterValue === -1) accidental = 'flat';
    else if (alterValue === 0) accidental = 'natural';
  }

  // Priority 2: If no <alter>, check <accidental> tag (visual notation)
  if (!accidental && accidentalEl) {
    const accType = accidentalEl.textContent;
    if (accType === 'sharp') accidental = 'sharp';
    else if (accType === 'flat') accidental = 'flat';
    else if (accType === 'natural') accidental = 'natural';
  }

  return {
    pitch: step,
    octave: parseInt(octave),
    duration: parseInt(durationEl.textContent || '0'),
    type: typeEl.textContent || 'quarter',
    accidental,
    dotted: dotEl !== null,
    isRest: false,
  };
}

/**
 * Convert note duration string to seconds based on tempo.
 */
export function durationToSeconds(duration: string, tempo: number, dotted: boolean = false): number {
  const quarterNoteDuration = 60 / tempo; // seconds per quarter note

  const durationMap: Record<string, number> = {
    'whole': quarterNoteDuration * 4,
    'half': quarterNoteDuration * 2,
    'quarter': quarterNoteDuration,
    'eighth': quarterNoteDuration / 2,
    '16th': quarterNoteDuration / 4,
    '32nd': quarterNoteDuration / 8,
  };

  let baseDuration = durationMap[duration] || quarterNoteDuration;

  if (dotted) {
    baseDuration *= 1.5;
  }

  return baseDuration;
}
