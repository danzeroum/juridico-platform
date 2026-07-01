FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1
COPY services/ingest/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
# Copia toda a árvore `services/` para que os imports `services.ingest.*`,
# `services.shared.*` etc. resolvam (convenção única do repositório).
COPY services /app/services
CMD ["celery", "-A", "services.ingest.celery_app", "worker", "--loglevel=info"]
