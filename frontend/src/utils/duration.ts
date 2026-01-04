/**
 * Duration conversion utilities for music notation.
 */

/**
 * Convert note duration to seconds based on tempo.
 *
 * @param duration - Note duration type (whole, half, quarter, eighth, 16th, 32nd)
 * @param tempo - Tempo in BPM
 * @param dotted - Whether the note is dotted (increases duration by 50%)
 * @returns Duration in seconds
 */
export function durationToSeconds(
  duration: string,
  tempo: number,
  dotted: boolean = false
): number {
  // Quarter note duration at given tempo
  const quarterNoteDuration = 60 / tempo;

  // Map durations to quarter note multipliers
  const durationMap: Record<string, number> = {
    'whole': 4,
    'half': 2,
    'quarter': 1,
    'eighth': 0.5,
    '16th': 0.25,
    '32nd': 0.125,
  };

  const baseDuration = durationMap[duration] || 1;
  const multiplier = dotted ? 1.5 : 1;

  return quarterNoteDuration * baseDuration * multiplier;
}
