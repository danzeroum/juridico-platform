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
from services.shared.contracts.defensor import (
    Canal,
    DefensorRequest,
    DefensorResponse,
    EventoAgente,
)
from services.shared.contracts.petibot import PetiRequest, TipoAcao

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
    eventos.append(EventoAgente(ts=_now_iso(), evento="defesa.redigindo", detalhe="rascunho v3"))
    eventos.append(EventoAgente(
        ts=_now_iso(), evento="defesa.pronta", detalhe=f"{len(peti.secoes)} seções",
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
        secoes=peti.secoes,
        precedentes_encontrados=peti.precedentes_encontrados,
        casos_anteriores=casos_anteriores,
        subsidios=subsidios,
        proximo_responsavel=proximo_responsavel,
        status=status,
        computed_at=_now_iso(),
    )
