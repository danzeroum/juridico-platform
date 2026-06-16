import os

from celery import Celery

app = Celery(
    "taxpredict",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)
app.conf.timezone = "America/Sao_Paulo"
app.conf.task_default_queue = "taxpredict"
