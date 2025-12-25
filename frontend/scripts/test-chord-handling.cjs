const fs = require('fs');
const { DOMParser } = require('@xmldom/xmldom');

const xml = fs.readFileSync('../storage/outputs/497306b6-8e09-41c2-b8c7-0792dbd22022.musicxml', 'utf-8');
const parser = new DOMParser();
const doc = parser.parseFromString(xml, 'text/xml');

// Look at measure 4 which has chords
const measures = doc.getElementsByTagName('measure');
const measure4 = measures[3]; // 0-indexed

console.log('=== MEASURE 4 ANALYSIS ===');
const notes = measure4.getElementsByTagName('note');
console.log('Total note elements:', notes.length);

let noteCount = 0;
let totalDuration = 0;

for (let i = 0; i < notes.length; i++) {
  const note = notes[i];
  const isChord = note.getElementsByTagName('chord').length > 0;
  const isRest = note.getElementsByTagName('rest').length > 0;
  const duration = parseInt(note.getElementsByTagName('duration')[0]?.textContent || '0');
  
  // Chord notes share duration with previous note
  if (!isChord) {
    totalDuration += duration;
  }
  
  if (!isRest) {
    const pitch = note.getElementsByTagName('step')[0]?.textContent;
    const octave = note.getElementsByTagName('octave')[0]?.textContent;
    const type = note.getElementsByTagName('type')[0]?.textContent;
    noteCount++;
    console.log('Note', noteCount, ':', pitch + octave, '(' + type + '), duration=' + duration, ', chord=' + isChord);
  }
}

const divisions = 10080;
const expected = divisions * 4;
console.log('\nTotal duration:', totalDuration, '(expected', expected + ')');
console.log('Duration ratio:', (totalDuration / expected).toFixed(2) + 'x');
