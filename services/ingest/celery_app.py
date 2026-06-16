from celery import Celery
from shared.config import settings

app = Celery(
    "ingest",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "ingest.tasks.datajud",
        "ingest.tasks.caged",
        "ingest.tasks.pncp",
        "ingest.tasks.siconfi",
        "ingest.tasks.pgfn",
        "ingest.tasks.transparencia",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
)

app.conf.beat_schedule = {
    "datajud-daily-ingest": {
        "task": "ingest.tasks.datajud.run_daily_ingest",
        "schedule": 24 * 60 * 60,
        "options": {"queue": "daily"},
    },
    "caged-monthly-ingest": {
        "task": "ingest.tasks.caged.run_monthly_ingest",
        "schedule": 30 * 24 * 60 * 60,
        "options": {"queue": "monthly"},
    },
    "pncp-daily-ingest": {
        "task": "ingest.tasks.pncp.run_daily_ingest",
        "schedule": 24 * 60 * 60,
        "options": {"queue": "daily"},
    },
}
