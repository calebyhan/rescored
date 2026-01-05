FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    gcc \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* && update-ca-certificates

# Set working directory
WORKDIR /app

# Enable glibc DNS retry mechanism (fixes transient DNS resolution failures in containers)
ENV RES_OPTIONS="single-request-reopen"
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1

# Copy requirements
COPY requirements.txt .

# Install build dependencies for madmom
RUN pip install --no-cache-dir Cython 'numpy<2.0.0'

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose API port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
