"""Celery tasks for background job processing."""
import sys
from pathlib import Path

# Ensure backend directory is in Python path for imports
backend_dir = Path(__file__).parent.resolve()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from celery import Task
from celery_app import celery_app
from pipeline import TranscriptionPipeline, run_transcription_pipeline
from redis_client import get_redis_client
import json
import os
from datetime import datetime
from app_config import settings
import shutil

# Get shared Redis client singleton
redis_client = get_redis_client()


class TranscriptionTask(Task):
    """Base task with progress tracking."""

    def update_progress(self, job_id: str, progress: int, stage: str, message: str) -> None:
        """
        Update job progress in Redis and publish to WebSocket subscribers.

        Args:
            job_id: Job identifier
            progress: Progress percentage (0-100)
            stage: Current stage name
            message: Status message
        """
        print(f"[PROGRESS] {progress}% - {stage} - {message}")
        job_key = f"job:{job_id}"

        # Update Redis hash
        redis_client.hset(job_key, mapping={
            "progress": progress,
            "current_stage": stage,
            "status_message": message,
            "updated_at": datetime.utcnow().isoformat(),
        })

        # Publish to pub/sub for WebSocket clients
        update = {
            "type": "progress",
            "job_id": job_id,
            "progress": progress,
            "stage": stage,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        num_subscribers = redis_client.publish(f"job:{job_id}:updates", json.dumps(update))
        print(f"[PROGRESS] Published to {num_subscribers} subscribers")


@celery_app.task(base=TranscriptionTask, bind=True)
def process_transcription_task(self, job_id: str):
    """
    Main transcription task.

    Args:
        job_id: Unique job identifier

    Returns:
        Path to generated MusicXML file
    """
    try:
        # Mark job as started
        redis_client.hset(f"job:{job_id}", mapping={
            "status": "processing",
            "started_at": datetime.utcnow().isoformat(),
        })

        # Get job data
        job_data = redis_client.hgetall(f"job:{job_id}")

        if not job_data:
            raise ValueError(f"Job not found: {job_id}")

        # Check if this is a file upload or YouTube URL job
        upload_path = job_data.get('upload_path')
        youtube_url = job_data.get('youtube_url')

        # Parse instruments option (defaults to piano only)
        instruments = ['piano']
        vocal_instrument_program = 40  # Default to violin
        if 'options' in job_data:
            try:
                options = json.loads(job_data['options'])
                instruments = options.get('instruments', ['piano'])
                vocal_instrument_program = options.get('vocal_instrument', 40)
            except (json.JSONDecodeError, KeyError):
                instruments = ['piano']
                vocal_instrument_program = 40

        # Import shutil and subprocess
        import shutil
        import subprocess

        # Create pipeline
        pipeline = TranscriptionPipeline(
            job_id=job_id,
            youtube_url=youtube_url or "file://uploaded",  # Dummy URL for file uploads
            storage_path=settings.storage_path,
            instruments=instruments
        )
        pipeline.set_progress_callback(lambda p, s, m: self.update_progress(job_id, p, s, m))

        # Get audio.wav - either from upload or YouTube download
        audio_path = pipeline.temp_dir / "audio.wav"

        if upload_path:
            # File upload - convert to WAV if needed
            upload_file = Path(upload_path)
            if upload_file.suffix.lower() == '.wav':
                shutil.copy(str(upload_file), str(audio_path))
            else:
                # Convert to WAV using ffmpeg
                result = subprocess.run([
                    'ffmpeg', '-i', str(upload_file),
                    '-ar', '44100', '-ac', '2',
                    str(audio_path)
                ], capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"Audio conversion failed: {result.stderr}")
        elif youtube_url:
            # YouTube download
            pipeline.progress(0, "download", "Starting audio download")
            audio_path = pipeline.download_audio()
        else:
            raise ValueError(f"Job missing both youtube_url and upload_path: {job_id}")

        # From here, both paths converge - process audio.wav the same way
        # Preprocess audio if enabled
        if pipeline.config.enable_audio_preprocessing:
            pipeline.progress(10, "preprocess", "Preprocessing audio")
            audio_path = pipeline.preprocess_audio(audio_path)

        # Source separation
        pipeline.progress(20, "separate", "Starting source separation")
        all_stems = pipeline.separate_sources(audio_path)

        # Select stems to transcribe based on user selection
        stems_to_transcribe = {}
        for instrument in instruments:
            if instrument in all_stems:
                stems_to_transcribe[instrument] = all_stems[instrument]
                print(f"   [DEBUG] Will transcribe {instrument} stem")
            else:
                print(f"   [WARNING] {instrument} stem not found in separated audio")

        # If no selected stems available, fall back to piano
        if not stems_to_transcribe:
            print(f"   [WARNING] No selected stems found, falling back to piano")
            if 'piano' in all_stems:
                stems_to_transcribe['piano'] = all_stems['piano']
            else:
                stems_to_transcribe['other'] = all_stems['other']

        pipeline.progress(50, "transcribe", f"Transcribing {len(stems_to_transcribe)} instrument(s)")

        # Transcribe stems
        if len(stems_to_transcribe) == 1:
            # Single stem - use original method
            stem_path = list(stems_to_transcribe.values())[0]
            combined_midi = pipeline.transcribe_to_midi(stem_path)
        else:
            # Multiple stems - use new multi-stem method
            combined_midi = pipeline.transcribe_multiple_stems(stems_to_transcribe)

        # Filter MIDI to only include selected instruments
        filtered_midi = pipeline.filter_midi_by_instruments(combined_midi)

        # Remap vocals MIDI program if vocals were selected
        if 'vocals' in instruments and vocal_instrument_program != 65:
            print(f"   [DEBUG] Remapping vocals MIDI program from 65 to {vocal_instrument_program}")
            import pretty_midi
            pm = pretty_midi.PrettyMIDI(str(filtered_midi))
            for inst in pm.instruments:
                if inst.program == 65 and not inst.is_drum:  # Singing Voice
                    inst.program = vocal_instrument_program
                    print(f"   [DEBUG] Changed track '{inst.name}' program to {vocal_instrument_program}")
            # Save remapped MIDI
            pm.write(str(filtered_midi))

        # Apply post-processing
        midi_path = pipeline.apply_post_processing_filters(filtered_midi)
        pipeline.final_midi_path = midi_path

        # Get audio stem for MusicXML generation (use piano if available, otherwise first available stem)
        audio_stem = stems_to_transcribe.get('piano') or list(stems_to_transcribe.values())[0]

        pipeline.progress(90, "musicxml", "Generating MusicXML")
        temp_output_path = pipeline.generate_musicxml_minimal(midi_path, audio_stem)
        pipeline.progress(100, "complete", "Transcription complete")

        # Output is already in the temp directory, move to persistent storage
        output_path = settings.outputs_path / f"{job_id}.musicxml"
        midi_path = settings.outputs_path / f"{job_id}.mid"

        # Ensure outputs directory exists
        settings.outputs_path.mkdir(parents=True, exist_ok=True)

        # Copy the MusicXML file to outputs
        shutil.copy(str(temp_output_path), str(output_path))

        # Copy the MIDI file to outputs (use actual processed MIDI from pipeline)
        # Pipeline stores the final MIDI path (after quantization) in final_midi_path
        temp_midi_path = getattr(pipeline, 'final_midi_path', pipeline.temp_dir / "piano.mid")
        print(f"[DEBUG] Using MIDI from pipeline: {temp_midi_path}")
        print(f"[DEBUG] MIDI exists: {temp_midi_path.exists()}")

        if temp_midi_path.exists():
            print(f"[DEBUG] Copying MIDI from {temp_midi_path} to {midi_path}")
            shutil.copy(str(temp_midi_path), str(midi_path))
            print(f"[DEBUG] Copy complete, destination exists: {midi_path.exists()}")
        else:
            print(f"[DEBUG] WARNING: No MIDI file found at {temp_midi_path}!")

        # Store metadata for API access
        metadata = getattr(pipeline, 'metadata', {
            "tempo": 120.0,
            "time_signature": {"numerator": 4, "denominator": 4},
            "key_signature": "C",
        })

        # Cleanup temp files (pipeline has its own cleanup method)
        pipeline.cleanup()

        # Mark job as completed
        redis_client.hset(f"job:{job_id}", mapping={
            "status": "completed",
            "progress": 100,
            "output_path": str(output_path.absolute()),
            "midi_path": str(midi_path.absolute()) if temp_midi_path.exists() else "",
            "metadata": json.dumps(metadata),
            "completed_at": datetime.utcnow().isoformat(),
        })

        # Publish completion message
        completion_msg = {
            "type": "completed",
            "job_id": job_id,
            "result_url": f"/api/v1/scores/{job_id}",
            "timestamp": datetime.utcnow().isoformat(),
        }
        redis_client.publish(f"job:{job_id}:updates", json.dumps(completion_msg))

        return str(output_path)

    except Exception as e:
        import traceback

        # Determine if error is retryable (only retry transient errors, not code bugs)
        RETRYABLE_EXCEPTIONS = (
            ConnectionError,  # Network errors
            TimeoutError,     # Timeout errors
            IOError,          # I/O errors (file system, disk full, etc.)
        )

        is_retryable = isinstance(e, RETRYABLE_EXCEPTIONS) and self.request.retries < self.max_retries

        # Mark job as failed
        redis_client.hset(f"job:{job_id}", mapping={
            "status": "failed",
            "error": json.dumps({
                "message": str(e),
                "type": type(e).__name__,
                "retryable": is_retryable,
                "traceback": traceback.format_exc(),
            }),
            "failed_at": datetime.utcnow().isoformat(),
        })

        # Publish error message
        error_msg = {
            "type": "error",
            "job_id": job_id,
            "error": {
                "message": str(e),
                "type": type(e).__name__,
                "retryable": is_retryable,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        redis_client.publish(f"job:{job_id}:updates", json.dumps(error_msg))

        # Only retry if the error is transient (network, I/O, etc.)
        if is_retryable:
            print(f"[RETRY] Retrying job {job_id} (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
        else:
            # Non-retryable error (code bug, validation error, etc.) - fail immediately
            print(f"[ERROR] Non-retryable error for job {job_id}: {type(e).__name__}: {e}")
            raise


# === Module-level helper functions ===

def update_progress(job_id: str, progress: int, stage: str, message: str) -> None:
    """
    Update job progress (wrapper for backward compatibility).

    Args:
        job_id: Job identifier
        progress: Progress percentage (0-100)
        stage: Current stage name
        message: Status message
    """
    # Instantiate task to use its update_progress method
    task = TranscriptionTask()
    task.update_progress(job_id, progress, stage, message)


def cleanup_temp_files(job_id: str, storage_path: Path = None) -> None:
    """
    Clean up temporary files for a job.

    Args:
        job_id: Job identifier
        storage_path: Path to storage directory (uses settings if not provided)
    """
    if storage_path is None:
        storage_path = settings.storage_path

    temp_dir = storage_path / "temp" / job_id
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
