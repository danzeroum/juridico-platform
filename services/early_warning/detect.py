"""
Núcleo puro do Early Warning System (produto Early Warning).

Detecta surtos em séries jurimétricas: (a) surto de volume — último período muito
acima da média histórica (z-score) e/ou variação percentual brusca; (b) pico de
congestionamento — taxa acima de um limiar crítico. Sem I/O — testável.

A saída são "gatilhos" com severidade (LOW→CRITICAL), prontos para virar
AlertEnvelope na borda (subject_ref sem PII: tribunal/assunto). Heurística.
"""
from __future__ import annotations

from typing import Any

# Limiares (heurísticos, documentados).
_Z_SURTO = 2.0            # z-score do último ponto para caracterizar surto
_PCT_SURTO = 0.5          # +50% vs período anterior
_CONG_CRITICO = 0.7       # taxa de congestionamento crítica
_MIN_PONTOS = 3


def _mean_std(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / n
    return m, var ** 0.5


def _severity_from_z(z: float) -> str:
    if z >= 4:
        return "CRITICAL"
    if z >= 3:
        return "HIGH"
    if z >= 2:
        return "MEDIUM"
    return "LOW"


def detect_surges(
    valores: list[float],
    taxa_congestionamento: float | None = None,
) -> dict[str, Any]:
    """
    Avalia a série `valores` (ordenada do mais antigo ao mais recente) e a taxa de
    congestionamento atual. Retorna gatilhos disparados.
    """
    gatilhos: list[dict[str, Any]] = []
    serie = [float(v) for v in valores if v is not None]

    if len(serie) >= _MIN_PONTOS:
        historico = serie[:-1]
        atual = serie[-1]
        media, desvio = _mean_std(historico)
        z = (atual - media) / desvio if desvio > 0 else 0.0
        var_pct = (atual - historico[-1]) / historico[-1] if historico[-1] > 0 else 0.0

        if z >= _Z_SURTO or var_pct >= _PCT_SURTO:
            gatilhos.append({
                "tipo": "SURTO_VOLUME",
                "severidade": _severity_from_z(z) if z >= _Z_SURTO else "MEDIUM",
                "z_score": round(z, 2),
                "variacao_pct": round(var_pct, 4),
                "valor_atual": round(atual, 2),
                "media_historica": round(media, 2),
            })

    if taxa_congestionamento is not None and taxa_congestionamento >= _CONG_CRITICO:
        gatilhos.append({
            "tipo": "PICO_CONGESTIONAMENTO",
            "severidade": "HIGH" if taxa_congestionamento >= 0.85 else "MEDIUM",
            "taxa_congestionamento": round(taxa_congestionamento, 4),
        })

    return {
        "n_gatilhos": len(gatilhos),
        "tem_alerta": len(gatilhos) > 0,
        "gatilhos": gatilhos,
        "disclaimer": "heurística de detecção de surto — não validada",
    }
