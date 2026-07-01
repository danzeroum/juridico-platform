"""Camada I/O do Chamber Profiler: lê jurimetria.indicador e aplica build_profile."""
from __future__ import annotations

import logging
from typing import Any

from services.chamber_profiler.profile import build_profile

logger = logging.getLogger(__name__)


def _rows(tribunal: str, classe: str | None) -> list[dict[str, Any]]:
    from sqlalchemy import text

    from services.shared.tenant_db import get_engine

    where = ["tribunal = :tribunal", "fonte IN ('DATAJUD', 'BLEND')"]
    params: dict[str, Any] = {"tribunal": tribunal.upper()}
    if classe:
        where.append("classe_tpu = :classe")
        params["classe"] = classe
    sql = (
        "SELECT classe_tpu, assunto_tpu, n_processos, pct_provimento, "
        "taxa_congestionamento, duracao_mediana_dias "
        f"FROM jurimetria.indicador WHERE {' AND '.join(where)}"
    )
    try:
        with get_engine().connect() as conn:
            return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("chamber_profiler indisponível: %s", exc)
        return []


def profile_tribunal(tribunal: str, classe: str | None = None) -> dict[str, Any]:
    return build_profile(tribunal, _rows(tribunal, classe))
