FROM python:3.12-slim
WORKDIR /app
COPY services/ingest/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services/ingest /app/ingest
CMD ["celery", "-A", "ingest.celery_app", "worker", "--loglevel=info"]
