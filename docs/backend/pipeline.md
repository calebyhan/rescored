# Audio Processing Pipeline

## Overview

This document details the complete workflow from YouTube URL to MusicXML notation, including implementation details for each stage.

## Pipeline Architecture

```mermaid
graph TB
    subgraph Stage1["Stage 1: URL Validation & Audio Extraction (0-20%)"]
        Validate["Validate<br/>YouTube<br/>URL"]
        Download["Download<br/>with<br/>yt-dlp"]
        Extract["Extract<br/>Audio<br/>Track"]
        Audio1["audio.wav<br/>(stereo, 44.1kHz)"]

        Validate --> Download
        Download --> Extract
        Extract --> Audio1
    end

    subgraph Stage2["Stage 2: Source Separation (20-50%)"]
        Load["Load<br/>Audio<br/>to Tensor"]
        Demucs["Demucs<br/>Inference<br/>(GPU)"]
        SaveStems["Save<br/>Stems<br/>(.wav)"]
        Stems["drums.wav, bass.wav,<br/>vocals.wav, other.wav"]

        Load --> Demucs
        Demucs --> SaveStems
        SaveStems --> Stems
    end

    subgraph Stage3["Stage 3: Transcription (50-90%)"]
        ForEach["For Each<br/>Stem"]
        BasicPitch["basic-pitch<br/>Inference"]
        Quantize["Quantize<br/>& Clean<br/>MIDI"]
        MIDI["drums.mid, bass.mid,<br/>vocals.mid, other.mid"]

        ForEach --> BasicPitch
        BasicPitch --> Quantize
        Quantize --> MIDI
    end

    subgraph Stage4["Stage 4: MusicXML Generation (90-100%)"]
        Merge["Merge<br/>MIDI<br/>Tracks"]
        Detect["Detect<br/>Metadata<br/>(tempo, key)"]
        WriteMXML["Write<br/>MusicXML<br/>File"]
        Output["output.musicxml"]

        Merge --> Detect
        Detect --> WriteMXML
        WriteMXML --> Output
    end

    Stage1 --> Stage2
    Stage2 --> Stage3
    Stage3 --> Stage4
```

---

## Stage 1: URL Validation & Audio Extraction

### 1.1 URL Validation

**Purpose**: Ensure the YouTube URL is valid and the video is accessible before processing.

**Implementation**:

```python
from urllib.parse import urlparse, parse_qs
import re

def validate_youtube_url(url: str) -> tuple[bool, str | None]:
    """
    Validate YouTube URL and extract video ID.

    Returns:
        (is_valid, video_id or error_message)
    """
    # Supported formats:
    # - https://www.youtube.com/watch?v=VIDEO_ID
    # - https://youtu.be/VIDEO_ID
    # - https://m.youtube.com/watch?v=VIDEO_ID

    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return True, match.group(1)

    return False, "Invalid YouTube URL format"

def check_video_availability(video_id: str) -> dict:
    """
    Check if video is available for download (not age-restricted, not private).

    Uses yt-dlp's extract_info with download=False to check metadata.
    """
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,  # Don't download, just check availability
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)

            # Check duration (limit to 15 minutes for MVP)
            duration = info.get('duration', 0)
            if duration > 900:  # 15 minutes
                return {'available': False, 'reason': 'Video too long (max 15 minutes)'}

            # Check if age-restricted
            if info.get('age_limit', 0) > 0:
                return {'available': False, 'reason': 'Age-restricted content not supported'}

            return {'available': True, 'info': info}

    except yt_dlp.utils.DownloadError as e:
        return {'available': False, 'reason': str(e)}
```

