/**
 * MIDI Parser - Converts MIDI files to internal Score format
 *
 * This parses MIDI directly to preserve YourMT3+ transcription accuracy.
 */

import { Midi } from '@tonejs/midi';
import type { Score, Part, Measure, Note } from '../store/notation';
import { intelligentStaffSplit, type MidiNote as StaffSplitterMidiNote } from './staff-splitter';

export interface MidiParseOptions {
  tempo?: number;
  timeSignature?: { numerator: number; denominator: number };
  keySignature?: string;
  splitAtMiddleC?: boolean; // For grand staff (treble + bass)
  middleCNote?: number; // MIDI note number for staff split (default: 60)
  useIntelligentSplit?: boolean; // Use intelligent clustering instead of simple middle C split (default: true)
}

/**
 * Parse MIDI file into Score format
 */
export async function parseMidiFile(
  midiData: ArrayBuffer,
  options: MidiParseOptions = {}
): Promise<Score> {
  const midi = new Midi(midiData);

  // Extract metadata
  const tempo = options.tempo || midi.header.tempos[0]?.bpm || 120;
  const timeSignature = options.timeSignature || {
    numerator: midi.header.timeSignatures[0]?.timeSignature[0] || 4,
    denominator: midi.header.timeSignatures[0]?.timeSignature[1] || 4,
  };
  const keySignature = options.keySignature || 'C';

  // Parse all tracks into single note list
  const allNotes = extractNotesFromMidi(midi);

  // Create measures from notes
  const measureDuration = (timeSignature.numerator / timeSignature.denominator) * 4; // in quarter notes
  const parts = createPartsFromNotes(
    allNotes,
    measureDuration,
    options.splitAtMiddleC ?? true,
    options.middleCNote ?? 60,
    tempo,
    options.useIntelligentSplit ?? true
  );

  return {
    id: 'score-1',
    title: midi.name || 'Transcribed Score',
    composer: 'YourMT3+',
    key: keySignature,
    timeSignature: `${timeSignature.numerator}/${timeSignature.denominator}`,
    tempo,
    parts,
    measures: parts[0]?.measures || [], // Legacy compatibility
  };
}

interface MidiNote {
  midi: number;
  time: number;
  duration: number;
  velocity: number;
}

/**
 * Extract all notes from MIDI tracks
 */
function extractNotesFromMidi(midi: Midi): MidiNote[] {
  const notes: MidiNote[] = [];

  for (const track of midi.tracks) {
    for (const note of track.notes) {
      notes.push({
        midi: note.midi,
        time: note.time,
        duration: note.duration,
        velocity: note.velocity,
      });
    }
  }

  // Sort by time
  notes.sort((a, b) => a.time - b.time);

  return notes;
}

/**
 * Create grand staff parts (treble + bass) or single part
 */
function createPartsFromNotes(
  notes: MidiNote[],
  measureDuration: number,
  splitStaff: boolean,
  middleCNote: number,
  tempo: number,
  useIntelligentSplit: boolean = true
): Part[] {
  if (splitStaff) {
    let trebleNotes: MidiNote[];
    let bassNotes: MidiNote[];

    if (useIntelligentSplit && notes.length > 0) {
      // Use intelligent clustering-based split
      try {
        const splitterNotes: StaffSplitterMidiNote[] = notes.map(n => ({
          midi: n.midi,
          time: n.time,
          duration: n.duration,
          velocity: n.velocity,
        }));

        const result = intelligentStaffSplit(splitterNotes, {
          fallbackSplit: middleCNote,
        });

        trebleNotes = result.trebleNotes;
        bassNotes = result.bassNotes;
      } catch (error) {
        console.warn('Intelligent split failed, falling back to middle C:', error);
        // Fallback to simple split
        trebleNotes = notes.filter((n) => n.midi >= middleCNote);
        bassNotes = notes.filter((n) => n.midi < middleCNote);
      }
    } else {
      // Simple split at middle C
      trebleNotes = notes.filter((n) => n.midi >= middleCNote);
      bassNotes = notes.filter((n) => n.midi < middleCNote);
    }

    return [
      {
        id: 'part-treble',
        name: 'Piano Right Hand',
        clef: 'treble',
        measures: createMeasures(trebleNotes, measureDuration, tempo),
      },
      {
        id: 'part-bass',
        name: 'Piano Left Hand',
        clef: 'bass',
        measures: createMeasures(bassNotes, measureDuration, tempo),
      },
    ];
  } else {
    // Single staff
    return [
      {
        id: 'part-1',
        name: 'Piano',
        clef: 'treble',
        measures: createMeasures(notes, measureDuration, tempo),
      },
    ];
  }
}

