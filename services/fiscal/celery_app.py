import os

from celery import Celery
from celery.schedules import crontab

app = Celery(
    'fiscal',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
)
app.conf.timezone = 'America/Sao_Paulo'
app.conf.task_default_queue = 'fiscal'

# Registro explícito das tasks — o worker (`-A services.fiscal.celery_app`) importa
# o módulo do app, mas NÃO as tasks. Sem isto, elas ficam não-registradas e o
# send_task do gateway / o beat não executam.
#
# As tasks de ingestão (SEFAZ→Chromium, CONFAZ→Tesseract) rodam no worker FISCAL
# porque só a imagem fiscal tem essas dependências de runtime (o worker `ingest`
# genérico, python-slim, não as tem). Ficam na fila `fiscal_ingest`.
app.conf.include = [
    'services.fiscal.tasks',
    'services.ingest.tasks.rfb_tipi',
    'services.ingest.tasks.sefaz_scraper',
    'services.ingest.tasks.confaz_ocr',
    'services.ingest.tasks.ncm_history',
]

# Agendamento (Celery Beat) das tasks com fonte/periodicidade bem definidas.
# CONFAZ e ncm_migração NÃO são agendados aqui: exigem descoberta de links / URL
# de fonte (a definir) — disparados sob demanda por ora.
app.conf.beat_schedule = {
    'rfb-tipi-mensal': {
        'task': 'fiscal.ingestion.rfb_tipi.run_ingest',
        'schedule': crontab(minute=17, hour=3, day_of_month=1),
    },
    'sefaz-sp-semanal': {
        'task': 'fiscal.ingestion.sefaz_scraper.run_ingest',
        'schedule': crontab(minute=23, hour=4, day_of_week=1),
        'args': ['SP'],
    },
    'sefaz-rj-semanal': {
        'task': 'fiscal.ingestion.sefaz_scraper.run_ingest',
        'schedule': crontab(minute=33, hour=4, day_of_week=1),
        'args': ['RJ'],
    },
    'sefaz-mg-semanal': {
        'task': 'fiscal.ingestion.sefaz_scraper.run_ingest',
        'schedule': crontab(minute=43, hour=4, day_of_week=1),
        'args': ['MG'],
    },
}