**Checks**:
- Valid YouTube domain and video ID format
- Video is publicly accessible (not private, deleted, or blocked)
- Video is not age-restricted (yt-dlp can't handle without login)
- Video duration under 15 minutes (limit for MVP)

**Progress Update**: 5%

---

### 1.2 Audio Download

**Purpose**: Extract audio from YouTube video in highest quality.

**Implementation**:

```python
import yt_dlp
from pathlib import Path

def download_audio(video_id: str, output_dir: Path) -> Path:
    """
    Download audio from YouTube video.

    Returns:
        Path to downloaded audio file (WAV format, 44.1kHz)
    """
    output_path = output_dir / f"{video_id}.wav"

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '0',  # Highest quality
        }],
        'postprocessor_args': [
            '-ar', '44100',  # 44.1kHz sample rate
            '-ac', '2',      # Stereo (Demucs expects stereo)
        ],
        'outtmpl': str(output_path.with_suffix('')),  # yt-dlp adds .wav
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [lambda d: update_progress(d)],  # Hook for progress updates
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://youtube.com/watch?v={video_id}"])

    return output_path
```

**Parameters**:
- **Format**: `bestaudio/best` - Prefer audio-only stream (smaller download)
- **Codec**: WAV (uncompressed, required for ML models)
- **Sample Rate**: 44.1kHz (standard for Demucs and basic-pitch)
- **Channels**: Stereo (Demucs trained on stereo)

**Output**: `{job_id}.wav` (~30-50MB for 3-minute song)

**Progress Update**: 20%

**Error Handling**:
- Network errors → Retry up to 3 times
- Copyright blocks → Return error to user
- Rate limiting → Exponential backoff

---

## Stage 2: Source Separation

### 2.1 Demucs Inference

**Purpose**: Separate audio into individual instrument stems (drums, bass, vocals, other).

**Why Source Separation?**
- Transcription works better on isolated instruments
- Polyphonic audio (multiple instruments) is harder to transcribe accurately
- Enables per-instrument editing in future features

**Implementation**:

```python
import torch
import torchaudio
from demucs import pretrained
from demucs.apply import apply_model
from pathlib import Path

class DemucsProcessor:
    def __init__(self, model_name: str = "htdemucs", device: str = "cuda"):
        """
        Initialize Demucs model.

        Args:
            model_name: "htdemucs" (4-stem) or "htdemucs_6s" (6-stem)
            device: "cuda" or "cpu"
        """
        self.device = device
        self.model = pretrained.get_model(model_name).to(device)
        self.model.eval()

    def separate(self, audio_path: Path, output_dir: Path) -> dict[str, Path]:
        """
        Separate audio into stems.

        Returns:
            Dictionary mapping stem name to output path
            e.g., {"drums": Path("drums.wav"), "bass": Path("bass.wav"), ...}
        """
        # Load audio
        wav, sr = torchaudio.load(str(audio_path))

        # Resample to 44.1kHz if needed
        if sr != 44100:
            wav = torchaudio.functional.resample(wav, sr, 44100)

        # Move to GPU
        wav = wav.to(self.device)

        # Add batch dimension
        wav = wav.unsqueeze(0)

        # Run inference
        with torch.no_grad():
            sources = apply_model(self.model, wav, device=self.device)

        # sources shape: (batch=1, stems=4, channels=2, samples)
        sources = sources[0]  # Remove batch dimension

        # Save each stem
        stem_names = ["drums", "bass", "other", "vocals"]
        output_paths = {}

        for i, stem_name in enumerate(stem_names):
            output_path = output_dir / f"{stem_name}.wav"
            torchaudio.save(str(output_path), sources[i].cpu(), 44100)
            output_paths[stem_name] = output_path

            # Update progress after each stem
            progress = 20 + (i + 1) / 4 * 30  # 20-50%
            update_progress(progress, f"Separated {stem_name}")

        return output_paths
```

**Model Choice**:
- **htdemucs** (4-stem): Drums, bass, vocals, other (everything else)
- **htdemucs_6s** (6-stem): Drums, bass, vocals, guitar, piano, other

**For MVP**: Use `htdemucs` (4-stem) - simpler, faster

**Future**: Use `htdemucs_6s` for better instrument-specific transcription

**GPU Requirements**:
- VRAM: ~4GB for 3-minute song
- Processing time: ~30-60 seconds on RTX 3080

**CPU Fallback**:
- Processing time: ~10-15 minutes per song
- Set `device="cpu"` in constructor

**Output**: 4 WAV files, each ~20MB (total ~80MB)

**Progress Update**: 50%

---

## Stage 3: Transcription (Audio → MIDI)

### 3.1 basic-pitch Inference

**Purpose**: Convert each audio stem to MIDI notes (pitch, timing, duration).

**Why Per-Stem Transcription?**
- Isolated instruments are easier for the model to detect
- Reduces polyphonic complexity (fewer simultaneous notes)
- Better note onset detection

**Implementation**:

```python
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
import numpy as np
from pathlib import Path
from mido import MidiFile, MidiTrack, Message

class BasicPitchTranscriber:
    def __init__(self):
        # Model is auto-loaded by basic-pitch
        pass

    def transcribe_stem(self, audio_path: Path, output_path: Path) -> Path:
        """
        Transcribe audio to MIDI using basic-pitch.

        Returns:
            Path to output MIDI file
        """
        # Run inference
        model_output, midi_data, note_events = predict(
            audio_path=str(audio_path),
            model_or_model_path=ICASSP_2022_MODEL_PATH,
            onset_threshold=0.5,      # Note onset confidence threshold
            frame_threshold=0.3,      # Frame activation threshold
            minimum_note_length=127,  # ~58ms at 44.1kHz (filter very short notes)
            minimum_frequency=None,   # No frequency limits
            maximum_frequency=None,
            multiple_pitch_bends=False,  # Simpler MIDI output
            melodia_trick=True,       # Improves melody extraction
        )

        # Save MIDI
        midi_data.write(str(output_path))

        # Post-process MIDI (quantization, cleanup)
        cleaned_midi = self.clean_midi(output_path)

        return cleaned_midi

    def clean_midi(self, midi_path: Path) -> Path:
        """
        Quantize notes to nearest 16th note, remove duplicates.
        """
        mid = MidiFile(midi_path)

        # Quantize to 16th note grid (480 ticks per quarter note)
        ticks_per_16th = mid.ticks_per_beat // 4

        for track in mid.tracks:
            time = 0
            for msg in track:
                time += msg.time
                if msg.type in ['note_on', 'note_off']:
                    # Quantize timing to nearest 16th
                    quantized_time = round(time / ticks_per_16th) * ticks_per_16th
                    msg.time = quantized_time - time
                    time = quantized_time

        # Save cleaned MIDI
        cleaned_path = midi_path.with_stem(f"{midi_path.stem}_clean")
        mid.save(cleaned_path)

        return cleaned_path
```

**Parameters**:
- **onset_threshold** (0.5): Higher = fewer false positive notes, but may miss quiet notes
- **frame_threshold** (0.3): Controls note sustain detection
- **minimum_note_length** (127): Filter out very short artifacts
- **melodia_trick** (True): Improves monophonic melody detection

**MVP: Piano-Only Transcription**

For MVP, only transcribe the "other" stem (likely contains piano/keyboard):

```python
def transcribe_for_mvp(stems: dict[str, Path], output_dir: Path) -> Path:
    """
    MVP: Only transcribe 'other' stem (assumes piano/keyboard).
    """
    transcriber = BasicPitchTranscriber()

    # Only process 'other' stem
    other_stem = stems['other']
    midi_path = output_dir / "piano.mid"

    transcriber.transcribe_stem(other_stem, midi_path)

    return midi_path
```

**Future: Multi-Instrument**

Transcribe all stems and assign to appropriate instruments:

```python
stem_to_instrument = {
    'drums': 128,      # MIDI percussion track
    'bass': 33,        # Acoustic Bass
    'vocals': 53,      # Voice Oohs
    'other': 0,        # Acoustic Grand Piano
}

for stem_name, instrument_id in stem_to_instrument.items():
    midi = transcriber.transcribe_stem(stems[stem_name], output_dir / f"{stem_name}.mid")
    # Set MIDI program change to instrument_id
```

**Output**: `piano.mid` (~10-50KB depending on complexity)

**Progress Update**: 90%

---

## Stage 4: MusicXML Generation

### 4.1 MIDI to MusicXML Conversion

**Purpose**: Convert MIDI to MusicXML with proper notation semantics (clefs, key signatures, measures).

**Why MusicXML?**
- MIDI lacks notation info (no clefs, no measure boundaries, no articulations)
- MusicXML is the standard interchange format for notation software
- Required for VexFlow rendering

**Implementation**:

```python
from music21 import converter, stream, tempo, key, meter, clef
from pathlib import Path

class MusicXMLGenerator:
    def __init__(self):
        pass

    def midi_to_musicxml(self, midi_path: Path, output_path: Path) -> Path:
        """
        Convert MIDI to MusicXML with music21.
        """
        # Parse MIDI
        score = converter.parse(midi_path)

        # Detect key signature
        analyzed_key = score.analyze('key')
        score.insert(0, analyzed_key)

        # Set time signature (default 4/4, could detect from MIDI)
        score.insert(0, meter.TimeSignature('4/4'))

        # Detect tempo (from MIDI tempo events, or default to 120 BPM)
        midi_tempo = self._extract_tempo(score)
        score.insert(0, tempo.MetronomeMark(number=midi_tempo))

        # Add clef (treble for piano right hand)
        for part in score.parts:
            part.insert(0, clef.TrebleClef())

        # Split into measures (music21 does this automatically)
        score = score.makeMeasures()

        # Write MusicXML
        score.write('musicxml', fp=str(output_path))

        return output_path

    def _extract_tempo(self, score) -> int:
        """
        Extract tempo from MIDI or default to 120 BPM.
        """
        # Look for MIDI tempo events
        for element in score.flatten():
            if isinstance(element, tempo.MetronomeMark):
                return int(element.number)

        # Default
        return 120
```

**Metadata Added**:
- **Key signature**: Detected by music21's key analysis algorithm
- **Time signature**: Default to 4/4 (could improve with beat detection)
- **Tempo**: Extracted from MIDI tempo events or default to 120 BPM
- **Clef**: Treble clef for piano (could detect range and use bass clef)
- **Measures**: Automatically calculated based on time signature

**Output**: `score.musicxml` (~100-500KB depending on length)

**Progress Update**: 100%

---

## Error Handling & Recovery

### Transient Errors (Retry)

- YouTube download network errors → Retry 3x with exponential backoff
- GPU OOM (out of memory) → Retry with smaller batch size or CPU
- Temporary file I/O errors → Retry with new temp directory

**Implementation**:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def download_with_retry(video_id: str) -> Path:
    return download_audio(video_id, temp_dir)
```

### Permanent Errors (Fail Fast)

- Invalid YouTube URL → Return error immediately
- Age-restricted or private video → Cannot access, fail
- Copyright-blocked video → Cannot download, fail
- Video over 15 minutes → Reject immediately (MVP limit)

**Error Response**:

```python
{
    "job_id": "abc123",
    "status": "failed",
    "error": {
        "stage": "download",
        "message": "Video is age-restricted and cannot be downloaded",
        "retryable": false
    }
}
```

### Partial Failures

- Some stems fail transcription → Return partial results (e.g., only piano)
- Key detection fails → Default to C major
- Tempo detection fails → Default to 120 BPM

---

## Performance Optimization

### GPU Utilization

- **Demucs**: Fully GPU-accelerated, ~30-60s per song
- **basic-pitch**: GPU-accelerated, ~5-10s per stem
- **Bottleneck**: Source separation (Demucs) is slowest stage

**Optimization**:
- Use mixed precision (FP16) for faster inference: `torch.cuda.amp.autocast()`
- Keep model in GPU memory between jobs (avoid re-loading)

### Parallel Processing

**Current (Sequential)**:
```
Download → Separate → Transcribe stem 1 → Transcribe stem 2 → ... → MusicXML
```

**Optimized (Parallel)**:
```
Download → Separate → [Transcribe stem 1, Transcribe stem 2, ...] → MusicXML
                          (parallel)
```

**Implementation** (Future):

```python
from concurrent.futures import ThreadPoolExecutor

def transcribe_all_stems_parallel(stems: dict[str, Path]):
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(transcriber.transcribe_stem, path, output_dir / f"{name}.mid"): name
            for name, path in stems.items()
        }
        results = {futures[f]: f.result() for f in futures}
    return results
