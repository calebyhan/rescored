"""FastAPI application for Rescored backend."""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import json
import asyncio
import tempfile
import shutil
import os
from typing import Optional
from app_config import settings
from app_utils import validate_youtube_url, check_video_availability
from redis_client import get_redis_client, get_async_redis_client
from tasks import process_transcription_task

# YourMT3+ transcription service
try:
    from yourmt3_wrapper import YourMT3Transcriber
    YOURMT3_AVAILABLE = True
except ImportError as e:
    YOURMT3_AVAILABLE = False
    print(f"WARNING: YourMT3+ not available: {e}")

# Initialize FastAPI
app = FastAPI(
    title="Rescored API",
    description="AI-powered music transcription from YouTube videos",
    version="1.0.0"
)

# Get shared Redis client singleton
redis_client = get_redis_client()
async_redis_client = get_async_redis_client()

# YourMT3+ transcriber (loaded on startup)
yourmt3_transcriber: Optional[YourMT3Transcriber] = None
YOURMT3_TEMP_DIR = Path(tempfile.gettempdir()) / "yourmt3_service"


# === Rate Limiting Middleware ===

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.

    Limits: 10 transcription jobs per IP per hour (security requirement).
    Uses Redis with sliding window counter.
    """

    async def dispatch(self, request: Request, call_next):
        # Only rate limit the transcribe endpoint
        if request.url.path == "/api/v1/transcribe" and request.method == "POST":
            # Get client IP (handle proxies)
            client_ip = request.client.host
            if "x-forwarded-for" in request.headers:
                client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()

            # Redis key for this IP
            rate_limit_key = f"ratelimit:{client_ip}"

            # Get current count
            current_count = redis_client.get(rate_limit_key)

            if current_count and int(current_count) >= 10:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Maximum 10 transcription jobs per hour per IP."
                    }
                )

            # Increment counter
            pipe = redis_client.pipeline()
            pipe.incr(rate_limit_key)
            pipe.expire(rate_limit_key, 3600)  # 1 hour TTL
            pipe.execute()

        response = await call_next(request)
        return response


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)


# === Application Lifecycle Events ===

@app.on_event("startup")
async def startup_event():
    """Initialize YourMT3+ model on startup."""
    global yourmt3_transcriber

    # Log deployment info
    print("\n" + "="*60)
    print("🎵 Rescored Backend Started")
    print("="*60)
    print(f"Device: {settings.yourmt3_device}")
    print(f"CORS Origins: {', '.join(settings.cors_origins_list)}")
    print(f"Redis: {settings.redis_url}")
    print("="*60 + "\n")

    if not YOURMT3_AVAILABLE or not settings.use_yourmt3_transcription:
        print("YourMT3+ transcription disabled or unavailable")
        return

    try:
        YOURMT3_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Loading YourMT3+ model (device: {settings.yourmt3_device})...")
        yourmt3_transcriber = YourMT3Transcriber(
            model_name="YPTF.MoE+Multi (noPS)",
            device=settings.yourmt3_device
        )
        print("✓ YourMT3+ model loaded successfully")
    except Exception as e:
        print(f"⚠ Failed to load YourMT3+ model: {e}")
        print("  Service will fall back to basic-pitch for transcription")
        yourmt3_transcriber = None


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up temporary files and close Redis connections on shutdown."""
    if YOURMT3_TEMP_DIR.exists():
        shutil.rmtree(YOURMT3_TEMP_DIR, ignore_errors=True)

    # Close async Redis client
    await async_redis_client.close()


# === Request/Response Models ===

class TranscribeRequest(BaseModel):
    """Request model for transcription."""
    youtube_url: HttpUrl
    options: dict = {"instruments": ["piano"]}


class FileUploadTranscribeRequest(BaseModel):
    """Request model for file upload transcription."""
    options: dict = {"instruments": ["piano"]}


class TranscribeResponse(BaseModel):
    """Response model for transcription submission."""
    job_id: str
    status: str
    created_at: datetime
    estimated_duration_seconds: int
    websocket_url: str


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    status: str
    progress: int
    current_stage: str | None
    status_message: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    failed_at: str | None
    error: dict | None
    result_url: str | None


