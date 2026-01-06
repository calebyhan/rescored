FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    git-lfs \
    gcc \
    g++ \
    make \
    build-essential \
    curl \
    ca-certificates \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/* && update-ca-certificates

# Initialize Git LFS
RUN git lfs install --skip-repo

WORKDIR /app

# Copy repository
COPY . .

# Pull LFS files if available
RUN git lfs pull 2>/dev/null || echo "Git LFS files skipped (may be pre-downloaded)"

# Install Python dependencies
RUN pip install --no-cache-dir 'numpy<2.0.0' 'scipy<1.14.0' Cython
RUN pip install --no-cache-dir 'fakeredis[lua]' mir_eval
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN pip install --no-cache-dir --force-reinstall 'numpy<2.0.0'

# Create storage directory
RUN mkdir -p /app/storage && chmod 777 /app/storage

# Copy and make startup script executable
COPY start-backend.sh /app/start-backend.sh
RUN chmod +x /app/start-backend.sh

# Set environment variables
ENV API_PORT=7860
ENV API_HOST=0.0.0.0
ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1

# DNS configuration for container environments
ENV RES_OPTIONS="single-request-reopen"
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Use in-memory Redis for HF Spaces
ENV USE_FAKE_REDIS=true

EXPOSE 7860

# Set working directory to backend
WORKDIR /app/backend

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Start with startup script
CMD ["/app/start-backend.sh"]
