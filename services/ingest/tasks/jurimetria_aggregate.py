"""
Agregação jurimétrica: computa `jurimetria.indicador` a partir de duas fontes.

(a) DATAJUD silver (OpenSearch `datajud-silver-*`): agregações por
    (tribunal, classe_tpu, assunto_tpu, periodo) — contagem de processos e
    % de provimento (de resultado_normalizado). Duração NÃO sai do DATAJUD:
    o contrato tem data_julgamento mas não data de ajuizamento (ver risco 4 do
    plano) → a duração vem da ABJ na linha BLEND.
(b) ABJ landing (`jurimetria.abj_indicador_raw`): tempo_medio_dias e
    taxa_congestionamento, usados para preencher duração/congestionamento e como
    cross-check.

Escrita: upsert em jurimetria.indicador (tabela GLOBAL, sem RLS) via get_engine()
— nunca sob contexto de tenant. Emite reconcile("JURIMETRIA_AGG", ...).

O núcleo de merge (`build_indicador_rows`) é PURO e testável sem infra.
"""
from __future__ import annotations

from typing import Any

from celery.utils.log import get_task_logger

from services.ingest.celery_app import app
from services.ingest.pipeline.base import reconcile

logger = get_task_logger(__name__)


# ---------------------------------------------------------------------------
# Núcleo puro (testável sem OpenSearch/Postgres)
# ---------------------------------------------------------------------------
def build_indicador_rows(
    datajud_buckets: list[dict[str, Any]],
    abj_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Combina buckets do DATAJUD com indicadores da ABJ em linhas de
    jurimetria.indicador.

    - Cada bucket DATAJUD vira uma linha fonte='DATAJUD' (volume + pct_provimento).
    - Onde há ABJ para o mesmo (tribunal, classe, assunto, periodo), gera também
      uma linha fonte='BLEND' com duração/congestionamento da ABJ e volume do
      DATAJUD (o melhor dos dois mundos).
    - Linhas ABJ sem correspondente no DATAJUD entram como fonte='ABJ'.
    """
    def key(r: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            str(r.get("tribunal") or ""),
            str(r.get("classe_tpu") or r.get("classe_cnj") or ""),
            str(r.get("assunto_tpu") or r.get("assunto_cnj") or ""),
            str(r.get("periodo") or ""),
        )

    abj_by_key = {key(r): r for r in abj_rows}
    rows: list[dict[str, Any]] = []
    seen_abj: set[tuple[str, str, str, str]] = set()

    for b in datajud_buckets:
        k = key(b)
        rows.append({
            "tribunal": k[0], "classe_tpu": k[1], "assunto_tpu": k[2], "periodo": k[3],
            "fonte": "DATAJUD",
            "n_processos": b.get("n_processos", 0),
            "duracao_mediana_dias": None,
            "duracao_p25_dias": None,
            "duracao_p75_dias": None,
            "taxa_congestionamento": None,
            "taxa_litigiosidade": b.get("n_processos", 0),
            "pct_provimento": b.get("pct_provimento"),
            "source": "DATAJUD",
        })
        abj = abj_by_key.get(k)
        if abj is not None:
            seen_abj.add(k)
            rows.append({
                "tribunal": k[0], "classe_tpu": k[1], "assunto_tpu": k[2], "periodo": k[3],
                "fonte": "BLEND",
                "n_processos": b.get("n_processos", 0),
                "duracao_mediana_dias": abj.get("tempo_medio_dias"),
                "duracao_p25_dias": None,
                "duracao_p75_dias": None,
                "taxa_congestionamento": abj.get("taxa_congestionamento"),
                "taxa_litigiosidade": abj.get("casos_novos"),
                "pct_provimento": b.get("pct_provimento"),
                "source": "BLEND(DATAJUD+ABJ)",
            })

    for k, abj in abj_by_key.items():
        if k in seen_abj:
            continue
        rows.append({
            "tribunal": k[0], "classe_tpu": k[1], "assunto_tpu": k[2], "periodo": k[3],
            "fonte": "ABJ",
            "n_processos": abj.get("casos_pendentes") or 0,
            "duracao_mediana_dias": abj.get("tempo_medio_dias"),
            "duracao_p25_dias": None,
            "duracao_p75_dias": None,
            "taxa_congestionamento": abj.get("taxa_congestionamento"),
            "taxa_litigiosidade": abj.get("casos_novos"),
            "pct_provimento": None,
            "source": "ABJ",
        })

    return rows


# ---------------------------------------------------------------------------
# I/O (OpenSearch + Postgres)
# ---------------------------------------------------------------------------
def _query_datajud_buckets(index_pattern: str = "datajud-silver-*") -> list[dict[str, Any]]:
    """Agrega o DATAJUD silver por (tribunal, classe_tpu, assunto_tpu, ano)."""
    from services.shared.storage.opensearch_client import _client

    client = _client()
    body = {
        "size": 0,
        "aggs": {
            "por_tribunal": {"terms": {"field": "tribunal", "size": 100}, "aggs": {
                "por_classe": {"terms": {"field": "classe_tpu", "size": 200}, "aggs": {
                    "por_assunto": {"terms": {"field": "assunto_tpu", "size": 200}, "aggs": {
                        "por_ano": {"terms": {"field": "data_julgamento", "size": 20}},
                        "provimentos": {"filter": {"term": {"resultado_normalizado": "PROVIMENTO"}}},
                    }},
                }},
            }},
        },
    }
    try:
        resp = client.search(index=index_pattern, body=body)
    except Exception as exc:  # noqa: BLE001
        logger.warning("JURIMETRIA_AGG: falha na agregação OpenSearch: %s", exc)
        return []

    buckets: list[dict[str, Any]] = []
    aggs = resp.get("aggregations", {})
    for t in aggs.get("por_tribunal", {}).get("buckets", []):
        for c in t.get("por_classe", {}).get("buckets", []):
            for a in c.get("por_assunto", {}).get("buckets", []):
                n = a.get("doc_count", 0)
                prov = a.get("provimentos", {}).get("doc_count", 0)
                buckets.append({
                    "tribunal": t["key"],
                    "classe_tpu": c["key"],
                    "assunto_tpu": a["key"],
                    "periodo": "TODOS",
                    "n_processos": n,
                    "pct_provimento": round(prov / n, 4) if n else None,
                })
    return buckets


def _load_abj_rows() -> list[dict[str, Any]]:
    from sqlalchemy import text

    from services.shared.tenant_db import get_engine

    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT tribunal, classe_cnj, assunto_cnj, periodo, tempo_medio_dias, "
                "taxa_congestionamento, casos_novos, casos_baixados, casos_pendentes "
                "FROM jurimetria.abj_indicador_raw"
            )).mappings().all()
        return [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("JURIMETRIA_AGG: falha ao ler abj_indicador_raw: %s", exc)
        return []


def _upsert_indicador(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    from sqlalchemy import text

    from services.shared.tenant_db import get_engine

    stmt = text(
        """
        INSERT INTO jurimetria.indicador
            (tribunal, classe_tpu, assunto_tpu, periodo, fonte, n_processos,
             duracao_mediana_dias, duracao_p25_dias, duracao_p75_dias,
             taxa_congestionamento, taxa_litigiosidade, pct_provimento, source)
        VALUES
            (:tribunal, :classe_tpu, :assunto_tpu, :periodo, :fonte, :n_processos,
             :duracao_mediana_dias, :duracao_p25_dias, :duracao_p75_dias,
             :taxa_congestionamento, :taxa_litigiosidade, :pct_provimento, :source)
        ON CONFLICT (tribunal, classe_tpu, assunto_tpu, periodo, fonte)
        DO UPDATE SET
            n_processos           = EXCLUDED.n_processos,
            duracao_mediana_dias  = EXCLUDED.duracao_mediana_dias,
            taxa_congestionamento = EXCLUDED.taxa_congestionamento,
            taxa_litigiosidade    = EXCLUDED.taxa_litigiosidade,
            pct_provimento        = EXCLUDED.pct_provimento,
            ingested_at           = NOW()
        """
    )
    engine = get_engine()
    with engine.begin() as conn:
        for r in rows:
            conn.execute(stmt, r)
    return len(rows)


@app.task(bind=True, queue="monthly")
def run_aggregation(self) -> dict:
    """Recomputa jurimetria.indicador. Idempotente (upsert)."""
    datajud_buckets = _query_datajud_buckets()
    abj_rows = _load_abj_rows()
    rows = build_indicador_rows(datajud_buckets, abj_rows)
    written = _upsert_indicador(rows)
    rec = reconcile("JURIMETRIA_AGG", len(datajud_buckets) + len(abj_rows), written, "agg")
    logger.info("JURIMETRIA_AGG: %s", rec)
    return rec
