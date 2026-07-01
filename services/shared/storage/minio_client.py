"""
Cliente MinIO para a camada bronze (dado bruto imutável, replayable).

Convenção de bronze (plano A.1):
- bucket privado por fonte: `bronze-<fonte>` (ex.: `bronze-datajud`)
- key particionada estilo Hive: `dt=YYYY-MM-DD/part-<uuid>.jsonl`
- formato JSONL (um registro por linha) — barato de anexar e reprocessar

I/O externo — omitido de cobertura; validado em E2E. O cliente é construído
lazy (import dentro de `_client()`) para que importar este módulo não exija o
pacote `minio` nem uma conexão viva (mesma disciplina de `fiscal/storage.py`).
"""
from __future__ import annotations

import io
import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def _client():
    from minio import Minio

    from services.shared.config import settings

    return Minio(
        settings.MINIO_URL.replace("http://", "").replace("https://", ""),
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_URL.startswith("https://"),
    )


def ensure_bucket(bucket: str, client: Any | None = None) -> None:
    """Cria o bucket se não existir (idempotente). Buckets são privados por padrão."""
    client = client or _client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("MinIO: bucket %s criado", bucket)


def bronze_bucket(source: str) -> str:
    """Nome do bucket bronze para uma fonte (ex.: 'DATAJUD' → 'bronze-datajud')."""
    return f"bronze-{source.lower()}"


def _partition_key(date_str: str, ext: str) -> str:
    return f"dt={date_str}/part-{uuid.uuid4().hex}.{ext}"


def put_json(bucket: str, key: str, obj: dict[str, Any], client: Any | None = None) -> str:
    """Grava um único objeto JSON no bucket. Retorna a key."""
    client = client or _client()
    ensure_bucket(bucket, client)
    data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
    client.put_object(bucket, key, io.BytesIO(data), length=len(data), content_type="application/json")
    return key


def put_jsonl(
    source: str,
    date_str: str,
    records: list[dict[str, Any]],
    client: Any | None = None,
) -> str | None:
    """
    Grava uma lista de registros como JSONL em `bronze-<source>/dt=<date>/part-*.jsonl`.

    Retorna a key gravada, ou None se `records` está vazio. Idempotente por
    execução no sentido de que cada chamada gera uma nova partição (replayable);
    a deduplicação lógica fica a cargo da camada silver (id estável no OpenSearch).
    """
    if not records:
        return None
    client = client or _client()
    bucket = bronze_bucket(source)
    ensure_bucket(bucket, client)
    key = _partition_key(date_str, "jsonl")
    body = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in records).encode("utf-8")
    client.put_object(bucket, key, io.BytesIO(body), length=len(body), content_type="application/x-ndjson")
    logger.info("MinIO: %d registros → %s/%s", len(records), bucket, key)
    return f"{bucket}/{key}"
