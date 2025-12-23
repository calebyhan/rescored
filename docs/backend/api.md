# API Design

## Overview

The Rescored API provides REST endpoints for job submission and status tracking, plus WebSocket connections for real-time progress updates.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://api.rescored.com` (future)

## Authentication

**MVP**: No authentication (local development only)

**Future**: JWT-based authentication
```http
Authorization: Bearer <jwt_token>
```

---

## REST Endpoints

### 1. Submit Transcription Job

**Endpoint**: `POST /api/v1/transcribe`

**Purpose**: Submit a YouTube URL for transcription processing.

**Request**:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "options": {
    "instruments": ["piano"],  // MVP: only "piano", future: ["drums", "bass", "guitar", etc.]
    "tempo_override": null,    // Optional: override detected tempo (BPM)
    "key_override": null       // Optional: override detected key (e.g., "C", "Gm")
  }
}
```

**Response** (201 Created):

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2025-01-15T10:30:00Z",
  "estimated_duration_seconds": 120,
  "websocket_url": "ws://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/stream"
}
```

**Errors**:

```json
// 400 Bad Request - Invalid URL
{
  "error": "Invalid YouTube URL format"
}

// 422 Unprocessable Entity - Video unavailable
{
  "error": "Video is age-restricted or private"
}

// 429 Too Many Requests - Rate limit exceeded
{
  "error": "Rate limit exceeded. Max 10 jobs per hour.",
  "retry_after_seconds": 3600
}
```

**Implementation**:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from uuid import uuid4
from datetime import datetime

app = FastAPI()

class TranscribeRequest(BaseModel):
    youtube_url: HttpUrl
    options: dict = {"instruments": ["piano"]}

class TranscribeResponse(BaseModel):
    job_id: str
    status: str
    created_at: datetime
    estimated_duration_seconds: int
    websocket_url: str

@app.post("/api/v1/transcribe", response_model=TranscribeResponse, status_code=201)
async def submit_transcription(request: TranscribeRequest):
    # Validate YouTube URL
    is_valid, video_id_or_error = validate_youtube_url(str(request.youtube_url))
    if not is_valid:
        raise HTTPException(status_code=400, detail=video_id_or_error)

    # Check video availability
    availability = check_video_availability(video_id_or_error)
    if not availability['available']:
        raise HTTPException(status_code=422, detail=availability['reason'])

    # Create job
    job_id = str(uuid4())
    job_data = {
        "job_id": job_id,
        "status": "queued",
        "youtube_url": str(request.youtube_url),
        "video_id": video_id_or_error,
        "options": request.options,
        "created_at": datetime.utcnow().isoformat(),
        "progress": 0,
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
        websocket_url=f"ws://localhost:8000/api/v1/jobs/{job_id}/stream"
    )
```

---

### 2. Get Job Status

**Endpoint**: `GET /api/v1/jobs/{job_id}`

**Purpose**: Poll job status (alternative to WebSocket).

**Response**:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",  // "queued" | "processing" | "completed" | "failed"
  "progress": 65,          // 0-100
  "current_stage": "transcription",  // "download" | "separation" | "transcription" | "musicxml"
  "created_at": "2025-01-15T10:30:00Z",
  "started_at": "2025-01-15T10:30:05Z",
  "completed_at": null,
  "error": null,
  "result_url": null       // Available when status="completed"
}
```

**Completed Job**:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "current_stage": "musicxml",
  "created_at": "2025-01-15T10:30:00Z",
  "started_at": "2025-01-15T10:30:05Z",
  "completed_at": "2025-01-15T10:32:15Z",
  "duration_seconds": 130,
  "result_url": "/api/v1/scores/550e8400-e29b-41d4-a716-446655440000"
}
```

**Failed Job**:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "progress": 35,
  "current_stage": "separation",
  "error": {
    "message": "GPU out of memory",
    "retryable": true
  },
  "created_at": "2025-01-15T10:30:00Z",
  "started_at": "2025-01-15T10:30:05Z",
  "failed_at": "2025-01-15T10:31:20Z"
}
```

**Implementation**:

```python
@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(job_id: str):
    job_data = redis_client.hgetall(f"job:{job_id}")

    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    return job_data
```

---

### 3. Download MusicXML

**Endpoint**: `GET /api/v1/scores/{job_id}`

**Purpose**: Download the generated MusicXML file.

**Response**: `application/vnd.recordare.musicxml+xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1">
      <part-name>Piano</part-name>
    </score-part>
  </part-list>
  <part id="P1">
    <!-- measures, notes, etc. -->
  </part>
</score-partwise>
```

**Headers**:
```
Content-Type: application/vnd.recordare.musicxml+xml
Content-Disposition: attachment; filename="score_550e8400.musicxml"
```

**Errors**:
```json
// 404 Not Found
{
  "error": "Job not found or not yet completed"
}
```

**Implementation**:

```python
from fastapi.responses import FileResponse

@app.get("/api/v1/scores/{job_id}")
async def download_score(job_id: str):
    job_data = redis_client.hgetall(f"job:{job_id}")

    if not job_data or job_data['status'] != 'completed':
        raise HTTPException(status_code=404, detail="Score not available")

    file_path = Path(job_data['output_path'])

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Score file not found")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.recordare.musicxml+xml",
        filename=f"score_{job_id}.musicxml"
    )
```