# === WebSocket Connection Manager ===

class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        """Remove a WebSocket connection."""
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast(self, job_id: str, message: dict):
        """Broadcast message to all clients connected to a job."""
        if job_id in self.active_connections:
            dead_connections = []

            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    # WebSocket connection failed, mark for removal
                    print(f"WebSocket error sending to connection: {e}")
                    dead_connections.append(connection)

            # Clean up dead connections
            for conn in dead_connections:
                self.disconnect(conn, job_id)


manager = ConnectionManager()


# === REST Endpoints ===

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Rescored API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.post("/api/v1/transcribe", response_model=TranscribeResponse, status_code=201)
async def submit_transcription(request: TranscribeRequest):
    """
    Submit a YouTube URL for transcription.

    Args:
        request: Transcription request with YouTube URL

    Returns:
        Job information including job ID and WebSocket URL
    """
    # Validate YouTube URL
    is_valid, video_id_or_error = validate_youtube_url(str(request.youtube_url))
    if not is_valid:
        raise HTTPException(status_code=400, detail=video_id_or_error)

    video_id = video_id_or_error

    # Check video availability
    availability = check_video_availability(video_id, settings.max_video_duration)
    if not availability['available']:
        raise HTTPException(status_code=422, detail=availability['reason'])

    # Create job
    job_id = str(uuid4())
    job_data = {
        "job_id": job_id,
        "status": "queued",
        "youtube_url": str(request.youtube_url),
        "video_id": video_id,
        "options": json.dumps(request.options),
        "created_at": datetime.utcnow().isoformat(),
        "progress": 0,
        "current_stage": "queued",
        "status_message": "Job queued for processing",
    }

    # Store in Redis
    redis_client.hset(f"job:{job_id}", mapping=job_data)

    # Queue Celery task
    process_transcription_task.delay(job_id)

    return TranscribeResponse(
        job_id=job_id,
        status="queued",
        created_at=datetime.utcnow(),
        estimated_duration_seconds=120,
        websocket_url=f"ws://localhost:{settings.api_port}/api/v1/jobs/{job_id}/stream"
    )


