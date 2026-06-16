from celery import Celery
import os

celery_app = Celery(
    'ingest',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
)
celery_app.conf.timezone = 'America/Sao_Paulo'
celery_app.conf.task_default_queue = 'daily'
