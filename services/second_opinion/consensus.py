"""
Núcleo puro do Second Opinion Engine.

Combina sinais de múltiplos produtos numa "segunda opinião" estatística sobre a
favorabilidade de um caso:

- legalscore (0-1000): quanto maior, menor o risco → favorabilidade = score/1000
- taxpredict_prob (0-1): probabilidade de desfecho favorável (direta)
- pct_provimento (0-1): taxa histórica de provimento no tema (base rate jurimétrica)

Produz favorabilidade combinada, nível de concordância entre os sinais e um
veredito em faixas. Sem I/O — testável. Heurística até validação formal.
"""
from __future__ import annotations

from typing import Any


def _normalize_signals(
    legalscore: float | None,
    taxpredict_prob: float | None,
    pct_provimento: float | None,
) -> dict[str, float]:
    sinais: dict[str, float] = {}
    if legalscore is not None:
        sinais["legalscore"] = max(0.0, min(1.0, legalscore / 1000.0))
    if taxpredict_prob is not None:
        sinais["taxpredict"] = max(0.0, min(1.0, taxpredict_prob))
    if pct_provimento is not None:
        sinais["jurimetria"] = max(0.0, min(1.0, pct_provimento))
    return sinais


def _verdict(favorabilidade: float) -> str:
    if favorabilidade >= 0.6:
        return "FAVORAVEL"
    if favorabilidade >= 0.4:
        return "INCERTO"
    return "DESFAVORAVEL"


def synthesize_opinion(
    legalscore: float | None = None,
    taxpredict_prob: float | None = None,
    pct_provimento: float | None = None,
) -> dict[str, Any]:
    """Síntese de consenso. Requer ≥1 sinal; concordância exige ≥2."""
    sinais = _normalize_signals(legalscore, taxpredict_prob, pct_provimento)
    if not sinais:
        return {"status": "sem_sinais"}

    valores = list(sinais.values())
    favorabilidade = sum(valores) / len(valores)

    # Concordância: 1 - amplitude (max-min). Só faz sentido com ≥2 sinais.
    if len(valores) >= 2:
        amplitude = max(valores) - min(valores)
        concordancia = round(1.0 - amplitude, 4)
        nivel = "ALTA" if amplitude <= 0.2 else ("MEDIA" if amplitude <= 0.4 else "BAIXA")
    else:
        concordancia = None
        nivel = "UNICO_SINAL"

    return {
        "status": "ok",
        "favorabilidade": round(favorabilidade, 4),
        "veredito": _verdict(favorabilidade),
        "concordancia": concordancia,
        "nivel_concordancia": nivel,
        "sinais": {k: round(v, 4) for k, v in sinais.items()},
        "n_sinais": len(sinais),
        "disclaimer": "heurística de consenso — não validada contra desfechos reais",
    }
