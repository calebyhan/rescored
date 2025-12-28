#!/bin/bash
# Test MPS performance with optimizations

echo "====================================="
echo "YourMT3+ MPS Performance Test"
echo "====================================="
echo ""

# Start service in background
echo "Starting transcription service with MPS + float16..."
cd /Users/calebhan/Documents/Coding/Personal/rescored/backend/transcription-service
source ../backend/.venv/bin/activate 2>/dev/null || true
python service.py > service.log 2>&1 &
SERVICE_PID=$!

echo "Service PID: $SERVICE_PID"
echo "Waiting for service to initialize (30s)..."
sleep 30

# Check health
echo ""
echo "Checking service health..."
curl -s http://localhost:8001/health | python -m json.tool

# Run test transcription with timing
echo ""
echo "Running test transcription..."
echo "Audio file: ../../audio.wav"
echo ""

START_TIME=$(date +%s)
curl -X POST "http://localhost:8001/transcribe" \
    -F "file=@../../audio.wav" \
    --output test_mps_output.mid \
    --max-time 600

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "====================================="
echo "Results:"
echo "====================================="
echo "Processing time: ${ELAPSED}s"
echo "MIDI output size: $(ls -lh test_mps_output.mid 2>/dev/null | awk '{print $5}')"
echo ""
echo "Service log (last 20 lines):"
tail -20 service.log
echo ""
echo "====================================="

# Cleanup
echo "Stopping service (PID: $SERVICE_PID)..."
kill $SERVICE_PID 2>/dev/null || true
echo "Done!"