---

### 4. Download MIDI

**Endpoint**: `GET /api/v1/scores/{job_id}/midi`

**Purpose**: Download MIDI version of the score.

**Response**: `audio/midi`

**Headers**:
```
Content-Type: audio/midi
Content-Disposition: attachment; filename="score_550e8400.mid"
```

**Implementation**:

```python
@app.get("/api/v1/scores/{job_id}/midi")
async def download_midi(job_id: str):
    # Similar to MusicXML download, but serve .mid file
    pass
```

---

## WebSocket Endpoint

### Real-Time Progress Updates

**Endpoint**: `WS /api/v1/jobs/{job_id}/stream`

**Purpose**: Stream real-time progress updates to the client.

**Connection**:

```javascript
// Frontend code
const ws = new WebSocket(`ws://localhost:8000/api/v1/jobs/${jobId}/stream`);

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log(update);
};
```

**Message Types**:

**1. Progress Update**:

```json
{
  "type": "progress",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "progress": 45,
  "stage": "separation",
  "message": "Separated drums stem",
  "timestamp": "2025-01-15T10:30:45Z"
}
```

**2. Completion**:

```json
{
  "type": "completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "progress": 100,
  "result_url": "/api/v1/scores/550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-01-15T10:32:15Z"
}
```

**3. Error**:

```json
{
  "type": "error",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "error": {
    "message": "Failed to download audio: Network error",
    "retryable": true
  },
  "timestamp": "2025-01-15T10:31:00Z"
}
```

**Implementation**:

```python
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        self.active_connections[job_id].remove(websocket)

    async def send_update(self, job_id: str, message: dict):
        if job_id in self.active_connections:
            for connection in self.active_connections[job_id]:
                await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/api/v1/jobs/{job_id}/stream")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(websocket, job_id)

    try:
        # Keep connection alive and send updates
        while True:
            # Check for updates in Redis
            job_data = redis_client.hgetall(f"job:{job_id}")

            if job_data:
                message = {
                    "type": "progress",
                    "job_id": job_id,
                    "progress": int(job_data.get('progress', 0)),
                    "stage": job_data.get('current_stage', ''),
                    "message": job_data.get('status_message', ''),
                    "timestamp": datetime.utcnow().isoformat(),
                }

                await websocket.send_json(message)

                # Check if job completed or failed
                if job_data['status'] in ['completed', 'failed']:
                    break

            await asyncio.sleep(1)  # Poll every second

    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)
```

**Alternative: Redis Pub/Sub for Efficiency**

Instead of polling Redis every second, use pub/sub:

```python
# Worker publishes updates
redis_client.publish(f"job:{job_id}:updates", json.dumps(message))

# WebSocket subscribes
pubsub = redis_client.pubsub()
pubsub.subscribe(f"job:{job_id}:updates")

for message in pubsub.listen():
    await websocket.send_json(json.loads(message['data']))
```

---

## Data Models

### Job Status

```python
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobStage(str, Enum):
    DOWNLOAD = "download"
    SEPARATION = "separation"
    TRANSCRIPTION = "transcription"
    MUSICXML = "musicxml"
```

### Job Schema (Redis)

```python
job_data = {
    "job_id": str,
    "status": JobStatus,
    "youtube_url": str,
    "video_id": str,
    "progress": int,  # 0-100
    "current_stage": JobStage,
    "status_message": str,  # e.g., "Separated drums stem"
    "created_at": str,  # ISO 8601
    "started_at": str | None,
    "completed_at": str | None,
    "failed_at": str | None,
    "output_path": str | None,  # Path to .musicxml file
    "error": dict | None,
}
```

---

## Error Handling

### HTTP Error Codes

| Code | Meaning | Example |
|------|---------|---------|
| 400 | Bad Request | Invalid URL format |
| 404 | Not Found | Job ID doesn't exist |
| 422 | Unprocessable Entity | Video unavailable or age-restricted |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |

### Error Response Format

```json
{
  "error": "Human-readable error message",
  "details": {
    "field": "youtube_url",
    "issue": "Invalid format"
  }
}
```

---

## Rate Limiting

**MVP**: Simple in-memory rate limiting

**Production**: Redis-based rate limiting with sliding window

**Limits**:
- 10 jobs per IP per hour (unauthenticated)
- 100 jobs per user per hour (authenticated, future)

**Implementation**:

```python
from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/v1/transcribe")
@limiter.limit("10/hour")
async def submit_transcription(request: Request, transcribe_request: TranscribeRequest):
    # ... implementation
    pass
```

---

## CORS Configuration

**Development**:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Production**:
```python
allow_origins=["https://rescored.com", "https://www.rescored.com"]
```

---

## API Versioning

**Current**: `/api/v1/`

**Future**: `/api/v2/` for breaking changes

**Deprecation Policy**: Support old version for 6 months after new version release

---

## Next Steps

1. Implement [Celery workers](workers.md) to process jobs
2. Test WebSocket connections with frontend
3. Add monitoring for API latency and error rates
4. Implement proper authentication for production

See [WebSocket Protocol](../integration/websocket-protocol.md) for detailed message specs.
