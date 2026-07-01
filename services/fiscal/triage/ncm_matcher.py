"""
Correspondência de NCM — determinística.

Caminho de maior valor: `ncm_hint` presente na planilha do cliente → lookup exato
(confidence 1.0). Sem hint → correspondência aproximada (rapidfuzz) da descrição
normalizada contra a descrição OFICIAL da NCM. Como as strings quase não se
sobrepõem lexicalmente (descrição comercial × linguagem legalista), a precisão do
fuzzy deve ser MEDIDA e o limiar CALIBRADO (minimizar erro tipo II) antes de
confiar em produção — ver plano §5. Abaixo do limiar → marca conflito p/ revisão.

Funções puras: recebem os dados (linha exata, catálogo) por injeção. Sem I/O aqui —
o acesso ao banco vive em services/fiscal/repository.py.
"""
from __future__ import annotations

from services.shared.contracts.fiscal import (
    FonteRegra,
    NcmCandidate,
    normalize_descricao,
)

# Limiar default de confiança para auto-aprovação do fuzzy (0..1). Calibrável por
# amostragem estratificada por capítulo NCM contra gold standard (ver plano §5).
DEFAULT_FUZZY_THRESHOLD = 0.82


def match_exact(ncm_hint: str | None, ncm_row: dict | None) -> NcmCandidate | None:
    """
    Lookup exato por código. `ncm_row` é a linha vigente de fiscal.ncm
    (dict com 'ncm_codigo' e 'descricao') ou None se o código não existir/estiver
    fora de vigência. Retorna candidato com confidence 1.0 ou None.
    """
    if not ncm_hint or ncm_row is None:
        return None
    return NcmCandidate(
        ncm_codigo=ncm_row["ncm_codigo"].strip(),
        descricao=ncm_row["descricao"],
        confidence=1.0,
        fonte_regra=FonteRegra.TIPI,
    )


def match_fuzzy(
    descricao: str,
    catalogo: list[tuple[str, str]],
    *,
    threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> tuple[NcmCandidate | None, bool]:
    """
    Correspondência aproximada da descrição contra `catalogo` = lista de
    (ncm_codigo, descricao_oficial). Retorna (candidato, conflito).

    - candidato None + conflito True: nada encontrado ou catálogo vazio.
    - candidato preenchido + conflito (score < threshold): sugerido, mas exige revisão.
    """
    alvo = normalize_descricao(descricao)
    if not alvo or not catalogo:
        return None, True

    try:
        from rapidfuzz import fuzz, process
    except ImportError:  # pragma: no cover - dependência instalada em produção
        return None, True

    # Índice de escolhas normalizadas → preserva mapeamento para o código.
    escolhas = {i: normalize_descricao(desc) for i, (_cod, desc) in enumerate(catalogo)}
    melhor = process.extractOne(alvo, escolhas, scorer=fuzz.token_sort_ratio)
    if melhor is None:
        return None, True

    _texto, score, idx = melhor
    codigo, desc_oficial = catalogo[idx]
    confidence = round(score / 100.0, 3)
    candidato = NcmCandidate(
        ncm_codigo=codigo.strip(),
        descricao=desc_oficial,
        confidence=confidence,
        fonte_regra=FonteRegra.FUZZY,
    )
    conflito = confidence < threshold
    return candidato, conflito
