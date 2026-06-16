from celery.utils.log import get_task_logger
from ingest.celery_app import app

logger = get_task_logger(__name__)


@app.task(bind=True)
def run_monthly_ingest(self):
    logger.info("Iniciando ingest SICONFI")
    # TODO: implementar integracao SICONFI/STN
    return {"source": "SICONFI", "status": "pending_implementation"}
