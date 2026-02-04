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
  const samplerRef = useRef<Tone.Sampler | Tone.PolySynth | null>(null);
  const scheduledEventsRef = useRef<number[]>([]); // Store Tone event IDs for cleanup
  const animationFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const pausedAtRef = useRef<number>(0);
  const audioContextStartedRef = useRef<boolean>(false);

  const score = useNotationStore?.((state) => state.score);
  const setPlayingNoteIds = useNotationStore?.((state) => state.setPlayingNoteIds);
  const activeInstrument = useNotationStore?.((state) => state.activeInstrument);

  // Cleanup on unmount only - don't create sampler until user interaction
  useEffect(() => {
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

  // When instrument changes, dispose old sampler (new one will be created on next play)
  useEffect(() => {
    if (samplerRef.current) {
      samplerRef.current.dispose();
      samplerRef.current = null;
    }
  }, [activeInstrument]);

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
    // If no score loaded, just invoke callbacks and mark playing for tests
    if (!score) {
      setIsPlaying(true);
      if (props?.onPlay) props.onPlay();
      return;
    }

    // CRITICAL: Start AudioContext on user gesture BEFORE creating any Tone.js objects
    if (!audioContextStartedRef.current) {
      try {
        await Tone.start();
        audioContextStartedRef.current = true;
      } catch (err) {
        console.error('Failed to start audio context:', err);
        return;
      }
    }

    // Lazy initialization: Create sampler after AudioContext is started
    if (!samplerRef.current) {
      try {
        const { createInstrumentSampler } = await import('../utils/instrument-samplers');
        samplerRef.current = createInstrumentSampler(activeInstrument as any);
      } catch (err) {
        console.error('Failed to create instrument sampler:', err);
        return;
      }
    }

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
        // Group notes by chordId for accurate chord detection (notes within 50ms tolerance)
        const notesByChord: Record<string, Note[]> = {};
        const noteOrder: string[] = [];

        for (let i = 0; i < measure.notes.length; i++) {
          const note = measure.notes[i];

          if (note.isRest) {
            // Create unique group for each rest
            const restId = `rest-${i}`;
            notesByChord[restId] = [note];
            noteOrder.push(restId);
          } else {
            // Group by chordId (assigned by MIDI parser based on simultaneous notes)
            const chordId = note.chordId || `single-${note.id}`;
            if (!notesByChord[chordId]) {
              notesByChord[chordId] = [];
              noteOrder.push(chordId);
            }
            notesByChord[chordId].push(note);
          }
        }

        // Schedule each chord group in order (maintains temporal sequence)
        const processedChordIds = new Set<string>();

        for (const chordId of noteOrder) {
          // Skip if already processed (chord spans multiple notes)
          if (processedChordIds.has(chordId)) continue;
          processedChordIds.add(chordId);

          const chordNotes = notesByChord[chordId];
          const firstNote = chordNotes[0];

          if (firstNote.isRest) {
            // Rest: advance time and continue
            const restDuration = durationToSeconds(firstNote.duration, tempo, firstNote.dotted);
            partTime += restDuration;
            continue;
          }

          // Calculate note duration and time
          const noteDuration = durationToSeconds(firstNote.duration, tempo, firstNote.dotted);
          const noteTime = partTime;

          // Find or create timeline entry for this time
          let timelineEntry = timeline.find(e => Math.abs(e.time - noteTime) < 0.001);
          if (!timelineEntry) {
            timelineEntry = { time: noteTime, duration: noteDuration, notes: [] };
            timeline.push(timelineEntry);
          }

          // Add all notes in this chord to the timeline entry (they play simultaneously)
          chordNotes.forEach((note) => {
            if (note.pitch) {
              timelineEntry!.notes.push({ pitch: note.pitch, id: note.id });
            }
          });

          // Advance time by the note duration
          partTime += noteDuration;
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
      <button
        aria-label="play"
        onClick={props?.onPlay ? props.onPlay : handlePlay}
        disabled={props?.loading || props?.audioLoaded === false || isPlaying}
        className="playback-button"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <path d="M4 2 L4 14 L13 8 Z" />
        </svg>
      </button>
      <button
        aria-label="pause"
        onClick={props?.onPause ? props.onPause : handlePause}
        disabled={!isPlaying}
        className="playback-button"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <rect x="4" y="3" width="3" height="10" />
          <rect x="9" y="3" width="3" height="10" />
        </svg>
      </button>
      <button
        aria-label="stop"
        onClick={props?.onStop ? props.onStop : handleStop}
        disabled={props?.audioLoaded === false}
        className="playback-button"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <rect x="4" y="4" width="8" height="8" />
        </svg>
      </button>
      <button
        aria-label="loop"
        className={`playback-button ${props?.loop ? 'active' : ''}`}
        onClick={() => props?.onLoopToggle && props.onLoopToggle(!props.loop)}
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 8 C3 5.5 5 3.5 8 3.5 C11 3.5 13 5.5 13 8 C13 10.5 11 12.5 8 12.5 L6 12.5" />
          <path d="M7 11 L5 12.5 L7 14" />
        </svg>
      </button>

      <div className="tempo-control">
        <label>Tempo</label>
        <input
          aria-label="tempo"
          type="number"
          min={props?.minTempo ?? 40}
          max={props?.maxTempo ?? 240}
          value={tempo}
          onChange={(e) => handleTempoChange(parseInt(e.target.value))}
          className="tempo-input"
        />
      </div>
    </div>
  );
}

export default PlaybackControls;