@app.post("/api/v1/transcribe/upload", response_model=TranscribeResponse, status_code=201)
async def submit_file_transcription(
    file: UploadFile = File(...),
    instruments: str = Form('["piano"]'),
    vocal_instrument: int = Form(40)  # Default to violin (program 40)
):
    """
    Submit an audio file for transcription.

    Args:
        file: Audio file (WAV, MP3, FLAC, etc.)
        instruments: JSON array of instruments (default: ["piano"])
        vocal_instrument: MIDI program number for vocals (default: 40 = violin)

    Returns:
        Job information including job ID and WebSocket URL
    """
    print(f"[DEBUG] FastAPI received instruments parameter: {instruments!r}")
    print(f"[DEBUG] FastAPI received vocal_instrument parameter: {vocal_instrument}")

    # Validate file type
    allowed_extensions = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac'}
    file_ext = Path(file.filename or '').suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Validate file size (max 100MB)
    max_size = 100 * 1024 * 1024  # 100MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: 100MB"
        )

    # Parse instruments option
    try:
        import json as json_module
        print(f"[DEBUG] Received instruments parameter (raw): {instruments}")
        instruments_list = json_module.loads(instruments)
        print(f"[DEBUG] Parsed instruments list: {instruments_list}")
    except Exception as e:
        print(f"[DEBUG] Failed to parse instruments, using default ['piano']. Error: {e}")
        instruments_list = ["piano"]

    # Create job
    job_id = str(uuid4())

    # Save uploaded file to storage
    upload_dir = settings.storage_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"{job_id}{file_ext}"

    with open(upload_path, "wb") as f:
        f.write(content)

    job_data = {
        "job_id": job_id,
        "status": "queued",
        "upload_path": str(upload_path),
        "original_filename": file.filename or "unknown",
        "options": json.dumps({"instruments": instruments_list, "vocal_instrument": vocal_instrument}),
        "created_at": datetime.utcnow().isoformat(),
        "progress": 0,
        "current_stage": "queued",
        "status_message": "Job queued for processing",
    }

    # Store in Redis
    redis_client.hset(f"job:{job_id}", mapping=job_data)

    # Queue Celery task
    process_transcription_task.delay(job_id)

    return TranscribeResponse(
        job_id=job_id,
        status="queued",
        created_at=datetime.utcnow(),
        estimated_duration_seconds=120,
        websocket_url=f"ws://localhost:{settings.api_port}/api/v1/jobs/{job_id}/stream"
    )


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get job status.

    Args:
        job_id: Job identifier

    Returns:
        Job status information
    """
    job_data = redis_client.hgetall(f"job:{job_id}")

    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    # Parse error if present
    error = None
    if 'error' in job_data:
        try:
            error = json.loads(job_data['error'])
        except json.JSONDecodeError:
            # Error is not JSON, wrap as plain message
            error = {"message": job_data['error']}

    # Construct result URL if completed
    result_url = None
    if job_data.get('status') == 'completed':
        result_url = f"/api/v1/scores/{job_id}"

    return JobStatusResponse(
        job_id=job_id,
        status=job_data.get('status', 'unknown'),
        progress=int(job_data.get('progress', 0)),
        current_stage=job_data.get('current_stage'),
        status_message=job_data.get('status_message'),
        created_at=job_data.get('created_at', ''),
        started_at=job_data.get('started_at'),
        completed_at=job_data.get('completed_at'),
        failed_at=job_data.get('failed_at'),
        error=error,
        result_url=result_url
    )


@app.get("/api/v1/scores/{job_id}")
async def download_score(job_id: str):
    """
    Download MusicXML score.

    Args:
        job_id: Job identifier

    Returns:
        MusicXML file
    """
    job_data = redis_client.hgetall(f"job:{job_id}")

    if not job_data or job_data.get('status') != 'completed':
        raise HTTPException(status_code=404, detail="Score not available")

    output_path = job_data.get('output_path')
    if not output_path:
        raise HTTPException(status_code=404, detail="Score file path not found")

    file_path = Path(output_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Score file not found")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.recordare.musicxml+xml",
        filename=f"score_{job_id}.musicxml"
    )


@app.get("/api/v1/scores/{job_id}/midi")
async def download_midi(job_id: str):
    """
    Download MIDI version of score.

    For MVP, this returns the cleaned MIDI from transcription (piano_clean.mid).

    Args:
        job_id: Job identifier

    Returns:
        MIDI file
    """
    job_data = redis_client.hgetall(f"job:{job_id}")

    if not job_data or job_data.get('status') != 'completed':
        raise HTTPException(status_code=404, detail="MIDI not available")

    midi_path_str = job_data.get('midi_path')
    if not midi_path_str:
        raise HTTPException(status_code=404, detail="MIDI file path not found")

    file_path = Path(midi_path_str)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="MIDI file not found")

    return FileResponse(
        path=file_path,
        media_type="audio/midi",
        filename=f"score_{job_id}.mid"
    )


@app.get("/api/v1/scores/{job_id}/metadata")
async def get_metadata(job_id: str):
    """
    Get detected metadata for a completed transcription.

    Returns tempo, key signature, and time signature detected from audio.

    Args:
        job_id: Job identifier

    Returns:
        JSON with tempo, key_signature, time_signature
    """
    job_data = redis_client.hgetall(f"job:{job_id}")

    if not job_data or job_data.get('status') != 'completed':
        raise HTTPException(status_code=404, detail="Metadata not available")

    metadata_str = job_data.get('metadata')
    if not metadata_str:
        # Return defaults if metadata not stored (for older jobs)
        return {
            "tempo": 120.0,
            "key_signature": "C",
            "time_signature": {"numerator": 4, "denominator": 4},
        }

    try:
        metadata = json.loads(metadata_str)
        return metadata
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid metadata format")


# === WebSocket Endpoint ===

@app.websocket("/api/v1/jobs/{job_id}/stream")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time progress updates.

    Args:
        websocket: WebSocket connection
        job_id: Job identifier
    """
    await manager.connect(websocket, job_id)
    pubsub = None

    try:
        # Subscribe to Redis pub/sub for this job using async client
        pubsub = async_redis_client.pubsub()
        await pubsub.subscribe(f"job:{job_id}:updates")

        # Send initial status
        job_data = redis_client.hgetall(f"job:{job_id}")
        if job_data:
            initial_update = {
                "type": "progress",
                "job_id": job_id,
                "progress": int(job_data.get('progress', 0)),
                "stage": job_data.get('current_stage', 'queued'),
                "message": job_data.get('status_message', 'Starting...'),
                "timestamp": datetime.utcnow().isoformat(),
            }
            await websocket.send_json(initial_update)

        # Listen for updates asynchronously
        async for message in pubsub.listen():
            if message['type'] == 'message':
                update = json.loads(message['data'])
                await websocket.send_json(update)

                # Close connection if job completed
                if update.get('type') == 'completed':
                    break

                # Close connection if job failed with non-retryable error
                if update.get('type') == 'error':
                    error_info = update.get('error', {})
                    is_retryable = error_info.get('retryable', False)
                    if not is_retryable:
                        # Only close if error is permanent
                        break
                    # If retryable, keep connection open for retry progress updates

    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)
    finally:
        if pubsub:
            await pubsub.unsubscribe(f"job:{job_id}:updates")
            await pubsub.close()


