# =============================================================================
# Ingest Pipeline - Celery Workers
# Pipeline de ingestao de dados publicos governamentais
# =============================================================================

FROM python:3.12-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY services/ingest/requirements.txt /tmp/
RUN pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

# --- Runtime ---
FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app
COPY --from=builder /install /usr/local
COPY services/shared/ ./shared/
COPY services/ingest/ ./ingest/

USER appuser
ENTRYPOINT ["tini", "--"]
CMD ["celery", "-A", "ingest.celery_app", "worker", "--loglevel=info"]
