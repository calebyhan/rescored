/**
 * Test setup and configuration for frontend tests.
 */
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock VexFlow since it requires DOM and Canvas
vi.mock('vexflow', () => {
  // Minimal mocks for named exports used by NotationCanvas
  const Renderer = vi.fn(() => ({
    resize: vi.fn(),
    getContext: vi.fn(() => ({
      clear: vi.fn(),
    })),
  }));

  const Stave = vi.fn(() => ({
    addClef: vi.fn().mockReturnThis(),
    addTimeSignature: vi.fn().mockReturnThis(),
    addKeySignature: vi.fn().mockReturnThis(),
    setContext: vi.fn().mockReturnThis(),
    draw: vi.fn(),
    getWidth: vi.fn(() => 200),
  }));

  const StaveNote = vi.fn(() => ({
    addModifier: vi.fn(),
  }));

  const Voice = vi.fn(() => ({
    addTickables: vi.fn(),
    setMode: vi.fn(),
    draw: vi.fn(),
  }));
  (Voice as any).Mode = { SOFT: 0 };

  const Formatter = vi.fn(() => ({
    joinVoices: vi.fn().mockReturnThis(),
    format: vi.fn(),
  }));

  const Accidental = vi.fn();

  const StaveConnector = vi.fn(() => ({
    setType: vi.fn().mockReturnThis(),
    setContext: vi.fn().mockReturnThis(),
    draw: vi.fn(),
  }));
  (StaveConnector as any).type = { BRACE: 'brace', SINGLE_LEFT: 'singleleft' };

  return {
    Renderer,
    Stave,
    StaveNote,
    Voice,
    Formatter,
    Accidental,
    StaveConnector,
  };
});

// Mock Tone.js for audio playback
vi.mock('tone', () => ({
  Sampler: vi.fn(() => ({
    toDestination: vi.fn().mockReturnThis(),
    triggerAttackRelease: vi.fn(),
    loaded: true,
  })),
  Transport: {
    start: vi.fn(),
    stop: vi.fn(),
    pause: vi.fn(),
    position: 0,
    bpm: { value: 120 },
  },
  context: {
    resume: vi.fn(),
  },
}));

// Mock WebSocket
global.WebSocket = vi.fn(() => ({
  send: vi.fn(),
  close: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  readyState: WebSocket.OPEN,
})) as any;

// Mock IntersectionObserver (used by some UI libraries)
global.IntersectionObserver = vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
})) as any;

// Mock ResizeObserver (used by VexFlow)
global.ResizeObserver = vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
})) as any;
