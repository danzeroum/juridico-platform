from celery.utils.log import get_task_logger
from ingest.celery_app import app

logger = get_task_logger(__name__)


@app.task(bind=True)
def run_weekly_ingest(self):
    logger.info("Iniciando ingest PGFN")
    # TODO: implementar integracao PGFN divida ativa
    return {"source": "PGFN", "status": "pending_implementation"}
