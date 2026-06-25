"""Testes do orquestrador Defensor."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.defensor.orchestrator import run_agente
from services.shared.contracts.defensor import (
    DEFENSOR_CONTRACT_VERSION,
    Canal,
    DefensorRequest,
    TipoCaso,
)

_DESCRICAO = (
    "Cobrança indevida recorrente em fatura de telefonia, sem contratação do serviço, "
    "com tentativas frustradas de cancelamento via SAC ao longo de três meses."
)


def _req(**over):
    base = dict(
        descricao=_DESCRICAO,
        canal="PROCON",
        tipo_caso="CONSUMERISTA",
        reclamante="Maria Souza",
        reclamada="Operadora XYZ S.A.",
    )
    base.update(over)
    return DefensorRequest(**base)


class TestDefensorRequest:
    def test_descricao_curta_invalida(self):
        with pytest.raises(ValidationError):
            _req(descricao="curta")

    def test_canal_invalido(self):
        with pytest.raises(ValidationError):
            _req(canal="STJ")

    def test_extra_proibido(self):
        with pytest.raises(ValidationError):
            DefensorRequest(
                descricao=_DESCRICAO, canal="PROCON", tipo_caso="CONSUMERISTA",
                reclamante="A. Silva", reclamada="Empresa", campo_extra="x",
            )


class TestRunAgente:
    def test_timeline_cobre_etapas_na_ordem(self):
        resp = run_agente(_req())
        eventos = [e.evento for e in resp.eventos]
        esperado = [
            "caso.classificado",
            "reclamante.consultado",
            "subsidios.solicitando",
            "subsidios.ok",
            "jurisprudencia.match",
            "defesa.redigindo",
            "defesa.pronta",
            "protocolo.preparado",
        ]
        assert eventos == esperado

    def test_secoes_nao_vazio(self):
        resp = run_agente(_req())
        assert len(resp.secoes) > 0

    def test_contract_version(self):
        assert run_agente(_req()).contract_version == DEFENSOR_CONTRACT_VERSION

    def test_rag_offline_degrada(self):
        # Sem ChromaDB, precedentes_encontrados=0 (degradação graciosa).
        assert run_agente(_req()).precedentes_encontrados >= 0

    def test_handoff_humano_em_contencioso(self):
        resp = run_agente(_req(canal="CONTENCIOSO", tipo_caso="CIVEL"))
        assert resp.proximo_responsavel == "humano"
        assert resp.status == "AGUARDA_PROTOCOLO"

    def test_handoff_humano_em_valor_alto(self):
        resp = run_agente(_req(valor=120_000.0))
        assert resp.proximo_responsavel == "humano"

    def test_agente_conclui_caso_simples(self):
        resp = run_agente(_req(valor=800.0))
        assert resp.proximo_responsavel == "agente"
        assert resp.status == "DEFESA_PRONTA"

    def test_classificacao_reflete_tipo_e_canal(self):
        resp = run_agente(_req(canal="OUVIDORIA", tipo_caso="CONSUMERISTA"))
        assert resp.classificacao == "CONSUMERISTA · OUVIDORIA"
        assert resp.canal == "OUVIDORIA"

    def test_todos_os_canais(self):
        for c in Canal:
            tipo = TipoCaso.CIVEL if c == Canal.CONTENCIOSO else TipoCaso.CONSUMERISTA
            resp = run_agente(_req(canal=c.value, tipo_caso=tipo.value))
            assert resp.canal == c.value
