/**
 * Instrument-specific sampler configurations for Tone.js
 * Provides different sounds for piano, vocals, drums, bass, guitar, and other instruments
 */
import * as Tone from 'tone';

export type InstrumentType = 'piano' | 'vocals' | 'drums' | 'bass' | 'guitar' | 'other';

export interface InstrumentSamplerConfig {
  type: 'sampler' | 'synth';
  config: any;
}

/**
 * Configuration for each instrument type
 * Piano uses samples, others use synthesizers
 */
export const INSTRUMENT_CONFIGS: Record<InstrumentType, InstrumentSamplerConfig> = {
  piano: {
    type: 'sampler',
    config: {
      baseUrl: 'https://tonejs.github.io/audio/salamander/',
      urls: {
        A0: 'A0.mp3',
        C1: 'C1.mp3',
        'D#1': 'Ds1.mp3',
        'F#1': 'Fs1.mp3',
        A1: 'A1.mp3',
        C2: 'C2.mp3',
        'D#2': 'Ds2.mp3',
        'F#2': 'Fs2.mp3',
        A2: 'A2.mp3',
        C3: 'C3.mp3',
        'D#3': 'Ds3.mp3',
        'F#3': 'Fs3.mp3',
        A3: 'A3.mp3',
        C4: 'C4.mp3',
        'D#4': 'Ds4.mp3',
        'F#4': 'Fs4.mp3',
        A4: 'A4.mp3',
        C5: 'C5.mp3',
        'D#5': 'Ds5.mp3',
        'F#5': 'Fs5.mp3',
        A5: 'A5.mp3',
        C6: 'C6.mp3',
        'D#6': 'Ds6.mp3',
        'F#6': 'Fs6.mp3',
        A6: 'A6.mp3',
        C7: 'C7.mp3',
        'D#7': 'Ds7.mp3',
        'F#7': 'Fs7.mp3',
        A7: 'A7.mp3',
        C8: 'C8.mp3',
      },
    },
  },

  vocals: {
    type: 'synth',
    config: {
      oscillator: { type: 'sine' as const },
      envelope: {
        attack: 0.02,
        decay: 0.1,
        sustain: 0.3,
        release: 1,
      },
      // Soft, smooth sound appropriate for vocals
    },
  },

  drums: {
    type: 'synth',
    config: {
      // MembraneSynth configuration for percussion
      synth: 'membrane',
      pitchDecay: 0.05,
      octaves: 10,
      oscillator: { type: 'sine' as const },
      envelope: {
        attack: 0.001,
        decay: 0.4,
        sustain: 0.01,
        release: 1.4,
      },
    },
  },

  bass: {
    type: 'synth',
    config: {
      oscillator: { type: 'square' as const },
      envelope: {
        attack: 0.01,
        decay: 0.1,
        sustain: 0.4,
        release: 0.5,
      },
      // Deep, rich bass sound
    },
  },

  guitar: {
    type: 'synth',
    config: {
      oscillator: { type: 'triangle' as const },
      envelope: {
        attack: 0.005,
        decay: 0.2,
        sustain: 0.2,
        release: 0.5,
      },
      // Plucky guitar-like sound
    },
  },

  other: {
    type: 'sampler',
    config: {
      // Fallback to piano samples for unknown instruments
      baseUrl: 'https://tonejs.github.io/audio/salamander/',
      urls: {
        C4: 'C4.mp3',
        C5: 'C5.mp3',
        C6: 'C6.mp3',
      },
    },
  },
};

/**
 * Create an instrument-specific sampler or synthesizer
 * @param instrument The instrument type
 * @returns Tone.Sampler or Tone.PolySynth configured for the instrument
 */
export function createInstrumentSampler(instrument: InstrumentType): Tone.Sampler | Tone.PolySynth {
  const config = INSTRUMENT_CONFIGS[instrument] || INSTRUMENT_CONFIGS.other;

  if (config.type === 'sampler') {
    // Use sampler for piano and other instruments with sample libraries
    return new Tone.Sampler(config.config).toDestination();
  } else {
    // Use synthesizers for vocals, drums, bass, guitar
    if (instrument === 'drums') {
      // Use MembraneSynth for drums (percussive sound)
      return new Tone.PolySynth(Tone.MembraneSynth, config.config).toDestination();
    } else {
      // Use regular Synth for vocals, bass, guitar
      return new Tone.PolySynth(Tone.Synth, config.config).toDestination();
    }
  }
}
