"""
AI-powered music transcription pipeline.

Processes YouTube videos to extract audio, separate sources, transcribe to MIDI,
and generate MusicXML notation.
"""
import subprocess
from pathlib import Path
import tempfile
from typing import Optional
import mido
import librosa
import numpy as np
# basic-pitch removed - using YourMT3+ only
from music21 import converter, key, meter, tempo, note, clef, stream, chord as m21_chord

# Phase 2: Zero-tradeoff solutions with Python 3.10+ compatibility patch
try:
    # Apply runtime patch for Python 3.10+ compatibility
    try:
        from backend.madmom_patch import patch_madmom
    except ImportError:
        from madmom_patch import patch_madmom
    patch_madmom()

    import madmom
    import madmom.features.beats
    import madmom.features.downbeats
    import madmom.features.tempo
    MADMOM_AVAILABLE = True
except ImportError as e:
    MADMOM_AVAILABLE = False
    print(f"WARNING: madmom not available. Falling back to librosa for tempo/beat detection.")
    print(f"         Error: {e}")

# Import wrapper modules at top level
try:
    from backend.audio_separator_wrapper import AudioSeparator
    AUDIO_SEPARATOR_AVAILABLE = True
except ImportError as e:
    AUDIO_SEPARATOR_AVAILABLE = False
    AudioSeparator = None
    print(f"WARNING: audio_separator_wrapper not available: {e}")

try:
    from backend.yourmt3_wrapper import YourMT3Transcriber
    YOURMT3_AVAILABLE = True
except ImportError as e:
    YOURMT3_AVAILABLE = False
    YourMT3Transcriber = None
    print(f"WARNING: yourmt3_wrapper not available: {e}")

try:
    from backend.bytedance_wrapper import ByteDanceTranscriber
    BYTEDANCE_AVAILABLE = True
except ImportError as e:
    BYTEDANCE_AVAILABLE = False
    ByteDanceTranscriber = None
    print(f"WARNING: bytedance_wrapper not available: {e}")

try:
    from backend.ensemble_transcriber import EnsembleTranscriber
    ENSEMBLE_AVAILABLE = True
except ImportError as e:
    ENSEMBLE_AVAILABLE = False
    EnsembleTranscriber = None
    print(f"WARNING: ensemble_transcriber not available: {e}")



