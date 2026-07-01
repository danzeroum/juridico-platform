"""
Base pipeline: linage fields, circuit breaker, bronze/silver/gold helpers.

Todas as tarefas de ingestão usam `add_linage` antes de salvar no bronze e
`circuit_breaker` para isolar falhas de fontes governamentais instáveis.
"""

import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


def add_linage(record: dict[str, Any], source: str, transform_version: str = "1.0.0") -> dict[str, Any]:
    """Adiciona campos de linhagem ao registro antes do bronze."""
    record = dict(record)
    record["source"] = source
    record["ingested_at"] = datetime.now(UTC).isoformat()
    record["transform_version"] = transform_version
    return record


def compute_lag_days(data_source_date: str) -> int:
    """Dias decorridos desde a data da fonte até hoje (staleness indicator)."""
    try:
        source_date = date.fromisoformat(data_source_date)
        return (date.today() - source_date).days
    except (ValueError, TypeError):
        return -1


class CircuitState(StrEnum):
    CLOSED = "CLOSED"      # normal — deixa passar
    OPEN = "OPEN"          # falha recente — bloqueia imediatamente
    HALF_OPEN = "HALF_OPEN"  # testando recuperação


class CircuitBreaker:
    """
    Circuit breaker simples por fonte externa.

    Estados:
    - CLOSED: chamadas passam normalmente.
    - OPEN: chamadas bloqueadas por `recovery_timeout` segundos após `failure_threshold` falhas.
    - HALF_OPEN: uma chamada de teste permitida; sucesso fecha, falha reabre.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 300.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            assert self._opened_at is not None
            if time.monotonic() - self._opened_at >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("CircuitBreaker[%s]: OPEN → HALF_OPEN", self.name)
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        if self._state != CircuitState.CLOSED:
            logger.info("CircuitBreaker[%s]: %s → CLOSED", self.name, self._state)
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning(
                "CircuitBreaker[%s]: OPEN após %d falhas", self.name, self._failure_count
            )

    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN


# Instâncias por fonte (singleton por processo Celery)
_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(source: str) -> CircuitBreaker:
    if source not in _breakers:
        _breakers[source] = CircuitBreaker(name=source)
    return _breakers[source]


def reconcile(source: str, records_in: int, records_out: int, date_str: str) -> dict[str, Any]:
    """Registro de reconciliação: contagem de entrada vs saída por execução."""
    return {
        "source": source,
        "date": date_str,
        "records_in": records_in,
        "records_out": records_out,
        "loss_pct": round((1 - records_out / records_in) * 100, 2) if records_in > 0 else 0.0,
        "reconciled_at": datetime.now(UTC).isoformat(),
    }


def safe_log1p(value: float | None) -> float:
    """log1p(value) com tratamento de None/negativo."""
    if value is None or value < 0:
        return 0.0
    return math.log1p(value)


def persist_silver(
    source: str,
    date_str: str,
    bronze_records: list[dict[str, Any]],
    silver_records: list[dict[str, Any]],
    *,
    opensearch_index: str | None = None,
    graph_writer: Callable[[list[dict[str, Any]]], int] | None = None,
    id_field: str = "id_processo",
) -> dict[str, Any]:
    """
    Sink DRY de persistência durável, chamado por todas as tasks de ingestão
    (plano Fase 1b). Encerra o TODO histórico do DATAJUD e evita que cada task
    refaça a fiação de três stores.

    Ordem e responsabilidades:
    1. bronze  → MinIO (JSONL particionado, `bronze-<source>/dt=.../part-*.jsonl`)
    2. silver  → OpenSearch (índice `opensearch_index`, se fornecido)
    3. grafo   → `graph_writer(silver_records)` (só o DATAJUD passa arestas; as
       demais fontes passam None)

    **Degradação graciosa:** cada store é isolado; a falha de um é logada e
    contada em `errors`, nunca aborta os demais nem a task. Coerente com o
    circuit breaker por fonte.

    IMPORTANTE (LGPD): `silver_records`/`bronze_records` devem já estar
    pseudonimizados pelo chamador — este sink não toca PII, só grava.
    """
    counts: dict[str, Any] = {
        "source": source,
        "date": date_str,
        "bronze": 0,
        "opensearch": 0,
        "graph": 0,
        "errors": [],
    }

    # 1. Bronze → MinIO
    try:
        from services.shared.storage.minio_client import put_jsonl

        put_jsonl(source, date_str, bronze_records)
        counts["bronze"] = len(bronze_records)
    except Exception as exc:  # noqa: BLE001 — degradação graciosa por store
        logger.warning("persist_silver[%s]: falha MinIO bronze: %s", source, exc)
        counts["errors"].append(f"minio:{exc}")

    # 2. Silver → OpenSearch
    if opensearch_index:
        try:
            from services.shared.storage.opensearch_client import bulk_index

            counts["opensearch"] = bulk_index(opensearch_index, silver_records, id_field=id_field)
        except Exception as exc:  # noqa: BLE001
            logger.warning("persist_silver[%s]: falha OpenSearch: %s", source, exc)
            counts["errors"].append(f"opensearch:{exc}")

    # 3. Grafo → Neo4j (opcional por fonte)
    if graph_writer is not None:
        try:
            counts["graph"] = graph_writer(silver_records)
        except Exception as exc:  # noqa: BLE001
            logger.warning("persist_silver[%s]: falha grafo: %s", source, exc)
            counts["errors"].append(f"graph:{exc}")

    return counts
