"""
Consultas do feature store jurimétrico (`jurimetria.indicador`).

Tabelas globais/públicas (sem RLS) → usam `get_engine()` (sem contexto de tenant).
O router mantém-se fino; toda a SQL vive aqui. Degradação graciosa: em falha de
banco, retorna lista vazia em vez de propagar 500 (coerente com P3 do ROADMAP).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_INDICADOR_COLS = (
    "tribunal, classe_tpu, assunto_tpu, periodo, fonte, n_processos, "
    "duracao_mediana_dias, duracao_p25_dias, duracao_p75_dias, "
    "taxa_congestionamento, taxa_litigiosidade, pct_provimento"
)


def _rows(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    from sqlalchemy import text

    from services.shared.tenant_db import get_engine

    try:
        with get_engine().connect() as conn:
            result = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in result]
    except Exception as exc:  # noqa: BLE001 — degradação graciosa
        logger.warning("jurimetria query falhou: %s", exc)
        return []


def get_indicators(
    tribunal: str | None = None,
    classe: str | None = None,
    assunto: str | None = None,
    periodo: str | None = None,
    fonte: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Indicadores filtrados. Todos os filtros são opcionais (AND)."""
    where: list[str] = []
    params: dict[str, Any] = {"limit": min(limit, 500), "offset": max(offset, 0)}
    if tribunal:
        where.append("tribunal = :tribunal")
        params["tribunal"] = tribunal.upper()
    if classe:
        where.append("classe_tpu = :classe")
        params["classe"] = classe
    if assunto:
        where.append("assunto_tpu = :assunto")
        params["assunto"] = assunto
    if periodo:
        where.append("periodo = :periodo")
        params["periodo"] = periodo
    if fonte:
        where.append("fonte = :fonte")
        params["fonte"] = fonte.upper()

    clause = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        f"SELECT {_INDICADOR_COLS} FROM jurimetria.indicador{clause} "
        "ORDER BY n_processos DESC LIMIT :limit OFFSET :offset"
    )
    return _rows(sql, params)


def get_congestion(tribunal: str) -> list[dict[str, Any]]:
    """Taxa de congestionamento por classe/assunto de um tribunal (preferindo BLEND/ABJ)."""
    sql = (
        "SELECT tribunal, classe_tpu, assunto_tpu, periodo, fonte, "
        "taxa_congestionamento, n_processos "
        "FROM jurimetria.indicador "
        "WHERE tribunal = :tribunal AND taxa_congestionamento IS NOT NULL "
        "ORDER BY taxa_congestionamento DESC LIMIT 200"
    )
    return _rows(sql, {"tribunal": tribunal.upper()})


def get_duration(classe: str) -> list[dict[str, Any]]:
    """Duração (mediana + IQR quando houver) por tribunal para uma classe TPU."""
    sql = (
        "SELECT tribunal, classe_tpu, assunto_tpu, periodo, fonte, "
        "duracao_mediana_dias, duracao_p25_dias, duracao_p75_dias, n_processos "
        "FROM jurimetria.indicador "
        "WHERE classe_tpu = :classe AND duracao_mediana_dias IS NOT NULL "
        "ORDER BY duracao_mediana_dias DESC LIMIT 200"
    )
    return _rows(sql, {"classe": classe})


def get_litigiosity(assunto: str | None = None) -> list[dict[str, Any]]:
    """Litigiosidade (volume de casos novos) por tribunal, opcionalmente por assunto."""
    params: dict[str, Any] = {}
    clause = ""
    if assunto:
        clause = " AND assunto_tpu = :assunto"
        params["assunto"] = assunto
    sql = (
        "SELECT tribunal, classe_tpu, assunto_tpu, periodo, fonte, "
        "taxa_litigiosidade, n_processos "
        "FROM jurimetria.indicador "
        f"WHERE taxa_litigiosidade IS NOT NULL{clause} "
        "ORDER BY taxa_litigiosidade DESC LIMIT 200"
    )
    return _rows(sql, params)


def market_intelligence(tribunal: str | None = None, ramo: str | None = None) -> dict[str, Any]:
    """
    Relatório agregado (produto Market Intelligence). Só dados agregados, ZERO PII.

    Retorna sumários por classe/assunto: volume total, congestionamento médio,
    duração mediana típica e % de provimento — combustível de relatório setorial.
    """
    where: list[str] = []
    params: dict[str, Any] = {}
    if tribunal:
        where.append("tribunal = :tribunal")
        params["tribunal"] = tribunal.upper()
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT classe_tpu, assunto_tpu, "
        "SUM(n_processos) AS total_processos, "
        "AVG(taxa_congestionamento) AS congestionamento_medio, "
        "AVG(duracao_mediana_dias) AS duracao_mediana_tipica, "
        "AVG(pct_provimento) AS provimento_medio "
        f"FROM jurimetria.indicador{clause} "
        "GROUP BY classe_tpu, assunto_tpu "
        "ORDER BY total_processos DESC LIMIT 100"
    )
    linhas = _rows(sql, params)
    total = sum((r.get("total_processos") or 0) for r in linhas)
    return {
        "tribunal": tribunal.upper() if tribunal else "TODOS",
        "ramo": ramo,
        "total_processos": total,
        "segmentos": linhas,
        "n_segmentos": len(linhas),
    }
