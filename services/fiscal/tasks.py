"""
Enriquecimento assíncrono de planilhas (Celery).

Correções do parecer técnico (plano §3):
- NÃO usa ThreadPoolExecutor (classify é CPU-bound sob GIL; threads quebrariam o
  escopo de SET LOCAL app.tenant_id). Processa em CHUNKS sequenciais. O scale-out
  horizontal é feito dividindo o job em subtasks Celery (chord) por chunk e
  aumentando réplicas do worker (--scale fiscal-worker=N) — todas do mesmo tenant.
- Decision Ledger: UMA única entrada por JOB (raiz Merkle do lote), nunca 1 por
  item (evita O(N²) — ver Pendencia.md QT-08). decision_proof por item = prova de
  inclusão na árvore do lote.
- triage_item gravado em BULK (repository.bulk_insert_triage_items).

Coberto por testes de integração/E2E (ver pyproject omit).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from services.fiscal.batch.anchor import batch_manifest_hash, build_batch_anchor
from services.fiscal.celery_app import app
from services.fiscal.repository import bulk_insert_triage_items, classify_one
from services.shared.contracts.fiscal import UF, NcmTriageRequest

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


@app.task(bind=True, queue="fiscal", name="fiscal.tasks.enrich_spreadsheet")
def enrich_spreadsheet(
    self,
    job_id: str,
    tenant_id: str,
    rows: list[dict],
    uf_origem: str = "SP",
) -> dict:
    """
    Classifica os itens de uma planilha (já lidos em `rows`), ancora o lote no
    Decision Ledger (1 entrada) e grava os itens em bulk. Retorna resumo do job.

    `rows`: lista de dicts {row, descricao, ncm_hint, uf} (services/fiscal/spreadsheet/reader).
    """
    from services.shared.ledger.merkle import PostgresDecisionLedger

    results = []
    for start in range(0, len(rows), _CHUNK):
        for row in rows[start : start + _CHUNK]:
            req = _to_request(row, uf_origem)
            if req is None:
                continue
            results.append(classify_one(req))
        logger.info("job %s: %d/%d itens classificados", job_id, len(results), len(rows))

    # Ancoragem: 1 raiz Merkle do lote, 1 entrada no Ledger para o job inteiro.
    anchor = build_batch_anchor(results)
    ledger = PostgresDecisionLedger(tenant_id)
    entry = ledger.add_entry(
        request_id=job_id,
        product="fiscal",
        inputs={"manifest": batch_manifest_hash(job_id, tenant_id, anchor["count"])},
        outputs={"batch_merkle_root": anchor["root"], "count": anchor["count"]},
        sources=["TIPI", "SENADO", "SEFAZ"],
    )

    # Persistência dos itens em bulk (decision_proof = índice da folha + raiz ancorada).
    items = [
        {
            "leaf_index": i,
            "sku_descricao": r.sku_descricao,
            "ncm_sugerido": r.suggested_ncm.ncm_codigo if r.suggested_ncm else None,
            "confidence": r.suggested_ncm.confidence if r.suggested_ncm else None,
            "fonte_regra": r.suggested_ncm.fonte_regra.value if r.suggested_ncm else None,
            "icms_interno_efetivo_pct": r.icms.interna_efetiva_pct,
            "icms_inter_pct": r.icms.interestadual_pct,
            "difal_pct": r.icms.difal_pct,
            "categoria": r.categoria,
            "conflito": r.conflito_detectado,
            "observacoes": r.observacoes,
        }
        for i, r in enumerate(results)
    ]
    bulk_insert_triage_items(tenant_id, job_id, items)

    return {
        "job_id": job_id,
        "processed": len(results),
        "total": len(rows),
        "batch_merkle_root": anchor["root"],
        "ledger_entry_index": entry["entry_index"],
        "completed_at": datetime.now(UTC).isoformat(),
    }
