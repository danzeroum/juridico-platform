"""
Defensor — orquestrador do agente jurídico de IA.

Executa um pipeline determinístico de etapas e devolve uma timeline de eventos
(EventoAgente) + o resultado (defesa montada, precedentes, handoff).

Reaproveita:
  - services.petibot.assembler.assemble_petition  → seções da defesa + precedentes (RAG)
  - services.shared.contracts.petibot.TipoAcao     → mapeamento de tipo de caso

Fase atual (scaffold): consulta de histórico e subsídios são stubs determinísticos
(sem CRM real); jurisprudência usa RAG real (ChromaDB, degradação graciosa offline);
o protocolo é apenas preparado, não submetido aos portais.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from services.petibot.assembler import assemble_petition
from services.shared.ai.generate import generate_text
from services.shared.contracts.defensor import (
    Canal,
    DefensorRequest,
    DefensorResponse,
    EventoAgente,
)
from services.shared.contracts.petibot import PetiRequest, PetiSection, TipoAcao

_LLM_SYSTEM = (
    "Você é advogado(a) redigindo a defesa de uma empresa em reclamação de "
    "consumidor. Escreva de forma objetiva, técnica e fundamentada, em português."
)

logger = logging.getLogger(__name__)

# Limiar de valor a partir do qual o caso é encaminhado a um humano (handoff).
_LIMIAR_HANDOFF_HUMANO = 50_000.0

# Subsídios típicos solicitados ao CRM — stub determinístico por canal.
_SUBSIDIOS_BASE = ["contrato/termo de adesão", "histórico de cobranças", "protocolos de atendimento"]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _classificar(request: DefensorRequest) -> str:
    """Classificação determinística do caso a partir de tipo + canal."""
    return f"{request.tipo_caso.value} · {request.canal.value}"


def _consultar_historico(request: DefensorRequest) -> int:
    """Histórico do reclamante (stub determinístico; sem CRM real)."""
    # Deriva um número estável a partir do nome — placeholder até integração de CRM.
    return len(request.reclamante) % 5


def _definir_responsavel(request: DefensorRequest) -> tuple[str, str]:
    """Regra de handoff: contencioso ou valor alto vai para humano; senão, agente conclui."""
    alto_valor = request.valor is not None and request.valor >= _LIMIAR_HANDOFF_HUMANO
    if request.canal == Canal.CONTENCIOSO or alto_valor:
        return "humano", "AGUARDA_PROTOCOLO"
    return "agente", "DEFESA_PRONTA"


def _redigir_secoes(
    request: DefensorRequest, secoes: list[PetiSection]
) -> tuple[list[PetiSection], str]:
    """
    Tenta redigir cada seção via LLM; cai para o template do PetiBot quando o LLM
    está indisponível. Retorna (secoes, via) com via ∈ {"llm", "template"}.

    Curto-circuita após a primeira falha de LLM para não acumular timeouts.
    """
    redigidas: list[PetiSection] = []
    n_llm = 0
    llm_ok = True

    for sec in secoes:
        texto: str | None = None
        if llm_ok:
            prompt = (
                f'Redija a seção "{sec.titulo}" da defesa, no canal {request.canal.value}, '
                f"para um caso do tipo {request.tipo_caso.value}.\n"
                f"Reclamante: {request.reclamante}. Reclamada: {request.reclamada}.\n"
                f"Fatos relatados: {request.descricao}\n"
                "Escreva 1 a 2 parágrafos em linguagem jurídica, sem inventar fatos não informados."
            )
            texto = generate_text(prompt, system=_LLM_SYSTEM, max_tokens=400)
            if texto is None:
                llm_ok = False  # provedor indisponível — não tenta as demais seções

        if texto:
            n_llm += 1
            redigidas.append(PetiSection(titulo=sec.titulo, conteudo=texto, precedentes=sec.precedentes))
        else:
            redigidas.append(sec)

    # Proveniência honesta: só "llm" quando TODAS as seções foram redigidas por IA.
    if n_llm == 0:
        via = "template"
    elif n_llm == len(secoes):
        via = "llm"
    else:
        via = "parcial"
    return redigidas, via


def run_agente(request: DefensorRequest) -> DefensorResponse:
    """
    Roda o pipeline do agente e devolve timeline + resultado.

    Funciona offline (RAG degrada para precedentes_encontrados=0).
    """
    eventos: list[EventoAgente] = []

    # 1. Classificação do caso
    classificacao = _classificar(request)
    eventos.append(EventoAgente(ts=_now_iso(), evento="caso.classificado", detalhe=classificacao))

    # 2. Consulta de histórico do reclamante
    casos_anteriores = _consultar_historico(request)
    eventos.append(EventoAgente(
        ts=_now_iso(), evento="reclamante.consultado",
        detalhe=f"{casos_anteriores} casos anteriores",
    ))

    # 3. Subsídios (CRM) — solicitando → ok
    eventos.append(EventoAgente(ts=_now_iso(), evento="subsidios.solicitando", detalhe="crm · pedidos"))
    subsidios = list(_SUBSIDIOS_BASE)
    eventos.append(EventoAgente(
        ts=_now_iso(), evento="subsidios.ok", detalhe=f"{len(subsidios)} docs anexados",
    ))

    # 4–5. Jurisprudência + redação da defesa (reaproveita PetiBot: RAG + montagem de seções)
    peti_req = PetiRequest(
        descricao=request.descricao,
        tipo_acao=TipoAcao(request.tipo_caso.value),
        polo_ativo=request.reclamante,
        polo_passivo=request.reclamada,
        valor_causa=request.valor,
        cnpj_parte=request.cnpj_reclamada,
    )
    peti = assemble_petition(peti_req)

    eventos.append(EventoAgente(
        ts=_now_iso(), evento="jurisprudencia.match",
        detalhe=f"{peti.precedentes_encontrados} precedentes",
    ))

    secoes, defesa_via = _redigir_secoes(request, peti.secoes)
    _detalhe_redacao = {
        "llm": "rascunho via IA",
        "parcial": "rascunho parcial (IA + template)",
        "template": "rascunho (template)",
    }
    eventos.append(EventoAgente(
        ts=_now_iso(), evento="defesa.redigindo",
        detalhe=_detalhe_redacao[defesa_via],
        status="ok" if defesa_via != "template" else "running",
    ))
    eventos.append(EventoAgente(
        ts=_now_iso(), evento="defesa.pronta", detalhe=f"{len(secoes)} seções",
    ))

    # 6. Preparo de protocolo + handoff
    proximo_responsavel, status = _definir_responsavel(request)
    eventos.append(EventoAgente(
        ts=_now_iso(), evento="protocolo.preparado",
        detalhe=f"{request.canal.value} · responsável: {proximo_responsavel}",
        status="ok" if proximo_responsavel == "agente" else "pending",
    ))

    return DefensorResponse(
        classificacao=classificacao,
        canal=request.canal.value,
        eventos=eventos,
        secoes=secoes,
        precedentes_encontrados=peti.precedentes_encontrados,
        casos_anteriores=casos_anteriores,
        subsidios=subsidios,
        proximo_responsavel=proximo_responsavel,
        status=status,
        defesa_via=defesa_via,
        computed_at=_now_iso(),
    )
