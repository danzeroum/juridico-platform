"""
PetiBot — montagem de petição jurídica.

Fase 4: retorna estrutura com seções template + precedentes via RAG.
Sem LLM: conteúdo das seções é template que o advogado preenche.
RAG: ChromaDB + BGE-M3 (degradação graciosa se offline).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from services.shared.contracts.petibot import (
    SECOES_MINIMAS_POR_TIPO,
    PetiRequest,
    PetiResponse,
    PetiSection,
)

logger = logging.getLogger(__name__)

_SECTION_TEMPLATES: dict[str, str] = {
    "DOS FATOS":
        "Expõe-se os fatos que embasam a presente ação, conforme narrado abaixo.",
    "DO DIREITO":
        "Com fundamento nas normas legais e constitucionais aplicáveis ao caso.",
    "DO DIREITO TRIBUTÁRIO":
        "Fundamenta-se na legislação tributária, CTN e jurisprudência aplicável.",
    "DA ILEGALIDADE":
        "Demonstra-se a ilegalidade/inconstitucionalidade do ato ou norma impugnada.",
    "DAS VERBAS RESCISÓRIAS":
        "Discriminam-se as verbas rescisórias devidas nos termos da CLT.",
    "DOS DANOS":
        "Demonstram-se os danos materiais e/ou morais suportados pelo autor.",
    "DO DIREITO PREVIDENCIÁRIO":
        "Fundamenta-se na legislação previdenciária e normas do INSS aplicáveis.",
    "DO BENEFÍCIO":
        "Demonstra-se o cumprimento dos requisitos legais para concessão do benefício.",
    "DO DIREITO ADMINISTRATIVO":
        "Fundamenta-se na Lei de Licitações, Lei de Processo Administrativo e correlatas.",
    "DO CABIMENTO":
        "Demonstra-se o cabimento da via eleita e a legitimidade ativa e passiva.",
    "DO DIREITO DO CONSUMIDOR":
        "Fundamenta-se no Código de Defesa do Consumidor e jurisprudência consumerista.",
    "DOS PEDIDOS":
        "Diante do exposto, requer-se a procedência da presente ação.",
}

_DEFAULT_SECTIONS = ["DOS FATOS", "DO DIREITO", "DOS PEDIDOS"]


def _lookup_precedentes(descricao: str, tipo_acao: str) -> tuple[list[str], int]:
    """RAG lookup de precedentes. Retorna (doc_ids, n_total). Degradação graciosa."""
    try:
        from services.shared.ai.rag import RAGEngine
        rag = RAGEngine(collection_name="petibot_jurisprudencia")
        results = rag.search(query=descricao, n_results=5)
        doc_ids = [str(r["id"]) for r in results]
        return doc_ids, len(doc_ids)
    except Exception as exc:
        logger.debug("RAG lookup indisponível para PetiBot: %s", exc)
        return [], 0


def assemble_petition(request: PetiRequest) -> PetiResponse:
    """
    Monta estrutura de petição com seções padrão e precedentes via RAG.
    Funciona sem ChromaDB (precedentes_encontrados=0 como degradação).
    """
    tipo = request.tipo_acao.value
    titulos = SECOES_MINIMAS_POR_TIPO.get(tipo, _DEFAULT_SECTIONS)
    precedente_ids, n_precedentes = _lookup_precedentes(request.descricao, tipo)

    secoes: list[PetiSection] = []
    for i, titulo in enumerate(titulos):
        template = _SECTION_TEMPLATES.get(titulo, f"[Fundamentar: {titulo}]")
        prec = [precedente_ids[i]] if i < len(precedente_ids) else []
        secoes.append(PetiSection(titulo=titulo, conteudo=template, precedentes=prec))

    return PetiResponse(
        tipo_acao=tipo,
        polo_ativo=request.polo_ativo,
        polo_passivo=request.polo_passivo,
        secoes=secoes,
        precedentes_encontrados=n_precedentes,
        computed_at=datetime.now(UTC).isoformat(),
    )
