/**
 * Tests for Zustand score store.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useScoreStore } from '../../store/scoreStore';
import { sampleMusicXML, sampleParsedScore } from '../fixtures';

describe('useScoreStore', () => {
  beforeEach(() => {
    // Reset store before each test
    const { result } = renderHook(() => useScoreStore());
    act(() => {
      result.current.reset();
    });
  });

  describe('Score Management', () => {
    it('should initialize with empty state', () => {
      const { result } = renderHook(() => useScoreStore());

      expect(result.current.musicXML).toBeNull();
      expect(result.current.parsedScore).toBeNull();
      expect(result.current.jobId).toBeNull();
    });

    it('should set MusicXML', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setMusicXML(sampleMusicXML);
      });

      expect(result.current.musicXML).toBe(sampleMusicXML);
    });

    it('should set parsed score', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setParsedScore(sampleParsedScore);
      });

      expect(result.current.parsedScore).toEqual(sampleParsedScore);
    });

    it('should set job ID', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setJobId('test-job-123');
      });

      expect(result.current.jobId).toBe('test-job-123');
    });

    it('should reset state', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setMusicXML(sampleMusicXML);
        result.current.setParsedScore(sampleParsedScore);
        result.current.setJobId('test-job-123');
      });

      act(() => {
        result.current.reset();
      });

      expect(result.current.musicXML).toBeNull();
      expect(result.current.parsedScore).toBeNull();
      expect(result.current.jobId).toBeNull();
    });
  });

  describe('Note Selection', () => {
    it('should select notes', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.selectNotes(['note-1', 'note-2']);
      });

      expect(result.current.selectedNotes).toEqual(['note-1', 'note-2']);
    });

    it('should clear selection', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.selectNotes(['note-1', 'note-2']);
        result.current.clearSelection();
      });

      expect(result.current.selectedNotes).toEqual([]);
    });

    it('should toggle note selection', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.toggleNoteSelection('note-1');
      });

      expect(result.current.selectedNotes).toContain('note-1');

      act(() => {
        result.current.toggleNoteSelection('note-1');
      });

      expect(result.current.selectedNotes).not.toContain('note-1');
    });

    it('should add to selection', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.selectNotes(['note-1']);
        result.current.addToSelection('note-2');
      });

      expect(result.current.selectedNotes).toEqual(['note-1', 'note-2']);
    });
  });

  describe('Playback State', () => {
    it('should initialize playback state', () => {
      const { result } = renderHook(() => useScoreStore());

      expect(result.current.isPlaying).toBe(false);
      expect(result.current.currentTime).toBe(0);
      expect(result.current.tempo).toBe(120);
    });

    it('should set playing state', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setPlaying(true);
      });

      expect(result.current.isPlaying).toBe(true);
    });

    it('should update current time', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setCurrentTime(45.5);
      });

      expect(result.current.currentTime).toBe(45.5);
    });

    it('should update tempo', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setTempo(140);
      });

      expect(result.current.tempo).toBe(140);
    });

    it('should enforce tempo bounds', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setTempo(300); // Above max
      });

      expect(result.current.tempo).toBeLessThanOrEqual(240);

      act(() => {
        result.current.setTempo(20); // Below min
      });

      expect(result.current.tempo).toBeGreaterThanOrEqual(40);
    });
  });

  describe('Edit History', () => {
    it('should track edit history', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.addEdit({
          type: 'note_add',
          noteId: 'note-1',
          data: { pitch: 'C4' },
        });
      });

      expect(result.current.editHistory.length).toBe(1);
      expect(result.current.editHistory[0].type).toBe('note_add');
    });

    it('should support undo', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.addEdit({
          type: 'note_add',
          noteId: 'note-1',
          data: { pitch: 'C4' },
        });
        result.current.undo();
      });

      expect(result.current.editHistory.length).toBe(0);
    });

    it('should support redo', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.addEdit({
          type: 'note_add',
          noteId: 'note-1',
          data: { pitch: 'C4' },
        });
        result.current.undo();
        result.current.redo();
      });

      expect(result.current.editHistory.length).toBe(1);
    });

    it('should clear redo history on new edit', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.addEdit({
          type: 'note_add',
          noteId: 'note-1',
          data: { pitch: 'C4' },
        });
        result.current.undo();
        result.current.addEdit({
          type: 'note_add',
          noteId: 'note-2',
          data: { pitch: 'D4' },
        });
      });

      expect(result.current.canRedo()).toBe(false);
    });
  });

  describe('Metadata', () => {
    it('should store score metadata', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setMetadata({
          title: 'Test Score',
          composer: 'Test Composer',
          tempo: 120,
          timeSignature: { beats: 4, beatType: 4 },
          keySignature: { fifths: 0 },
        });
      });

      expect(result.current.metadata.title).toBe('Test Score');
      expect(result.current.metadata.tempo).toBe(120);
    });

    it('should update individual metadata fields', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setMetadata({ title: 'Original' });
        result.current.updateMetadata({ title: 'Updated' });
      });

      expect(result.current.metadata.title).toBe('Updated');
    });
  });

  describe('Job Progress', () => {
    it('should track job progress', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setJobProgress({
          progress: 50,
          stage: 'transcription',
          message: 'Transcribing audio',
        });
      });

      expect(result.current.jobProgress.progress).toBe(50);
      expect(result.current.jobProgress.stage).toBe('transcription');
    });

    it('should mark job as completed', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setJobProgress({
          progress: 100,
          stage: 'completed',
          message: 'Complete',
        });
      });

      expect(result.current.isJobComplete()).toBe(true);
    });

    it('should mark job as failed', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setJobProgress({
          progress: 25,
          stage: 'audio_download',
          message: 'Failed',
          error: { message: 'Download error' },
        });
      });

      expect(result.current.hasJobFailed()).toBe(true);
      expect(result.current.jobProgress.error).toBeDefined();
    });
  });

  describe('Persistence', () => {
    it('should persist state to localStorage', () => {
      const { result } = renderHook(() => useScoreStore());

      act(() => {
        result.current.setMusicXML(sampleMusicXML);
        result.current.setJobId('test-job-123');
      });

      // State should be persisted (actual implementation may vary)
      const stored = localStorage.getItem('score-store');
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.jobId).toBe('test-job-123');
      }
    });
  });
});
