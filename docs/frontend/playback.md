# Audio Playback with Tone.js

## Overview

Tone.js provides browser-based MIDI playback with synthesis, allowing users to hear their notation.

## Why Tone.js?

- High-level WebAudio API wrapper
- Built-in Transport for timing and tempo control
- Multiple synthesis methods (samplers, synths)
- Scheduling for precise timing
- Easy MIDI playback

## Basic Playback Implementation

```typescript
import * as Tone from 'tone';

class PlaybackEngine {
  private sampler: Tone.Sampler;
  private isPlaying: boolean = false;

  constructor() {
    // Load piano samples
    this.sampler = new Tone.Sampler({
      urls: {
        A0: "A0.mp3",
        C1: "C1.mp3",
        // ... more samples across piano range
        C8: "C8.mp3",
      },
      baseUrl: "https://tonejs.github.io/audio/salamander/",
    }).toDestination();
  }

  async play(notes: Note[]) {
    await Tone.start();  // Required for browser autoplay policy

    const now = Tone.now();

    notes.forEach((note, index) => {
      const time = now + index * 0.5;  // 0.5s between notes
      this.sampler.triggerAttackRelease(note.pitch, note.duration, time);
    });

    this.isPlaying = true;
  }

  stop() {
    Tone.Transport.stop();
    this.isPlaying = false;
  }
}
```

## Playback Controls Component

```typescript
export const PlaybackControls: React.FC = () => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [tempo, setTempo] = useState(120);  // BPM
  const [currentBeat, setCurrentBeat] = useState(0);

  const playback = useRef(new PlaybackEngine());

  const handlePlay = async () => {
    const { score } = useNotationStore.getState();
    await playback.current.play(score.measures.flatMap(m => m.notes));
    setIsPlaying(true);
  };

  const handlePause = () => {
    playback.current.stop();
    setIsPlaying(false);
  };

  const handleTempoChange = (newTempo: number) => {
    setTempo(newTempo);
    Tone.Transport.bpm.value = newTempo;
  };

  return (
    <div className="playback-controls">
      <button onClick={isPlaying ? handlePause : handlePlay}>
        {isPlaying ? 'Pause' : 'Play'}
      </button>

      <label>
        Tempo: {tempo} BPM
        <input
          type="range"
          min="40"
          max="240"
          value={tempo}
          onChange={(e) => handleTempoChange(parseInt(e.target.value))}
        />
      </label>

      <div>Beat: {currentBeat} / {totalBeats}</div>
    </div>
  );
};
```

## Timing with Transport

```typescript
// Schedule notes using Transport for better timing control
Tone.Transport.bpm.value = 120;

notes.forEach((note) => {
  Tone.Transport.schedule((time) => {
    sampler.triggerAttackRelease(note.pitch, note.duration, time);
  }, note.startTime);
});

Tone.Transport.start();
```

## Visual Sync (Cursor Following Playhead)

```typescript
function syncCursorWithPlayback() {
  Tone.Transport.scheduleRepeat((time) => {
    const currentPosition = Tone.Transport.seconds;
    const currentMeasure = positionToMeasure(currentPosition);

    // Update UI to highlight current measure
    setActiveMeasure(currentMeasure);
  }, "16n");  // Update every 16th note
}
```

## Next Steps

See [Data Flow](data-flow.md) for state management integration.