/**
 * Create measures from notes
 */
function createMeasures(notes: MidiNote[], measureDuration: number, tempo: number = 120): Measure[] {
  if (notes.length === 0) {
    return [
      {
        id: 'measure-1',
        number: 1,
        notes: [],
      },
    ];
  }

  // Calculate total duration and number of measures
  const maxTime = Math.max(...notes.map((n) => n.time + n.duration));
  const numMeasures = Math.ceil(maxTime / measureDuration);

  const measures: Measure[] = [];

  for (let i = 0; i < numMeasures; i++) {
    const measureStart = i * measureDuration;
    const measureEnd = (i + 1) * measureDuration;

    // Find notes that start in this measure
    const measureNotes = notes
      .filter((n) => n.time >= measureStart && n.time < measureEnd)
      .map((midiNote, idx) => convertMidiNoteToNote(midiNote, `m${i + 1}-n${idx}`, measureStart, tempo));

    measures.push({
      id: `measure-${i + 1}`,
      number: i + 1,
      notes: measureNotes,
    });
  }

  return measures;
}

/**
 * Convert MIDI note to internal Note format
 */
function convertMidiNoteToNote(midiNote: MidiNote, id: string, measureStart: number, tempo: number): Note {
  const { pitch, octave, accidental } = midiNumberToPitch(midiNote.midi);
  const { duration, dotted } = durationToNoteName(midiNote.duration, tempo);

  return {
    id,
    pitch: `${pitch}${octave}`,
    duration,
    octave,
    startTime: midiNote.time - measureStart, // Relative to measure start
    dotted,
    accidental,
    isRest: false,
    // chordId will be assigned by grouping simultaneous notes
  };
}

/**
 * Convert MIDI note number to pitch name, octave, and accidental
 */
function midiNumberToPitch(midiNumber: number): {
  pitch: string;
  octave: number;
  accidental?: 'sharp' | 'flat' | 'natural';
} {
  const pitchClasses = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const pitchClass = midiNumber % 12;
  const octave = Math.floor(midiNumber / 12) - 1;
  const pitchName = pitchClasses[pitchClass];

  let accidental: 'sharp' | 'flat' | 'natural' | undefined;
  if (pitchName.includes('#')) {
    accidental = 'sharp';
  }

  return {
    pitch: pitchName.replace('#', ''),
    octave,
    accidental,
  };
}

/**
 * Convert duration (in seconds) to note name (whole, half, quarter, etc.)
 */
function durationToNoteName(duration: number, tempo: number): { duration: string; dotted: boolean } {
  // Calculate quarter note duration based on actual tempo
  // At tempo BPM: 1 quarter note = 60/BPM seconds
  const quarterNoteDuration = 60 / tempo;

  const durationInQuarters = duration / quarterNoteDuration;

  // Find closest standard duration (including dotted notes)
  const durations: [number, string, boolean][] = [
    [4, 'whole', false],
    [3, 'half', true],     // dotted half
    [2, 'half', false],
    [1.5, 'quarter', true], // dotted quarter
    [1, 'quarter', false],
    [0.75, 'eighth', true], // dotted eighth
    [0.5, 'eighth', false],
    [0.375, '16th', true],  // dotted 16th
    [0.25, '16th', false],
    [0.125, '32nd', false],
  ];

  let closestDuration = durations[0];
  let minDiff = Math.abs(durationInQuarters - durations[0][0]);

  for (const [value, name, dotted] of durations) {
    const diff = Math.abs(durationInQuarters - value);
    if (diff < minDiff) {
      minDiff = diff;
      closestDuration = [value, name, dotted];
    }
  }

  return {
    duration: closestDuration[1],
    dotted: closestDuration[2],
  };
}

/**
 * Group simultaneous notes into chords
 */
export function assignChordIds(score: Score): Score {
  const CHORD_TOLERANCE = 0.05; // Notes within 50ms are considered simultaneous

  for (const part of score.parts) {
    for (const measure of part.measures) {
      const notes = measure.notes;

      // Group notes by start time
      const groups: Record<string, Note[]> = {};

      for (const note of notes) {
        const timeKey = Math.round(note.startTime / CHORD_TOLERANCE).toString();
        if (!groups[timeKey]) {
          groups[timeKey] = [];
        }
        groups[timeKey].push(note);
      }

      // Assign chordId to groups with multiple notes
      for (const [timeKey, groupNotes] of Object.entries(groups)) {
        if (groupNotes.length > 1) {
          const chordId = `chord-${measure.id}-${timeKey}`;
          groupNotes.forEach((note) => {
            note.chordId = chordId;
          });
        }
      }
    }
  }

  return score;
}
