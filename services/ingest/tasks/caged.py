from celery.utils.log import get_task_logger
from ingest.celery_app import app

logger = get_task_logger(__name__)


@app.task(bind=True)
def run_monthly_ingest(self, month: str = None):
    logger.info(f"Iniciando ingest CAGED para {month or 'mes atual'}")
    # TODO: implementar download via FTP do MTE ou API publica
    # Se nao houver granularidade por CNPJ: usar agregado + estimativa proporcional
    return {"source": "CAGED", "status": "pending_implementation"}
