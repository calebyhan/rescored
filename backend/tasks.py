"""Celery tasks for background job processing."""
from celery import Task
from celery_app import celery_app
from pipeline import TranscriptionPipeline, run_transcription_pipeline
import redis
import json
import os
from datetime import datetime
from pathlib import Path
from app_config import settings
import shutil

# Redis client - use fakeredis if USE_FAKE_REDIS is set
if os.getenv('USE_FAKE_REDIS', '').lower() == 'true':
    import fakeredis
    redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
    print("Using fakeredis for in-memory caching")
else:
    redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


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
        
        youtube_url = job_data.get('youtube_url')
        if not youtube_url:
            raise ValueError(f"Job missing youtube_url: {job_id}")

        # Initialize pipeline
        pipeline = TranscriptionPipeline(
            job_id=job_id,
            youtube_url=youtube_url,
            storage_path=settings.storage_path
        )
        pipeline.set_progress_callback(lambda p, s, m: self.update_progress(job_id, p, s, m))

        # Run pipeline
        temp_output_path = pipeline.run()

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
