/**
 * Intelligent staff splitting for grand staff notation.
 * Uses note density and clustering to split notes between treble and bass clefs
 * based on hand position, not just middle C.
 */

export interface MidiNote {
  midi: number;
  time: number;
  duration: number;
  velocity: number;
}

export interface NoteSplitResult {
  trebleNotes: MidiNote[];
  bassNotes: MidiNote[];
}

interface SplitOptions {
  windowSize?: number; // Time window in seconds (default: 2.0)
  hysteresis?: number; // Semitones before switching split point (default: 5)
  fallbackSplit?: number; // Fallback MIDI note (default: 60 - middle C)
  minNotesForClustering?: number; // Min notes needed for clustering (default: 3)
}

/**
 * Intelligently split notes between treble and bass staves.
 *
 * Algorithm:
 * 1. Divide notes into time windows
 * 2. For each window, find two clusters (upper/lower hand) using K-means
 * 3. Apply hysteresis to prevent rapid split point changes
 * 4. Keep chords together (never split across staves)
 * 5. Fallback to middle C if clustering fails or note density is low
 */
export function intelligentStaffSplit(
  notes: MidiNote[],
  options: SplitOptions = {}
): NoteSplitResult {
  const {
    windowSize = 2.0,
    hysteresis = 5,
    fallbackSplit = 60,
    minNotesForClustering = 3,
  } = options;

  // Handle empty or very few notes
  if (notes.length === 0) {
    return { trebleNotes: [], bassNotes: [] };
  }

  if (notes.length < minNotesForClustering) {
    // Too few notes - use simple middle C split
    return simpleSplit(notes, fallbackSplit);
  }

  // Sort notes by time
  const sortedNotes = [...notes].sort((a, b) => a.time - b.time);

  // Find max time to determine number of windows
  const maxTime = Math.max(...sortedNotes.map((n) => n.time + n.duration));
  const numWindows = Math.ceil(maxTime / windowSize);

  // Calculate split point for each window
  const windowSplits: number[] = [];
  let previousSplit = fallbackSplit;

  for (let i = 0; i < numWindows; i++) {
    const windowStart = i * windowSize;
    const windowEnd = (i + 1) * windowSize;

    // Get notes in this window
    const windowNotes = sortedNotes.filter(
      (n) => n.time >= windowStart && n.time < windowEnd
    );

    if (windowNotes.length < minNotesForClustering) {
      // Not enough notes - use previous split
      windowSplits.push(previousSplit);
      continue;
    }

    // Find split point using K-means clustering
    const midiValues = windowNotes.map((n) => n.midi);
    const split = findSplitPoint(midiValues);

    // Apply hysteresis: only change split if difference > threshold
    if (Math.abs(split - previousSplit) >= hysteresis) {
      windowSplits.push(split);
      previousSplit = split;
    } else {
      // Keep previous split to avoid rapid changes
      windowSplits.push(previousSplit);
    }
  }

  // Assign each note to treble or bass based on its window's split point
  const trebleNotes: MidiNote[] = [];
  const bassNotes: MidiNote[] = [];

  for (const note of sortedNotes) {
    const windowIndex = Math.floor(note.time / windowSize);
    const split = windowSplits[windowIndex] || fallbackSplit;

    if (note.midi >= split) {
      trebleNotes.push(note);
    } else {
      bassNotes.push(note);
    }
  }

  // Post-process: ensure chords stay together
  return ensureChordsStayTogether(sortedNotes, trebleNotes, bassNotes);
}

/**
 * Simple split at a fixed MIDI note (fallback).
 */
function simpleSplit(notes: MidiNote[], splitPoint: number): NoteSplitResult {
  const trebleNotes = notes.filter((n) => n.midi >= splitPoint);
  const bassNotes = notes.filter((n) => n.midi < splitPoint);
  return { trebleNotes, bassNotes };
}

/**
 * Find split point using K-means clustering (k=2).
 * Returns the boundary between the two clusters.
 */
function findSplitPoint(midiValues: number[]): number {
  if (midiValues.length < 2) {
    return midiValues[0] || 60;
  }

  // Initialize centroids: pick min and max values
  const sortedValues = [...midiValues].sort((a, b) => a - b);
  let centroid1 = sortedValues[0];
  let centroid2 = sortedValues[sortedValues.length - 1];

  // K-means iteration (max 10 iterations)
  for (let iteration = 0; iteration < 10; iteration++) {
    const cluster1: number[] = [];
    const cluster2: number[] = [];

    // Assign each value to nearest centroid
    for (const value of midiValues) {
      const dist1 = Math.abs(value - centroid1);
      const dist2 = Math.abs(value - centroid2);

      if (dist1 < dist2) {
        cluster1.push(value);
      } else {
        cluster2.push(value);
      }
    }

    // Recalculate centroids
    const newCentroid1 = cluster1.length > 0
      ? cluster1.reduce((sum, v) => sum + v, 0) / cluster1.length
      : centroid1;

    const newCentroid2 = cluster2.length > 0
      ? cluster2.reduce((sum, v) => sum + v, 0) / cluster2.length
      : centroid2;

    // Check convergence
    if (
      Math.abs(newCentroid1 - centroid1) < 0.1 &&
      Math.abs(newCentroid2 - centroid2) < 0.1
    ) {
      // Converged
      break;
    }

    centroid1 = newCentroid1;
    centroid2 = newCentroid2;
  }

  // Split point is midway between centroids
  return Math.round((centroid1 + centroid2) / 2);
}

/**
 * Ensure chord notes stay together on the same staff.
 * If a chord is split across staves, move all notes to the staff with majority.
 */
function ensureChordsStayTogether(
  allNotes: MidiNote[],
  trebleNotes: MidiNote[],
  bassNotes: MidiNote[]
): NoteSplitResult {
  const CHORD_TOLERANCE = 0.05; // 50ms - notes within this are considered simultaneous

  // Group notes by time (identify chords)
  const chordGroups = groupChords(allNotes, CHORD_TOLERANCE);

  const finalTreble: MidiNote[] = [];
  const finalBass: MidiNote[] = [];

  for (const chord of chordGroups) {
    if (chord.length === 1) {
      // Single note - keep assignment
      if (trebleNotes.includes(chord[0])) {
        finalTreble.push(chord[0]);
      } else {
        finalBass.push(chord[0]);
      }
    } else {
      // Chord - count how many are in treble vs bass
      const trebleCount = chord.filter((n) => trebleNotes.includes(n)).length;
      const bassCount = chord.length - trebleCount;

      // Move entire chord to staff with majority
      if (trebleCount >= bassCount) {
        finalTreble.push(...chord);
      } else {
        finalBass.push(...chord);
      }
    }
  }

  return {
    trebleNotes: finalTreble,
    bassNotes: finalBass,
  };
}

/**
 * Group simultaneous notes into chords.
 */
function groupChords(notes: MidiNote[], tolerance: number): MidiNote[][] {
  const sorted = [...notes].sort((a, b) => a.time - b.time);
  const groups: MidiNote[][] = [];

  let currentGroup: MidiNote[] = [];
  let currentTime = -1;

  for (const note of sorted) {
    if (currentTime < 0 || Math.abs(note.time - currentTime) <= tolerance) {
      // Same chord
      currentGroup.push(note);
      currentTime = note.time;
    } else {
      // New chord
      if (currentGroup.length > 0) {
        groups.push(currentGroup);
      }
      currentGroup = [note];
      currentTime = note.time;
    }
  }

  // Push last group
  if (currentGroup.length > 0) {
    groups.push(currentGroup);
  }

  return groups;
}
