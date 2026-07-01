"""
Camada de ingestão do FiscalEngine — lógica PURA e testável de parse/extração.

As fontes governamentais são heterogêneas (CSV estruturado, HTML dinâmico, PDF
escaneado). Este pacote separa a lógica determinística (parse, extração de regras,
hashing) — coberta por testes reais — dos wrappers de I/O de rede/Playwright/Celery,
que ficam finos em services/ingest/tasks/ (omitidos de cobertura, testados em E2E).
"""
