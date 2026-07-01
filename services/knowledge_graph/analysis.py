"""
Núcleo puro de análise da rede de litigância (produto Litigant Network).

Classifica a relação entre duas empresas pelo número de processos em comum e
sumariza a rede. Sem I/O — testável isoladamente. Os limiares são heurísticos e
documentados; ajustáveis conforme calibração futura com dados reais.
"""
from __future__ import annotations

from typing import Any

# Limiares de processos em comum → intensidade da relação.
_OCASIONAL = 2
_RECORRENTE = 5
_PREDATORIO = 20


def classify_relationship(processos_em_comum: int) -> str:
    """ISOLADO | OCASIONAL | RECORRENTE | PREDATORIO conforme volume compartilhado."""
    if processos_em_comum >= _PREDATORIO:
        return "PREDATORIO"
    if processos_em_comum >= _RECORRENTE:
        return "RECORRENTE"
    if processos_em_comum >= _OCASIONAL:
        return "OCASIONAL"
    return "ISOLADO"


def annotate_network(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adiciona a classificação de relação a cada vizinho da rede."""
    out: list[dict[str, Any]] = []
    for r in rows:
        n = int(r.get("processos_em_comum") or 0)
        out.append({**r, "relacao": classify_relationship(n)})
    return out


def network_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Sumário da rede: total de vizinhos e distribuição por intensidade."""
    annotated = annotate_network(rows)
    dist: dict[str, int] = {"ISOLADO": 0, "OCASIONAL": 0, "RECORRENTE": 0, "PREDATORIO": 0}
    for r in annotated:
        dist[r["relacao"]] += 1
    predatorios = [r for r in annotated if r["relacao"] == "PREDATORIO"]
    return {
        "n_vizinhos": len(annotated),
        "distribuicao": dist,
        "tem_litigancia_predatoria": len(predatorios) > 0,
        "vizinhos": annotated,
    }
