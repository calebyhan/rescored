# Instrument Remapping (Future Feature)

## Overview

**Note**: This feature is **out of scope for MVP** but documented for future reference.

Instrument remapping allows users to convert notation from one instrument to another (e.g., piano → violin, guitar → trumpet). This requires transposition, range validation, and potentially articulation adjustments.

---

## Use Cases

1. **Transposing Instruments**: Convert concert pitch (piano, guitar) to transposing instruments (Bb clarinet, F horn, Eb alto sax)
2. **Range Adaptation**: Convert piano part to instrument with smaller range (e.g., piano → flute)
3. **Arrangement**: Create string quartet from piano score
4. **Learning**: Transcribe piano tutorial, convert to your instrument

---

## Challenges

### 1. Pitch Range Differences

Each instrument has a playable range:

| Instrument | Range (Concert Pitch) | MIDI Notes |
|------------|----------------------|------------|
| Piano | A0 - C8 | 21-108 |
| Violin | G3 - E7 | 55-100 |
| Flute | C4 - C7 | 60-96 |
| Trumpet (Bb) | E3 - C6 | 52-84 (written Bb3-D6) |
| Cello | C2 - A5 | 36-81 |

**Problem**: Piano note C2 can't be played on violin (too low)

**Solutions**:
- **Octave shift**: Transpose notes up/down by octaves to fit range
- **Drop notes**: Remove unplayable notes (warn user)
- **Split parts**: Divide into multiple parts if range too wide

---

### 2. Transposing Instruments

Transposing instruments read different pitches than they sound:

| Instrument | Written vs. Sounding |
|------------|---------------------|
| Bb Trumpet | Written C = Sounds Bb |
| Eb Alto Sax | Written C = Sounds Eb |
| F Horn | Written C = Sounds F |

**Example**: Piano plays C4 (concert pitch)
- For Bb trumpet: Write D4 (sounds C4)
- For Eb alto sax: Write A4 (sounds C4)

**Implementation**:

```typescript
const transpositionMap = {
  'Bb-trumpet': 2,  // +2 semitones
  'Eb-alto-sax': 9,  // +9 semitones
  'F-horn': -7,  // -7 semitones
};

function transposeForInstrument(note: Note, instrument: string): Note {
  const semitones = transpositionMap[instrument] || 0;
  return {
    ...note,
    pitch: transposePitch(note.pitch, semitones),
  };
}
```

---

### 3. Articulations & Playing Techniques

Different instruments have different capabilities:

**Piano**:
- Can play 10-note chords
- Sustain pedal
- No breath control

**Violin**:
- Monophonic (one note at a time, unless double-stops)
- Bowing techniques (legato, staccato, spiccato)
- Vibrato

**Flute**:
- Monophonic
- Breath attacks
- Flutter-tongue

**Conversion Challenges**:
- Piano chord → Violin: Must arpeggiate or drop notes
- Sustained piano notes → Flute: Must add breath marks
- Piano staccato → Violin: Use staccato bowing

---

## Implementation Approach

### 1. Range Validation

```typescript
const instrumentRanges: Record<string, { low: string, high: string }> = {
  'piano': { low: 'A0', high: 'C8' },
  'violin': { low: 'G3', high: 'E7' },
  'flute': { low: 'C4', high: 'C7' },
  'trumpet-Bb': { low: 'E3', high: 'C6' },
};

function validateNoteRange(note: Note, instrument: string): boolean {
  const range = instrumentRanges[instrument];
  const noteMIDI = pitchToMIDI(note.pitch);
  const lowMIDI = pitchToMIDI(range.low);
  const highMIDI = pitchToMIDI(range.high);

  return noteMIDI >= lowMIDI && noteMIDI <= highMIDI;
}

function fitToRange(notes: Note[], instrument: string): Note[] {
  const range = instrumentRanges[instrument];

  return notes.map(note => {
    while (!validateNoteRange(note, instrument)) {
      // Shift by octave
      if (pitchToMIDI(note.pitch) < pitchToMIDI(range.low)) {
        note = transposePitch(note.pitch, 12);  // Up octave
      } else {
        note = transposePitch(note.pitch, -12);  // Down octave
      }
    }
    return note;
  });
}
```

---

### 2. Transposition

```typescript
function remapInstrument(score: Score, targetInstrument: string): Score {
  // 1. Transpose for transposing instruments
  const transposition = transpositionMap[targetInstrument] || 0;

  let notes = score.measures.flatMap(m => m.notes);
  notes = notes.map(n => transposeForInstrument(n, targetInstrument));

  // 2. Fit to range
  notes = fitToRange(notes, targetInstrument);

  // 3. Handle polyphony (reduce chords for monophonic instruments)
  if (isMonophonic(targetInstrument)) {
    notes = reduceToMelody(notes);
  }

  // 4. Update clef
  const clef = getClefForInstrument(targetInstrument);

  // 5. Rebuild score
  return {
    ...score,
    instrument: targetInstrument,
    clef,
    measures: rebuildMeasures(notes),
  };
}
```

---

### 3. Polyphony Reduction

For monophonic instruments (violin, flute, trumpet), convert chords to single melody line:

```typescript
function reduceToMelody(notes: Note[]): Note[] {
  // Strategy 1: Keep highest note (soprano line)
  // Strategy 2: Keep lowest note (bass line)
  // Strategy 3: Arpeggiate chord

  // Example: Keep highest note at each time point
  const groupedByTime = groupBy(notes, n => n.startTime);

  return Object.values(groupedByTime).map(group => {
    return group.reduce((highest, note) =>
      pitchToMIDI(note.pitch) > pitchToMIDI(highest.pitch) ? note : highest
    );
  });
}
```

---

## UI for Remapping

```typescript
export const InstrumentRemapDialog: React.FC = () => {
  const [targetInstrument, setTargetInstrument] = useState('violin');

  const handleRemap = () => {
    const { score } = useNotationStore.getState();
    const remapped = remapInstrument(score, targetInstrument);

    useNotationStore.getState().updateScore(remapped);
  };

  return (
    <Dialog>
      <h2>Convert to Different Instrument</h2>

      <Select value={targetInstrument} onChange={setTargetInstrument}>
        <option value="violin">Violin</option>
        <option value="flute">Flute</option>
        <option value="trumpet-Bb">Trumpet (Bb)</option>
        <option value="cello">Cello</option>
      </Select>

      <Warning>
        Some notes may be shifted by octaves or removed if outside instrument range.
      </Warning>

      <button onClick={handleRemap}>Convert</button>
    </Dialog>
  );
};
```

---

## Future Enhancements

- **Smart arrangement**: AI suggests best octave shifts
- **Voice leading**: Maintain smooth transitions between notes
- **Idiomatic writing**: Suggest instrument-specific techniques
- **Multi-instrument output**: Generate string quartet from piano score

---

## Next Steps

This feature will be implemented in Phase 3 or later. For now, focus on [MVP](mvp.md).
