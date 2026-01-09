/**
 * MIDI exporter - converts Score state back to MIDI format
 * This allows users to export their edited scores
 */
import { Midi, Track } from '@tonejs/midi';
import { Score, Note } from '../store/notation';

/**
 * Generate MIDI file from current Score state
 * @param score The score to export
 * @returns Uint8Array containing MIDI file data
 */
export function generateMidiFromScore(score: Score): Uint8Array {
  const midi = new Midi();

  // Set tempo in header
  midi.header.setTempo(score.tempo);

  // Parse time signature (e.g., "4/4" -> {numerator: 4, denominator: 4})
  const [numerator, denominator] = score.timeSignature.split('/').map(n => parseInt(n));
  midi.header.timeSignatures.push({
    ticks: 0,
    measures: 0,
    timeSignature: [numerator, denominator],
  });

  // Create a track for each part (treble/bass or single staff)
  score.parts.forEach((part) => {
    const track = midi.addTrack();
    track.name = part.name;

    // Convert all notes in all measures to MIDI events
    part.measures.forEach((measure) => {
      measure.notes.forEach((note) => {
        if (!note.isRest && note.pitch) {
          // Convert pitch string (e.g., "C4") to MIDI note number
          const midiNote = pitchToMidiNumber(note.pitch);

          // Calculate note duration in seconds
          const duration = calculateDuration(note.duration, note.dotted, score.tempo);

          // Add note to track
          track.addNote({
            midi: midiNote,
            time: note.startTime,
            duration: duration,
            velocity: 0.8, // Default velocity
          });
        }
      });
    });
  });

  // Convert to array buffer
  return new Uint8Array(midi.toArray());
}

/**
 * Convert pitch string (e.g., "C4", "F#5", "Bb3") to MIDI note number (0-127)
 */
function pitchToMidiNumber(pitch: string): number {
  // Parse pitch string: first char is note, optional # or b, last char is octave
  const match = pitch.match(/^([A-G])(#|b)?(\d+)$/);

  if (!match) {
    console.warn(`Invalid pitch: ${pitch}, defaulting to C4`);
    return 60; // C4
  }

  const [, noteName, accidental, octaveStr] = match;
  const octave = parseInt(octaveStr);

  // Map note names to semitone offsets (C = 0)
  const noteMap: Record<string, number> = {
    'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
  };

  let semitone = noteMap[noteName];

  // Apply accidental
  if (accidental === '#') semitone += 1;
  if (accidental === 'b') semitone -= 1;

  // Calculate MIDI note number: (octave + 1) * 12 + semitone
  // Middle C (C4) = 60
  return (octave + 1) * 12 + semitone;
}

/**
 * Calculate note duration in seconds based on tempo
 * @param noteDuration VexFlow duration string (e.g., "quarter", "eighth")
 * @param dotted Whether the note is dotted (1.5x duration)
 * @param tempo Tempo in BPM
 * @returns Duration in seconds
 */
function calculateDuration(noteDuration: string, dotted: boolean, tempo: number): number {
  // Convert VexFlow duration to quarter note multiples
  const durationsMap: Record<string, number> = {
    'whole': 4,
    'half': 2,
    'quarter': 1,
    'eighth': 0.5,
    '16th': 0.25,
    '32nd': 0.125,
    '64th': 0.0625,
    '128th': 0.03125,
  };

  let quarters = durationsMap[noteDuration] || 1;

  // Apply dotted multiplier
  if (dotted) {
    quarters *= 1.5;
  }

  // Convert to seconds: quarters * (60 / tempo)
  const quarterNoteDuration = 60 / tempo;
  return quarters * quarterNoteDuration;
}
