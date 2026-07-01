"""
Camada I/O do Demand Forecasting: lê a série histórica de `jurimetria.indicador`
e aplica o núcleo puro `forecast_series`. Degradação graciosa em falha de banco.
"""
from __future__ import annotations

import logging
from typing import Any

from services.forecasting.forecast import forecast_series

logger = logging.getLogger(__name__)


def _serie_historica(tribunal: str, classe: str | None, assunto: str | None) -> list[dict[str, Any]]:
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
        "SELECT periodo, SUM(n_processos) AS n FROM jurimetria.indicador "
        f"WHERE {' AND '.join(where)} GROUP BY periodo ORDER BY periodo ASC"
    )
    try:
        with get_engine().connect() as conn:
            return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("forecasting série indisponível: %s", exc)
        return []


def forecast_demand(
    tribunal: str, classe: str | None = None, assunto: str | None = None, horizonte: int = 3
) -> dict[str, Any]:
    serie = _serie_historica(tribunal, classe, assunto)
    valores = [row["n"] for row in serie]
    resultado = forecast_series(valores, horizonte)
    return {
        "tribunal": tribunal.upper(),
        "classe_tpu": classe,
        "assunto_tpu": assunto,
        "periodos_historicos": [row["periodo"] for row in serie],
        **resultado,
    }