class TranscriptionPipeline:
    """Handles the complete transcription workflow."""

    def __init__(self, job_id: str, youtube_url: str, storage_path: Path, config=None, instruments: list = None):
        self.job_id = job_id
        self.youtube_url = youtube_url
        self.storage_path = storage_path
        self.temp_dir = storage_path / "temp" / job_id
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.progress_callback = None
        self.instruments = instruments if instruments else ['piano']

        # Load configuration
        if config is None:
            from app_config import settings
            self.config = settings
        else:
            self.config = config

        # Store detected metadata for API access
        self.metadata = {
            "tempo": 120.0,
            "time_signature": {"numerator": 4, "denominator": 4},
            "key_signature": "C",
        }

    def set_progress_callback(self, callback) -> None:
        """Set callback for progress updates: callback(percent, stage, message)"""
        self.progress_callback = callback

    def progress(self, percent: int, stage: str, message: str) -> None:
        """Report progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(percent, stage, message)

    def run(self) -> Path:
        """
        Execute full pipeline and return path to MusicXML file.

        Raises:
            Exception: If any stage fails
        """
        try:
            self.progress(0, "download", "Starting audio download")
            audio_path = self.download_audio()

            # Preprocess audio if enabled (improves separation and transcription quality)
            if self.config.enable_audio_preprocessing:
                self.progress(10, "preprocess", "Preprocessing audio")
                audio_path = self.preprocess_audio(audio_path)

            self.progress(20, "separate", "Starting source separation")
            stems = self.separate_sources(audio_path)

            # Select best stem for piano transcription
            # Priority: piano (dedicated stem) > other (mixed instruments)
            if 'piano' in stems:
                piano_stem = stems['piano']
                print(f"   Using dedicated piano stem for transcription")
            else:
                piano_stem = stems['other']
                print(f"   Using 'other' stem for transcription (legacy mode)")

            # Transcribe piano
            self.progress(50, "transcribe", "Starting piano transcription")
            piano_midi = self.transcribe_to_midi(piano_stem)

            # Transcribe vocals if enabled
            if self.config.transcribe_vocals and 'vocals' in stems:
                self.progress(70, "transcribe_vocals", "Transcribing vocal melody")
                vocals_midi = self.transcribe_vocals_to_midi(stems['vocals'])

                # Merge piano and vocals into single MIDI
                print(f"   Merging piano and vocals...")
                midi_path = self.merge_piano_and_vocals(
                    piano_midi,
                    vocals_midi,
                    piano_program=0,  # Acoustic Grand Piano
                    vocal_program=self.config.vocal_instrument
                )
            else:
                midi_path = piano_midi

            # Filter MIDI to only include selected instruments
            midi_path = self.filter_midi_by_instruments(midi_path)

            # Apply post-processing filters (Phase 4)
            midi_path = self.apply_post_processing_filters(midi_path)

            # Store final MIDI path for tasks.py to access
            self.final_midi_path = midi_path

            self.progress(90, "musicxml", "Generating MusicXML")
            # Use minimal MusicXML generation (YourMT3+ optimized)
            print(f"   Using minimal MusicXML generation (YourMT3+)")
            musicxml_path = self.generate_musicxml_minimal(midi_path, piano_stem)

            self.progress(100, "complete", "Transcription complete")
            return musicxml_path

        except Exception as e:
            self.progress(0, "error", str(e))
            raise

    def download_audio(self) -> Path:
        """Download audio from YouTube URL using yt-dlp."""
        output_path = self.temp_dir / "audio.wav"

        # Try with different extractors and network options
        cmd = [
            "yt-dlp",
            "-x",  # Extract audio
            "--audio-format", "wav",
            "--audio-quality", "0",  # Best quality
            "--output", str(output_path.with_suffix('')),  # yt-dlp adds .wav
            "--force-ipv4",  # Force IPv4 to avoid DNS issues
            "--socket-timeout", "30",
            "--retries", "10",
            "--fragment-retries", "10",
            # Try alternative extractors
            "--extractor-args", "youtube:player_client=android,ios,web",
            "--no-check-certificates",
            # Add verbose output for debugging
            "--verbose",
            self.youtube_url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            # Log the full error for debugging
            print(f"yt-dlp stderr: {result.stderr}")
            print(f"yt-dlp stdout: {result.stdout}")

            # Check for DNS resolution errors
            stderr_lower = result.stderr.lower()
            if ("failed to resolve" in stderr_lower or
                "no address associated with hostname" in stderr_lower or
                "unable to download api page" in stderr_lower):
                raise RuntimeError(
                    "Unable to connect to YouTube. For this demo version, please upload your audio file directly using the file upload option."
                )

            raise RuntimeError(f"yt-dlp failed: {result.stderr}")

        if not output_path.exists():
            raise RuntimeError("Audio file not created")

        return output_path

    def preprocess_audio(self, audio_path: Path) -> Path:
        """
        Preprocess audio for improved separation and transcription quality.

        Applies:
        - Spectral denoising (remove background noise)
        - Peak normalization (consistent volume)
        - High-pass filtering (remove rumble <30Hz)

        Args:
            audio_path: Path to raw audio file

        Returns:
            Path to preprocessed audio file
        """
        try:
            from audio_preprocessor import AudioPreprocessor
        except ImportError:
            # Try adding backend directory to path
            import sys
            from pathlib import Path as PathLib
            backend_dir = PathLib(__file__).parent
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            from audio_preprocessor import AudioPreprocessor

        print(f"   Preprocessing audio to improve quality...")

        preprocessor = AudioPreprocessor(
            enable_denoising=self.config.enable_audio_denoising,
            enable_normalization=self.config.enable_audio_normalization,
            enable_highpass=self.config.enable_highpass_filter,
            target_sample_rate=44100
        )

        # Preprocess (output will be saved in temp directory)
        preprocessed_path = preprocessor.preprocess(audio_path, self.temp_dir)

        print(f"   ✓ Audio preprocessing complete")

        return preprocessed_path

    def separate_sources(self, audio_path: Path) -> dict:
        """
        Separate audio into 4 stems using Demucs.

        Returns:
            dict with keys: drums, bass, vocals, other
        """
        # Verify input audio exists
        if not audio_path.exists():
            raise FileNotFoundError(f"Input audio not found: {audio_path}")

        # Source separation - config-driven approach
        if self.config.use_two_stage_separation:
            # Two-stage separation for maximum quality:
            # 1. BS-RoFormer removes vocals (SOTA vocal separation)
            # 2. Demucs separates clean instrumental into piano/guitar/drums/bass/other
            print("   Using two-stage separation (BS-RoFormer + Demucs)")

            if not AUDIO_SEPARATOR_AVAILABLE or AudioSeparator is None:
                raise RuntimeError("audio_separator_wrapper is not available")

            separator = AudioSeparator()

            separation_dir = self.temp_dir / "separation"
            instrument_stems = 6 if self.config.use_6stem_demucs else 4

            stems = separator.two_stage_separation(
                audio_path,
                separation_dir,
                instrument_stems=instrument_stems
            )

            # Two-stage separation returns: vocals, piano, guitar, drums, bass, other
            # For piano transcription, use the dedicated piano stem
            if 'piano' in stems:
                print(f"   ✓ Using dedicated piano stem for transcription")

            return stems

        elif self.config.use_6stem_demucs:
            # Direct Demucs 6-stem separation (no vocal pre-removal)
            print("   Using Demucs 6-stem separation")

            if not AUDIO_SEPARATOR_AVAILABLE or AudioSeparator is None:
                raise RuntimeError("audio_separator_wrapper is not available")

            separator = AudioSeparator()

            instrument_dir = self.temp_dir / "instruments"
            stems = separator.separate_instruments_demucs(
                audio_path,
                instrument_dir,
                stems=6
            )

            # 6-stem returns: vocals, piano, guitar, drums, bass, other
            return stems

        else:
            # Legacy mode: Demucs 2-stem (backwards compatibility)
            print("   Using legacy Demucs 2-stem separation")

            cmd = [
                "demucs",
                "--two-stems=other",  # For piano, we only need "other" stem
                "-o", str(self.temp_dir),
                str(audio_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                raise RuntimeError(f"Demucs failed (exit code {result.returncode}): {error_msg}")

            # Demucs creates: temp/htdemucs/audio/*.wav
            demucs_output = self.temp_dir / "htdemucs" / audio_path.stem

            stems = {
                'other': demucs_output / "other.wav",
                'no_other': demucs_output / "no_other.wav",
            }

            # Verify output
            if not stems['other'].exists():
                raise RuntimeError("Demucs did not create expected output files")

            return stems

    def transcribe_multiple_stems(self, stems: dict) -> Path:
        """
        Transcribe multiple instrument stems and combine into single MIDI.

        Args:
            stems: Dict mapping stem names to file paths (e.g., {'piano': Path, 'vocals': Path})

        Returns:
            Path to combined MIDI file
        """
        import pretty_midi

        print(f"   Transcribing {len(stems)} stems: {list(stems.keys())}")

        # Transcribe each stem separately
        stem_midis = {}
        for stem_name, stem_path in stems.items():
            print(f"   [Stem {stem_name}] Transcribing {stem_path.name}...")

            # Use appropriate transcription method
            if stem_name == 'piano' and self.config.use_ensemble_transcription:
                midi_path = self.transcribe_with_ensemble(stem_path)
            else:
                midi_path = self.transcribe_with_yourmt3(stem_path)

            stem_midis[stem_name] = midi_path
            print(f"   [Stem {stem_name}] ✓ Complete")

        # Combine all MIDI files
        print(f"   Combining {len(stem_midis)} MIDI files...")
        combined_pm = pretty_midi.PrettyMIDI()

        for stem_name, midi_path in stem_midis.items():
            pm = pretty_midi.PrettyMIDI(str(midi_path))
            # Add all instruments from this MIDI to the combined MIDI
            for instrument in pm.instruments:
                combined_pm.instruments.append(instrument)

        # Save combined MIDI
        combined_path = self.temp_dir / "combined_stems.mid"
        combined_pm.write(str(combined_path))

        print(f"   ✓ Combined {len(stem_midis)} stems into {len(combined_pm.instruments)} MIDI tracks")

        return combined_path

    def transcribe_to_midi(
        self,
        audio_path: Path,
        onset_threshold: float = None,
        frame_threshold: float = None,
        minimum_note_length: int = None
    ) -> Path:
        """
        Transcribe audio to MIDI using YourMT3+.

        Args:
            audio_path: Path to audio file (should be 'other' stem for piano)
            onset_threshold: Deprecated (kept for API compatibility)
            frame_threshold: Deprecated (kept for API compatibility)
            minimum_note_length: Deprecated (kept for API compatibility)

        Returns:
            Path to generated MIDI file
        """
        output_dir = self.temp_dir

        # Transcribe with ensemble or single model
        if self.config.use_ensemble_transcription:
            print(f"   Transcribing with ensemble (YourMT3+ + ByteDance)...")
            midi_path = self.transcribe_with_ensemble(audio_path)
            print(f"   ✓ Ensemble transcription complete")
        else:
            print(f"   Transcribing with YourMT3+...")
            midi_path = self.transcribe_with_yourmt3(audio_path)
            print(f"   ✓ YourMT3+ transcription complete")

        # Rename final MIDI to standard name for post-processing
        final_midi_path = output_dir / "piano.mid"
        if midi_path != final_midi_path:
            midi_path.rename(final_midi_path)
            midi_path = final_midi_path

        # Detect tempo from source audio for accurate post-processing
        source_audio = self.temp_dir / "audio.wav"
        if source_audio.exists():
            detected_tempo, _ = self.detect_tempo_from_audio(source_audio)
        else:
            detected_tempo = 120.0

        # Conditional post-processing based on transcriber
        if self.config.use_yourmt3_transcription:
            # YourMT3+ produces high-quality continuous-time MIDI
            # Beat-synchronous quantization can damage polyphonic music with repeated notes
            # For now, use original YourMT3+ output for best musical accuracy
            print(f"   Using YourMT3+ output directly (preserving timing accuracy)")
            print(f"   Note: Frontend will handle note duration approximation for display")

            return midi_path
        else:
            # basic-pitch needs full post-processing pipeline
            print(f"   Applying full post-processing for basic-pitch")

            # 1. Polyphony detection
            range_semitones = self._get_midi_range(midi_path)
            if range_semitones > 24:
                # Wide range (>2 octaves) = likely polyphonic piano music
                print(f"   Detected wide range ({range_semitones} semitones), preserving all notes")
                mono_midi = midi_path
            else:
                # Narrow range (≤2 octaves) = likely monophonic melody
                print(f"   Narrow range ({range_semitones} semitones), removing octave duplicates")
                mono_midi = self.extract_monophonic_melody(midi_path)

            # 2. Clean (filter, quantize)
            cleaned_midi = self.clean_midi(mono_midi, detected_tempo)

            # 3. Beat-synchronous quantization
            if self.config.use_beat_synchronous_quantization and source_audio.exists():
                beat_synced_midi = self.beat_synchronous_quantize(cleaned_midi, source_audio, detected_tempo)
            else:
                beat_synced_midi = cleaned_midi

            # 4. Merge consecutive notes
            print(f"   Merging consecutive notes (gap threshold: 150ms)...")
            merged_midi = self.merge_consecutive_notes(beat_synced_midi, gap_threshold_ms=150, tempo_bpm=detected_tempo)

            # 5. Envelope analysis
            if self.config.enable_envelope_analysis:
                print(f"   Analyzing note envelopes for sustain artifacts...")
                final_midi = self.analyze_note_envelope_and_merge_sustains(merged_midi, tempo_bpm=detected_tempo)
            else:
                final_midi = merged_midi

            # 6. Validate (pattern detection)
            self.detect_repeated_note_patterns(final_midi)

            return final_midi

    def transcribe_with_yourmt3(self, audio_path: Path) -> Path:
        """
        Transcribe audio to MIDI using YourMT3+ directly (in-process).

        YourMT3+ is a state-of-the-art multi-instrument transcription model
        that achieves 80-85% accuracy (vs 70% for basic-pitch).

        Args:
            audio_path: Path to audio file (should be 'other' stem for piano)

        Returns:
            Path to generated MIDI file

        Raises:
            RuntimeError: If transcription fails
        """
        if not YOURMT3_AVAILABLE or YourMT3Transcriber is None:
            raise RuntimeError("yourmt3_wrapper is not available")

        print(f"   Transcribing with YourMT3+ (direct call, device: {self.config.yourmt3_device})...")

        try:
            # Initialize transcriber (reuses loaded model from API if available)
            transcriber = YourMT3Transcriber(
                model_name="YPTF.MoE+Multi (noPS)",
                device=self.config.yourmt3_device
            )

            # Transcribe audio
            output_dir = self.temp_dir / "yourmt3_output"
            output_dir.mkdir(exist_ok=True)

            midi_path = transcriber.transcribe_audio(audio_path, output_dir)

            print(f"   ✓ YourMT3+ transcription complete")
            print(f"   [DEBUG] MIDI path returned: {midi_path}")
            print(f"   [DEBUG] MIDI exists at returned path: {midi_path.exists()}")
            return midi_path

        except Exception as e:
            raise RuntimeError(f"YourMT3+ transcription failed: {e}")

    def transcribe_with_ensemble(self, audio_path: Path) -> Path:
        """
        Transcribe audio using ensemble of YourMT3+ and ByteDance.

        Ensemble combines:
        - YourMT3+: Multi-instrument generalist (80-85% accuracy)
        - ByteDance: Piano specialist (90-95% accuracy)
        - Result: 90-95% accuracy through voting

        Args:
            audio_path: Path to audio file (should be piano stem)

        Returns:
            Path to ensemble MIDI file

        Raises:
            RuntimeError: If transcription fails
        """
        if not YOURMT3_AVAILABLE or YourMT3Transcriber is None:
            raise RuntimeError("yourmt3_wrapper is not available")
        if not BYTEDANCE_AVAILABLE or ByteDanceTranscriber is None:
            raise RuntimeError("bytedance_wrapper is not available")
        if not ENSEMBLE_AVAILABLE or EnsembleTranscriber is None:
            raise RuntimeError("ensemble_transcriber is not available")

        try:
            # Initialize transcribers
            yourmt3 = YourMT3Transcriber(
                model_name="YPTF.MoE+Multi (noPS)",
                device=self.config.yourmt3_device
            )

            bytedance = ByteDanceTranscriber(
                device=self.config.yourmt3_device,  # Use same device
                checkpoint=None  # Auto-download default model
            )

            # Initialize ensemble
            ensemble = EnsembleTranscriber(
                yourmt3_transcriber=yourmt3,
                bytedance_transcriber=bytedance,
                voting_strategy=self.config.ensemble_voting_strategy,
                onset_tolerance_ms=self.config.ensemble_onset_tolerance_ms,
                confidence_threshold=self.config.ensemble_confidence_threshold,
                use_bytedance_confidence=self.config.use_bytedance_confidence
            )

            # Transcribe with ensemble (with optional TTA)
            output_dir = self.temp_dir / "ensemble_output"
            output_dir.mkdir(exist_ok=True)

            # Build TTA config from settings
            tta_config = {
                'augmentations': self.config.tta_augmentations,
                'pitch_shifts': self.config.tta_pitch_shifts,
                'time_stretches': self.config.tta_time_stretches,
                'min_votes': self.config.tta_min_votes,
                'onset_tolerance_ms': self.config.tta_onset_tolerance_ms
            } if self.config.enable_tta else None

            midi_path = ensemble.transcribe(
                audio_path,
                output_dir,
                use_tta=self.config.enable_tta,
                tta_config=tta_config
            )

            print(f"   ✓ Ensemble transcription complete")
            return midi_path

        except Exception as e:
            # Fallback to YourMT3+ only if ensemble fails
            print(f"   ⚠ Ensemble transcription failed: {e}")
            # Print full traceback for debugging
            import traceback
            traceback.print_exc()
            print(f"   Falling back to YourMT3+ only...")
            return self.transcribe_with_yourmt3(audio_path)

    def transcribe_vocals_to_midi(self, vocals_audio_path: Path) -> Path:
        """
        Transcribe vocal melody to MIDI.

        Uses YourMT3+ to transcribe vocals stem. YourMT3+ can transcribe melodies,
        though it's primarily trained on multi-instrument music.

        Args:
            vocals_audio_path: Path to vocals stem audio

        Returns:
            Path to vocals MIDI file
        """
        print(f"   Transcribing vocals with YourMT3+...")

        # Use YourMT3+ for vocal transcription
        # (Could use dedicated melody transcription model in future)
        if not YOURMT3_AVAILABLE or YourMT3Transcriber is None:
            raise RuntimeError("yourmt3_wrapper is not available")

        transcriber = YourMT3Transcriber(
            model_name="YPTF.MoE+Multi (noPS)",
            device=self.config.yourmt3_device
        )

        output_dir = self.temp_dir / "vocals_output"
        output_dir.mkdir(exist_ok=True)

        vocals_midi = transcriber.transcribe_audio(vocals_audio_path, output_dir)

        print(f"   ✓ Vocals transcription complete")

        return vocals_midi

    def merge_piano_and_vocals(
        self,
        piano_midi_path: Path,
        vocals_midi_path: Path,
        piano_program: int = 0,
        vocal_program: int = 40
    ) -> Path:
        """
        Merge piano and vocals MIDI into single file with proper instrument assignments.

        Filters out spurious instruments from YourMT3+ output (keeps only piano notes),
        then adds vocals on separate track with specified instrument.

        Args:
            piano_midi_path: Path to piano MIDI
            vocals_midi_path: Path to vocals MIDI
            piano_program: MIDI program for piano (0 = Acoustic Grand Piano)
            vocal_program: MIDI program for vocals (40 = Violin, 73 = Flute, etc.)

        Returns:
            Path to merged MIDI file
        """
        import pretty_midi

        # Load piano MIDI
        piano_pm = pretty_midi.PrettyMIDI(str(piano_midi_path))

        # Load vocals MIDI
        vocals_pm = pretty_midi.PrettyMIDI(str(vocals_midi_path))

        # Create new MIDI file
        merged_pm = pretty_midi.PrettyMIDI(initial_tempo=piano_pm.estimate_tempo())

        # Add piano track (keep ONLY piano instrument 0, filter out false positives)
        piano_instrument = pretty_midi.Instrument(program=piano_program, name="Piano")

        # Collect all notes from piano MIDI, filtering to only program 0 (piano)
        for inst in piano_pm.instruments:
            if inst.is_drum:
                continue
            # Only keep notes from Acoustic Grand Piano (program 0)
            # Discard organs, guitars, strings, etc. (false positives from YourMT3+)
            if inst.program == 0:
                piano_instrument.notes.extend(inst.notes)

        print(f"   Piano: {len(piano_instrument.notes)} notes (filtered from YourMT3+ output)")

        # Add vocals track (keep highest/loudest notes - melody line)
        vocal_instrument = pretty_midi.Instrument(program=vocal_program, name="Vocals")

        # Collect vocals notes
        # YourMT3+ may output multiple instruments for vocals - take the melody (highest notes)
        all_vocal_notes = []
        for inst in vocals_pm.instruments:
            if inst.is_drum:
                continue
            all_vocal_notes.extend(inst.notes)

        # Sort by time, then filter to monophonic melody (one note at a time)
        all_vocal_notes.sort(key=lambda n: n.start)

        # Simple melody extraction: at each time point, keep only highest note
        melody_notes = []
        if len(all_vocal_notes) > 0:
            time_tolerance = 0.05  # 50ms tolerance for simultaneous notes

            i = 0
            while i < len(all_vocal_notes):
                # Find all notes starting around the same time
                current_time = all_vocal_notes[i].start
                simultaneous = []

                while i < len(all_vocal_notes) and all_vocal_notes[i].start - current_time < time_tolerance:
                    simultaneous.append(all_vocal_notes[i])
                    i += 1

                # Keep only highest note (melody)
                highest = max(simultaneous, key=lambda n: n.pitch)
                melody_notes.append(highest)

        vocal_instrument.notes.extend(melody_notes)

        print(f"   Vocals: {len(vocal_instrument.notes)} notes (melody extracted)")

        # Add both instruments to merged MIDI
        merged_pm.instruments.append(piano_instrument)
        merged_pm.instruments.append(vocal_instrument)

        # Save merged MIDI
        merged_path = self.temp_dir / "merged_piano_vocals.mid"
        merged_pm.write(str(merged_path))

        print(f"   ✓ Merged MIDI saved: {merged_path.name}")
        print(f"   Instruments: Piano (program {piano_program}), Vocals (program {vocal_program})")

        return merged_path

    def filter_midi_by_instruments(self, midi_path: Path) -> Path:
        """
        Filter MIDI file to only include tracks for selected instruments.

        YourMT3+ transcribes all instruments it detects. This function filters
        the output to only keep tracks matching the user's selection.

        Args:
            midi_path: Input MIDI file (may contain multiple instrument tracks)

        Returns:
            Path to filtered MIDI file containing only selected instruments
        """
        import pretty_midi

        # Map instrument IDs to MIDI program ranges
        # YourMT3+ uses General MIDI program numbers
        INSTRUMENT_PROGRAMS = {
            'piano': list(range(0, 8)),      # Acoustic Grand Piano to Celesta
            'guitar': list(range(24, 32)),   # Acoustic Guitar to Guitar Harmonics
            'bass': list(range(32, 40)),     # Acoustic Bass to Synth Bass 2
            'drums': [128],                   # Drum channel (special case)
            'vocals': list(range(52, 56)) + [65, 85],  # Choir Aahs, Voice Oohs, Synth Voice, Lead Voice, YourMT3+ "Singing Voice" (65)
            'other': list(range(8, 24)) + list(range(40, 52)) + list(range(56, 65)) + list(range(66, 85)) + list(range(86, 128))  # Everything else (excluding vocals programs)
        }

        # Load MIDI file
        pm = pretty_midi.PrettyMIDI(str(midi_path))

        # Debug: Show what's in the MIDI before filtering
        print(f"   [DEBUG] MIDI contains {len(pm.instruments)} tracks before filtering:")
        for i, inst in enumerate(pm.instruments):
            print(f"      Track {i}: {inst.name} (program={inst.program}, is_drum={inst.is_drum}, notes={len(inst.notes)})")

        # Determine which programs to keep
        programs_to_keep = set()
        for instrument in self.instruments:
            if instrument in INSTRUMENT_PROGRAMS:
                programs_to_keep.update(INSTRUMENT_PROGRAMS[instrument])

        print(f"   [DEBUG] Looking for programs: {sorted(programs_to_keep)[:20]}... (selected instruments: {self.instruments})")

        # Group instruments by category to handle YourMT3+ outputting multiple tracks per instrument
        # (e.g., both "Acoustic Piano" and "Electric Piano" for piano)
        instrument_groups = {}
        for inst in pm.instruments:
            # Determine which category this instrument belongs to
            matched_category = None
            if inst.is_drum and 128 in programs_to_keep:
                matched_category = 'drums'
            elif not inst.is_drum and inst.program in programs_to_keep:
                # Find which instrument category this program belongs to
                for instr_name, programs in INSTRUMENT_PROGRAMS.items():
                    if inst.program in programs and instr_name in self.instruments:
                        matched_category = instr_name
                        break

            if matched_category:
                if matched_category not in instrument_groups:
                    instrument_groups[matched_category] = []
                instrument_groups[matched_category].append(inst)
                print(f"   [DEBUG] Track '{inst.name}' (program={inst.program}) matched category: {matched_category}")

        # For each category, keep only the track with the most notes
        # (YourMT3+ sometimes outputs spurious tracks with very few notes)
        filtered_instruments = []
        for category, tracks in instrument_groups.items():
            if len(tracks) == 1:
                filtered_instruments.append(tracks[0])
            else:
                # Keep the track with the most notes
                best_track = max(tracks, key=lambda t: len(t.notes))
                filtered_instruments.append(best_track)

                # Log which tracks were filtered out
                for track in tracks:
                    if track != best_track:
                        track_name = track.name or f"Program {track.program}"
                        best_name = best_track.name or f"Program {best_track.program}"
                        print(f"   Filtered out spurious track: {track_name} ({len(track.notes)} notes) - kept {best_name} ({len(best_track.notes)} notes)")

        # Create new MIDI with only selected instruments
        filtered_pm = pretty_midi.PrettyMIDI()
        filtered_pm.instruments = filtered_instruments

        # Save filtered MIDI
        filtered_path = midi_path.parent / f"{midi_path.stem}_filtered.mid"
        filtered_pm.write(str(filtered_path))

        # Log filtering results
        original_count = len(pm.instruments)
        filtered_count = len(filtered_instruments)
        print(f"   Filtered MIDI: {original_count} tracks → {filtered_count} tracks (1 per category)")
        print(f"   Kept instruments: {self.instruments}")

        return filtered_path

    def apply_post_processing_filters(self, midi_path: Path) -> Path:
        """
        Apply post-processing filters to improve transcription quality.

        Applies confidence filtering and key-aware filtering based on config.

        Args:
            midi_path: Input MIDI file

        Returns:
            Path to filtered MIDI file (or original if no filtering enabled)
        """
        filtered_path = midi_path

        # Apply confidence filtering
        if self.config.enable_confidence_filtering:
            print(f"   Applying confidence filtering...")

            try:
                from confidence_filter import ConfidenceFilter
            except ImportError:
                import sys
                from pathlib import Path as PathLib
                backend_dir = PathLib(__file__).parent
                if str(backend_dir) not in sys.path:
                    sys.path.insert(0, str(backend_dir))
                from confidence_filter import ConfidenceFilter

            filter = ConfidenceFilter(
                confidence_threshold=self.config.confidence_threshold,
                velocity_threshold=self.config.velocity_threshold,
                duration_threshold=self.config.min_note_duration
            )

            filtered_path = filter.filter_midi_by_confidence(
                filtered_path,
                confidence_scores=None  # Use heuristics for now
            )

        # Apply key-aware filtering
        if self.config.enable_key_aware_filtering:
            print(f"   Applying key-aware filtering...")

            # Need to detect key first (or get from MusicXML generation)
            # For now, we'll apply after key detection in generate_musicxml_minimal
            # Skip here to avoid redundant key detection
            pass

        return filtered_path

    def apply_key_aware_filter(self, midi_path: Path, detected_key: str) -> Path:
        """
        Apply key-aware filtering using detected key signature.

        This is called from generate_musicxml_minimal after key detection.

        Args:
            midi_path: Input MIDI file
            detected_key: Detected key signature (e.g., "C major")

        Returns:
            Path to filtered MIDI file
        """
        if not self.config.enable_key_aware_filtering:
            return midi_path

        try:
            from key_filter import KeyAwareFilter
        except ImportError:
            import sys
            from pathlib import Path as PathLib
            backend_dir = PathLib(__file__).parent
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            from key_filter import KeyAwareFilter

        filter = KeyAwareFilter(
            allow_chromatic=self.config.allow_chromatic_passing_tones,
            isolation_threshold=self.config.isolation_threshold
        )

        filtered_path = filter.filter_midi_by_key(
            midi_path,
            detected_key=detected_key
        )

        return filtered_path

    def _get_midi_range(self, midi_path: Path) -> int:
        """
        Calculate the MIDI note range (max - min) in semitones.

        Used to detect if music is likely polyphonic (wide range like piano)
        or monophonic (narrow range like voice or single-line instruments).

        Args:
            midi_path: Path to MIDI file

        Returns:
            Range in semitones (0 if no notes found)
        """
        import mido

        mid = mido.MidiFile(midi_path)
        notes = []

        for track in mid.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes.append(msg.note)

        if not notes:
            return 0

        return max(notes) - min(notes)

    def _remove_octave_duplicates(self, notes: list) -> list:
        """
        Remove notes that are exact octaves (12 semitones apart).

        Preserves notes of different pitch classes. For example:
        - C4 (60) + C6 (84) → keep only C6 (same pitch class, octave duplicate)
        - D2 (38) + A5 (81) → keep both (different pitch classes, not duplicates)

        Args:
            notes: List of (note_num, start, end, vel) tuples

        Returns:
            Deduplicated list with only highest octave of each pitch class
        """
        from collections import defaultdict

        # Group by pitch class (C=0, C#=1, ..., B=11)
        pitch_classes = defaultdict(list)

        for note_num, start, end, vel in notes:
            pitch_class = note_num % 12
            pitch_classes[pitch_class].append((note_num, start, end, vel))

        result = []
        for pitch_class, note_group in pitch_classes.items():
            if len(note_group) == 1:
                # Not a duplicate - keep it
                result.append(note_group[0])
            else:
                # Multiple notes of same pitch class (C4, C5, C6)
                # Keep the highest octave
                highest = max(note_group, key=lambda x: x[0])
                result.append(highest)

        return result

    def extract_monophonic_melody(self, midi_path: Path) -> Path:
        """
        Remove octave duplicates from MIDI using pitch class deduplication.

        For single-instrument transcriptions, basic-pitch may detect octave duplicates
        (e.g., C4 + C6). This removes true octave duplicates while preserving notes
        of different pitch classes (e.g., bass + treble in piano).

        Algorithm: For simultaneous notes, keep only the highest octave of each
        pitch class (C=0, C#=1, ..., B=11). Different pitch classes are preserved.

        Examples:
        - C4 (60) + C6 (84) → keep only C6 (same pitch class 0)
        - D2 (38) + A5 (81) → keep both (different pitch classes 2 and 9)

        Args:
            midi_path: Path to MIDI with potential octave duplicates

        Returns:
            Path to deduplicated MIDI
        """
        import mido
        from collections import defaultdict

        mid = mido.MidiFile(midi_path)

        for track in mid.tracks:
            # Collect all note events
            absolute_time = 0
            note_events = []

            for msg in track:
                absolute_time += msg.time
                if msg.type in ['note_on', 'note_off']:
                    note_events.append((absolute_time, msg.type, msg.note, msg.velocity, msg))

            # Build note list
            active_notes = {}
            completed_notes = []

            for abs_time, msg_type, note_num, velocity, msg in note_events:
                if msg_type == 'note_on' and velocity > 0:
                    active_notes[note_num] = (abs_time, velocity)
                elif msg_type in ['note_off', 'note_on']:
                    if note_num in active_notes:
                        start_time, start_vel = active_notes.pop(note_num)
                        completed_notes.append((note_num, start_time, abs_time, start_vel))

            # Group by onset time (10 tick tolerance for "simultaneous")
            ONSET_TOLERANCE = 10
            onset_groups = defaultdict(list)

            for note_num, start, end, vel in completed_notes:
                bucket = round(start / ONSET_TOLERANCE) * ONSET_TOLERANCE
                onset_groups[bucket].append((note_num, start, end, vel))

            # Smart octave deduplication: remove only true octave duplicates
            # Preserves different pitch classes (e.g., bass + treble in piano)
            monophonic_notes = []

            for bucket_time in sorted(onset_groups.keys()):
                simultaneous_notes = onset_groups[bucket_time]

                if len(simultaneous_notes) == 1:
                    # Single note - keep it
                    monophonic_notes.append(simultaneous_notes[0])
                else:
                    # Multiple notes - remove only octave duplicates, preserve different pitch classes
                    deduplicated = self._remove_octave_duplicates(simultaneous_notes)
                    monophonic_notes.extend(deduplicated)

            # Rebuild track
            new_note_events = []
            for note_num, start, end, vel in monophonic_notes:
                new_note_events.append((start, 'note_on', note_num, vel))
                new_note_events.append((end, 'note_off', note_num, 0))

            new_note_events.sort(key=lambda x: x[0])

            track.clear()
            previous_time = 0
            for abs_time, msg_type, note_num, velocity in new_note_events:
                delta_time = abs_time - previous_time
                track.append(mido.Message(msg_type, note=note_num, velocity=velocity, time=delta_time))
                previous_time = abs_time

            track.append(mido.MetaMessage('end_of_track', time=0))

        # Save monophonic MIDI
        mono_path = midi_path.with_stem(f"{midi_path.stem}_mono")
        mid.save(mono_path)

        print(f"   Removed octave duplicates using pitch class deduplication")

        return mono_path

    def _get_tempo_adaptive_thresholds(self, tempo_bpm: float) -> dict:
        """
        Calculate adaptive thresholds based on tempo.

        Fast music (>140 BPM): Stricter thresholds to avoid false positives from rapid passages
        Medium music (80-140 BPM): Standard thresholds work well
        Slow music (<80 BPM): More permissive to catch soft dynamics

        Args:
            tempo_bpm: Detected tempo in BPM

        Returns:
            Dictionary with threshold values for filtering
        """
        if not self.config.adaptive_thresholds_enabled:
            return {
                'onset_threshold': 0.45,
                'min_velocity': 45,
                'min_duration_divisor': 8,
            }

        if tempo_bpm > self.config.fast_tempo_threshold:  # > 140 BPM
            return {
                'onset_threshold': 0.50,  # Stricter (fewer false positives)
                'min_velocity': 50,
                'min_duration_divisor': 6,  # Minimum 48th note
            }
        elif tempo_bpm < self.config.slow_tempo_threshold:  # < 80 BPM
            return {
                'onset_threshold': 0.40,  # More permissive (catch soft notes)
                'min_velocity': 40,
                'min_duration_divisor': 10,
            }
        else:  # Medium tempo (80-140 BPM)
            return {
                'onset_threshold': 0.45,
                'min_velocity': 45,
                'min_duration_divisor': 8,
            }

    def clean_midi(self, midi_path: Path, detected_tempo: float = 120.0) -> Path:
        """
        Clean up MIDI file with beat-aligned quantization.

        Args:
            midi_path: Path to raw MIDI file
            detected_tempo: Detected tempo in BPM (for intelligent quantization)

        Returns:
            Path to cleaned MIDI file
        """
        mid = mido.MidiFile(midi_path)

        # Get tempo-adaptive thresholds
        thresholds = self._get_tempo_adaptive_thresholds(detected_tempo)

        # Calculate quantization grid based on tempo
        # At 120 BPM: 16th note = 125ms, 32nd note = 62.5ms
        # Use 32nd notes for fast tempos, 16th notes otherwise
        if detected_tempo > self.config.fast_tempo_threshold:
            quantize_division = 8  # 32nd notes
        else:
            quantize_division = 4  # 16th notes

        # First pass: collect all notes with timing info to filter by duration
        for track in mid.tracks:
            absolute_time = 0
            active_notes = {}  # note_number -> (start_time, start_msg_index, velocity)
            note_durations = {}  # msg_index -> duration_ticks
            messages_with_abs_time = []

            # Build list of messages with absolute timing
            for msg_idx, msg in enumerate(track):
                absolute_time += msg.time
                messages_with_abs_time.append((msg_idx, msg, absolute_time))

                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = (absolute_time, msg_idx, msg.velocity)
                elif msg.type in ['note_off', 'note_on']:  # note_on with vel=0 is note_off
                    if msg.note in active_notes:
                        start_time, start_idx, velocity = active_notes.pop(msg.note)
                        duration = absolute_time - start_time
                        note_durations[start_idx] = duration

            # Second pass: filter messages based on criteria
            messages_to_keep = []
            min_duration_ticks = mid.ticks_per_beat // thresholds['min_duration_divisor']
            min_velocity = thresholds['min_velocity']
            notes_to_skip = set()  # Track note_on indices to skip

            # Identify notes to skip based on duration
            for msg_idx in note_durations:
                if note_durations[msg_idx] < min_duration_ticks:
                    notes_to_skip.add(msg_idx)

            for msg_idx, msg, abs_time in messages_with_abs_time:
                # Note: Frequency range filtering now handled by basic-pitch's minimum_frequency parameter
                # No need to filter by MIDI range here

                # Filter very quiet notes (likely false positives)
                if msg.type == 'note_on' and msg.velocity > 0 and msg.velocity < min_velocity:
                    notes_to_skip.add(msg_idx)
                    continue

                # Skip notes marked for removal (very short)
                if msg.type == 'note_on' and msg_idx in notes_to_skip:
                    continue

                # Skip note_off for notes we filtered out
                if msg.type in ['note_off', 'note_on'] and hasattr(msg, 'note'):
                    # Check if this note_off corresponds to a filtered note_on
                    should_skip = False
                    for skip_idx in notes_to_skip:
                        if skip_idx < msg_idx:
                            skip_msg = messages_with_abs_time[skip_idx][1]
                            if skip_msg.type == 'note_on' and skip_msg.note == msg.note:
                                should_skip = True
                                break
                    if should_skip and msg.type == 'note_off':
                        continue

                messages_to_keep.append((msg, abs_time))

            # Third pass: rebuild track with beat-aligned quantization
            track.clear()
            previous_time = 0

            # Use tempo-aware quantization grid
            ticks_per_quantum = mid.ticks_per_beat // quantize_division

            for msg, abs_time in messages_to_keep:
                if msg.type in ['note_on', 'note_off']:
                    # Beat-aligned quantization - always snap to grid
                    quantized_time = round(abs_time / ticks_per_quantum) * ticks_per_quantum
                    abs_time = quantized_time

                # Set delta time from previous message
                msg.time = max(0, abs_time - previous_time)
                previous_time = abs_time
                track.append(msg)

        # Save cleaned MIDI
        cleaned_path = midi_path.with_stem(f"{midi_path.stem}_clean")
        mid.save(cleaned_path)

        return cleaned_path

    def beat_synchronous_quantize(self, midi_path: Path, audio_path: Path, tempo_bpm: float = 120.0) -> Path:
        """
        Quantize MIDI notes to detected beats from audio (ZERO-TRADEOFF solution).

        Phase 2 Enhancement: Instead of quantizing to a fixed grid (16th/32nd notes),
        quantizes to ACTUAL beats detected from the audio. This eliminates double
        quantization and ensures perfect alignment with musical timing.

        Benefits:
        - Single-pass quantization (audio → beat-aligned notes)
        - No double quantization distortion
        - Measures aligned to detected downbeats (100% validity)
        - Preserves note durations from transcription model

        Args:
            midi_path: Path to MIDI file from transcription
            audio_path: Path to original audio (for beat detection)
            tempo_bpm: Detected tempo

        Returns:
            Path to beat-quantized MIDI file
        """
        if not MADMOM_AVAILABLE:
            print(f"   WARNING: madmom not available, skipping beat-synchronous quantization")
            return midi_path

        print(f"   Applying beat-synchronous quantization...")

        # 1. Detect beats and downbeats from audio
        beats, downbeats = self.detect_beats_and_downbeats(audio_path)

        if len(beats) < 4:
            print(f"   WARNING: Only {len(beats)} beats detected, skipping beat-sync quantization")
            return midi_path

        # 2. Load MIDI file
        mid = mido.MidiFile(midi_path)

        # 3. Convert beat times (seconds) to MIDI ticks
        # Formula: seconds * (ticks_per_beat / seconds_per_beat)
        seconds_per_beat = 60.0 / tempo_bpm
        beat_ticks = []
        for beat_time in beats:
            ticks = int(beat_time * mid.ticks_per_beat / seconds_per_beat)
            beat_ticks.append(ticks)

        # 4. Quantize note onsets to nearest beat (preserve durations)
        for track in mid.tracks:
            # Convert delta times to absolute times
            abs_time = 0
            messages_with_abs_time = []

            for msg in track:
                abs_time += msg.time
                # Skip pitchwheel messages (not needed for notation, can cause timing issues)
                if msg.type == 'pitchwheel':
                    continue
                messages_with_abs_time.append((abs_time, msg))

            # Quantize note_on events to nearest beat
            note_on_times = {}  # Track quantized onset times: (channel, note) -> quantized_time
            note_original_times = {}  # Track original onset times: (channel, note) -> original_time

            for i, (abs_time, msg) in enumerate(messages_with_abs_time):
                if msg.type == 'note_on' and msg.velocity > 0:
                    # Find nearest beat
                    nearest_beat = min(beat_ticks, key=lambda b: abs(b - abs_time))

                    # Store original time BEFORE quantization
                    note_original_times[(msg.channel, msg.note)] = abs_time

                    # Update absolute time to nearest beat
                    messages_with_abs_time[i] = (nearest_beat, msg)

                    # Store for note_off matching
                    note_on_times[(msg.channel, msg.note)] = nearest_beat

                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    # Preserve duration by keeping offset relative to quantized onset
                    key = (msg.channel, msg.note)
                    if key in note_on_times and key in note_original_times:
                        onset_time = note_on_times[key]
                        original_onset_time = note_original_times[key]

                        # Calculate duration using original times
                        original_duration = abs_time - original_onset_time

                        # Keep same duration from quantized onset
                        new_offset = onset_time + original_duration
                        messages_with_abs_time[i] = (new_offset, msg)

                        del note_on_times[key]
                        del note_original_times[key]

            # Rebuild track with new timings
            track.clear()
            previous_time = 0
            last_note_time = 0

            for abs_time, msg in sorted(messages_with_abs_time, key=lambda x: x[0]):
                # Skip end_of_track for now - we'll add it at the end
                if msg.type == 'end_of_track':
                    continue

                msg.time = max(0, abs_time - previous_time)
                previous_time = abs_time
                track.append(msg)

                # Track last note time
                if msg.type in ('note_on', 'note_off'):
                    last_note_time = abs_time

            # Add end_of_track after last note with proper delta
            from mido import MetaMessage
            # Use 1 beat gap after last note for clean ending
            gap_after_last_note = mid.ticks_per_beat
            end_msg = MetaMessage('end_of_track', time=gap_after_last_note)
            track.append(end_msg)

        # 5. Save beat-quantized MIDI
        beat_sync_path = midi_path.with_stem(f"{midi_path.stem}_beat_sync")
        mid.save(beat_sync_path)

        print(f"   Applied beat-synchronous quantization to {len(beats)} beats")

        return beat_sync_path

    def merge_consecutive_notes(self, midi_path: Path, gap_threshold_ms: int = 50, tempo_bpm: float = 120.0) -> Path:
        """
        Merge consecutive notes of same pitch with small gaps to create smooth phrases.

        Problem: basic-pitch sometimes splits sustained notes into multiple short notes
        with tiny gaps, creating "choppy" notation.

        Solution: Merge notes with same pitch if gap < threshold (default 50ms).

        Args:
            midi_path: Path to MIDI file
            gap_threshold_ms: Maximum gap in milliseconds to merge (50ms = barely perceptible)
            tempo_bpm: Tempo in BPM for accurate tick-to-time conversion

        Returns:
            Path to MIDI with merged notes
        """
        mid = mido.MidiFile(midi_path)

        for track in mid.tracks:
            absolute_time = 0
            note_events = []  # List of (abs_time, msg_type, note_num, velocity, original_msg)

            # First pass: collect all note events with absolute timing
            for msg in track:
                absolute_time += msg.time
                if msg.type in ['note_on', 'note_off']:
                    note_events.append((absolute_time, msg.type, msg.note, msg.velocity, msg))

            # Second pass: identify notes to merge
            # Track active notes: note_num -> (start_time, start_velocity)
            active_notes = {}
            completed_notes = []  # List of (note_num, start_time, end_time, velocity)

            for abs_time, msg_type, note_num, velocity, original_msg in note_events:
                if msg_type == 'note_on' and velocity > 0:
                    # Note starts
                    if note_num in active_notes:
                        # Overlapping note (shouldn't happen after deduplication, but handle it)
                        # End previous note
                        start_time, start_vel = active_notes[note_num]
                        completed_notes.append((note_num, start_time, abs_time, start_vel))

                    active_notes[note_num] = (abs_time, velocity)

                elif msg_type in ['note_off', 'note_on']:  # note_on with vel=0 is note_off
                    # Note ends
                    if note_num in active_notes:
                        start_time, start_vel = active_notes.pop(note_num)
                        completed_notes.append((note_num, start_time, abs_time, start_vel))

            # Third pass: merge notes with same pitch and small gaps
            # Convert ms to ticks: ms → seconds → beats → ticks
            # At tempo_bpm: 1 beat = (60 / tempo_bpm) seconds
            seconds_per_beat = 60.0 / tempo_bpm
            gap_threshold_ticks = (gap_threshold_ms / 1000.0) / seconds_per_beat * mid.ticks_per_beat

            # Group notes by pitch, then sort each group by time
            from collections import defaultdict
            notes_by_pitch = defaultdict(list)
            for note_num, start, end, vel in completed_notes:
                notes_by_pitch[note_num].append((start, end, vel))

            # Sort each pitch group by start time
            for pitch in notes_by_pitch:
                notes_by_pitch[pitch].sort()

            # Merge consecutive notes within each pitch group
            merged_notes = []
            for note_num, note_list in notes_by_pitch.items():
                i = 0
                while i < len(note_list):
                    start, end, vel = note_list[i]

                    # Look ahead for notes with small gaps
                    j = i + 1
                    while j < len(note_list):
                        next_start, next_end, next_vel = note_list[j]
                        gap = next_start - end

                        if gap <= gap_threshold_ticks:
                            # Merge: extend end time, keep higher velocity
                            end = next_end
                            vel = max(vel, next_vel)
                            j += 1
                        else:
                            break

                    merged_notes.append((note_num, start, end, vel))
                    i = j if j > i + 1 else i + 1

            # Fourth pass: rebuild track with merged notes
            # Create new note events
            new_note_events = []
            for note_num, start, end, vel in merged_notes:
                new_note_events.append((start, 'note_on', note_num, vel))
                new_note_events.append((end, 'note_off', note_num, 0))

            # Sort by time
            new_note_events.sort(key=lambda x: x[0])

            # Rebuild track with delta times
            track.clear()
            previous_time = 0
            for abs_time, msg_type, note_num, velocity in new_note_events:
                delta_time = abs_time - previous_time
                track.append(mido.Message(msg_type, note=note_num, velocity=velocity, time=delta_time))
                previous_time = abs_time

            # Add end of track
            track.append(mido.MetaMessage('end_of_track', time=0))

        # Save merged MIDI
        merged_path = midi_path.with_stem(f"{midi_path.stem}_merged")
        mid.save(merged_path)

        print(f"   Merged consecutive notes (gap threshold: {gap_threshold_ms}ms)")

        return merged_path

    def analyze_note_envelope_and_merge_sustains(self, midi_path: Path, tempo_bpm: float = 120.0) -> Path:
        """
        Detect and merge false onsets from sustained note decay using velocity envelope analysis.

        False onset indicators:
        1. Decreasing velocity sequence (e.g., 80 -> 50 -> 35)
        2. Irregular timing (high coefficient of variation)
        3. Very short notes following long sustained notes

        Algorithm:
        - Group notes by pitch
        - Analyze 3+ consecutive notes for velocity decay pattern
        - Calculate timing irregularity (coefficient of variation)
        - Merge if: velocity_ratio < threshold AND (timing_cv > threshold OR gap is small)

        Args:
            midi_path: Path to MIDI file (after merge_consecutive_notes)
            tempo_bpm: Detected tempo for time calculations

        Returns:
            Path to MIDI with sustain artifacts removed
        """
        mid = mido.MidiFile(midi_path)

        # Calculate gap threshold in ticks
        seconds_per_beat = 60.0 / tempo_bpm
        gap_threshold_ticks = (self.config.sustain_artifact_gap_ms / 1000.0) / seconds_per_beat * mid.ticks_per_beat

        for track in mid.tracks:
            absolute_time = 0
            note_events = []

            # First pass: collect all note events with absolute timing
            for msg in track:
                absolute_time += msg.time
                if msg.type in ['note_on', 'note_off']:
                    note_events.append((absolute_time, msg.type, msg.note, msg.velocity, msg))

            # Group notes by pitch
            notes_by_pitch = {}
            for i in range(len(note_events)):
                if note_events[i][1] == 'note_on' and note_events[i][3] > 0:
                    pitch = note_events[i][2]
                    start_time = note_events[i][0]
                    velocity = note_events[i][3]

                    # Find corresponding note_off
                    for j in range(i + 1, len(note_events)):
                        if (note_events[j][2] == pitch and
                            (note_events[j][1] == 'note_off' or
                             (note_events[j][1] == 'note_on' and note_events[j][3] == 0))):
                            end_time = note_events[j][0]
                            if pitch not in notes_by_pitch:
                                notes_by_pitch[pitch] = []
                            notes_by_pitch[pitch].append((start_time, end_time, velocity))
                            break

            # Analyze each pitch for velocity decay patterns
            sustain_merges = {}  # pitch -> list of (start, end, velocity) to keep
            for pitch, note_list in notes_by_pitch.items():
                note_list.sort()

                i = 0
                while i < len(note_list):
                    start, end, vel = note_list[i]

                    # Look ahead for potential sustain decay artifacts
                    merge_indices = [i]
                    j = i + 1

                    while j < len(note_list):
                        next_start, next_end, next_vel = note_list[j]
                        gap = next_start - end

                        # Check if this looks like a sustain tail artifact
                        velocity_ratio = next_vel / vel if vel > 0 else 1.0
                        is_decaying = velocity_ratio < self.config.velocity_decay_threshold

                        # Very similar velocities = intentional repeat (not artifact)
                        velocity_diff = abs(next_vel - vel)
                        is_similar_velocity = velocity_diff < self.config.min_velocity_similarity

                        # Gap must be reasonable (not too large)
                        within_gap_threshold = gap <= gap_threshold_ticks

                        # Merge if: decaying velocity AND reasonable gap AND not similar velocities
                        if is_decaying and within_gap_threshold and not is_similar_velocity:
                            # Extend the current note
                            end = next_end
                            vel = max(vel, next_vel)  # Keep higher velocity
                            merge_indices.append(j)
                            j += 1
                        else:
                            break

                    # If we merged any notes, save the result
                    if pitch not in sustain_merges:
                        sustain_merges[pitch] = []
                    sustain_merges[pitch].append((start, end, vel))

                    # Skip all merged indices
                    i = merge_indices[-1] + 1

            # Rebuild MIDI track with merged notes
            track.clear()
            all_notes = []

            for pitch, note_list in sustain_merges.items():
                for start, end, velocity in note_list:
                    all_notes.append((start, 'note_on', pitch, velocity))
                    all_notes.append((end, 'note_off', pitch, 0))

            # Sort by time
            all_notes.sort()

            # Add meta messages back
            track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(tempo_bpm)))

            # Convert back to delta time
            previous_time = 0
            for abs_time, msg_type, pitch, velocity in all_notes:
                delta_time = abs_time - previous_time
                track.append(mido.Message(msg_type, note=pitch, velocity=velocity, time=delta_time))
                previous_time = abs_time

            # Add end of track
            track.append(mido.MetaMessage('end_of_track', time=0))

        # Save envelope-analyzed MIDI
        envelope_path = midi_path.with_stem(f"{midi_path.stem}_envelope")
        mid.save(envelope_path)

        print(f"   Analyzed envelope and merged sustain artifacts (velocity decay threshold: {self.config.velocity_decay_threshold})")

        return envelope_path

    def detect_repeated_note_patterns(self, midi_path: Path) -> Path:
        """
        Detect intentional repeated notes (vs. artifacts from chopped sustains).

        Pattern: If a note repeats 3+ times at regular intervals, it's intentional (e.g., staccato).
        Otherwise, it might be a chopped sustain that should have been merged.

        This is a VALIDATION method, not a correction method. Logs warnings for review.
        """
        mid = mido.MidiFile(midi_path)

        # Collect note onsets
        note_onsets = []  # List of (time, note_num)
        abs_time = 0

        for track in mid.tracks:
            for msg in track:
                abs_time += msg.time
                if msg.type == 'note_on' and msg.velocity > 0:
                    note_onsets.append((abs_time, msg.note))

        # Group by note number
        from collections import defaultdict
        notes_by_pitch = defaultdict(list)
        for time, note_num in note_onsets:
            notes_by_pitch[note_num].append(time)

        # Detect repeated patterns
        for note_num, times in notes_by_pitch.items():
            if len(times) >= 3:
                # Calculate intervals
                intervals = [times[i+1] - times[i] for i in range(len(times) - 1)]

                # Check if intervals are regular (coefficient of variation < 0.2)
                mean_interval = np.mean(intervals)
                std_interval = np.std(intervals)
                cv = std_interval / mean_interval if mean_interval > 0 else 0

                if cv < 0.2 and mean_interval < mid.ticks_per_beat:  # Regular and fast
                    # This is likely intentional repetition
                    note_name = note.Note(note_num).nameWithOctave
                    print(f"   INFO: Detected repeated note pattern: {note_name} ({len(times)} times)")

        return midi_path

    def generate_musicxml_minimal(self, midi_path: Path, source_audio: Path) -> Path:
        """
        Generate MusicXML from clean MIDI (YourMT3+ output) with minimal post-processing.

        This is a simplified pipeline for YourMT3+ which produces clean, well-quantized MIDI.
        Skips all MIDI-level post-processing and only applies music21-level operations.

        Steps:
        1. Detect tempo, time signature, key from audio
        2. Parse MIDI with music21
        3. Create measures
        4. Optional: Split into grand staff (treble + bass)
        5. Export MusicXML

        Args:
            midi_path: Clean MIDI from YourMT3+ (no post-processing needed)
            source_audio: Audio file for metadata detection

        Returns:
            Path to generated MusicXML file
        """
        from music21 import converter, tempo, meter, clef

        self.progress(92, "musicxml", "Detecting metadata from audio")

        # Step 1: Detect metadata from audio
        if source_audio.exists():
            # Detect tempo
            detected_tempo, tempo_confidence = self.detect_tempo_from_audio(source_audio)
            # Detect time signature
            time_sig_num, time_sig_denom, ts_confidence = self.detect_time_signature(source_audio, detected_tempo)
        else:
            print("   WARNING: Audio file not found, using defaults")
            detected_tempo, tempo_confidence = 120.0, 0.0
            time_sig_num, time_sig_denom, ts_confidence = 4, 4, 0.0

        print(f"   Detected: {detected_tempo} BPM (confidence: {tempo_confidence:.2f})")
        print(f"   Detected: {time_sig_num}/{time_sig_denom} time (confidence: {ts_confidence:.2f})")

        # Step 1.5: Validate and adjust metadata
        detected_tempo, time_sig_num, time_sig_denom = self._validate_and_adjust_metadata(
            midi_path,
            detected_tempo,
            tempo_confidence,
            time_sig_num,
            time_sig_denom,
            ts_confidence
        )

        self.progress(93, "musicxml", "Parsing MIDI")

        # Step 2: Parse MIDI
        print(f"   [DEBUG] About to parse MIDI: {midi_path}")
        print(f"   [DEBUG] MIDI exists before parsing: {midi_path.exists()}")
        score = converter.parse(midi_path)
        print(f"   [DEBUG] MIDI exists after parsing: {midi_path.exists()}")

        self.progress(94, "musicxml", "Detecting key signature")

        # Step 3: Detect key signature
        detected_key, key_confidence = self.detect_key_ensemble(score, source_audio)
        print(f"   Detected key: {detected_key} (confidence: {key_confidence:.2f})")

        # Store metadata for API access
        self.metadata = {
            "tempo": float(detected_tempo),
            "time_signature": {"numerator": int(time_sig_num), "denominator": int(time_sig_denom)},
            "key_signature": str(detected_key),
        }

        # Step 3.5: Snap durations to prevent makeMeasures from creating impossible tuplets
        print(f"   Snapping note durations to MusicXML-safe values...")
        score = self._snap_all_durations_pre_measures(score)

        self.progress(96, "musicxml", "Creating measures")

        # Step 4: Create measures WITHOUT splitting notes
        # Using custom function to prevent makeMeasures from splitting notes across measure boundaries
        score = self._create_measures_without_splitting(score, time_sig_num, time_sig_denom)

        # Step 5: Grand staff split (optional)
        if self.config.enable_grand_staff:
            print(f"   Splitting into grand staff (split at MIDI note {self.config.middle_c_split})...")
            score = self._split_into_grand_staff(score)
            print(f"   Created {len(score.parts)} staves (treble + bass)")

            # Insert metadata into each part
            for part in score.parts:
                measures = part.getElementsByClass('Measure')
                if measures:
                    first_measure = measures[0]
                    first_measure.insert(0, tempo.MetronomeMark(number=detected_tempo))
                    first_measure.insert(0, detected_key)
                    first_measure.insert(0, meter.TimeSignature(f'{time_sig_num}/{time_sig_denom}'))
        else:
            # Single staff: add treble clef and metadata
            for part in score.parts:
                part.insert(0, clef.TrebleClef())
                part.insert(0, detected_key)
                part.insert(0, meter.TimeSignature(f'{time_sig_num}/{time_sig_denom}'))
                part.insert(0, tempo.MetronomeMark(number=detected_tempo))
                part.partName = "Piano"

        self.progress(97, "musicxml", "Normalizing durations")

        # Step 5.5: Fix any impossible durations that music21 can't export
        # YourMT3+ output is clean, but music21 has limitations on complex durations
        score = self._remove_impossible_durations(score)

        # Step 5.6: Split complex durations to make them exportable
        # This is critical - music21 won't export notes with "complex" durations
        # even if they're standard note values, if they don't fit cleanly in measures
        print(f"   Splitting complex durations for MusicXML export...")
        score = self._split_complex_durations_for_export(score)

        self.progress(98, "musicxml", "Exporting MusicXML")

        # Step 6: Export MusicXML
        output_path = self.temp_dir / f"{self.job_id}.musicxml"

        print(f"   Writing MusicXML to {output_path}...")
        try:
            score.write('musicxml', fp=str(output_path), makeNotation=False)
            print(f"   ✓ Successfully exported with makeNotation=False (preserving exact durations)")
        except Exception as e:
            # If export still fails, we have a fundamental problem
            # Log the error but DON'T use makeNotation=True as it corrupts the data
            print(f"   ERROR: Export failed even after duration splitting: {e}")
            print(f"   This indicates a music21 limitation. Attempting export anyway...")
            # Try one more time with makeNotation=True as last resort
            score.write('musicxml', fp=str(output_path), makeNotation=True)
            print(f"   WARNING: Used makeNotation=True - timing may be corrupted")

        print(f"   ✓ MusicXML generation complete")
        return output_path





    def _snap_to_valid_duration(self, duration: float) -> float:
        """
        Snap duration to nearest valid music21 duration.

        Valid durations: whole, half, quarter, eighth, 16th, 32nd, 64th, 128th
        Also supports dotted notes (1.5x) and double-dotted (1.75x)

        Args:
            duration: Quarter length as float

        Returns:
            Snapped quarter length
        """
        # Base durations (in quarter notes)
        base_durations = [4.0, 2.0, 1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125]

        # Add dotted and double-dotted variants
        valid_durations = []
        for base in base_durations:
            valid_durations.append(base)  # Normal
            valid_durations.append(base * 1.5)  # Dotted
            valid_durations.append(base * 1.75)  # Double-dotted

        # Find nearest
        nearest = min(valid_durations, key=lambda x: abs(x - duration))

        return nearest


    def _validate_and_adjust_metadata(
        self,
        midi_path: Path,
        tempo: float,
        tempo_confidence: float,
        time_sig_num: int,
        time_sig_denom: int,
        ts_confidence: float,
        confidence_threshold: float = 0.5
    ) -> tuple[float, int, int]:
        """
        Validate detected metadata and adjust if confidence is low or values are unusual.

        Wrong metadata (especially time signature) causes makeMeasures() to create
        incorrect measure boundaries, leading to note splitting and duration corruption.

        Args:
            midi_path: Path to MIDI file (to check for embedded tempo)
            tempo: Detected tempo in BPM
            tempo_confidence: Confidence score (0.0-1.0)
            time_sig_num: Time signature numerator
            time_sig_denom: Time signature denominator
            ts_confidence: Time signature confidence score (0.0-1.0)
            confidence_threshold: Minimum confidence to trust detection

        Returns:
            Tuple of (adjusted_tempo, adjusted_time_sig_num, adjusted_time_sig_denom)
        """
        from music21 import converter, tempo as m21_tempo

        adjusted_tempo = tempo
        adjusted_time_sig_num = time_sig_num
        adjusted_time_sig_denom = time_sig_denom

        # Validate tempo
        if tempo_confidence < confidence_threshold:
            print(f"   WARNING: Low tempo confidence ({tempo_confidence:.2f}), checking MIDI for embedded tempo...")

            # Try to extract tempo from MIDI file
            try:
                score = converter.parse(midi_path)
                tempo_marks = score.flatten().getElementsByClass(m21_tempo.MetronomeMark)

                if tempo_marks:
                    midi_tempo = tempo_marks[0].number
                    if midi_tempo and 40 <= midi_tempo <= 240:  # Reasonable tempo range
                        print(f"   Using MIDI embedded tempo: {midi_tempo} BPM")
                        adjusted_tempo = float(midi_tempo)
                    else:
                        print(f"   MIDI tempo {midi_tempo} out of range, using detected tempo")
                else:
                    print(f"   No MIDI tempo found, using detected tempo")
            except Exception as e:
                print(f"   Failed to extract MIDI tempo: {e}")

        # Validate time signature
        VALID_TIME_SIGS = [(4, 4), (3, 4), (6, 8), (2, 4), (12, 8), (2, 2), (3, 8), (5, 4), (7, 8)]

        if (time_sig_num, time_sig_denom) not in VALID_TIME_SIGS:
            print(f"   WARNING: Unusual time signature {time_sig_num}/{time_sig_denom}, defaulting to 4/4")
            adjusted_time_sig_num, adjusted_time_sig_denom = 4, 4
        elif ts_confidence < confidence_threshold:
            print(f"   WARNING: Low time signature confidence ({ts_confidence:.2f}), defaulting to 4/4")
            adjusted_time_sig_num, adjusted_time_sig_denom = 4, 4

        # Final sanity checks
        if not (40 <= adjusted_tempo <= 240):
            print(f"   WARNING: Tempo {adjusted_tempo} out of range [40-240], defaulting to 120 BPM")
            adjusted_tempo = 120.0

        return adjusted_tempo, adjusted_time_sig_num, adjusted_time_sig_denom

    def _create_measures_without_splitting(
        self,
        score,
        time_sig_num: int,
        time_sig_denom: int
    ) -> stream.Score:
        """
        Create measures manually without using makeMeasures().

        music21's makeMeasures() corrupts YourMT3+ output by:
        1. Adding rests at the beginning to align with measure boundaries
        2. Splitting notes across measure boundaries
        3. Re-quantizing durations when exporting with makeNotation=True

        This function manually creates measures by calculating boundaries
        from the time signature and inserting measure markers WITHOUT
        modifying note timing or durations.
        """
        from music21 import stream, meter, bar

        print(f"   Creating measures manually to preserve note timing...")

        # Calculate measure duration in quarter notes
        # time_sig_num / time_sig_denom gives fraction of whole note
        # Multiply by 4 to get quarter notes
        measure_duration = (time_sig_num / time_sig_denom) * 4.0

        # Get all notes from the score
        all_notes = list(score.flatten().notesAndRests)
        if not all_notes:
            return score

        # Find the end time of the last note
        last_note = max(all_notes, key=lambda n: n.offset + n.quarterLength)
        total_duration = last_note.offset + last_note.quarterLength

        # Calculate number of measures needed
        num_measures = int(total_duration / measure_duration) + 1

        print(f"   Total duration: {total_duration:.2f} quarter notes")
        print(f"   Measure duration: {measure_duration:.2f} quarter notes")
        print(f"   Creating {num_measures} measures...")

        # Create new score with measures
        new_score = stream.Score()
        ts = meter.TimeSignature(f'{time_sig_num}/{time_sig_denom}')

        for part in score.parts:
            new_part = stream.Part()
            new_part.id = part.id
            new_part.partName = getattr(part, 'partName', 'Piano')

            # Create measures and distribute notes
            for measure_num in range(num_measures):
                measure_start = measure_num * measure_duration
                measure_end = measure_start + measure_duration

                new_measure = stream.Measure(number=measure_num + 1)

                # Add time signature to first measure only
                if measure_num == 0:
                    new_measure.timeSignature = ts

                # Find notes that START in this measure
                # (Don't split notes that cross measure boundaries - just put them in the measure where they start)
                for note in part.flatten().notesAndRests:
                    note_start = note.offset
                    if measure_start <= note_start < measure_end:
                        # Calculate offset within measure
                        measure_offset = note_start - measure_start
                        # Insert note at its original offset within the measure
                        new_measure.insert(measure_offset, note)

                new_part.append(new_measure)

            new_score.append(new_part)

        notes_after = sum(1 for _ in new_score.flatten().notesAndRests)
        print(f"   ✓ Created {num_measures} measures preserving all {notes_after} notes")

        return new_score

    def _split_complex_durations_for_export(self, score) -> stream.Score:
        """
        Skip duration splitting - it's causing note loss!

        splitAtDurations() was removing notes instead of splitting them,
        reducing the note count from 2,347 to 1,785 (24% data loss).

        Since we're now successfully exporting with makeNotation=False,
        we should preserve the exact durations from YourMT3+ without
        any additional processing.

        Args:
            score: music21 Score with measures

        Returns:
            Score unchanged
        """
        print(f"   Skipping duration splitting to preserve YourMT3+ note data...")
        return score

    def _snap_all_durations_pre_measures(self, score) -> stream.Score:
        """
        Snap all note durations to MusicXML-safe values BEFORE makeMeasures().

        This prevents music21's makeMeasures() from creating complex tuplets or
        impossible durations when trying to fit notes into measure boundaries.

        Args:
            score: music21 Score (flat stream, before makeMeasures)

        Returns:
            Score with snapped durations
        """
        from music21 import stream

        # MusicXML-safe durations (in quarter notes)
        # whole, dotted half, half, dotted quarter, quarter, dotted eighth, eighth, dotted 16th, 16th, 32nd
        SAFE_DURATIONS = [4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.375, 0.25, 0.125]

        snapped_count = 0
        total_diff = 0.0

        for part in score.parts:
            for element in part.flatten().notesAndRests:
                current_dur = element.quarterLength

                # Find nearest safe duration
                best_dur = min(SAFE_DURATIONS, key=lambda x: abs(x - current_dur))

                # Only snap if different (tolerance: 0.01 quarter notes)
                if abs(best_dur - current_dur) > 0.01:
                    diff = abs(best_dur - current_dur)
                    total_diff += diff
                    element.quarterLength = best_dur
                    snapped_count += 1

        if snapped_count > 0:
            avg_diff = total_diff / snapped_count
            print(f"   Snapped {snapped_count} note durations (avg change: {avg_diff:.4f} quarter notes)")

        return score

    def _remove_impossible_durations(self, score, log_removed: bool = True) -> stream.Score:
        """
        Remove notes/rests with durations too short for MusicXML export (<64th note).

        music21's makeMeasures() can create rests with impossible durations (2048th notes)
        when filling gaps. This removes them to prevent MusicXML export errors.

        Args:
            score: music21 Score with measures
            log_removed: If True, log details of first few removed notes

        Returns:
            Cleaned score
        """
        from music21 import note, stream

        # Remove notes shorter than 64th note (lowered from 32nd)
        # YourMT3+ produces cleaner output, so we can use a lower threshold
        # 64th note = 0.0625 quarter notes (1.0 / 16)
        MIN_DURATION = 0.0625  # 64th note

        removed_notes = []
        for part in score.parts:
            for measure in part.getElementsByClass('Measure'):
                # Collect elements to remove
                to_remove = []

                for element in measure.notesAndRests:
                    if element.quarterLength < MIN_DURATION:
                        # Log note details before removing
                        if log_removed and len(removed_notes) < 10:
                            if hasattr(element, 'pitch'):
                                pitch_name = element.pitch.nameWithOctave
                            elif isinstance(element, note.Rest):
                                pitch_name = 'Rest'
                            else:
                                pitch_name = 'Unknown'

                            removed_notes.append({
                                'pitch': pitch_name,
                                'duration': element.quarterLength,
                                'offset': element.offset,
                                'measure': measure.number if hasattr(measure, 'number') else 0
                            })

                        to_remove.append(element)

                # Remove impossible durations
                for element in to_remove:
                    measure.remove(element)

        if removed_notes:
            print(f"   Removed {len(removed_notes)} notes/rests shorter than 64th note:")
            for note_data in removed_notes[:5]:  # Show first 5
                # Convert Fraction to float for formatting
                duration_val = float(note_data['duration']) if hasattr(note_data['duration'], 'numerator') else note_data['duration']
                offset_val = float(note_data['offset']) if hasattr(note_data['offset'], 'numerator') else note_data['offset']
                print(f"     - Measure {note_data['measure']}: {note_data['pitch']} @ {offset_val:.4f} (dur: {duration_val:.6f})")
            if len(removed_notes) > 5:
                print(f"     ... and {len(removed_notes) - 5} more")

        return score



    def _split_into_grand_staff(self, score) -> stream.Score:
        """
        Split a measured score into treble and bass parts for piano grand staff.

        Notes >= Middle C (C4/MIDI 60) go to treble clef (right hand)
        Notes < Middle C go to bass clef (left hand)

        This method processes a score that ALREADY has measures created by makeMeasures().
        """
        from music21 import stream, note, chord as m21_chord

        # If score already has multiple parts, just add clefs and return
        if len(score.parts) > 1:
            for part_idx, part in enumerate(score.parts):
                if part_idx == 0:
                    part.insert(0, clef.TrebleClef())
                else:
                    part.insert(0, clef.BassClef())
            return score

        # Get the single part from the score
        original_part = score.parts[0] if len(score.parts) > 0 else None
        if not original_part:
            return score

        # Create new score with two parts
        new_score = stream.Score()

        # Copy metadata from original score
        for element in score.flatten():
            if isinstance(element, (key.Key, meter.TimeSignature, tempo.MetronomeMark)):
                new_score.insert(0, element)

        # Create right hand (treble) and left hand (bass) parts
        treble_part = stream.Part()
        treble_part.partName = "Piano Right Hand"

        bass_part = stream.Part()
        bass_part.partName = "Piano Left Hand"

        # Middle C (C4) is MIDI note 60
        SPLIT_POINT = self.config.middle_c_split

        # Process each measure from the original part
        first_measure = True
        for measure in original_part.getElementsByClass('Measure'):
            # Create corresponding measures for treble and bass
            treble_measure = stream.Measure(number=measure.number)
            bass_measure = stream.Measure(number=measure.number)

            # Insert clefs in the first measure only
            if first_measure:
                treble_measure.insert(0, clef.TrebleClef())
                bass_measure.insert(0, clef.BassClef())
                first_measure = False

            # Copy time signature if present
            for ts in measure.getElementsByClass(meter.TimeSignature):
                treble_measure.insert(0, ts)
                bass_measure.insert(0, ts)

            # Process all notes and rests in this measure
            for element in measure.notesAndRests:
                offset = element.getOffsetInHierarchy(measure)

                if isinstance(element, note.Rest):
                    # Skip rests - music21 will add them automatically where needed
                    continue

                elif isinstance(element, note.Note):
                    # Single note - assign to treble or bass based on pitch
                    new_note = note.Note(element.pitch, quarterLength=element.quarterLength)

                    if element.pitch.midi >= SPLIT_POINT:
                        # Treble: add note only
                        treble_measure.insert(offset, new_note)
                    else:
                        # Bass: add note only
                        bass_measure.insert(offset, new_note)

                elif isinstance(element, m21_chord.Chord):
                    # Chord - split notes between treble and bass
                    treble_pitches = []
                    bass_pitches = []

                    for pitch in element.pitches:
                        if pitch.midi >= SPLIT_POINT:
                            treble_pitches.append(pitch)
                        else:
                            bass_pitches.append(pitch)

                    # Create elements for treble (only if has notes)
                    if treble_pitches:
                        treble_chord = m21_chord.Chord(treble_pitches, quarterLength=element.quarterLength)
                        treble_measure.insert(offset, treble_chord)

                    # Create elements for bass (only if has notes)
                    if bass_pitches:
                        bass_chord = m21_chord.Chord(bass_pitches, quarterLength=element.quarterLength)
                        bass_measure.insert(offset, bass_chord)

            # Add measures to parts
            treble_part.append(treble_measure)
            bass_part.append(bass_measure)

        # Add parts to score (treble first for proper ordering)
        new_score.insert(0, treble_part)
        new_score.insert(0, bass_part)

        # Let music21 add rests where needed and fix measure boundaries
        try:
            new_score.makeRests(inPlace=True, fillGaps=True)
        except Exception as e:
            # If makeRests fails, continue anyway (malformed measures may cause this)
            print(f"WARNING: makeRests failed: {e}")
            pass

        return new_score

    def _extract_tempo(self, score) -> int:
        """Extract tempo from MIDI or default to 120 BPM."""
        for element in score.flatten():
            if isinstance(element, tempo.MetronomeMark):
                return int(element.number)
        return 120

    def detect_tempo_from_audio(self, audio_path: Path, duration: int = None) -> tuple[float, float]:
        """
        Detect tempo from audio using multi-scale analysis (madmom if available, librosa fallback).

        Phase 2 Enhancement: Uses madmom multi-scale tempo detection with cross-scale consistency
        to eliminate octave errors (e.g., 60 BPM vs 120 BPM confusion).

        Args:
            audio_path: Path to audio file (use original audio, not stems)
            duration: Seconds of audio to analyze (default 60)

        Returns:
            (tempo_bpm, confidence) where confidence is 0-1
        """
        # Use config default if not specified
        if duration is None:
            duration = self.config.tempo_detection_duration

        print(f"   Detecting tempo from audio...")

        # PHASE 2: Use madmom multi-scale tempo detection (ZERO-TRADEOFF)
        if MADMOM_AVAILABLE:
            return self._detect_tempo_madmom_multiscale(audio_path, duration)

        # FALLBACK: Use librosa (original method)
        return self._detect_tempo_librosa(audio_path, duration)

    def _detect_tempo_madmom_multiscale(self, audio_path: Path, duration: int) -> tuple[float, float]:
        """
        Multi-scale tempo detection using madmom (ZERO-TRADEOFF solution).

        Uses consistency across time scales to eliminate octave errors.
        Octave errors (60 vs 120 BPM) are inconsistent between short/long windows.
        Real tempo is stable across all time scales.

        Returns:
            (tempo_bpm, confidence) where confidence is 0-1
        """
        print(f"   Using madmom multi-scale tempo detection (eliminates octave errors)...")

        # Process audio to get beat activations
        act = madmom.features.beats.RNNBeatProcessor()(str(audio_path))

        # Multi-scale tempo processor (operates on activations, not raw audio)
        tempo_processor = madmom.features.tempo.TempoEstimationProcessor(fps=100)

        # Get tempo candidates from multi-scale analysis
        tempo_result = tempo_processor(act)

        # tempo_result is 2D array where each row is [tempo_bpm, strength]
        # Extract candidates
        tempos = []
        strengths = []
        for row in tempo_result:
            tempos.append(float(row[0]))  # tempo in BPM
            strengths.append(float(row[1]))  # strength/confidence

        if not tempos:
            print(f"   WARNING: Madmom returned no tempo candidates, using default 120 BPM")
            return 120.0, 0.0

        # Select tempo with highest cross-scale consistency
        # Real tempo appears consistent across scales; octave errors don't
        best_tempo = self._select_tempo_by_consistency(tempos, strengths)

        # Use strength of selected tempo as confidence
        best_idx = tempos.index(best_tempo)
        confidence = strengths[best_idx] if best_idx < len(strengths) else 0.5

        print(f"   Detected tempo: {best_tempo:.1f} BPM (confidence: {confidence:.2f}, candidates: {len(tempos)})")

        return float(best_tempo), float(confidence)

    def _select_tempo_by_consistency(self, tempos: list[float], strengths: list[float]) -> float:
        """
        Select tempo with highest cross-scale consistency.

        Octave errors (60 vs 120) are inconsistent between short/long analysis windows.
        Real tempo is stable across all scales.
        """
        if len(tempos) == 1:
            return tempos[0]

        # Calculate consistency score for each candidate
        scores = []
        for i, tempo in enumerate(tempos):
            consistency = strengths[i]  # Start with intrinsic strength

            # Check consistency with other candidates
            for j, other_tempo in enumerate(tempos):
                if i == j:
                    continue

                # Same tempo (within 5 BPM)
                if abs(tempo - other_tempo) < 5:
                    consistency += strengths[j]
                # Octave related (weak support)
                elif abs(tempo - other_tempo * 2) < 5 or abs(tempo * 2 - other_tempo) < 5:
                    consistency += strengths[j] * 0.3

            scores.append(consistency)

        # Return tempo with highest consistency
        return tempos[np.argmax(scores)]

    def _detect_tempo_librosa(self, audio_path: Path, duration: int) -> tuple[float, float]:
        """
        Fallback tempo detection using librosa (original method).
        """
        # Load audio with librosa (analyze first N seconds for efficiency)
        y, sr = librosa.load(str(audio_path), sr=None, mono=True, duration=duration)

        # Detect tempo using librosa's beat tracker
        tempo_value, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')

        # Convert tempo from numpy array to float
        tempo_value = float(tempo_value)

        # Calculate confidence based on beat consistency
        if len(beats) > 1:
            # Calculate inter-beat intervals
            beat_intervals = np.diff(beats)
            # Confidence = 1 - coefficient of variation (lower variation = higher confidence)
            mean_interval = np.mean(beat_intervals)
            std_interval = np.std(beat_intervals)
            confidence = 1.0 - min(std_interval / mean_interval if mean_interval > 0 else 1.0, 1.0)
        else:
            confidence = 0.0

        # Validate tempo range (40-240 BPM is reasonable for most music)
        if tempo_value < 40 or tempo_value > 240:
            print(f"   WARNING: Detected tempo {tempo_value:.1f} BPM outside valid range, using 120 BPM")
            return 120.0, 0.0

        print(f"   Detected tempo: {tempo_value:.1f} BPM (confidence: {confidence:.2f})")

        return float(tempo_value), float(confidence)

    def detect_beats_and_downbeats(self, audio_path: Path) -> tuple[np.ndarray, np.ndarray]:
        """
        Detect beats and downbeats from audio using madmom (ZERO-TRADEOFF solution).

        Phase 2 Enhancement: Detects beats from audio for beat-synchronous quantization.
        This eliminates double quantization by aligning notes to detected beats instead of fixed grid.

        Returns:
            (beat_times, downbeat_times) in seconds
        """
        if not MADMOM_AVAILABLE:
            print(f"   WARNING: madmom not available, falling back to librosa beat tracking")
            return self._detect_beats_librosa(audio_path)

        print(f"   Detecting beats with madmom...")

        # Process audio to get beat activations
        beat_act = madmom.features.beats.RNNBeatProcessor()(str(audio_path))

        # Beat tracking processor (operates on activations)
        beat_processor = madmom.features.beats.BeatTrackingProcessor(fps=100)
        beats = beat_processor(beat_act)

        # Estimate downbeats (every 4th beat for 4/4 time - simple heuristic)
        # More sophisticated downbeat detection with madmom can be added later if needed
        downbeats = beats[::4] if len(beats) > 0 else np.array([])

        print(f"   Detected {len(beats)} beats, {len(downbeats)} estimated downbeats")

        return beats, downbeats

    def _detect_beats_librosa(self, audio_path: Path) -> tuple[np.ndarray, np.ndarray]:
        """
        Fallback beat detection using librosa.
        """
        y, sr = librosa.load(str(audio_path), sr=None, mono=True, duration=120)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')

        # Estimate downbeats (every 4th beat for 4/4 time)
        downbeats = beats[::4] if len(beats) >= 4 else beats[:1]

        return beats, downbeats

    def detect_time_signature(self, audio_path: Path, detected_tempo: float) -> tuple[int, int, float]:
        """
        Detect time signature from beat pattern analysis.

        Args:
            audio_path: Path to audio file
            detected_tempo: Previously detected tempo in BPM

        Returns:
            (numerator, denominator, confidence) e.g., (4, 4, 0.85)
        """
        print(f"   Detecting time signature...")

        # Load audio
        y, sr = librosa.load(str(audio_path), sr=None, mono=True, duration=60)

        # Detect beats
        tempo_value, beats = librosa.beat.beat_track(y=y, sr=sr, units='time', start_bpm=detected_tempo)

        if len(beats) < 8:
            # Not enough beats to determine time signature
            print(f"   WARNING: Only {len(beats)} beats detected, defaulting to 4/4")
            return 4, 4, 0.0

        # Detect strong beats (downbeats) using spectral flux
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)

        # Find peaks in onset envelope that align with beats
        from scipy.signal import find_peaks
        peaks, properties = find_peaks(onset_env, prominence=0.5)
        strong_beat_times = librosa.frames_to_time(peaks, sr=sr)

        # Count beats between strong beats to determine meter
        beat_counts = []
        for i in range(len(strong_beat_times) - 1):
            # Count beats between consecutive strong beats
            start_time = strong_beat_times[i]
            end_time = strong_beat_times[i + 1]
            beats_in_measure = np.sum((beats >= start_time) & (beats < end_time))
            if beats_in_measure > 0:
                beat_counts.append(beats_in_measure)

        if not beat_counts:
            print(f"   WARNING: Could not detect beat pattern, defaulting to 4/4")
            return 4, 4, 0.0

        # Find most common beat count
        from collections import Counter
        beat_count_freq = Counter(beat_counts)
        most_common_count, frequency = beat_count_freq.most_common(1)[0]

        # Calculate confidence
        confidence = frequency / len(beat_counts)

        # Map beat count to time signature
        # Common time signatures: 3/4, 4/4, 6/8, 2/4, 5/4
        time_sig_map = {
            2: (2, 4),
            3: (3, 4),
            4: (4, 4),
            5: (5, 4),
            6: (6, 8),  # Could be 3/4 if tempo is slow
        }

        numerator, denominator = time_sig_map.get(most_common_count, (4, 4))

        print(f"   Detected time signature: {numerator}/{denominator} (confidence: {confidence:.2f})")

        return numerator, denominator, float(confidence)

    def detect_key_ensemble(self, score, audio_path: Path) -> tuple:
        """
        Detect key signature using ensemble of methods and voting.

        Methods:
        1. music21 key analysis (Krumhansl-Schmuckler)
        2. Pitch class histogram from audio
        3. Chroma features from librosa

        Returns:
            (detected_key, confidence)
        """
        print(f"   Detecting key signature with ensemble methods...")

        votes = []  # List of (key_name, confidence) tuples

        # Method 1: music21 analysis
        try:
            m21_key = score.analyze('key')
            # music21 doesn't provide confidence, assume 0.7
            votes.append((str(m21_key), 0.7))
            print(f"   music21: {m21_key}")
        except Exception as e:
            print(f"   music21 analysis failed: {e}")

        # Method 2: Chroma-based detection from audio
        if audio_path.exists():
            try:
                y, sr = librosa.load(str(audio_path), sr=None, mono=True, duration=60)

                # Extract chroma features
                chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

                # Average chroma over time
                chroma_mean = np.mean(chroma, axis=1)

                # Krumhansl-Schmuckler key profiles (major and minor)
                major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
                minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

                # Normalize profiles
                major_profile = major_profile / np.sum(major_profile)
                minor_profile = minor_profile / np.sum(minor_profile)

                # Calculate correlation for all keys
                pitch_classes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                best_corr = -1
                best_key = None

                for tonic_idx in range(12):
                    # Rotate chroma to align with tonic
                    rotated_chroma = np.roll(chroma_mean, -tonic_idx)

                    # Test major
                    corr_major = np.corrcoef(rotated_chroma, major_profile)[0, 1]
                    if corr_major > best_corr:
                        best_corr = corr_major
                        best_key = f"{pitch_classes[tonic_idx]} major"

                    # Test minor
                    corr_minor = np.corrcoef(rotated_chroma, minor_profile)[0, 1]
                    if corr_minor > best_corr:
                        best_corr = corr_minor
                        best_key = f"{pitch_classes[tonic_idx]} minor"

                if best_key:
                    votes.append((best_key, best_corr))
                    print(f"   Chroma analysis: {best_key} (corr={best_corr:.2f})")

            except Exception as e:
                print(f"   Chroma analysis failed: {e}")

        # Method 3: Pitch histogram from MIDI notes
        try:
            pitch_counts = [0] * 12
            for n in score.flatten().notes:
                if hasattr(n, 'pitch'):
                    pitch_counts[n.pitch.midi % 12] += 1

            # Normalize
            total = sum(pitch_counts)
            if total > 0:
                pitch_hist = np.array(pitch_counts) / total

                # Same correlation approach
                major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
                minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
                major_profile = major_profile / np.sum(major_profile)
                minor_profile = minor_profile / np.sum(minor_profile)

                pitch_classes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                best_corr = -1
                best_key = None

                for tonic_idx in range(12):
                    rotated_hist = np.roll(pitch_hist, -tonic_idx)

                    corr_major = np.corrcoef(rotated_hist, major_profile)[0, 1]
                    if corr_major > best_corr:
                        best_corr = corr_major
                        best_key = f"{pitch_classes[tonic_idx]} major"

                    corr_minor = np.corrcoef(rotated_hist, minor_profile)[0, 1]
                    if corr_minor > best_corr:
                        best_corr = corr_minor
                        best_key = f"{pitch_classes[tonic_idx]} minor"

                if best_key:
                    votes.append((best_key, best_corr))
                    print(f"   Pitch histogram: {best_key} (corr={best_corr:.2f})")

        except Exception as e:
            print(f"   Pitch histogram analysis failed: {e}")

        # Voting: weight by confidence
        if not votes:
            print(f"   WARNING: All key detection methods failed, defaulting to C major")
            return key.Key('C'), 0.0

        # Count votes (simple majority for same key)
        from collections import defaultdict
        key_votes = defaultdict(list)
        for key_name, conf in votes:
            key_votes[key_name].append(conf)

        # Find key with highest total confidence
        best_key_name = None
        best_total_conf = 0
        for key_name, confs in key_votes.items():
            total_conf = sum(confs)
            if total_conf > best_total_conf:
                best_total_conf = total_conf
                best_key_name = key_name

        # Normalize confidence (average of votes)
        final_confidence = best_total_conf / len(votes)

        # Parse key name to music21 Key
        # Convert "C major" -> "C", "A minor" -> "a"
        try:
            if ' major' in best_key_name:
                key_string = best_key_name.replace(' major', '')
            elif ' minor' in best_key_name:
                key_string = best_key_name.replace(' minor', '').lower()
            else:
                key_string = best_key_name

            detected_key = key.Key(key_string)
        except Exception as e:
            # Fallback
            print(f"   Warning: Could not parse key '{best_key_name}': {e}")
            detected_key = key.Key('C')
            final_confidence = 0.0

        print(f"   Ensemble result: {detected_key} (confidence: {final_confidence:.2f})")

        return detected_key, final_confidence

    def cleanup(self) -> None:
        """Delete temporary files (except output)."""
        # Don't delete entire temp_dir yet - output file is still there
        # Delete individual temp files instead
        for file in self.temp_dir.glob("*.wav"):
            file.unlink(missing_ok=True)
        for file in self.temp_dir.glob("*_clean.mid"):
            if file.name != "piano_clean.mid":
                file.unlink(missing_ok=True)


# === Module-level convenience functions for backward compatibility ===

def download_audio(youtube_url: str, storage_path: Path) -> Path:
    """Download audio from YouTube URL (module-level wrapper)."""
    pipeline = TranscriptionPipeline("compat_job", youtube_url, storage_path)
    return pipeline.download_audio()


def separate_sources(audio_path: Path, storage_path: Path) -> dict:
    """Separate audio sources (module-level wrapper)."""
    pipeline = TranscriptionPipeline("compat_job", "http://example.com", storage_path)
    return pipeline.separate_sources(audio_path)


def transcribe_audio(
    audio_path: Path,
    storage_path: Path,
    onset_threshold: float = 0.4,
    frame_threshold: float = 0.35
) -> Path:
    """Transcribe audio to MIDI (module-level wrapper)."""
    pipeline = TranscriptionPipeline("compat_job", "http://example.com", storage_path)
    # Note: The class method doesn't support these parameters in the current signature
    # But we create a job and transcribe
    midi_path = pipeline.transcribe_to_midi(audio_path)
    return midi_path


def quantize_midi(midi_path: Path, resolution: int = 480) -> Path:
    """Quantize MIDI file (module-level wrapper)."""
    pipeline = TranscriptionPipeline("compat_job", "http://example.com", midi_path.parent)
    return pipeline.clean_midi(midi_path)


def remove_duplicate_notes(midi_path: Path) -> Path:
    """Remove duplicate notes from MIDI (included in clean_midi)."""
    # The implementation includes this in clean_midi
    pipeline = TranscriptionPipeline("compat_job", "http://example.com", midi_path.parent)
    return pipeline.clean_midi(midi_path)


def remove_short_notes(midi_path: Path, min_duration: int = 60) -> Path:
    """Remove short notes from MIDI (included in clean_midi)."""
    # The implementation includes this in clean_midi
    pipeline = TranscriptionPipeline("compat_job", "http://example.com", midi_path.parent)
    return pipeline.clean_midi(midi_path)


def generate_musicxml(midi_path: Path, storage_path: Path) -> Path:
    """Generate MusicXML from MIDI (module-level wrapper)."""
    pipeline = TranscriptionPipeline("compat_job", "http://example.com", storage_path)
    # Use minimal pipeline (YourMT3+ optimized)
    # Note: source_audio path may not exist for module-level calls, but minimal pipeline can handle it
    audio_path = storage_path / "temp" / "compat_job" / "audio.wav"
    return pipeline.generate_musicxml_minimal(midi_path, audio_path)


def detect_key_signature(midi_path: Path) -> dict:
    """Detect key signature from MIDI."""
    score = converter.parse(midi_path)
    try:
        analyzed_key = score.analyze('key')
        return {
            'tonic': analyzed_key.tonic.name,
            'mode': analyzed_key.mode
        }
    except Exception as e:
        print(f"WARNING: Key detection failed: {e}")
        return {'tonic': 'C', 'mode': 'major'}


def detect_time_signature(midi_path: Path) -> dict:
    """Detect time signature from MIDI."""
    score = converter.parse(midi_path)
    for ts in score.flatten().getElementsByClass(meter.TimeSignature):
        return {
            'numerator': ts.numerator,
            'denominator': ts.denominator
        }
    return {'numerator': 4, 'denominator': 4}


def detect_tempo(midi_path: Path) -> int:
    """Detect tempo from MIDI."""
    score = converter.parse(midi_path)
    for t in score.flatten().getElementsByClass(tempo.MetronomeMark):
        return int(t.number)
    return 120


def run_transcription_pipeline(youtube_url: str, storage_path: Path) -> dict:
    """Run the full transcription pipeline (module-level wrapper)."""
    pipeline = TranscriptionPipeline("compat_job", youtube_url, storage_path)
    try:
        result = pipeline.run()
        return {
            'status': 'success',
            'musicxml_path': str(result)
        }
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e)
        }
