"""
Núcleo puro do Chamber Profiler (produto Judge/Chamber Profiler).

GOVERNANÇA LGPD: perfila **órgão julgador agregado** (tribunal/câmara), NUNCA juiz
individual (pessoa natural). Ver riscos do plano e pendencias.md. O grão atual é
tribunal+classe (o DATAJUD silver ainda não carrega orgao_julgador); câmara/vara
exige campo adicional + parecer do DPO — registrado em pendencias.md.

Classifica o comportamento do órgão em faixas explicáveis a partir de linhas de
`jurimetria.indicador`. Sem I/O — testável isoladamente.
"""
from __future__ import annotations

from typing import Any


def _tier_provimento(pct: float | None) -> str:
    if pct is None:
        return "SEM_DADOS"
    if pct >= 0.5:
        return "ALTO_PROVIMENTO"
    if pct >= 0.25:
        return "MODERADO_PROVIMENTO"
    return "BAIXO_PROVIMENTO"


def _tier_congestionamento(taxa: float | None) -> str:
    if taxa is None:
        return "SEM_DADOS"
    if taxa >= 0.7:
        return "MUITO_CONGESTIONADO"
    if taxa >= 0.5:
        return "CONGESTIONADO"
    return "FLUIDO"


def _tier_duracao(dias: float | None) -> str:
    if dias is None:
        return "SEM_DADOS"
    if dias >= 720:
        return "LENTO"
    if dias >= 365:
        return "MEDIANO"
    return "RAPIDO"


def _wavg(pairs: list[tuple[float | None, int]]) -> float | None:
    """Média ponderada por n_processos, ignorando valores None."""
    num = 0.0
    den = 0
    for val, peso in pairs:
        if val is None or peso <= 0:
            continue
        num += float(val) * peso
        den += peso
    return (num / den) if den else None


def build_profile(tribunal: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Sintetiza um perfil agregado do órgão a partir de linhas de indicador.

    Cada row: {classe_tpu, assunto_tpu, n_processos, pct_provimento,
               taxa_congestionamento, duracao_mediana_dias}.
    """
    total = sum(int(r.get("n_processos") or 0) for r in rows)
    prov = _wavg([(r.get("pct_provimento"), int(r.get("n_processos") or 0)) for r in rows])
    cong = _wavg([(r.get("taxa_congestionamento"), int(r.get("n_processos") or 0)) for r in rows])
    dur = _wavg([(r.get("duracao_mediana_dias"), int(r.get("n_processos") or 0)) for r in rows])

    return {
        "tribunal": tribunal.upper(),
        "grao": "tribunal+classe",  # câmara/vara: ver pendencias.md
        "n_processos": total,
        "n_segmentos": len(rows),
        "perfil": {
            "provimento": {"valor": round(prov, 4) if prov is not None else None,
                           "faixa": _tier_provimento(prov)},
            "congestionamento": {"valor": round(cong, 4) if cong is not None else None,
                                 "faixa": _tier_congestionamento(cong)},
            "duracao_mediana_dias": {"valor": round(dur, 1) if dur is not None else None,
                                     "faixa": _tier_duracao(dur)},
        },
        "disclaimer": (
            "perfil AGREGADO por órgão (não por juiz individual) — heurística, "
            "não validada; ver governança LGPD em pendencias.md"
        ),
    }
