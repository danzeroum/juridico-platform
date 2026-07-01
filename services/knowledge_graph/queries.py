"""
Camada de consulta do Knowledge Graph (I/O Neo4j). Degradação graciosa: em falha
do grafo, retorna vazio/zeros em vez de propagar 500 (coerente com P3 do ROADMAP).
"""
from __future__ import annotations

import logging
from typing import Any

from services.knowledge_graph.analysis import network_summary

logger = logging.getLogger(__name__)


def company_processes(cnpj: str, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from services.shared.storage.neo4j_client import company_processes as _q
        return _q(cnpj, limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("KG company_processes indisponível para %s: %s", cnpj, exc)
        return []


def litigant_network(cnpj: str, limit: int = 50) -> dict[str, Any]:
    try:
        from services.shared.storage.neo4j_client import litigant_network as _q
        rows = _q(cnpj, limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("KG litigant_network indisponível para %s: %s", cnpj, exc)
        rows = []
    return {"cnpj": cnpj, **network_summary(rows)}


def graph_stats() -> dict[str, Any]:
    try:
        from services.shared.storage.neo4j_client import graph_stats as _q
        return _q()
    except Exception as exc:  # noqa: BLE001
        logger.warning("KG graph_stats indisponível: %s", exc)
        return {"empresas": 0, "processos": 0, "arestas": 0}
