"""
Classificação semântica de NCM (fallback para descrições "sujas" sem NCM).

Motivação (plano §5): o fuzzy léxico falha quando o termo comercial não se
sobrepõe à descrição oficial legalista ("refrigerante" × "águas gaseificadas com
adição de açúcar"). A ponte correta é EMBEDDING semântico — RAG com BGE-M3
(Ollama) + ChromaDB, que a plataforma já provê em services/shared/ai/rag.py.

Aqui: uma fonte semântica plugável (SemanticNcmSource) e o mapeamento puro de hits
→ candidato (testável de verdade). O RagNcmSource executa o embedding real e é
validado em E2E (depende de Ollama/ChromaDB — não roda em unit).
"""
from __future__ import annotations

from typing import Any, Protocol

from services.shared.contracts.fiscal import FonteRegra, NcmCandidate

# Limiar default de confiança semântica para auto-aprovação (0..1).
DEFAULT_SEMANTIC_THRESHOLD = 0.78


class SemanticNcmSource(Protocol):
    def suggest(self, descricao: str, k: int = 5) -> list[tuple[str, str, float]]:
        """Retorna [(ncm_codigo, descricao_oficial, score 0..1)] por relevância."""
        ...


def hits_to_candidate(
    hits: list[tuple[str, str, float]],
    *,
    threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
) -> tuple[NcmCandidate | None, bool]:
    """
    Converte hits semânticos no melhor candidato. Retorna (candidato, conflito).
    conflito=True quando o melhor score < threshold (exige revisão humana).
    """
    if not hits:
        return None, True
    codigo, descricao, score = max(hits, key=lambda h: h[2])
    codigo = "".join(ch for ch in codigo if ch.isdigit()).zfill(8)
    confidence = round(max(0.0, min(1.0, score)), 3)
    candidate = NcmCandidate(
        ncm_codigo=codigo,
        descricao=descricao,
        confidence=confidence,
        fonte_regra=FonteRegra.RAG,
    )
    return candidate, confidence < threshold


class RagNcmSource:
    """
    Fonte semântica sobre o RAGEngine (ChromaDB + BGE-M3 via Ollama).

    index_ncm() indexa as descrições oficiais; suggest() faz a busca semântica.
    Requer ChromaDB + Ollama no ar → coberto por E2E, não por unit.
    """

    def __init__(self, collection: str = "fiscal_ncm"):
        from services.shared.ai.rag import RAGEngine

        self._rag = RAGEngine(collection_name=collection)

    def index_ncm(self, catalogo: list[tuple[str, str]]) -> int:  # pragma: no cover - requer ChromaDB/Ollama
        n = 0
        for codigo, descricao in catalogo:
            if self._rag.upsert_document(f"ncm:{codigo}", descricao, {"ncm": codigo}):
                n += 1
        return n

    def suggest(self, descricao: str, k: int = 5) -> list[tuple[str, str, float]]:  # pragma: no cover - requer ChromaDB/Ollama
        results: list[dict[str, Any]] = self._rag.search(descricao, n_results=k)
        out: list[tuple[str, str, float]] = []
        for r in results:
            codigo = (r.get("metadata") or {}).get("ncm") or r.get("id", "").replace("ncm:", "")
            dist = r.get("distance")
            # distância de cosseno (0=idêntico) → score de similaridade.
            score = 1.0 - float(dist) if dist is not None else 0.5
            out.append((str(codigo), r.get("document", ""), score))
        return out
