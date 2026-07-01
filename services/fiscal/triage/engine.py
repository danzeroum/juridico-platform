"""
Motor de triagem — orquestra NCM + ICMS. `classify()` é PURO: não toca o Decision
Ledger (a ancoragem é etapa separada; ver services/fiscal/batch/anchor.py e o plano
§3). Isso evita o anti-padrão O(N²) ao processar lotes de 40k itens.

As fontes de dados (NCM, ICMS interno, categoria) são injetadas via Protocol,
permitindo teste sem banco. As implementações reais vivem em repository.py.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol

from services.fiscal.triage.icms_resolver import resolve_icms
from services.fiscal.triage.ncm_matcher import (
    DEFAULT_FUZZY_THRESHOLD,
    match_exact,
    match_fuzzy,
)
from services.fiscal.triage.semantic import (
    SemanticNcmSource,
    hits_to_candidate,
)
from services.shared.contracts.fiscal import (
    NcmTriageRequest,
    NcmTriageResult,
)


class NcmSource(Protocol):
    def get_ncm(self, codigo: str, data: date | None) -> dict | None: ...
    def catalog(self, data: date | None) -> list[tuple[str, str]]: ...


class IcmsSource(Protocol):
    def interna(self, uf: str, ncm_codigo: str | None, data: date | None) -> dict | None: ...


class CategorySource(Protocol):
    def categoria(self, ncm_codigo: str | None) -> str | None: ...


def classify(
    request: NcmTriageRequest,
    ncm_source: NcmSource,
    icms_source: IcmsSource,
    category_source: CategorySource | None = None,
    semantic_source: SemanticNcmSource | None = None,
    *,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> NcmTriageResult:
    """
    Classifica um item: descrição → NCM → ICMS. Determinístico e puro.
    `decision_proof` fica None aqui — é preenchido na etapa de ancoragem.

    Sem `ncm_hint`, tenta fuzzy léxico; se a confiança for baixa e houver
    `semantic_source` (RAG/embeddings), usa a sugestão semântica como fallback.
    """
    observacoes: list[str] = []
    conflito = False

    # 1. NCM: prioriza hint (lookup exato); senão, fuzzy + fallback semântico.
    if request.ncm_hint:
        row = ncm_source.get_ncm(request.ncm_hint, request.data)
        candidate = match_exact(request.ncm_hint, row)
        if candidate is None:
            conflito = True
            observacoes.append(
                f"NCM {request.ncm_hint} informado não encontrado na base vigente — revisão manual."
            )
    else:
        candidate, fuzzy_conflito = match_fuzzy(
            request.descricao, ncm_source.catalog(request.data), threshold=fuzzy_threshold
        )
        conflito = fuzzy_conflito

        # Fallback semântico quando o fuzzy é fraco (léxico não cobre termo comercial).
        if semantic_source is not None and (candidate is None or fuzzy_conflito):
            sem_cand, sem_conflito = hits_to_candidate(semantic_source.suggest(request.descricao))
            if sem_cand is not None and (not sem_conflito or candidate is None):
                candidate = sem_cand
                conflito = sem_conflito
                observacoes.append(
                    f"NCM sugerido por busca semântica (RAG), confiança {sem_cand.confidence:.2f}."
                    + ("" if not sem_conflito else " Baixa confiança — revisar.")
                )

        if candidate is None:
            observacoes.append("Não foi possível sugerir NCM a partir da descrição — revisão manual.")
        elif conflito and candidate.fonte_regra.value == "FUZZY":
            observacoes.append(
                f"NCM sugerido por similaridade com baixa confiança ({candidate.confidence:.2f}) — revisar."
            )

    ncm_codigo = candidate.ncm_codigo if candidate else None

    # 2. ICMS interno vigente no destino + resolução (interestadual/DIFAL).
    interna_row = icms_source.interna(request.uf_destino, ncm_codigo, request.data)
    if interna_row is None:
        observacoes.append(
            f"Sem alíquota interna vigente de ICMS para {request.uf_destino} — verificar SEFAZ."
        )
    icms = resolve_icms(
        request.uf_origem,
        request.uf_destino,
        interna_row,
        importado=request.importado,
        conteudo_importacao_pct=request.conteudo_importacao_pct,
    )

    # 3. Categoria contábil (opcional).
    categoria = category_source.categoria(ncm_codigo) if category_source else None

    return NcmTriageResult(
        sku_descricao=request.descricao,
        suggested_ncm=candidate,
        icms=icms,
        categoria=categoria,
        conflito_detectado=conflito,
        observacoes=observacoes,
    )
