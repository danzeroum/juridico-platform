# Worker do FiscalEngine — inclui Chromium (Playwright) e Tesseract (OCR) para os
# pipelines de ingestão SEFAZ (scraping) e CONFAZ (OCR de PDF escaneado).
#
# Copia toda a árvore `services/` para que os imports `services.fiscal.*` e
# `services.shared.*` resolvam; roda com PYTHONPATH=/app.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Tesseract (OCR, português) + libs de sistema exigidas pelo Chromium headless.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-por \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libasound2 libpango-1.0-0 libcairo2 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY services/fiscal/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m playwright install chromium

COPY services /app/services

# Fila fiscal (triagem/enriquecimento) + batch (chunks do chord).
CMD ["celery", "-A", "services.fiscal.celery_app", "worker", \
     "--loglevel=info", "-Q", "fiscal,batch", "--concurrency=4"]
