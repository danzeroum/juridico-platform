from celery.utils.log import get_task_logger

from services.ingest.celery_app import app

logger = get_task_logger(__name__)


@app.task(bind=True)
def run_hourly_check(self):
    logger.info("Iniciando ingest Portal da Transparencia")
    # TODO: implementar check horario com cache Redis
    return {"source": "TRANSPARENCIA", "status": "pending_implementation"}
