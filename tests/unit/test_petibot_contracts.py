"""Testes dos contratos PetiBot."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.shared.contracts.petibot import (
    PETIBOT_CONTRACT_VERSION,
    SECOES_MINIMAS_POR_TIPO,
    PetiRequest,
    PetiResponse,
    PetiSection,
    TipoAcao,
)


@pytest.fixture
def req_valido():
    return {
        "descricao": "Reclamação trabalhista por horas extras não pagas ao longo de dois anos, conforme documentação juntada.",
        "tipo_acao": "TRABALHISTA",
        "polo_ativo": "João Silva",
        "polo_passivo": "Empresa XYZ Ltda",
        "valor_causa": 50_000.0,
    }


class TestPetiRequest:
    def test_valido(self, req_valido):
        r = PetiRequest(**req_valido)
        assert r.tipo_acao == TipoAcao.TRABALHISTA
        assert r.polo_ativo == "João Silva"

    def test_descricao_muito_curta(self, req_valido):
        req_valido["descricao"] = "Curta"
        with pytest.raises(ValidationError):
            PetiRequest(**req_valido)

    def test_tipo_acao_invalido(self, req_valido):
        req_valido["tipo_acao"] = "CRIMINAL"
        with pytest.raises(ValidationError):
            PetiRequest(**req_valido)

    def test_polo_ativo_muito_curto(self, req_valido):
        req_valido["polo_ativo"] = "AB"
        with pytest.raises(ValidationError):
            PetiRequest(**req_valido)

    def test_valor_negativo(self, req_valido):
        req_valido["valor_causa"] = -1.0
        with pytest.raises(ValidationError):
            PetiRequest(**req_valido)

    def test_cnpj_parte_invalido(self, req_valido):
        req_valido["cnpj_parte"] = "123"
        with pytest.raises(ValidationError):
            PetiRequest(**req_valido)

    def test_cnpj_parte_valido(self, req_valido):
        req_valido["cnpj_parte"] = "12345678000195"
        r = PetiRequest(**req_valido)
        assert r.cnpj_parte == "12345678000195"

    def test_campos_opcionais_none(self, req_valido):
        req_valido.pop("valor_causa")
        r = PetiRequest(**req_valido)
        assert r.valor_causa is None
        assert r.cnpj_parte is None

    def test_extra_proibido(self, req_valido):
        req_valido["campo_extra"] = "invalido"
        with pytest.raises(ValidationError):
            PetiRequest(**req_valido)

    def test_todos_os_tipos(self):
        base = "Descrição suficientemente longa para atender ao requisito mínimo da petição em questão."
        for t in TipoAcao:
            r = PetiRequest(descricao=base, tipo_acao=t, polo_ativo="Autor", polo_passivo="Réu")
            assert r.tipo_acao == t


class TestPetiSection:
    def test_valida(self):
        s = PetiSection(titulo="DOS FATOS", conteudo="Conteúdo da seção")
        assert s.precedentes == []

    def test_com_precedentes(self):
        s = PetiSection(titulo="DO DIREITO", conteudo="X", precedentes=["doc1", "doc2"])
        assert len(s.precedentes) == 2


class TestSecoesPorTipo:
    def test_trabalhista_tem_verbas_rescisorias(self):
        assert "DAS VERBAS RESCISÓRIAS" in SECOES_MINIMAS_POR_TIPO["TRABALHISTA"]

    def test_tributario_tem_direito_tributario(self):
        assert "DO DIREITO TRIBUTÁRIO" in SECOES_MINIMAS_POR_TIPO["TRIBUTARIO"]

    def test_todos_tem_pedidos(self):
        for tipo, secoes in SECOES_MINIMAS_POR_TIPO.items():
            assert "DOS PEDIDOS" in secoes, f"{tipo} não tem DOS PEDIDOS"

    def test_todos_tem_fatos(self):
        for tipo, secoes in SECOES_MINIMAS_POR_TIPO.items():
            assert "DOS FATOS" in secoes, f"{tipo} não tem DOS FATOS"


class TestPetiResponse:
    def test_valida(self):
        r = PetiResponse(
            tipo_acao="TRABALHISTA",
            polo_ativo="Autor",
            polo_passivo="Réu",
            secoes=[PetiSection(titulo="DOS PEDIDOS", conteudo="...")],
            precedentes_encontrados=0,
            computed_at="2026-06-16T00:00:00+00:00",
        )
        assert r.contract_version == PETIBOT_CONTRACT_VERSION

    def test_precedentes_negativos_invalidos(self):
        with pytest.raises(ValidationError):
            PetiResponse(
                tipo_acao="CIVEL",
                polo_ativo="A",
                polo_passivo="B",
                secoes=[],
                precedentes_encontrados=-1,
                computed_at="2026-06-16T00:00:00+00:00",
            )
