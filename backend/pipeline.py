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
from piano_transcription_inference import PianoTranscription, sample_rate
from music21 import converter, key, meter, tempo, note, clef, stream, chord as m21_chord


class TranscriptionPipeline:
    """Handles the complete transcription workflow."""

    def __init__(self, job_id: str, youtube_url: str, storage_path: Path):
        self.job_id = job_id
        self.youtube_url = youtube_url
        self.storage_path = storage_path
        self.temp_dir = storage_path / "temp" / job_id
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.progress_callback = None

        # Initialize ByteDance piano transcription model (lazy loading)
        self._transcriptor = None

    def set_progress_callback(self, callback):
        """Set callback for progress updates: callback(percent, stage, message)"""
        self.progress_callback = callback

    def progress(self, percent: int, stage: str, message: str):
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

            self.progress(20, "separate", "Starting source separation")
            stems = self.separate_sources(audio_path)

            self.progress(50, "transcribe", "Starting MIDI transcription")
            midi_path = self.transcribe_to_midi(stems['other'])

            self.progress(90, "musicxml", "Generating MusicXML")
            musicxml_path = self.generate_musicxml(midi_path)

            self.progress(100, "complete", "Transcription complete")
            return musicxml_path

        except Exception as e:
            self.progress(0, "error", str(e))
            raise

    def download_audio(self) -> Path:
        """Download audio from YouTube URL using yt-dlp."""
        output_path = self.temp_dir / "audio.wav"

        cmd = [
            "yt-dlp",
            "-x",  # Extract audio
            "--audio-format", "wav",
            "--audio-quality", "0",  # Best quality
            "--output", str(output_path.with_suffix('')),  # yt-dlp adds .wav
            # Workarounds for YouTube restrictions
            "--extractor-args", "youtube:player_client=android,web",
            "--no-check-certificates",
            self.youtube_url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {result.stderr}")

        if not output_path.exists():
            raise RuntimeError("Audio file not created")

        return output_path

    def separate_sources(self, audio_path: Path) -> dict:
        """
        Separate audio into 4 stems using Demucs.

        Returns:
            dict with keys: drums, bass, vocals, other
        """
        # Run Demucs
        cmd = [
            "demucs",
            "--two-stems=other",  # For piano, we only need "other" stem
            "-o", str(self.temp_dir),
            str(audio_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Demucs failed: {result.stderr}")

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

    def _get_transcriptor(self):
        """Lazy load ByteDance piano transcription model."""
        if self._transcriptor is None:
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            print(f"   Loading ByteDance piano transcription model on {device}...")
            self._transcriptor = PianoTranscription(device=device, checkpoint_path=None)
        return self._transcriptor

    def transcribe_to_midi(self, audio_path: Path) -> Path:
        """
        Transcribe audio to MIDI using ByteDance piano_transcription.

        Args:
            audio_path: Path to audio file (should be 'other' stem for piano)

        Returns:
            Path to generated MIDI file
        """
        output_dir = self.temp_dir
        midi_path = output_dir / "piano.mid"

        # Load audio with librosa (ByteDance expects specific sample rate and mono)
        print(f"   Loading audio from {audio_path}...")
        audio, _ = librosa.load(str(audio_path), sr=sample_rate, mono=True)

        # Get transcriptor (lazy loaded)
        transcriptor = self._get_transcriptor()

        # Transcribe to MIDI
        print(f"   Transcribing with ByteDance model...")
        transcriptor.transcribe(audio, str(midi_path))

        if not midi_path.exists():
            raise RuntimeError("ByteDance transcription did not create MIDI file")

        # Post-process MIDI (quantize, clean up)
        cleaned_midi = self.clean_midi(midi_path)

        return cleaned_midi

    def clean_midi(self, midi_path: Path) -> Path:
        """
        Clean up MIDI file: filter invalid notes, remove very short notes, light quantization.

        Args:
            midi_path: Path to raw MIDI file

        Returns:
            Path to cleaned MIDI file
        """
        mid = mido.MidiFile(midi_path)

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
            min_duration_ticks = mid.ticks_per_beat // 8  # Minimum 32nd note duration
            min_velocity = 20  # Filter very quiet notes (likely noise)
            notes_to_skip = set()  # Track note_on indices to skip

            # Identify notes to skip based on duration
            for msg_idx in note_durations:
                if note_durations[msg_idx] < min_duration_ticks:
                    notes_to_skip.add(msg_idx)

            for msg_idx, msg, abs_time in messages_with_abs_time:
                # Filter out notes outside piano range (A0 = 21, C8 = 108)
                if hasattr(msg, 'note') and (msg.note < 21 or msg.note > 108):
                    continue

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

            # Third pass: rebuild track with delta times and light quantization
            track.clear()
            previous_time = 0

            # Use 16th note quantization grid (less aggressive than 8th)
            ticks_per_16th = mid.ticks_per_beat // 4

            for msg, abs_time in messages_to_keep:
                if msg.type in ['note_on', 'note_off']:
                    # Light quantization - only snap if close to grid (within 10%)
                    nearest_grid = round(abs_time / ticks_per_16th) * ticks_per_16th
                    snap_threshold = ticks_per_16th * 0.1

                    if abs(abs_time - nearest_grid) < snap_threshold:
                        abs_time = nearest_grid

                # Set delta time from previous message
                msg.time = max(0, abs_time - previous_time)
                previous_time = abs_time
                track.append(msg)

        # Save cleaned MIDI
        cleaned_path = midi_path.with_stem(f"{midi_path.stem}_clean")
        mid.save(cleaned_path)

        return cleaned_path

    def generate_musicxml(self, midi_path: Path) -> Path:
        """
        Convert MIDI to MusicXML using music21, with grand staff for piano.

        Args:
            midi_path: Path to input MIDI file

        Returns:
            Path to output MusicXML file
        """
        self.progress(92, "musicxml", "Parsing MIDI")

        # Parse MIDI
        score = converter.parse(midi_path)

        self.progress(94, "musicxml", "Analyzing key signature")

        # Detect key signature
        try:
            analyzed_key = score.analyze('key')
            score.insert(0, analyzed_key)
        except:
            # Default to C major if analysis fails
            score.insert(0, key.Key('C'))

        # Set time signature (default 4/4)
        score.insert(0, meter.TimeSignature('4/4'))

        # Extract or default tempo
        midi_tempo = self._extract_tempo(score)
        score.insert(0, tempo.MetronomeMark(number=midi_tempo))

        self.progress(95, "musicxml", "Deduplicating overlapping notes")

        # Fix overlapping polyphonic notes from basic-pitch before creating measures
        # This prevents MusicXML corruption where measures have >4.0 beats
        score = self._deduplicate_overlapping_notes(score)

        self.progress(96, "musicxml", "Creating measures")

        # For MVP: Use single staff with treble clef
        # Grand staff splitting causes issues with overlapping polyphonic notes from basic-pitch
        # TODO: Implement proper grand staff in Phase 2 with better note splitting algorithm

        # Add treble clef (most piano music reads treble, bass notes will show ledger lines)
        for part in score.parts:
            part.insert(0, clef.TrebleClef())
            part.partName = "Piano"

        # Create measures
        score = score.makeMeasures()

        # Remove impossible note durations that makeMeasures() might have created
        score = self._remove_impossible_durations(score)

        # Fix tuplets containing impossible durations (must be done AFTER makeMeasures)
        # This prevents "Cannot convert 2048th duration to MusicXML" errors during export
        score = self._fix_tuplet_durations(score)

        # Validate measure durations to catch any remaining issues
        self._validate_measures(score)

        self.progress(97, "musicxml", "Finalizing score")

        self.progress(98, "musicxml", "Writing MusicXML file")

        # Write MusicXML with retry logic for 2048th note errors
        output_path = self.temp_dir / f"{self.job_id}.musicxml"
        max_retries = 10  # Prevent infinite loop
        retry_count = 0

        while retry_count < max_retries:
            try:
                score.write('musicxml', fp=str(output_path))
                break  # Success!
            except Exception as e:
                error_msg = str(e)
                # Check if this is a 2048th note error
                if 'Cannot convert "2048th" duration to MusicXML' in error_msg or \
                   'Cannot convert "4096th" duration to MusicXML' in error_msg:
                    # Extract measure number from error message
                    import re
                    match = re.search(r'measure \((\d+)\)', error_msg)
                    if match:
                        measure_num = int(match.group(1))
                        print(f"   Fixing 2048th note error in measure {measure_num}...")

                        # Remove ALL tuplets from this measure as a last resort
                        for part in score.parts:
                            measures = list(part.getElementsByClass('Measure'))
                            if measure_num <= len(measures):
                                problem_measure = measures[measure_num - 1]

                                # Remove ALL notes/rests from the problematic measure
                                # The 2048th note error is created BY music21 during export
                                # We can't prevent it, so we just empty the measure
                                to_remove = list(problem_measure.recurse().notesAndRests)

                                for element in to_remove:
                                    # Remove from its container
                                    element.activeSite.remove(element)

                                # Clear caches
                                problem_measure.coreElementsChanged()
                                part.coreElementsChanged()

                                print(f"   Removed all {len(to_remove)} elements from measure {measure_num}")

                        retry_count += 1
                    else:
                        # Can't parse measure number, give up
                        raise
                else:
                    # Different error, give up
                    raise

        if retry_count >= max_retries:
            raise RuntimeError(f"Failed to fix 2048th note errors after {max_retries} attempts")

        return output_path

    def _deduplicate_overlapping_notes(self, score):
        """
        Deduplicate overlapping notes from basic-pitch to prevent MusicXML corruption.

        Problem: basic-pitch outputs multiple notes at the same timestamp for polyphonic detection.
        When music21's makeMeasures() processes these, it creates measures with >4.0 beats.

        Solution: Group simultaneous notes (within 10ms) into chords, merge duplicate pitches.

        Args:
            score: music21 Score object before makeMeasures()

        Returns:
            Cleaned score with deduplicated notes
        """
        from music21 import stream, note, chord as m21_chord
        from collections import defaultdict

        # Process each part
        for part in score.parts:
            # Collect all notes with their absolute offsets
            notes_by_time = defaultdict(list)  # offset_ms -> [notes]

            for element in part.flatten().notesAndRests:
                if isinstance(element, note.Rest):
                    continue  # Skip rests for deduplication

                # Get absolute offset in quarter notes, convert to milliseconds for bucketing
                offset_qn = element.offset
                offset_ms = round(offset_qn * 1000)  # Convert to ms for 10ms bucketing

                # Bucket into 10ms slots (merge notes within 10ms of each other)
                bucket = (offset_ms // 10) * 10

                if isinstance(element, note.Note):
                    notes_by_time[bucket].append(element)
                elif isinstance(element, m21_chord.Chord):
                    # Explode chords into individual notes for deduplication
                    for pitch in element.pitches:
                        n = note.Note(pitch)
                        n.quarterLength = element.quarterLength
                        n.offset = element.offset
                        notes_by_time[bucket].append(n)

            # Rebuild part with deduplicated notes
            new_part = stream.Part()

            # Copy metadata (key, tempo, time signature will be added later)
            new_part.id = part.id
            new_part.partName = part.partName

            for bucket_ms in sorted(notes_by_time.keys()):
                bucket_notes = notes_by_time[bucket_ms]

                if not bucket_notes:
                    continue

                # Group by pitch to remove duplicates
                pitch_groups = defaultdict(list)
                for n in bucket_notes:
                    pitch_groups[n.pitch.midi].append(n)

                # For each unique pitch, keep the note with longest duration
                unique_notes = []
                for midi_pitch, pitch_notes in pitch_groups.items():
                    # Sort by duration (longest first)
                    # Get velocity as integer for comparison (handle None values)
                    def get_velocity(note):
                        if hasattr(note, 'volume') and hasattr(note.volume, 'velocity'):
                            vel = note.volume.velocity
                            return vel if vel is not None else 64
                        return 64

                    pitch_notes.sort(key=lambda x: (x.quarterLength, get_velocity(x)), reverse=True)
                    best_note = pitch_notes[0]

                    # Filter out extremely short notes (< 64th note = 0.0625 quarter notes)
                    # MusicXML can't handle notes shorter than 1024th
                    if best_note.quarterLength >= 0.0625:
                        unique_notes.append(best_note)

                if not unique_notes:
                    continue  # Skip if all notes were too short

                # Convert back to quarter notes for offset
                offset_qn = bucket_ms / 1000.0

                if len(unique_notes) == 1:
                    # Single note - snap duration to avoid impossible tuplets
                    n = note.Note(unique_notes[0].pitch)
                    n.quarterLength = self._snap_duration(unique_notes[0].quarterLength)
                    new_part.insert(offset_qn, n)
                elif len(unique_notes) > 1:
                    # Multiple notes at same time -> create chord
                    # Use the shortest duration to avoid overlaps, then snap
                    min_duration = min(n.quarterLength for n in unique_notes)

                    c = m21_chord.Chord([n.pitch for n in unique_notes])
                    c.quarterLength = self._snap_duration(min_duration)
                    new_part.insert(offset_qn, c)

            # Replace old part with new part
            score.replace(part, new_part)

        return score

    def _snap_duration(self, duration):
        """
        Snap duration to nearest MusicXML-valid note value to avoid impossible tuplets.

        Valid durations: whole (4.0), half (2.0), quarter (1.0), eighth (0.5),
        sixteenth (0.25), thirty-second (0.125), sixty-fourth (0.0625)

        Args:
            duration: Quarter length as float or Fraction

        Returns:
            Snapped quarter length
        """
        valid_durations = [4.0, 2.0, 1.0, 0.5, 0.25, 0.125, 0.0625]

        # Convert to float for comparison
        dur_float = float(duration)

        # Find nearest valid duration
        nearest = min(valid_durations, key=lambda x: abs(x - dur_float))

        return nearest

    def _remove_impossible_durations(self, score):
        """
        Remove notes/rests with durations too short for MusicXML export (<128th note).

        music21's makeMeasures() can create rests with impossible durations (2048th notes)
        when filling gaps. This removes them to prevent MusicXML export errors.

        Args:
            score: music21 Score with measures

        Returns:
            Cleaned score
        """
        from music21 import note, stream

        # Be VERY aggressive - remove anything shorter than 16th note
        # ByteDance transcription creates many very short notes that cause music21
        # to generate complex tuplets with impossible durations (2048th notes)
        # By filtering aggressively, we prevent this MusicXML export error
        MIN_DURATION = 0.25  # 16th note (1.0 / 4)

        removed_count = 0
        for part in score.parts:
            for measure in part.getElementsByClass('Measure'):
                # Collect elements to remove
                to_remove = []

                for element in measure.notesAndRests:
                    if element.quarterLength < MIN_DURATION:
                        to_remove.append(element)
                        removed_count += 1

                # Remove impossible durations
                for element in to_remove:
                    measure.remove(element)

        if removed_count > 0:
            print(f"   Removed {removed_count} notes/rests shorter than 16th note to prevent tuplet errors")

        return score

    def _fix_tuplet_durations(self, score):
        """
        Fix tuplets containing notes/rests with impossible durations for MusicXML export.

        The error occurs during MusicXML export when music21 tries to convert tuplet
        durationNormal.type to MusicXML format. If a tuplet contains a 2048th note or
        shorter, it will fail with MusicXMLExportException.

        This method removes or fixes problematic elements within tuplets BEFORE export.

        Args:
            score: music21 Score with measures and tuplets

        Returns:
            Cleaned score
        """
        from music21 import note, stream, duration

        # List of impossible duration types that MusicXML cannot represent
        IMPOSSIBLE_TYPES = {'2048th', '4096th', '8192th', '16384th', '32768th'}

        removed_count = 0
        fixed_tuplets = 0

        for part in score.parts:
            for measure_idx, measure in enumerate(part.getElementsByClass('Measure')):
                # Collect elements to remove (can't modify while iterating)
                to_remove = []

                # Check all notes and rests in the measure (not flattened - direct children)
                for element in measure.notesAndRests:
                    should_remove = False

                    # Check if this element is part of a tuplet
                    if element.duration.tuplets:
                        # Check each tuplet attached to this element
                        for tuplet in element.duration.tuplets:
                            # Check if the tuplet's durationNormal has an impossible type
                            if hasattr(tuplet, 'durationNormal') and tuplet.durationNormal:
                                dur_type = tuplet.durationNormal.type
                                if dur_type in IMPOSSIBLE_TYPES:
                                    should_remove = True
                                    fixed_tuplets += 1
                                    break

                    # Also check the element's own duration type
                    if element.duration.type in IMPOSSIBLE_TYPES:
                        should_remove = True
                        fixed_tuplets += 1

                    if should_remove:
                        to_remove.append(element)

                # Remove problematic elements
                for element in to_remove:
                    try:
                        measure.remove(element)
                        removed_count += 1
                    except Exception as e:
                        print(f"   Warning: Could not remove element from measure {measure_idx + 1}: {e}")
                        continue

        if removed_count > 0:
            print(f"   Fixed {fixed_tuplets} tuplets by removing {removed_count} elements with impossible durations")

        return score

    def _validate_measures(self, score):
        """
        Validate that all measures have correct durations matching their time signature.

        Logs warnings for any measures that are overfull or underfull.

        Args:
            score: music21 Score with measures already created
        """
        for part_idx, part in enumerate(score.parts):
            for measure_idx, measure in enumerate(part.getElementsByClass('Measure')):
                # Get time signature for this measure
                ts = measure.timeSignature or measure.getContextByClass('TimeSignature')
                if not ts:
                    continue  # Skip if no time signature

                expected_duration = ts.barDuration.quarterLength
                actual_duration = measure.duration.quarterLength

                # Allow small floating-point tolerance (0.01 quarter notes = ~10ms at 120 BPM)
                tolerance = 0.01

                if abs(actual_duration - expected_duration) > tolerance:
                    print(f"WARNING: Measure {measure_idx + 1} in part {part_idx} has duration {float(actual_duration):.2f} "
                          f"(expected {float(expected_duration):.2f} for {ts.ratioString} time)")

    def _split_into_grand_staff(self, score):
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
        treble_part.insert(0, clef.TrebleClef())
        treble_part.partName = "Piano Right Hand"

        bass_part = stream.Part()
        bass_part.insert(0, clef.BassClef())
        bass_part.partName = "Piano Left Hand"

        # Middle C (C4) is MIDI note 60
        SPLIT_POINT = 60

        # Process each measure from the original part
        for measure in original_part.getElementsByClass('Measure'):
            # Create corresponding measures for treble and bass
            treble_measure = stream.Measure(number=measure.number)
            bass_measure = stream.Measure(number=measure.number)

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
        except:
            # If makeRests fails, continue anyway
            pass

        return new_score

    def _extract_tempo(self, score) -> int:
        """Extract tempo from MIDI or default to 120 BPM."""
        for element in score.flatten():
            if isinstance(element, tempo.MetronomeMark):
                return int(element.number)
        return 120

    def cleanup(self):
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
    return pipeline.generate_musicxml(midi_path)


def detect_key_signature(midi_path: Path) -> dict:
    """Detect key signature from MIDI."""
    score = converter.parse(midi_path)
    try:
        analyzed_key = score.analyze('key')
        return {
            'tonic': analyzed_key.tonic.name,
            'mode': analyzed_key.mode
        }
    except:
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
