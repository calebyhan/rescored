"""FastAPI application for Rescored backend."""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import redis
import json
import asyncio
from config import settings
from utils import validate_youtube_url, check_video_availability
from tasks import process_transcription_task

# Initialize FastAPI
app = FastAPI(
    title="Rescored API",
    description="AI-powered music transcription from YouTube videos",
    version="1.0.0"
)

# Redis client (initialized before middleware)
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


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


# === Request/Response Models ===

class TranscribeRequest(BaseModel):
    """Request model for transcription."""
    youtube_url: HttpUrl
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
                except:
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
        except:
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

    try:
        # Subscribe to Redis pub/sub for this job
        pubsub = redis_client.pubsub()
        pubsub.subscribe(f"job:{job_id}:updates")

        # Listen for updates in a separate task
        async def listen_for_updates():
            for message in pubsub.listen():
                if message['type'] == 'message':
                    update = json.loads(message['data'])
                    await websocket.send_json(update)

                    # Close connection if job completed or failed
                    if update.get('type') in ['completed', 'error']:
                        break

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

        # Listen for updates (blocking)
        await listen_for_updates()

    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)
    finally:
        pubsub.unsubscribe(f"job:{job_id}:updates")
        pubsub.close()


# === Health Check ===

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check Redis connection
    try:
        redis_client.ping()
        redis_status = "healthy"
    except:
        redis_status = "unhealthy"

    return {
        "status": "healthy" if redis_status == "healthy" else "degraded",
        "redis": redis_status,
        "storage": str(settings.storage_path)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
