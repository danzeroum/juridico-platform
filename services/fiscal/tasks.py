"""
Enriquecimento assíncrono de planilhas (Celery) — fan-out por CHORD.

Correções do parecer técnico (plano §3):
- Fan-out horizontal via chord: `group(classify_chunk)` processa os chunks em
  paralelo entre réplicas do worker (--scale fiscal-worker=N), e o finalizer ancora
  o lote UMA vez. NÃO usa ThreadPoolExecutor (classify é CPU-bound sob GIL; threads
  quebrariam o escopo de SET LOCAL app.tenant_id). Cada subtask é do mesmo tenant.
- Decision Ledger: UMA única entrada por JOB (raiz Merkle do lote), nunca 1 por
  item (evita O(N²) — Pendencia.md QT-08). decision_proof por item = prova de
  inclusão na árvore do lote (leaf_index + raiz ancorada).
- triage_item gravado em BULK.

Coberto por E2E (broker + worker + Postgres). A serialização result↔dict usada no
transporte do chord e a ancoragem são testadas de verdade nos unit tests.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from services.fiscal.batch.anchor import (
    batch_manifest_hash,
    build_batch_anchor,
    serialize_result,
)
from services.fiscal.celery_app import app
from services.fiscal.repository import bulk_insert_triage_items, classify_one
from services.shared.contracts.fiscal import UF, NcmTriageRequest, NcmTriageResult

logger = logging.getLogger(__name__)

_CHUNK = 500


def _to_request(row: dict, uf_origem: str) -> NcmTriageRequest | None:
    """Converte uma linha lida da planilha em NcmTriageRequest, ou None se inválida."""
    uf_destino = row.get("uf") or uf_origem
    if uf_destino not in UF.__members__ or uf_origem not in UF.__members__:
        return None
    if not row.get("descricao"):
        return None
    return NcmTriageRequest(
        descricao=row["descricao"],
        uf_origem=UF(uf_origem),
        uf_destino=UF(uf_destino),
        ncm_hint=row.get("ncm_hint"),
    )


@app.task(bind=True, queue="fiscal", name="fiscal.tasks.classify_chunk")
def classify_chunk(self, rows: list[dict], uf_origem: str) -> list[dict]:
    """Classifica um chunk de linhas. Retorna NcmTriageResult serializados (JSON)."""
    out: list[dict] = []
    for row in rows:
        req = _to_request(row, uf_origem)
        if req is None:
            continue
        out.append(classify_one(req).model_dump(mode="json"))
    return out


@app.task(bind=True, queue="fiscal", name="fiscal.tasks.finalize_enrichment")
def finalize_enrichment(self, chunk_results: list[list[dict]], job_id: str, tenant_id: str) -> dict:
    """
    Callback do chord: junta os chunks (na ordem do group), ancora o lote no Ledger
    (1 entrada) e grava os itens em bulk.
    """
    from services.shared.ledger.merkle import PostgresDecisionLedger

    dicts = [d for chunk in chunk_results for d in (chunk or [])]
    results = [NcmTriageResult(**d) for d in dicts]

    anchor = build_batch_anchor(results)
    ledger = PostgresDecisionLedger(tenant_id)
    entry = ledger.add_entry(
        request_id=job_id,
        product="fiscal",
        inputs={"manifest": batch_manifest_hash(job_id, tenant_id, anchor["count"])},
        outputs={"batch_merkle_root": anchor["root"], "count": anchor["count"]},
        sources=["TIPI", "SENADO", "SEFAZ"],
    )
    bulk_insert_triage_items(
        tenant_id, job_id, [serialize_result(i, r) for i, r in enumerate(results)]
    )
    logger.info("job %s: %d itens ancorados (raiz %s)", job_id, anchor["count"], anchor["root"][:12])
    return {
        "job_id": job_id,
        "processed": anchor["count"],
        "batch_merkle_root": anchor["root"],
        "ledger_entry_index": entry["entry_index"],
        "completed_at": datetime.now(UTC).isoformat(),
    }


@app.task(bind=True, queue="fiscal", name="fiscal.tasks.enrich_spreadsheet")
def enrich_spreadsheet(self, job_id: str, tenant_id: str, rows: list[dict], uf_origem: str = "SP") -> dict:
    """
    Orquestra o enriquecimento: divide em chunks, dispara o chord (classify em
    paralelo → finalize ancora uma vez). Assinatura estável (chamada pelo gateway).
    """
    from celery import chord, group

    chunks = [rows[i : i + _CHUNK] for i in range(0, len(rows), _CHUNK)]
    if not chunks:
        return finalize_enrichment.run([], job_id, tenant_id)

    callback = finalize_enrichment.s(job_id, tenant_id)
    chord(group(classify_chunk.s(c, uf_origem) for c in chunks))(callback)
    return {"job_id": job_id, "chunks": len(chunks), "status": "dispatched"}
