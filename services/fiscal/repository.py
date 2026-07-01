"""
Acesso a dados do FiscalEngine.

Tabelas de referência (NCM/ICMS) são globais (sem RLS) → lidas por conexão simples.
Jobs/itens de triagem são por tenant → escritos via tenant_transaction (RLS FORCED).

As classes de fonte implementam os Protocols de services/fiscal/triage/engine.py.
Coberto por testes de integração (ver pyproject omit).
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import text

from services.fiscal.triage.engine import classify
from services.shared.contracts.fiscal import NcmTriageRequest, NcmTriageResult
from services.shared.tenant_db import get_engine, tenant_transaction


class DbNcmSource:
    """Fonte de NCM sobre fiscal.ncm (global, temporal)."""

    def __init__(self, conn: Any):
        self._conn = conn

    def get_ncm(self, codigo: str, data: date | None) -> dict | None:
        row = self._conn.execute(
            text(
                "SELECT ncm_codigo, descricao FROM fiscal.ncm "
                "WHERE ncm_codigo = :c AND vigencia @> COALESCE(:d, CURRENT_DATE) LIMIT 1"
            ),
            {"c": codigo, "d": data},
        ).fetchone()
        return {"ncm_codigo": row[0], "descricao": row[1]} if row else None

    def catalog(self, data: date | None) -> list[tuple[str, str]]:
        rows = self._conn.execute(
            text(
                "SELECT ncm_codigo, descricao FROM fiscal.ncm "
                "WHERE vigencia @> COALESCE(:d, CURRENT_DATE)"
            ),
            {"d": data},
        ).fetchall()
        return [(r[0].strip(), r[1]) for r in rows]


class DbIcmsSource:
    """Fonte de ICMS interno sobre fiscal.icms_interno (global, temporal)."""

    def __init__(self, conn: Any):
        self._conn = conn

    def interna(self, uf: str, ncm_codigo: str | None, data: date | None) -> dict | None:
        # Prefere a regra mais específica por prefixo NCM; fallback = alíquota geral (prefix NULL).
        row = self._conn.execute(
            text(
                "SELECT aliquota_pct, fcp_pct, fundamento_legal FROM fiscal.icms_interno "
                "WHERE uf = :uf AND vigencia @> COALESCE(:d, CURRENT_DATE) "
                "  AND (ncm_prefix IS NULL OR :ncm LIKE ncm_prefix || '%') "
                "ORDER BY COALESCE(length(ncm_prefix), 0) DESC LIMIT 1"
            ),
            {"uf": uf, "ncm": ncm_codigo or "", "d": data},
        ).fetchone()
        if row is None:
            return None
        return {
            "aliquota_pct": float(row[0]) if row[0] is not None else None,
            "fcp_pct": float(row[1]) if row[1] is not None else None,
            "fundamento_legal": row[2],
        }


class DbCategorySource:
    def __init__(self, conn: Any):
        self._conn = conn

    def categoria(self, ncm_codigo: str | None) -> str | None:
        if not ncm_codigo:
            return None
        row = self._conn.execute(
            text(
                "SELECT c.slug FROM fiscal.ncm_categoria nc "
                "JOIN fiscal.categoria c ON c.id = nc.categoria_id "
                "WHERE :ncm LIKE nc.ncm_prefix || '%' "
                "ORDER BY length(nc.ncm_prefix) DESC LIMIT 1"
            ),
            {"ncm": ncm_codigo},
        ).fetchone()
        return row[0] if row else None


def classify_one(request: NcmTriageRequest) -> NcmTriageResult:
    """Triagem síncrona de um item usando as fontes de referência globais."""
    with get_engine().connect() as conn:
        return classify(
            request,
            DbNcmSource(conn),
            DbIcmsSource(conn),
            DbCategorySource(conn),
        )


def bulk_insert_triage_items(tenant_id: str, job_id: str, items: list[dict]) -> None:
    """Insere resultados de triagem em bulk (um executemany), não 1 INSERT por item."""
    if not items:
        return
    with tenant_transaction(tenant_id) as conn:
        conn.execute(
            text(
                "INSERT INTO fiscal.triage_item "
                "(job_id, tenant_id, leaf_index, sku_descricao, ncm_sugerido, confidence, "
                " fonte_regra, icms_interno_efetivo_pct, icms_inter_pct, difal_pct, "
                " categoria, conflito, observacoes) "
                "VALUES (:job_id, :tenant_id::uuid, :leaf_index, :sku, :ncm, :conf, :fonte, "
                " :interno, :inter, :difal, :categoria, :conflito, :obs::jsonb)"
            ),
            [
                {
                    "job_id": job_id,
                    "tenant_id": tenant_id,
                    "leaf_index": it["leaf_index"],
                    "sku": it["sku_descricao"],
                    "ncm": it["ncm_sugerido"],
                    "conf": it["confidence"],
                    "fonte": it["fonte_regra"],
                    "interno": it["icms_interno_efetivo_pct"],
                    "inter": it["icms_inter_pct"],
                    "difal": it["difal_pct"],
                    "categoria": it["categoria"],
                    "conflito": it["conflito"],
                    "obs": json.dumps(it["observacoes"], ensure_ascii=False),
                }
                for it in items
            ],
        )
