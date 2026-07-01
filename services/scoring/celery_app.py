import os

from celery import Celery

app = Celery(
    'scoring',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
)
app.conf.timezone = 'America/Sao_Paulo'
app.conf.task_default_queue = 'scoring'

# Registro explícito das tasks — sem isto, run_batch_score fica não-registrada e o
# send_task do gateway (batch de scoring) não executa no worker.
app.conf.include = ['services.scoring.tasks']
