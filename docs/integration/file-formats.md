# File Formats & Data Exchange

## Overview

Rescored uses MIDI as the primary file format:
- **MIDI** - Primary format for transcription output, notation display, playback, and export
- **JSON** - Internal frontend state representation

---

## MIDI

### Purpose

- **Transcription Output**: basic-pitch outputs MIDI
- **Intermediate Format**: Easier to work with than raw audio
- **Playback**: Tone.js can play MIDI directly
- **Export Option**: Some users prefer MIDI for DAWs

### Structure (SMF = Standard MIDI File)

```
Header:
  Format: 1 (multi-track)
  Tracks: 1 (piano)
  Division: 480 (ticks per quarter note)

Track 1:
  Time  Event
  0     Note On, pitch=60 (C4), velocity=80
  480   Note Off, pitch=60
  480   Note On, pitch=62 (D4), velocity=80
  960   Note Off, pitch=62
```

### MIDI Note Numbers

```
C-1 = 0
C0  = 12
C1  = 24
...
C4  = 60 (Middle C)
...
C8  = 108
G9  = 127 (max)
```

### Limitations vs. MusicXML

- No clef, key signature, time signature (metadata only)
- No articulation marks (staccato, accents)
- No staff layout or page breaks
- No lyrics, dynamics (can encode as control messages, but not standardized)

### Conversion: MIDI → MusicXML

```python
from music21 import converter

# Parse MIDI
midi_score = converter.parse('input.mid')

# Analyze key
key_sig = midi_score.analyze('key')
midi_score.insert(0, key_sig)

# Add time signature
midi_score.insert(0, meter.TimeSignature('4/4'))

# Write MusicXML
midi_score.write('musicxml', fp='output.musicxml')
```

---

## Internal JSON Format

### Purpose

- **Frontend State**: Zustand store representation
- **REST API**: Alternative to MusicXML for API responses
- **Easier Editing**: Simpler than XML for programmatic manipulation

### Structure

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Transcribed Score",
  "composer": "Unknown",
  "key": "C",
  "timeSignature": "4/4",
  "tempo": 120,
  "measures": [
    {
      "id": "m1",
      "number": 1,
      "notes": [
        {
          "id": "n1",
          "pitch": "C4",
          "duration": "quarter",
          "startTime": 0,
          "octave": 4,
          "dotted": false
        },
        {
          "id": "n2",
          "pitch": "D4",
          "duration": "quarter",
          "startTime": 0.5,
          "octave": 4,
          "dotted": false
        }
      ]
    }
  ]
}
```

### Conversion: MusicXML ↔ JSON

```typescript
// MusicXML → JSON
function musicXMLToJSON(xml: string): Score {
  const parsed = parseScore(xml);

  return {
    id: generateId(),
    title: parsed.work?.workTitle || 'Untitled',
    key: parsed.parts[0].measures[0].attributes?.key?.fifths || 0,
    measures: parsed.parts[0].measures.map(m => ({
      id: `m${m.number}`,
      number: m.number,
      notes: m.notes.map(n => ({
        id: generateId(),
        pitch: `${n.pitch.step}${n.pitch.octave}`,
        duration: mapDuration(n.type),
        startTime: n.time,
      })),
    })),
  };
}

// JSON → MusicXML
function jsonToMusicXML(score: Score): string {
  // Use music21 or manual XML generation
  return `<?xml version="1.0"?>...`;
}
```

---

## Export Formats

### MusicXML Export

```typescript
const exportMusicXML = () => {
  const { score } = useNotationStore.getState();
  const xml = generateMusicXML(score);

  const blob = new Blob([xml], { type: 'application/vnd.recordare.musicxml+xml' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = 'score.musicxml';
  a.click();
};
```

### MIDI Export

```typescript
const exportMIDI = () => {
  const { score } = useNotationStore.getState();

  // Convert to MIDI using @tonejs/midi or similar
  const midi = new Midi();
  const track = midi.addTrack();

  score.measures.flatMap(m => m.notes).forEach(note => {
    track.addNote({
      midi: pitchToMIDI(note.pitch),
      time: note.startTime,
      duration: durationToSeconds(note.duration, score.tempo),
    });
  });

  const blob = new Blob([midi.toArray()], { type: 'audio/midi' });
  // ... download
};
```

### PDF Export (Future)

Requires server-side rendering (MuseScore CLI, LilyPond, or headless browser):

```bash
# Server-side
musescore score.musicxml -o score.pdf
```

---

## File Size Comparison

For a 3-minute piano piece (~200 notes):

| Format | Size | Use Case |
|--------|------|----------|
| MusicXML | ~200KB | Editing, archival, interchange |
| MIDI | ~5KB | Playback, DAW import |
| JSON | ~50KB | Frontend state, API responses |
| PDF | ~100KB | Printing, sharing (future) |

---

## Next Steps

See [WebSocket Protocol](websocket-protocol.md) for real-time data transfer.
