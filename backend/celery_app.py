"""Celery application configuration."""
from celery import Celery
from kombu import Exchange, Queue
from config import settings

# Initialize Celery
celery_app = Celery(
    "rescored",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
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
