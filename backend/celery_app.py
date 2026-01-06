"""Celery application configuration."""
import sys
from pathlib import Path
import os

# Ensure backend directory is in Python path for imports
backend_dir = Path(__file__).parent.resolve()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from celery import Celery
from kombu import Exchange, Queue
from app_config import settings

# Determine broker and backend based on configuration
if settings.use_fake_redis:
    # Use eager mode for HF Spaces - execute tasks synchronously
    broker_url = "memory://"
    backend_url = "cache+memory://"
    task_always_eager = True
else:
    # Use Redis for production
    broker_url = settings.redis_url
    backend_url = settings.redis_url
    task_always_eager = False

# Initialize Celery
celery_app = Celery(
    "rescored",
    broker=broker_url,
    backend=backend_url,
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Eager mode for HF Spaces (synchronous execution)
    task_always_eager=task_always_eager,
    task_eager_propagates=True,
    enable_utc=True,

    # Task settings
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # Soft limit at 9 minutes
    task_acks_late=True,  # Acknowledge task after completion (safer)
    worker_prefetch_multiplier=1,  # Take 1 task at a time

    # Retry settings
    task_autoretry_for=(Exception,),
    task_retry_kwargs={'max_retries': 3},
    task_retry_backoff=True,  # Exponential backoff
    task_retry_backoff_max=600,

    # Priority queues
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default', priority=5),
        Queue('high_priority', Exchange('high_priority'), routing_key='high_priority', priority=10),
    ),
    task_default_queue='default',
    task_default_routing_key='default',
)

# Import tasks to register them with Celery
# This must come after celery_app is created
import tasks  # noqa: E402, F401
