import os

from celery import Celery

app = Celery(
    'ingest',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
)
app.conf.timezone = 'America/Sao_Paulo'
app.conf.task_default_queue = 'daily'

# Registro explícito das tasks — o worker (`-A services.ingest.celery_app`) importa
# o módulo do app, mas NÃO as tasks; sem isto elas ficam não-registradas e não
# executam. Lista apenas as tasks do app `ingest` (as de ingestão fiscal —
# rfb_tipi/sefaz_scraper/confaz_ocr/ncm_history — rodam no worker fiscal).
app.conf.include = [
    'services.ingest.tasks.caged',
    'services.ingest.tasks.consumidor_gov',
    'services.ingest.tasks.datajud',
    'services.ingest.tasks.ibge',
    'services.ingest.tasks.pgfn',
    'services.ingest.tasks.pncp',
    'services.ingest.tasks.receita',
    'services.ingest.tasks.siconfi',
    'services.ingest.tasks.transparencia',
]
