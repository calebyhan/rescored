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
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Initialize Git LFS
RUN git lfs install --skip-repo

WORKDIR /app

# Copy repository
COPY . .

# Pull LFS files if available
RUN git lfs pull 2>/dev/null || echo "Git LFS files skipped (may be pre-downloaded)"

# Install Python dependencies
RUN pip install --no-cache-dir Cython 'numpy<2.0.0' 'scipy<1.14.0'
RUN pip install --no-cache-dir -r backend/requirements.txt

# Create storage directory
RUN mkdir -p /app/storage && chmod 777 /app/storage

# Expose HF Spaces port
EXPOSE 7860

# Set environment for HF Spaces
ENV API_PORT=7860
ENV API_HOST=0.0.0.0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Start FastAPI server
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
