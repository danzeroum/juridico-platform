"""
Feature assembler para LegalScore PJ.

Busca dados dos caches Redis (PGFN, Receita) e compõe o feature vector
para o PythonScoreEngine. Em Fase 1c, OpenSearch/Neo4j substituem o cache.

Fontes por feature:
- processos_ativos:          DATAJUD (Neo4j — Fase 1c)
- processos_trabalhistas:    DATAJUD (Neo4j — Fase 1c)
- divida_ativa_valor_log:    PGFN    (Redis cache da task semanal)
- divida_ativa_crescimento:  PGFN    (histórico — Fase 1c)
- saldo_emprego_12m:         CAGED   (Fase 2)
- capital_social_log:        Receita (Redis cache da task semanal)
- processos_repetitivos:     DATAJUD (Neo4j — Fase 1c)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

FEATURE_NAMES: tuple[str, ...] = (
    "processos_ativos",
    "processos_trabalhistas",
    "divida_ativa_valor_log",
    "divida_ativa_crescimento",
    "saldo_emprego_12m",
    "capital_social_log",
    "processos_repetitivos",
)


@dataclass
class FeatureVector:
    cnpj: str
    features: dict[str, float]
    cnae_2dig: str
    sources_used: list[str] = field(default_factory=list)
    sources_missing: list[str] = field(default_factory=list)
    source_date: str | None = None
    lag_days: int | None = None
    is_partial: bool = False


def assemble_features(cnpj: str, redis_client: Any) -> FeatureVector:
    """
    Monta feature vector para scoring a partir dos caches disponíveis.

    Fontes ausentes: feature = 0.0 e `is_partial = True`.
    O caller deve incluir `is_partial` na resposta para o cliente.
    """
    features: dict[str, float] = {name: 0.0 for name in FEATURE_NAMES}
    sources_used: list[str] = []
    sources_missing: list[str] = []
    source_date: str | None = None
    cnae_2dig = "00"

    # ── PGFN: dívida ativa ───────────────────────────────────────────────────
    pgfn = _fetch_pgfn(cnpj, redis_client)
    if pgfn:
        features["divida_ativa_valor_log"] = pgfn.get("valor_divida_log", 0.0)
        sources_used.append("PGFN")
    else:
        sources_missing.append("PGFN")

    # ── Receita: capital social + CNAE ───────────────────────────────────────
    receita = _fetch_receita(cnpj, redis_client)
    if receita:
        features["capital_social_log"] = receita.get("capital_social_log", 0.0)
        ingested = receita.get("ingested_at", "")
        if ingested:
            source_date = ingested[:10]
        cnae_raw = receita.get("cnae_fiscal") or "0000000"
        cnae_2dig = cnae_raw[:2] if len(cnae_raw) >= 2 else "00"
        sources_used.append("RECEITA")
    else:
        sources_missing.append("RECEITA")

    # ── DATAJUD: processos — Neo4j (grafo PARTE_EM populado pela ingestão) ───
    datajud = _fetch_datajud(cnpj)
    if datajud and datajud.get("total", 0) > 0:
        features["processos_ativos"] = float(datajud["total"])
        features["processos_trabalhistas"] = float(datajud.get("trabalhistas", 0))
        features["processos_repetitivos"] = float(datajud.get("repetitivos", 0))
        sources_used.append("DATAJUD")
    else:
        # Grafo vazio para o CNPJ OU indisponível: mantém features em 0.0 e marca
        # a fonte como ausente (score parcial, coerente com degradação graciosa).
        sources_missing.append("DATAJUD")

    is_partial = len(sources_missing) > 0

    return FeatureVector(
        cnpj=cnpj,
        features=features,
        cnae_2dig=cnae_2dig,
        sources_used=sources_used,
        sources_missing=sources_missing,
        source_date=source_date,
        is_partial=is_partial,
    )


def _fetch_pgfn(cnpj: str, redis_client: Any) -> dict[str, Any] | None:
    try:
        raw = redis_client.get(f"pgfn:{cnpj}")
        if not raw:
            return None
        data = json.loads(raw)
        from services.ingest.pipeline.quality import pgfn_bronze_to_silver
        return pgfn_bronze_to_silver(data)
    except Exception as exc:
        logger.warning("PGFN cache parse error for %s: %s", cnpj, exc)
        return None


def _fetch_datajud(cnpj: str) -> dict[str, Any] | None:
    """
    Contagens de processos da empresa a partir do grafo Neo4j (arestas PARTE_EM
    criadas pela ingestão DATAJUD). Degradação graciosa: qualquer falha do grafo
    devolve None → feature ausente, nunca 500.
    """
    try:
        from services.shared.storage.neo4j_client import count_processos_por_cnpj
        return count_processos_por_cnpj(cnpj)
    except Exception as exc:  # noqa: BLE001
        logger.warning("DATAJUD/Neo4j indisponível para %s: %s", cnpj, exc)
        return None


def _fetch_receita(cnpj: str, redis_client: Any) -> dict[str, Any] | None:
    try:
        raw = redis_client.get(f"receita:{cnpj}")
        if not raw:
            return None
        data = json.loads(raw)
        from services.ingest.pipeline.quality import receita_bronze_to_silver
        return receita_bronze_to_silver(data)
    except Exception as exc:
        logger.warning("Receita cache parse error for %s: %s", cnpj, exc)
        return None
