// Quick script to test the parser
const fs = require('fs');
const { DOMParser } = require('@xmldom/xmldom');

const xml = fs.readFileSync('../storage/outputs/497306b6-8e09-41c2-b8c7-0792dbd22022.musicxml', 'utf-8');
const parser = new DOMParser();
const doc = parser.parseFromString(xml, 'text/xml');

// Check what we're getting
const beats = doc.getElementsByTagName('beats')[0]?.textContent;
const beatType = doc.getElementsByTagName('beat-type')[0]?.textContent;
console.log('Time signature:', beats + '/' + beatType);
console.log('Divisions:', doc.getElementsByTagName('divisions')[0]?.textContent);
console.log('Key (fifths):', doc.getElementsByTagName('fifths')[0]?.textContent);

const soundEl = doc.getElementsByTagName('sound')[0];
console.log('Tempo:', soundEl?.getAttribute('tempo'));

const measures = doc.getElementsByTagName('measure');
console.log('\nTotal measures:', measures.length);
console.log('First 10 measures:');

const divisions = parseInt(doc.getElementsByTagName('divisions')[0]?.textContent || '10080');

for (let i = 0; i < Math.min(10, measures.length); i++) {
  const m = measures[i];
  const notes = m.getElementsByTagName('note');
  const pitchedNotes = [];
  let totalDuration = 0;

  for (let n = 0; n < notes.length; n++) {
    const note = notes[n];
    const isRest = note.getElementsByTagName('rest').length > 0;
    const duration = parseInt(note.getElementsByTagName('duration')[0]?.textContent || '0');
    totalDuration += duration;

    if (!isRest) {
      pitchedNotes.push(note);
    }
  }

  const expectedDuration = divisions * 4; // 4 beats in 4/4
  const durationMatch = totalDuration === expectedDuration ? '✓' : `✗ (expected ${expectedDuration}, got ${totalDuration})`;

  console.log(`  Measure ${m.getAttribute('number')}: ${notes.length} total notes, ${pitchedNotes.length} pitched notes, duration ${durationMatch}`);

  // Show first 3 pitched notes
  for (let j = 0; j < Math.min(3, pitchedNotes.length); j++) {
    const note = pitchedNotes[j];
    const pitch = note.getElementsByTagName('step')[0]?.textContent;
    const octave = note.getElementsByTagName('octave')[0]?.textContent;
    const duration = note.getElementsByTagName('duration')[0]?.textContent;
    const type = note.getElementsByTagName('type')[0]?.textContent;
    const alter = note.getElementsByTagName('alter')[0]?.textContent;
    const accidental = alter === '1' ? '#' : alter === '-1' ? 'b' : '';
    console.log(`    Note ${j+1}: ${pitch}${accidental}${octave}, duration=${duration}, type=${type}`);
  }
}