```

**Speedup**: ~2-3x faster for multi-stem transcription

---

## Storage Management

### Temporary Files

Created during processing:
- `{job_id}.wav` - Original audio (~40MB)
- `{job_id}/drums.wav`, `bass.wav`, etc. - Stems (~80MB total)
- `{job_id}/piano.mid` - MIDI (~50KB)

**Cleanup Strategy**:
- Delete after successful MusicXML generation
- Keep for 1 hour on failure (for debugging)
- Automatic cleanup via cron job or S3 lifecycle policy

### Output Files

Kept persistently:
- `{job_id}.musicxml` - Final output (~200KB)
- `{job_id}.midi` - MIDI export (~50KB)

**Retention**: 30 days, then delete (or move to user account storage)

---

## Monitoring & Metrics

### Per-Stage Metrics

Track processing time for each stage:
- Download time
- Separation time
- Transcription time per stem
- MusicXML generation time
- Total end-to-end time

**Target**:
- Total: < 2 minutes for 3-minute song on GPU
- Total: < 10 minutes on CPU

### Success Rates

- % of jobs that complete successfully
- % of jobs that fail at each stage
- Most common error types

**Alert** if success rate drops below 90%

---

## Next Steps

1. Implement [API endpoints](api.md) to trigger this pipeline
2. Set up [Celery workers](workers.md) to run pipeline asynchronously
3. Add WebSocket updates for real-time progress
4. Test with diverse YouTube videos (piano, rock, orchestral, etc.)

See [API Design](api.md) for how the frontend triggers this pipeline.
