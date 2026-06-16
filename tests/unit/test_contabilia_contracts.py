"""Testes dos data contracts CAGED e SICONFI."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.ingest.contracts.caged import (
    CagedEstabelecimentoBronze,
    CagedEstabelecimentoSilver,
)
from services.ingest.contracts.siconfi import (
    SiconfiContaBronze,
    SiconfiContaSilver,
    siconfi_bronze_to_silver,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def caged_bronze_valido():
    return {
        "competencia": "2024-03",
        "cnpj_estabelecimento": "12345678000195",
        "uf": "sp",
        "municipio": "São Paulo",
        "secao_cnae": "c",
        "saldo_admissoes_desligamentos": 5,
        "admissoes": 10,
        "desligamentos": 5,
        "salario_medio": 3500.0,
    }


@pytest.fixture
def siconfi_bronze_valido():
    return {
        "cod_ibge": "3550308",
        "uf": "sp",
        "municipio": "São Paulo",
        "exercicio": 2024,
        "conta": "3.1.90.01",
        "valor": 15_000_000.0,
        "descricao_conta": "PESSOAL E ENCARGOS SOCIAIS",
        "periodicidade": "QUADRIMESTRAL",
        "periodo": "Q1",
    }


# ---------------------------------------------------------------------------
# CAGED Bronze — validação
# ---------------------------------------------------------------------------

class TestCagedBronze:
    def test_valido(self, caged_bronze_valido):
        b = CagedEstabelecimentoBronze(**caged_bronze_valido)
        assert b.cnpj_estabelecimento == "12345678000195"
        assert b.uf == "SP"          # uppercase
        assert b.secao_cnae == "C"   # uppercase
        assert b.source == "CAGED"
        assert b.transform_version == "1.0.0"

    def test_competencia_invalida(self, caged_bronze_valido):
        caged_bronze_valido["competencia"] = "2024/03"
        with pytest.raises(ValidationError, match="YYYY-MM"):
            CagedEstabelecimentoBronze(**caged_bronze_valido)

    def test_competencia_com_dia_invalido(self, caged_bronze_valido):
        caged_bronze_valido["competencia"] = "2024-03-01"
        with pytest.raises(ValidationError):
            CagedEstabelecimentoBronze(**caged_bronze_valido)

    def test_cnpj_nao_numerico(self, caged_bronze_valido):
        caged_bronze_valido["cnpj_estabelecimento"] = "123456780001XX"
        with pytest.raises(ValidationError, match="dígitos"):
            CagedEstabelecimentoBronze(**caged_bronze_valido)

    def test_cnpj_tamanho_errado(self, caged_bronze_valido):
        caged_bronze_valido["cnpj_estabelecimento"] = "1234567800019"  # 13 dígitos
        with pytest.raises(ValidationError):
            CagedEstabelecimentoBronze(**caged_bronze_valido)

    def test_secao_cnae_invalida(self, caged_bronze_valido):
        caged_bronze_valido["secao_cnae"] = "Z"
        with pytest.raises(ValidationError, match="secao_cnae"):
            CagedEstabelecimentoBronze(**caged_bronze_valido)

    def test_campos_opcionais_none(self, caged_bronze_valido):
        caged_bronze_valido.pop("admissoes")
        caged_bronze_valido.pop("desligamentos")
        caged_bronze_valido.pop("salario_medio")
        b = CagedEstabelecimentoBronze(**caged_bronze_valido)
        assert b.admissoes is None
        assert b.desligamentos is None
        assert b.salario_medio is None

    def test_saldo_negativo_valido(self, caged_bronze_valido):
        caged_bronze_valido["saldo_admissoes_desligamentos"] = -20
        b = CagedEstabelecimentoBronze(**caged_bronze_valido)
        assert b.saldo_admissoes_desligamentos == -20

    def test_ingested_at_gerado(self, caged_bronze_valido):
        b = CagedEstabelecimentoBronze(**caged_bronze_valido)
        assert b.ingested_at  # não vazio
        assert "T" in b.ingested_at  # formato ISO


# ---------------------------------------------------------------------------
# CAGED Silver — campos derivados
# ---------------------------------------------------------------------------

class TestCagedSilver:
    def test_is_crescendo_positivo(self):
        s = CagedEstabelecimentoSilver(
            competencia="2024-03",
            cnpj_estabelecimento="12345678000195",
            uf="SP",
            municipio="São Paulo",
            secao_cnae="C",
            saldo_admissoes_desligamentos=5,
            admissoes=10,
            desligamentos=5,
            salario_medio_normalizado=3500.0,
            is_crescendo=True,
            ingested_at="2024-03-01T00:00:00+00:00",
        )
        assert s.is_crescendo is True

    def test_is_crescendo_negativo(self):
        s = CagedEstabelecimentoSilver(
            competencia="2024-03",
            cnpj_estabelecimento="12345678000195",
            uf="SP",
            municipio="São Paulo",
            secao_cnae="C",
            saldo_admissoes_desligamentos=-3,
            admissoes=2,
            desligamentos=5,
            salario_medio_normalizado=0.0,
            is_crescendo=False,
            ingested_at="2024-03-01T00:00:00+00:00",
        )
        assert s.is_crescendo is False


# ---------------------------------------------------------------------------
# SICONFI Bronze — validação
# ---------------------------------------------------------------------------

class TestSiconfiContaBronze:
    def test_valido(self, siconfi_bronze_valido):
        b = SiconfiContaBronze(**siconfi_bronze_valido)
        assert b.uf == "SP"  # uppercase
        assert b.cod_ibge == "3550308"
        assert b.source == "SICONFI"
        assert b.exercicio == 2024

    def test_cod_ibge_nao_numerico(self, siconfi_bronze_valido):
        siconfi_bronze_valido["cod_ibge"] = "355030A"
        with pytest.raises(ValidationError, match="dígitos"):
            SiconfiContaBronze(**siconfi_bronze_valido)

    def test_cod_ibge_tamanho_errado(self, siconfi_bronze_valido):
        siconfi_bronze_valido["cod_ibge"] = "355030"  # 6 dígitos
        with pytest.raises(ValidationError):
            SiconfiContaBronze(**siconfi_bronze_valido)

    def test_exercicio_fora_do_range(self, siconfi_bronze_valido):
        siconfi_bronze_valido["exercicio"] = 1999
        with pytest.raises(ValidationError):
            SiconfiContaBronze(**siconfi_bronze_valido)

    def test_conta_trimmed(self, siconfi_bronze_valido):
        siconfi_bronze_valido["conta"] = "  3.1.90.01  "
        b = SiconfiContaBronze(**siconfi_bronze_valido)
        assert b.conta == "3.1.90.01"

    def test_campos_opcionais_none(self, siconfi_bronze_valido):
        siconfi_bronze_valido.pop("descricao_conta")
        siconfi_bronze_valido.pop("periodicidade")
        siconfi_bronze_valido.pop("periodo")
        b = SiconfiContaBronze(**siconfi_bronze_valido)
        assert b.descricao_conta is None
        assert b.periodicidade is None

    def test_valor_negativo_valido(self, siconfi_bronze_valido):
        siconfi_bronze_valido["valor"] = -5_000_000.0
        b = SiconfiContaBronze(**siconfi_bronze_valido)
        assert b.valor == -5_000_000.0


# ---------------------------------------------------------------------------
# siconfi_bronze_to_silver
# ---------------------------------------------------------------------------

class TestSiconfiTransform:
    def test_transform_valido(self, siconfi_bronze_valido):
        bronze = SiconfiContaBronze(**siconfi_bronze_valido)
        silver = siconfi_bronze_to_silver(bronze)
        assert isinstance(silver, SiconfiContaSilver)
        assert silver.cod_ibge == "3550308"
        assert silver.valor_log > 0
        assert silver.is_despesa is True  # conta inicia com "3"

    def test_transform_is_despesa_receita(self, siconfi_bronze_valido):
        siconfi_bronze_valido["conta"] = "1.1.1.1"  # conta de ativo = não despesa
        bronze = SiconfiContaBronze(**siconfi_bronze_valido)
        silver = siconfi_bronze_to_silver(bronze)
        assert silver.is_despesa is False

    def test_transform_valor_log_correto(self, siconfi_bronze_valido):
        import math
        siconfi_bronze_valido["valor"] = 1000.0
        bronze = SiconfiContaBronze(**siconfi_bronze_valido)
        silver = siconfi_bronze_to_silver(bronze)
        assert abs(silver.valor_log - math.log1p(1000.0)) < 1e-4

    def test_transform_defaults_opcionais(self, siconfi_bronze_valido):
        siconfi_bronze_valido.pop("periodicidade")
        siconfi_bronze_valido.pop("periodo")
        siconfi_bronze_valido.pop("descricao_conta")
        bronze = SiconfiContaBronze(**siconfi_bronze_valido)
        silver = siconfi_bronze_to_silver(bronze)
        assert silver.periodicidade == "ANUAL"
        assert silver.periodo == "A"
        assert silver.descricao_conta == ""

    def test_transform_valor_negativo(self, siconfi_bronze_valido):
        import math
        siconfi_bronze_valido["valor"] = -5_000_000.0
        bronze = SiconfiContaBronze(**siconfi_bronze_valido)
        silver = siconfi_bronze_to_silver(bronze)
        assert silver.valor == -5_000_000.0
        assert silver.valor_log == pytest.approx(math.log1p(5_000_000.0), rel=1e-4)
