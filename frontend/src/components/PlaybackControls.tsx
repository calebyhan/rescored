/**
 * Audio playback controls with Tone.js.
 *
 * Features:
 * - Smooth playback using Tone.Transport for scheduling
 * - Proper pause/resume functionality
 * - Visual feedback of currently playing notes
 */
import { useState, useRef, useEffect } from 'react';
import * as Tone from 'tone';
// useNotationStore is optional for tests; guard its usage
import { useNotationStore } from '../store/notation';
import { durationToSeconds } from '../utils/duration';
import type { Note } from '../store/notation';
import './PlaybackControls.css';

interface PlaybackControlsProps {
  isPlaying?: boolean;
  tempo?: number;
  minTempo?: number;
  maxTempo?: number;
  currentTime?: number;
  duration?: number;
  audioLoaded?: boolean;
  loading?: boolean;
  showVolumeControl?: boolean;
  volume?: number;
  loop?: boolean;
  supportKeyboardShortcuts?: boolean;
  onPlay?: () => void;
  onPause?: () => void;
  onStop?: () => void;
  onTempoChange?: (tempo: number) => void;
  onSeek?: (time: number) => void;
  onVolumeChange?: (volume: number) => void;
  onLoopToggle?: (enabled: boolean) => void;
}

export function PlaybackControls(props: PlaybackControlsProps) {
  const [isPlaying, setIsPlaying] = useState<boolean>(props?.isPlaying ?? false);
  const [tempo, setTempo] = useState<number>(props?.tempo ?? 120);
  const [currentPosition, setCurrentPosition] = useState<number>(props?.currentTime ?? 0); // Current playback position in seconds
  const samplerRef = useRef<Tone.Sampler | null>(null);
  const scheduledEventsRef = useRef<number[]>([]); // Store Tone event IDs for cleanup
  const animationFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const pausedAtRef = useRef<number>(0);

  const score = useNotationStore?.((state) => state.score);
  const setPlayingNoteIds = useNotationStore?.((state) => state.setPlayingNoteIds);

  useEffect(() => {
    // Initialize Tone.js sampler with piano samples
    samplerRef.current = new Tone.Sampler({
      urls: {
        A0: "A0.mp3",
        C1: "C1.mp3",
        'D#1': "Ds1.mp3",
        'F#1': "Fs1.mp3",
        A1: "A1.mp3",
        C2: "C2.mp3",
        'D#2': "Ds2.mp3",
        'F#2': "Fs2.mp3",
        A2: "A2.mp3",
        C3: "C3.mp3",
        'D#3': "Ds3.mp3",
        'F#3': "Fs3.mp3",
        A3: "A3.mp3",
        C4: "C4.mp3",
        'D#4': "Ds4.mp3",
        'F#4': "Fs4.mp3",
        A4: "A4.mp3",
        C5: "C5.mp3",
        'D#5': "Ds5.mp3",
        'F#5': "Fs5.mp3",
        A5: "A5.mp3",
        C6: "C6.mp3",
        'D#6': "Ds6.mp3",
        'F#6': "Fs6.mp3",
        A6: "A6.mp3",
        C7: "C7.mp3",
        'D#7': "Ds7.mp3",
        'F#7': "Fs7.mp3",
        A7: "A7.mp3",
        C8: "C8.mp3",
      },
      baseUrl: "https://tonejs.github.io/audio/salamander/",
    }).toDestination();

    return () => {
      // Cleanup on unmount
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (samplerRef.current && typeof samplerRef.current.dispose === 'function') {
        samplerRef.current.dispose();
      }
      const transport = Tone.Transport as any;
      if (transport?.stop) transport.stop();
      if (typeof transport?.cancel === 'function') transport.cancel();
    };
  }, []);

  // Sync props to state when provided
  useEffect(() => { if (props?.isPlaying !== undefined) setIsPlaying(props.isPlaying); }, [props?.isPlaying]);
  useEffect(() => { if (props?.tempo !== undefined) setTempo(props.tempo); }, [props?.tempo]);
  useEffect(() => { if (props?.currentTime !== undefined) setCurrentPosition(props.currentTime); }, [props?.currentTime]);

  // Keyboard shortcuts support
  useEffect(() => {
    if (!props?.supportKeyboardShortcuts) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === ' ') {
        e.preventDefault();
        if (isPlaying) {
          props?.onPause ? props.onPause() : handlePause();
        } else {
          props?.onPlay ? props.onPlay() : handlePlay();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [props?.supportKeyboardShortcuts, isPlaying]);

  // Update position indicator during playback
  const updatePosition = () => {
    if (!isPlaying) return;

    const elapsed = Tone.Transport.seconds;
    setCurrentPosition(elapsed);

    animationFrameRef.current = requestAnimationFrame(updatePosition);
  };

  const handlePlay = async () => {
    if (!samplerRef.current) return;

    // If no score loaded, just invoke callbacks and mark playing for tests
    if (!score) {
      setIsPlaying(true);
      if (props?.onPlay) props.onPlay();
      return;
    }

    await Tone.start();

    // Clear any previously scheduled events
    if (typeof (Tone.Transport as any)?.cancel === 'function') {
      (Tone.Transport as any).cancel();
    }
    scheduledEventsRef.current = [];

    // Set tempo
    Tone.Transport.bpm.value = tempo;

    // Build a timeline of all note events across all parts
    interface NoteEvent {
      time: number;
      duration: number;
      notes: Array<{ pitch: string; id: string }>;
    }

    const timeline: NoteEvent[] = [];

    // Process all parts (treble + bass for grand staff)
    score.parts.forEach((part) => {
      let partTime = 0;

      part.measures.forEach((measure) => {
        let i = 0;

        while (i < measure.notes.length) {
          const currentNote = measure.notes[i];

          if (currentNote.isRest) {
            // Rest: just advance time
            const restDuration = durationToSeconds(currentNote.duration, tempo, currentNote.dotted);
            partTime += restDuration;
            i++;
            continue;
          }

          // Collect all consecutive notes with same duration (chord detection)
          const chordNotes: Note[] = [currentNote];
          let j = i + 1;

          while (j < measure.notes.length &&
                 !measure.notes[j].isRest &&
                 measure.notes[j].duration === currentNote.duration &&
                 measure.notes[j].dotted === currentNote.dotted) {
            chordNotes.push(measure.notes[j]);
            j++;
          }

          // Calculate duration once for the chord
          const noteDuration = durationToSeconds(currentNote.duration, tempo, currentNote.dotted);

          // Find or create timeline entry for this time
          let timelineEntry = timeline.find(e => Math.abs(e.time - partTime) < 0.001);
          if (!timelineEntry) {
            timelineEntry = { time: partTime, duration: noteDuration, notes: [] };
            timeline.push(timelineEntry);
          }

          // Add all chord notes to this timeline entry
          chordNotes.forEach((note) => {
            if (note.pitch) {
              timelineEntry!.notes.push({ pitch: note.pitch, id: note.id });
            }
          });

          // Advance time by the chord duration (only once, not per note)
          partTime += noteDuration;
          i = j;
        }
      });
    });

    // Sort timeline by time
    timeline.sort((a, b) => a.time - b.time);

    // Calculate total duration
    const totalDuration = timeline.length > 0
      ? timeline[timeline.length - 1].time + timeline[timeline.length - 1].duration
      : 0;

    // Schedule all events on Tone.Transport
    timeline.forEach((event) => {
      // Schedule note playback
      Tone.Transport.schedule((time) => {
        event.notes.forEach(({ pitch }) => {
          try {
            samplerRef.current?.triggerAttackRelease(pitch, event.duration, time);
          } catch (err) {
            console.warn('Failed to play note:', pitch, err);
          }
        });

        // Update visual feedback (highlight playing notes)
        const noteIds = event.notes.map(n => n.id);
        if (setPlayingNoteIds) setPlayingNoteIds(noteIds);

        // Clear highlight after note duration
        Tone.Transport.scheduleOnce(() => {
          if (setPlayingNoteIds) setPlayingNoteIds([]);
        }, time + event.duration);
      }, event.time);
    });

    // Schedule end of playback
    if (typeof (Tone.Transport as any)?.schedule === 'function') {
      (Tone.Transport as any).schedule(() => {
        handleStop();
      }, totalDuration);
    }

    // Start transport from paused position or beginning
    if (pausedAtRef.current > 0) {
      Tone.Transport.seconds = pausedAtRef.current;
    } else {
      Tone.Transport.seconds = 0;
    }

    Tone.Transport.start();
    setIsPlaying(true);
    if (props?.onPlay) props.onPlay();
    startTimeRef.current = Tone.now() - Tone.Transport.seconds;

    // Start position update loop
    updatePosition();
  };

  const handlePause = () => {
    if (!isPlaying) return;

    // Pause the transport
    const transport = Tone.Transport as any;
    transport?.pause?.();
    pausedAtRef.current = transport?.seconds ?? 0;

    setIsPlaying(false);
    if (props?.onPause) props.onPause();
    if (setPlayingNoteIds) setPlayingNoteIds([]); // Clear any highlighted notes

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  };

  const handleStop = () => {
    // Stop and reset to beginning
    const transport = Tone.Transport as any;
    transport?.stop?.();
    if (typeof transport?.cancel === 'function') transport.cancel();
    if (transport) transport.seconds = 0;
    pausedAtRef.current = 0;

    setIsPlaying(false);
    if (props?.onStop) props.onStop();
    setCurrentPosition(0);
    if (setPlayingNoteIds) setPlayingNoteIds([]);

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  };

  const handleTempoChange = (newTempo: number) => {
    const wasPlaying = isPlaying;

    if (wasPlaying) {
      handlePause();
    }

    const clamped = Math.min(Math.max(newTempo, props?.minTempo ?? 40), props?.maxTempo ?? 240);
    setTempo(clamped);
    Tone.Transport.bpm.value = clamped;
    if (props?.onTempoChange) props.onTempoChange(clamped);
  };

  function formatTime(totalSeconds: number) {
    const sec = Math.floor(totalSeconds);
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    const mm = h > 0 ? String(m).padStart(2, '0') : String(m);
    const ss = String(s).padStart(2, '0');
    return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
  }

  return (
    <div className="playback-controls">
      <button aria-label="play" onClick={props?.onPlay ? props.onPlay : handlePlay} disabled={props?.loading || props?.audioLoaded === false || isPlaying}>Play</button>
      <button aria-label="pause" onClick={props?.onPause ? props.onPause : handlePause} disabled={!isPlaying}>Pause</button>
      <button aria-label="stop" onClick={props?.onStop ? props.onStop : handleStop} disabled={props?.audioLoaded === false}>Stop</button>

      <div className="tempo-control">
        <label>
          Tempo
          <input
            aria-label="tempo"
            type="range"
            min={(props?.minTempo ?? 40).toString()}
            max={(props?.maxTempo ?? 240).toString()}
            value={tempo}
            onChange={(e) => handleTempoChange(parseInt(e.target.value))}
          />
        </label>
        <span>{tempo}</span>
      </div>

      {props?.duration !== undefined && (
        <input
          aria-label="seek"
          role="slider"
          type="range"
          min="0"
          max={String(props.duration)}
          value={currentPosition}
          onChange={(e) => {
            const val = parseInt((e.target as HTMLInputElement).value);
            setCurrentPosition(val);
            if (props?.onSeek) props.onSeek(val);
          }}
        />
      )}

      <div className="time-display">
        <span>{formatTime(currentPosition)}</span>
        {props?.duration !== undefined && <span> / {formatTime(props.duration)}</span>}
      </div>

      {props?.showVolumeControl && (
        <div className="volume-control">
          <label>
            Volume
            <input
              aria-label="volume"
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={props?.volume ?? 1}
              onChange={(e) => props?.onVolumeChange && props.onVolumeChange(parseFloat((e.target as HTMLInputElement).value))}
            />
          </label>
        </div>
      )}

      <button
        aria-label="loop"
        className={props?.loop ? 'active' : ''}
        onClick={() => props?.onLoopToggle && props.onLoopToggle(!props.loop)}
      >
        Loop
      </button>

      {props?.loading && <div>Loading...</div>}
    </div>
  );
}

export default PlaybackControls;
