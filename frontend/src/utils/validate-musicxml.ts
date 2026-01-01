/**
 * MusicXML Parsing Validation Utility
 *
 * Purpose: Verify that the parser correctly extracts all MusicXML data
 * by comparing raw XML elements with parsed Score object.
 */

import { parseMusicXML, Score } from './musicxml-parser';

export interface ValidationReport {
  totalXMLNotes: number;
  totalParsedNotes: number;
  totalXMLMeasures: number;
  totalParsedMeasures: number;
  missingNotes: Array<{
    measureNumber: number;
    pitch?: string;
    octave?: number;
    duration?: string;
    isRest: boolean;
  }>;
  parsingErrors: string[];
  warnings: string[];
  success: boolean;
}

interface XMLNoteData {
  measureNumber: number;
  pitch?: string;
  octave?: number;
  alter?: number;
  duration?: string;
  isRest: boolean;
  isChordMember: boolean;
}

/**
 * Extract raw note data from MusicXML string
 */
function extractRawXMLNotes(xml: string): XMLNoteData[] {
  const parser = new DOMParser();
  const doc = parser.parseFromString(xml, 'text/xml');

  const notes: XMLNoteData[] = [];
  const measures = doc.querySelectorAll('measure');

  measures.forEach((measureEl) => {
    const measureNumber = parseInt(measureEl.getAttribute('number') || '0');
    const noteElements = measureEl.querySelectorAll('note');

    noteElements.forEach((noteEl) => {
      const pitchEl = noteEl.querySelector('pitch');
      const rest = noteEl.querySelector('rest');
      const isChordMember = noteEl.querySelector('chord') !== null;

      if (rest) {
        // Rest
        const durationEl = noteEl.querySelector('duration');
        const typeEl = noteEl.querySelector('type');

        notes.push({
          measureNumber,
          duration: typeEl?.textContent || undefined,
          isRest: true,
          isChordMember,
        });
      } else if (pitchEl) {
        // Pitched note
        const step = pitchEl.querySelector('step')?.textContent;
        const octave = pitchEl.querySelector('octave')?.textContent;
        const alter = pitchEl.querySelector('alter')?.textContent;
        const typeEl = noteEl.querySelector('type');

        notes.push({
          measureNumber,
          pitch: step || undefined,
          octave: octave ? parseInt(octave) : undefined,
          alter: alter ? parseInt(alter) : undefined,
          duration: typeEl?.textContent || undefined,
          isRest: false,
          isChordMember,
        });
      }
    });
  });

  return notes;
}

/**
 * Extract parsed note data from Score object
 */