# === Health Check ===

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check Redis connection
    try:
        redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        # Catch all exceptions (Redis errors, connection failures, etc.)
        print(f"Redis health check failed: {e}")
        redis_status = "unhealthy"

    return {
        "status": "healthy" if redis_status == "healthy" else "degraded",
        "redis": redis_status,
        "storage": str(settings.storage_path)
    }


# === YourMT3+ Transcription Endpoints ===

@app.get("/api/v1/yourmt3/health")
async def yourmt3_health():
    """
    Check YourMT3+ transcription service health.

    Returns model status, device, and availability.
    """
    if not YOURMT3_AVAILABLE:
        return {
            "status": "unavailable",
            "model_loaded": False,
            "reason": "YourMT3+ dependencies not installed"
        }

    model_loaded = yourmt3_transcriber is not None

    return {
        "status": "healthy" if model_loaded else "degraded",
        "model_loaded": model_loaded,
        "model_name": "YPTF.MoE+Multi (noPS)" if model_loaded else "not loaded",
        "device": yourmt3_transcriber.device if model_loaded else "unknown"
    }


@app.post("/api/v1/yourmt3/transcribe")
async def yourmt3_transcribe(file: UploadFile = File(...)):
    """
    Transcribe audio file to MIDI using YourMT3+.

    This endpoint is used by the pipeline for direct transcription.
    """
    if yourmt3_transcriber is None:
        raise HTTPException(status_code=503, detail="YourMT3+ model not loaded")

    # Save uploaded file
    input_file = YOURMT3_TEMP_DIR / f"input_{uuid4().hex}_{file.filename}"
    try:
        with open(input_file, "wb") as f:
            content = await file.read()
            f.write(content)

        # Transcribe
        output_dir = YOURMT3_TEMP_DIR / f"output_{uuid4().hex}"
        output_dir.mkdir(parents=True, exist_ok=True)

        midi_path = yourmt3_transcriber.transcribe_audio(input_file, output_dir)

        # Return MIDI file
        return FileResponse(
            path=str(midi_path),
            media_type="audio/midi",
            filename=midi_path.name
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Clean up input file
        if input_file.exists():
            input_file.unlink()


@app.get("/api/v1/yourmt3/models")
async def yourmt3_models():
    """List available YourMT3+ model variants."""
    return {
        "models": [
            {
                "name": "YPTF.MoE+Multi (noPS)",
                "description": "Mixture of Experts multi-instrument transcription (default)",
                "loaded": yourmt3_transcriber is not None
            }
        ],
        "default": "YPTF.MoE+Multi (noPS)"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
