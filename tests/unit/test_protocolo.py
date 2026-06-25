"""Testes da automação de protocolo (simulação, fábrica, gating, serviço)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.defensor.protocolo.factory import get_driver
from services.defensor.protocolo.real import ConsumidorGovDriver, ProconSPDriver
from services.defensor.protocolo.simulacao import SimulacaoDriver
from services.shared.contracts.defensor import Canal
from services.shared.contracts.protocolo import ProtocoloRequest


def _req(**over):
    base = dict(
        canal="PROCON",
        reclamante="Maria Souza",
        reclamada="Operadora XYZ S.A.",
        resumo="Cobrança indevida recorrente em fatura, sem contratação do serviço.",
    )
    base.update(over)
    return ProtocoloRequest(**base)


class TestContract:
    def test_resumo_curto_invalido(self):
        with pytest.raises(ValidationError):
            _req(resumo="curto")

    def test_canal_invalido(self):
        with pytest.raises(ValidationError):
            _req(canal="STJ")


class TestSimulacao:
    def test_status_simulado(self):
        res = SimulacaoDriver().submit(_req())
        assert res.status == "SIMULADO"
        assert res.modo == "simulacao"
        assert res.numero_protocolo and res.numero_protocolo.startswith("SIM-PROCON-")

    def test_numero_deterministico(self):
        a = SimulacaoDriver().submit(_req())
        b = SimulacaoDriver().submit(_req())
        assert a.numero_protocolo == b.numero_protocolo


class TestFactory:
    def test_modo_simulacao_sempre_simula(self):
        assert isinstance(get_driver(Canal.CONSUMIDOR_GOV, "simulacao"), SimulacaoDriver)

    def test_modo_real_mapeia_driver_do_canal(self):
        assert isinstance(get_driver(Canal.CONSUMIDOR_GOV, "real"), ConsumidorGovDriver)
        assert isinstance(get_driver(Canal.PROCON, "real"), ProconSPDriver)

    def test_modo_real_canal_sem_driver_simula(self):
        assert isinstance(get_driver(Canal.OUVIDORIA, "real"), SimulacaoDriver)


class TestGatingReal:
    def test_sem_credenciais_aguarda_sem_tocar_rede(self, monkeypatch):
        # Sem credenciais → AGUARDA_CREDENCIAIS; nenhuma chamada de rede/playwright.
        monkeypatch.delenv("CONSUMIDOR_GOV_USER", raising=False)
        monkeypatch.delenv("CONSUMIDOR_GOV_PASSWORD", raising=False)
        res = ConsumidorGovDriver().submit(_req(canal="CONSUMIDOR_GOV"))
        assert res.status == "AGUARDA_CREDENCIAIS"
        assert res.modo == "real"
        assert res.numero_protocolo is None

    def test_com_credenciais_falha_controlada_nao_propaga(self, monkeypatch):
        # Com credenciais mas portal inacessível/scaffold → FALHA controlada (sem exceção).
        monkeypatch.setenv("CONSUMIDOR_GOV_USER", "user")
        monkeypatch.setenv("CONSUMIDOR_GOV_PASSWORD", "pwd")
        res = ConsumidorGovDriver().submit(_req(canal="CONSUMIDOR_GOV"))
        assert res.status == "FALHA"


class TestServico:
    def test_protocolar_padrao_simula(self, monkeypatch):
        monkeypatch.delenv("PROTOCOLO_MODO", raising=False)
        from services.defensor.protocolar import protocolar
        res = protocolar(_req())
        assert res.status == "SIMULADO"

    def test_protocolar_modo_real_sem_credenciais_aguarda(self, monkeypatch):
        monkeypatch.setenv("PROTOCOLO_MODO", "real")
        monkeypatch.delenv("CONSUMIDOR_GOV_USER", raising=False)
        monkeypatch.delenv("CONSUMIDOR_GOV_PASSWORD", raising=False)
        from services.defensor.protocolar import protocolar
        res = protocolar(_req(canal="CONSUMIDOR_GOV"))
        assert res.status == "AGUARDA_CREDENCIAIS"
