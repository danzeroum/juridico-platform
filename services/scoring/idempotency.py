"""
Redis-backed idempotency store e batch job tracker para LegalScore.

Separa a lógica de estado (Redis) do router (FastAPI) para facilitar testes.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

_IDEMP_TTL = 86400   # 24h (RFC 9456 recomenda ao menos 24h)
_BATCH_TTL = 86400   # 24h


def get_idempotency_result(redis: Any, tenant_id: str, key: str) -> dict | None:
    raw = redis.get(f"idemp:{tenant_id}:{key}")
    if raw:
        return json.loads(raw)
    return None


def set_idempotency_result(
    redis: Any,
    tenant_id: str,
    key: str,
    result: dict,
    ttl_secs: int = _IDEMP_TTL,
) -> None:
    redis.setex(f"idemp:{tenant_id}:{key}", ttl_secs, json.dumps(result))


def create_batch_job(redis: Any, cnpjs: list[str], tenant_id: str) -> str:
    """Cria entrada de acompanhamento de batch. Retorna job_id."""
    job_id = f"batch_{uuid.uuid4().hex[:16]}"
    payload = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "status": "queued",
        "total": len(cnpjs),
        "processed": 0,
        "results": [],
        "created_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
    }
    redis.setex(f"batch:{job_id}", _BATCH_TTL, json.dumps(payload))
    return job_id


def get_batch_status(redis: Any, job_id: str) -> dict | None:
    raw = redis.get(f"batch:{job_id}")
    if raw:
        return json.loads(raw)
    return None


def update_batch_progress(
    redis: Any,
    job_id: str,
    processed: int,
    results: list[dict],
    status: str = "processing",
    completed_at: str | None = None,
) -> None:
    raw = redis.get(f"batch:{job_id}")
    if not raw:
        return
    payload = json.loads(raw)
    payload["processed"] = processed
    payload["results"] = results
    payload["status"] = status
    if completed_at:
        payload["completed_at"] = completed_at
    # Manter TTL original (não redefinir para não encurtar o prazo)
    remaining = redis.ttl(f"batch:{job_id}")
    if remaining and remaining > 0:
        redis.setex(f"batch:{job_id}", remaining, json.dumps(payload))
    else:
        redis.setex(f"batch:{job_id}", _BATCH_TTL, json.dumps(payload))
