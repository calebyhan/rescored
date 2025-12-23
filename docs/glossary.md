# Glossary

## Musical Terms

### Notation Basics

**Staff** - Five horizontal lines on which music notation is written. Notes are placed on lines or in spaces between lines.

**Clef** - Symbol at the beginning of a staff indicating the pitch range:
- **Treble Clef** (G clef): Higher pitches (typically right hand for piano, melody instruments)
- **Bass Clef** (F clef): Lower pitches (typically left hand for piano, bass instruments)

**Grand Staff** - Two staves connected by a brace, used for piano (treble + bass clefs).

**Measure** (Bar) - Segment of music separated by vertical bar lines, containing a specific number of beats.

**Time Signature** - Indicates beats per measure and beat value:
- **4/4** (Common time): 4 beats per measure, quarter note gets one beat
- **3/4** (Waltz time): 3 beats per measure
- **6/8**: 6 eighth notes per measure

**Key Signature** - Sharps or flats at the start of the staff indicating the key:
- **C Major**: No sharps or flats
- **G Major**: One sharp (F#)
- **D Minor**: One flat (Bb)

**Tempo** - Speed of music, measured in BPM (beats per minute). Common tempos:
- 60 BPM: Slow (largo)
- 120 BPM: Moderate (moderato)
- 180 BPM: Fast (presto)

---

### Notes & Durations

**Pitch** - The frequency of a note, designated by letter (A-G) and octave number:
- **C4**: Middle C (261.6 Hz)
- **A4**: Concert A (440 Hz)

**Octave** - Interval between one pitch and another with double or half its frequency. Piano has ~7 octaves (A0-C8).

**Duration** - How long a note is held:
- **Whole Note**: 4 beats (in 4/4 time)
- **Half Note**: 2 beats
- **Quarter Note**: 1 beat
- **Eighth Note**: 0.5 beats
- **Sixteenth Note**: 0.25 beats

**Dotted Note** - Note with a dot after it, increasing duration by 50%:
- Dotted half note: 3 beats (2 + 1)
- Dotted quarter: 1.5 beats

**Rest** - Symbol indicating silence for a specific duration (whole rest, half rest, etc.).

---

### Accidentals & Alterations

**Sharp (♯)** - Raises pitch by one semitone (half step).

**Flat (♭)** - Lowers pitch by one semitone.

**Natural (♮)** - Cancels a sharp or flat.

**Semitone** - Smallest interval in Western music (e.g., C to C#, E to F).

---

### Performance Markings

**Articulation** - How a note is played:
- **Staccato**: Short, detached
- **Legato**: Smooth, connected
- **Accent**: Emphasized

**Dynamics** - Volume markings:
- **pp** (pianissimo): Very soft
- **p** (piano): Soft
- **mf** (mezzo forte): Moderately loud
- **f** (forte): Loud
- **ff** (fortissimo): Very loud

**Slur** - Curved line connecting notes to be played smoothly (legato).

**Tie** - Curved line connecting two notes of the same pitch, combining their durations.

---

## Technical Terms

### Audio Processing

**Sample Rate** - Number of audio samples per second (Hz). Standard: 44,100 Hz (44.1 kHz).

**Bit Depth** - Number of bits per audio sample. CD quality: 16-bit.

**WAV** - Uncompressed audio format. Large files but lossless quality.

**MP3/M4A** - Compressed audio formats. Smaller files but lossy quality.

**Frequency** - Pitch of a sound, measured in Hertz (Hz). Middle C = 261.6 Hz.

**Amplitude** - Volume/loudness of a sound.

---

### Music Information Retrieval (MIR)

**Source Separation** - Separating a mixed audio recording into individual instrument tracks (stems).

**Stem** - Isolated audio track for a single instrument (e.g., drums stem, bass stem, vocals stem).

**Transcription** - Converting audio into musical notation (MIDI or sheet music).

**Onset Detection** - Identifying the start time of each note in audio.

**Pitch Detection** - Identifying the frequency/pitch of a sound.

**Polyphonic** - Multiple notes sounding simultaneously (e.g., piano chord).

**Monophonic** - Single note at a time (e.g., flute melody, voice).

**Quantization** - Snapping note timings to a grid (e.g., 16th note grid) for cleaner notation.

---

### Machine Learning

**Model** - Trained neural network that performs a task (e.g., Demucs for source separation).

**Inference** - Running a model on new data to get predictions.

**GPU** (Graphics Processing Unit) - Specialized hardware for parallel computation, used to accelerate ML models.

**VRAM** - GPU memory. Demucs requires ~4-8GB VRAM.

**PyTorch** - Python ML framework, used by Demucs and basic-pitch.

**TensorFlow** - Python ML framework, used by Spleeter.

---

### File Formats

**MIDI** (Musical Instrument Digital Interface) - File format encoding note events (pitch, duration, velocity). Good for playback, lacks notation info.

**MusicXML** - XML-based format for music notation. Industry standard, used by Finale, Sibelius, MuseScore.

**PDF** - Portable Document Format. Used for printable sheet music.

**JSON** - JavaScript Object Notation. Used for internal state representation.

---

### Web Technologies

**REST API** - HTTP-based API using GET, POST, PUT, DELETE methods.

**WebSocket** - Persistent bidirectional connection for real-time updates (e.g., progress updates).

**SVG** (Scalable Vector Graphics) - XML-based vector image format. VexFlow renders notation as SVG.

**Canvas** - HTML5 element for drawing graphics programmatically (alternative to SVG).

---

### Backend Technologies

**FastAPI** - Modern Python web framework with async support and automatic API documentation.

**Celery** - Python task queue for async job processing.

**Redis** - In-memory data store used as Celery broker and cache.

**Worker** - Background process that executes jobs from the queue (Celery worker).

**Job Queue** - List of tasks waiting to be processed (e.g., transcription jobs).

**Task** - Unit of work in Celery (e.g., transcribe YouTube video).

---

### Frontend Technologies

**React** - JavaScript UI library for building component-based interfaces.

**VexFlow** - JavaScript library for rendering music notation in the browser.

**Tone.js** - JavaScript library for audio synthesis and playback, built on Web Audio API.

**Zustand** - Lightweight state management library for React.

**WebAudio API** - Browser API for audio processing, synthesis, and playback.

---

### Music Theory

**Concert Pitch** - Standard pitch reference (A4 = 440 Hz). Non-transposing instruments (piano, guitar) play in concert pitch.

**Transposing Instrument** - Instrument where written pitch differs from sounding pitch:
- **Bb Trumpet**: Written C sounds as Bb (2 semitones lower)
- **Eb Alto Sax**: Written C sounds as Eb (9 semitones lower)

**Voicing** - How notes of a chord are arranged (e.g., close voicing vs. open voicing).

**Arpeggio** - Playing chord notes one at a time instead of simultaneously.

---

## Rescored-Specific Terms

**Job** - Single transcription request with unique ID, tracked through processing pipeline.

**Progress** - Percentage (0-100) indicating how much of the job is complete.

**Stage** - Phase of processing: "download", "separation", "transcription", "musicxml".

**Score** - Complete musical notation for a piece (includes all parts, measures, notes).

**Part** - Single instrument's notation in a multi-instrument score.

**Stem** (in Rescored context) - Output of Demucs source separation (drums, bass, vocals, other).

---

## Acronyms

**API** - Application Programming Interface

**BPM** - Beats Per Minute

**CPU** - Central Processing Unit

**DMCA** - Digital Millennium Copyright Act

**GPU** - Graphics Processing Unit

**GUI** - Graphical User Interface

**HTTP** - HyperText Transfer Protocol

**MIDI** - Musical Instrument Digital Interface

**MIR** - Music Information Retrieval

**ML** - Machine Learning

**MVP** - Minimum Viable Product

**REST** - Representational State Transfer

**SDK** - Software Development Kit

**SVG** - Scalable Vector Graphics

**UI** - User Interface

**URL** - Uniform Resource Locator

**UX** - User Experience

**WS** - WebSocket

**XML** - eXtensible Markup Language

---

## Further Reading

- **Music Notation**: https://www.musictheory.net/
- **MIDI Specification**: https://www.midi.org/specifications
- **MusicXML**: https://www.musicxml.com/
- **Web Audio API**: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API

---

## See Also

- [Getting Started](getting-started.md) - How to use this documentation
- [Architecture Overview](architecture/overview.md) - System design
- [Challenges](research/challenges.md) - Known limitations
