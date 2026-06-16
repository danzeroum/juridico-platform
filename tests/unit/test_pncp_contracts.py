"""Testes do data contract PNCP."""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from services.ingest.contracts.pncp import (
    Modalidade,
    PncpContratoBronze,
    PncpContratoSilver,
    pncp_bronze_to_silver,
)


@pytest.fixture
def bronze_valido():
    return {
        "numero_controle": "PNCP-2023-001",
        "cnpj_orgao": "12345678000195",
        "cnpj_fornecedor": "98765432000110",
        "objeto": "Aquisição de materiais de escritório",
        "modalidade": "PREGAO_ELETRONICO",
        "valor_contrato": 50_000.0,
        "data_publicacao": "2023-03-01",
        "data_abertura": "2023-03-15",
        "num_propostas": 5,
    }


class TestPncpBronze:
    def test_valido(self, bronze_valido):
        b = PncpContratoBronze(**bronze_valido)
        assert b.modalidade == Modalidade.PREGAO_ELETRONICO
        assert b.source == "PNCP"

    def test_cnpj_orgao_invalido(self, bronze_valido):
        bronze_valido["cnpj_orgao"] = "1234567800"
        with pytest.raises(ValidationError):
            PncpContratoBronze(**bronze_valido)

    def test_cnpj_fornecedor_nao_numerico(self, bronze_valido):
        bronze_valido["cnpj_fornecedor"] = "9876543A000110"
        with pytest.raises(ValidationError):
            PncpContratoBronze(**bronze_valido)

    def test_valor_negativo_invalido(self, bronze_valido):
        bronze_valido["valor_contrato"] = -1.0
        with pytest.raises(ValidationError):
            PncpContratoBronze(**bronze_valido)

    def test_campos_opcionais_none(self, bronze_valido):
        bronze_valido.pop("cnpj_fornecedor")
        bronze_valido.pop("data_abertura")
        bronze_valido.pop("num_propostas")
        b = PncpContratoBronze(**bronze_valido)
        assert b.cnpj_fornecedor is None
        assert b.data_abertura is None

    def test_modalidade_dispensa(self, bronze_valido):
        bronze_valido["modalidade"] = "DISPENSA"
        b = PncpContratoBronze(**bronze_valido)
        assert b.modalidade == Modalidade.DISPENSA

    def test_modalidade_invalida(self, bronze_valido):
        bronze_valido["modalidade"] = "MODALIDADE_INEXISTENTE"
        with pytest.raises(ValidationError):
            PncpContratoBronze(**bronze_valido)


class TestPncpTransform:
    def test_valor_log_calculado(self, bronze_valido):
        b = PncpContratoBronze(**bronze_valido)
        s = pncp_bronze_to_silver(b)
        assert isinstance(s, PncpContratoSilver)
        assert s.valor_log == pytest.approx(math.log10(50_000.0 + 1), abs=1e-4)

    def test_prazo_abertura_calculado(self, bronze_valido):
        b = PncpContratoBronze(**bronze_valido)
        s = pncp_bronze_to_silver(b)
        assert s.prazo_abertura_dias == 14  # 2023-03-01 → 2023-03-15

    def test_prazo_none_sem_data_abertura(self, bronze_valido):
        bronze_valido.pop("data_abertura")
        b = PncpContratoBronze(**bronze_valido)
        s = pncp_bronze_to_silver(b)
        assert s.prazo_abertura_dias is None

    def test_is_dispensa_true(self, bronze_valido):
        bronze_valido["modalidade"] = "DISPENSA"
        b = PncpContratoBronze(**bronze_valido)
        s = pncp_bronze_to_silver(b)
        assert s.is_dispensa is True

    def test_is_dispensa_false_pregao(self, bronze_valido):
        b = PncpContratoBronze(**bronze_valido)
        s = pncp_bronze_to_silver(b)
        assert s.is_dispensa is False

    def test_inexigibilidade_eh_dispensa(self, bronze_valido):
        bronze_valido["modalidade"] = "INEXIGIBILIDADE"
        b = PncpContratoBronze(**bronze_valido)
        s = pncp_bronze_to_silver(b)
        assert s.is_dispensa is True

    def test_unico_proponente(self, bronze_valido):
        bronze_valido["num_propostas"] = 1
        b = PncpContratoBronze(**bronze_valido)
        s = pncp_bronze_to_silver(b)
        assert s.is_unico_proponente is True

    def test_multiplos_proponentes(self, bronze_valido):
        b = PncpContratoBronze(**bronze_valido)
        s = pncp_bronze_to_silver(b)
        assert s.is_unico_proponente is False

    def test_sem_propostas_nao_eh_unico(self, bronze_valido):
        bronze_valido["num_propostas"] = None
        b = PncpContratoBronze(**bronze_valido)
        s = pncp_bronze_to_silver(b)
        assert s.is_unico_proponente is False
