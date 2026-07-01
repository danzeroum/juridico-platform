import os

from celery import Celery

app = Celery(
    'fiscal',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
)
app.conf.timezone = 'America/Sao_Paulo'
app.conf.task_default_queue = 'fiscal'

# Registro explícito das tasks — o worker (`-A services.fiscal.celery_app`) importa
# o módulo do app, mas NÃO as tasks; sem isto, classify_chunk/finalize_enrichment/
# enrich_spreadsheet ficam não-registradas e o send_task do gateway não executa.
app.conf.include = ['services.fiscal.tasks']
