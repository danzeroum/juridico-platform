"""
Clientes de armazenamento durável compartilhados (MinIO, OpenSearch, Neo4j).

Motivação (plano Fase 1b): as tasks de ingestão validam e pseudonimizam os dados
mas hoje só os gravam no cache Redis (48h). Este pacote generaliza o padrão de
`services/fiscal/storage.py` (cliente lazy, config de `settings`, I/O fora de
cobertura — validado em E2E) para os três destinos duráveis:

- MinIO   → camada bronze (JSONL particionado por data, buckets privados)
- OpenSearch → camada silver (índices consultáveis, bulk indexing)
- Neo4j   → grafo de entidades (Empresa → Processo)

Cada módulo expõe helpers idempotentes e com degradação graciosa: uma falha de
um store é logada e contada, nunca fatal para a task de ingestão inteira
(coerente com o circuit breaker já existente em `pipeline/base.py`).
"""
from __future__ import annotations

from services.shared.storage.minio_client import ensure_bucket, put_json, put_jsonl
from services.shared.storage.neo4j_client import (
    ensure_constraints,
    upsert_process_edges,
)
from services.shared.storage.opensearch_client import bulk_index, ensure_index

__all__ = [
    "ensure_bucket",
    "put_json",
    "put_jsonl",
    "bulk_index",
    "ensure_index",
    "ensure_constraints",
    "upsert_process_edges",
]
