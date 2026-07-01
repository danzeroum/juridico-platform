"""Camada I/O do Early Warning: lê série de jurimetria.indicador e aplica detect_surges."""
from __future__ import annotations

import logging
from typing import Any

from services.early_warning.detect import detect_surges

logger = logging.getLogger(__name__)


def _serie_e_congestionamento(
    tribunal: str, classe: str | None, assunto: str | None
) -> tuple[list[float], float | None]:
    from sqlalchemy import text

    from services.shared.tenant_db import get_engine

    where = ["tribunal = :tribunal", "periodo <> 'TODOS'"]
    params: dict[str, Any] = {"tribunal": tribunal.upper()}
    if classe:
        where.append("classe_tpu = :classe")
        params["classe"] = classe
    if assunto:
        where.append("assunto_tpu = :assunto")
        params["assunto"] = assunto
    sql = (
        "SELECT periodo, SUM(n_processos) AS n, AVG(taxa_congestionamento) AS cong "
        f"FROM jurimetria.indicador WHERE {' AND '.join(where)} "
        "GROUP BY periodo ORDER BY periodo ASC"
    )
    try:
        with get_engine().connect() as conn:
            rows = [dict(r) for r in conn.execute(text(sql), params).mappings().all()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("early_warning série indisponível: %s", exc)
        return [], None
    valores = [row["n"] for row in rows]
    cong = rows[-1]["cong"] if rows else None
    return valores, (float(cong) if cong is not None else None)


def evaluate(tribunal: str, classe: str | None = None, assunto: str | None = None) -> dict[str, Any]:
    valores, cong = _serie_e_congestionamento(tribunal, classe, assunto)
    resultado = detect_surges(valores, cong)
    return {"tribunal": tribunal.upper(), "classe_tpu": classe, "assunto_tpu": assunto, **resultado}