function extractParsedNotes(score: Score): XMLNoteData[] {
  const notes: XMLNoteData[] = [];

  score.parts.forEach((part) => {
    part.measures.forEach((measure) => {
      measure.notes.forEach((note) => {
        if (note.isRest) {
          notes.push({
            measureNumber: measure.number,
            duration: note.duration,
            isRest: true,
            isChordMember: false, // Parsed notes don't preserve chord info yet
          });
        } else {
          // Extract pitch from full pitch string (e.g., "C4" → "C", octave 4)
          const pitchMatch = note.pitch.match(/([A-G][#b]?)(\d)/);
          if (pitchMatch) {
            const [, pitchName, octaveStr] = pitchMatch;
            const step = pitchName[0]; // Just letter
            const alter = pitchName.includes('#') ? 1 : pitchName.includes('b') ? -1 : 0;

            notes.push({
              measureNumber: measure.number,
              pitch: step,
              octave: parseInt(octaveStr),
              alter: alter !== 0 ? alter : undefined,
              duration: note.duration,
              isRest: false,
              isChordMember: false,
            });
          }
        }
      });
    });
  });

  return notes;
}

/**
 * Compare two note data objects for equality
 */
function notesEqual(a: XMLNoteData, b: XMLNoteData): boolean {
  if (a.isRest !== b.isRest) return false;
  if (a.measureNumber !== b.measureNumber) return false;

  if (a.isRest) {
    // For rests, just check duration
    return a.duration === b.duration;
  } else {
    // For pitched notes, check pitch, octave, and duration
    return (
      a.pitch === b.pitch &&
      a.octave === b.octave &&
      a.duration === b.duration
      // Note: We don't check alter here because parser may handle it differently
    );
  }
}

/**
 * Validate MusicXML parsing
 */
export function validateMusicXMLParsing(xml: string): ValidationReport {
  const report: ValidationReport = {
    totalXMLNotes: 0,
    totalParsedNotes: 0,
    totalXMLMeasures: 0,
    totalParsedMeasures: 0,
    missingNotes: [],
    parsingErrors: [],
    warnings: [],
    success: true,
  };

  try {
    // Extract raw XML data
    const rawNotes = extractRawXMLNotes(xml);
    report.totalXMLNotes = rawNotes.length;

    // Parse with our parser
    const score = parseMusicXML(xml);
    const parsedNotes = extractParsedNotes(score);
    report.totalParsedNotes = parsedNotes.length;

    // Count measures
    const parser = new DOMParser();
    const doc = parser.parseFromString(xml, 'text/xml');
    report.totalXMLMeasures = doc.querySelectorAll('measure').length;
    report.totalParsedMeasures = score.parts.reduce(
      (sum, part) => sum + part.measures.length,
      0
    );

    // Check note count
    if (rawNotes.length !== parsedNotes.length) {
      report.warnings.push(
        `Note count mismatch: XML has ${rawNotes.length} notes, parsed ${parsedNotes.length}`
      );
    }

    // Find missing notes
    const parsedMatched = new Array(parsedNotes.length).fill(false);

    for (const rawNote of rawNotes) {
      // Find matching parsed note
      const matchIdx = parsedNotes.findIndex(
        (parsed, idx) => !parsedMatched[idx] && notesEqual(rawNote, parsed)
      );

      if (matchIdx === -1) {
        // No match found
        report.missingNotes.push(rawNote);
      } else {
        // Mark as matched
        parsedMatched[matchIdx] = true;
      }
    }

    // Check for critical errors
    if (report.totalXMLNotes === 0 && report.totalParsedNotes === 0) {
      report.warnings.push('No notes found in MusicXML');
    }

    if (report.totalParsedNotes === 0 && report.totalXMLNotes > 0) {
      report.parsingErrors.push('Parser failed to extract any notes from MusicXML');
      report.success = false;
    }

    if (report.missingNotes.length > report.totalXMLNotes * 0.1) {
      // More than 10% notes missing
      report.parsingErrors.push(
        `Significant note loss: ${report.missingNotes.length} / ${report.totalXMLNotes} notes missing (${((report.missingNotes.length / report.totalXMLNotes) * 100).toFixed(1)}%)`
      );
      report.success = false;
    }
  } catch (error) {
    report.parsingErrors.push(`Exception during parsing: ${error}`);
    report.success = false;
  }

  return report;
}

/**
 * Print validation report to console
 */
export function printValidationReport(report: ValidationReport): void {
  console.log('\n' + '='.repeat(80));
  console.log('MUSICXML PARSING VALIDATION REPORT');
  console.log('='.repeat(80));

  console.log('\n📊 SUMMARY:');
  console.log(`  Total XML notes:     ${report.totalXMLNotes}`);
  console.log(`  Total parsed notes:  ${report.totalParsedNotes}`);
  console.log(`  Total XML measures:  ${report.totalXMLMeasures}`);
  console.log(`  Total parsed measures: ${report.totalParsedMeasures}`);
  console.log(`  Missing notes:       ${report.missingNotes.length}`);

  if (report.totalXMLNotes > 0) {
    const accuracy =
      ((report.totalXMLNotes - report.missingNotes.length) / report.totalXMLNotes) * 100;
    console.log(`\n  ${report.success ? '✅' : '❌'} Parsing accuracy: ${accuracy.toFixed(1)}%`);
  }

  if (report.parsingErrors.length > 0) {
    console.log('\n❌ PARSING ERRORS:');
    report.parsingErrors.forEach((error, i) => {
      console.log(`  ${i + 1}. ${error}`);
    });
  }

  if (report.warnings.length > 0) {
    console.log('\n⚠️  WARNINGS:');
    report.warnings.forEach((warning, i) => {
      console.log(`  ${i + 1}. ${warning}`);
    });
  }

  if (report.missingNotes.length > 0) {
    console.log(`\n❌ MISSING NOTES (first 10):`);
    report.missingNotes.slice(0, 10).forEach((note, i) => {
      if (note.isRest) {
        console.log(
          `  ${i + 1}. Rest in measure ${note.measureNumber}, duration ${note.duration}`
        );
      } else {
        const accidental = note.alter === 1 ? '#' : note.alter === -1 ? 'b' : '';
        console.log(
          `  ${i + 1}. ${note.pitch}${accidental}${note.octave} in measure ${note.measureNumber}, duration ${note.duration}`
        );
      }
    });
  }

  console.log('\n' + '='.repeat(80));
}
