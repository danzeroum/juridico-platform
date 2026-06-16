from celery.utils.log import get_task_logger
from ingest.celery_app import app

logger = get_task_logger(__name__)


@app.task(bind=True)
def run_daily_ingest(self):
    logger.info("Iniciando ingest PNCP")
    # TODO: implementar integracao PNCP
    return {"source": "PNCP", "status": "pending_implementation"}
