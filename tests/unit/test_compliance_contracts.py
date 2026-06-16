"""Testes dos data contracts SNIS e IBGE."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.ingest.contracts.ibge import (
    IbgeMunicipioBronze,
    IbgeMunicipioSilver,
    ibge_bronze_to_silver,
)
from services.ingest.contracts.snis import (
    SnisMunicipioBronze,
    SnisMunicipioSilver,
    snis_bronze_to_silver,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def snis_bronze_valido():
    return {
        "cod_ibge": "3550308",
        "municipio": "São Paulo",
        "uf": "sp",
        "exercicio": 2022,
        "populacao_total": 12_396_372,
        "populacao_atendida_agua": 11_900_000,
        "populacao_atendida_esgoto": 10_500_000,
        "source_date": "2024-03-15",
    }


@pytest.fixture
def ibge_bronze_valido():
    return {
        "cod_ibge": "3550308",
        "municipio": "São Paulo",
        "uf": "sp",
        "ano": 2021,
        "populacao": 12_396_372,
        "pib_per_capita": 45_000.0,
        "idhm": 0.805,
        "taxa_desemprego": 14.5,
        "area_km2": 1521.1,
        "source_date": "2023-06-01",
    }


# ---------------------------------------------------------------------------
# SNIS Bronze — validação
# ---------------------------------------------------------------------------

class TestSnisBronze:
    def test_valido(self, snis_bronze_valido):
        b = SnisMunicipioBronze(**snis_bronze_valido)
        assert b.uf == "SP"
        assert b.cod_ibge == "3550308"
        assert b.source == "SNIS"
        assert b.transform_version == "1.0.0"

    def test_cod_ibge_nao_numerico(self, snis_bronze_valido):
        snis_bronze_valido["cod_ibge"] = "355030A"
        with pytest.raises(ValidationError, match="dígitos"):
            SnisMunicipioBronze(**snis_bronze_valido)

    def test_cod_ibge_tamanho_errado(self, snis_bronze_valido):
        snis_bronze_valido["cod_ibge"] = "355030"
        with pytest.raises(ValidationError):
            SnisMunicipioBronze(**snis_bronze_valido)

    def test_exercicio_fora_do_range(self, snis_bronze_valido):
        snis_bronze_valido["exercicio"] = 1999
        with pytest.raises(ValidationError):
            SnisMunicipioBronze(**snis_bronze_valido)

    def test_populacao_negativa_invalida(self, snis_bronze_valido):
        snis_bronze_valido["populacao_total"] = -1
        with pytest.raises(ValidationError):
            SnisMunicipioBronze(**snis_bronze_valido)

    def test_campos_opcionais_none(self, snis_bronze_valido):
        snis_bronze_valido.pop("volume_agua_produzido", None)
        snis_bronze_valido.pop("volume_esgoto_coletado", None)
        snis_bronze_valido.pop("source_date", None)
        b = SnisMunicipioBronze(**snis_bronze_valido)
        assert b.source_date is None


# ---------------------------------------------------------------------------
# SNIS Bronze → Silver
# ---------------------------------------------------------------------------

class TestSnisTransform:
    def test_percentuais_calculados(self, snis_bronze_valido):
        bronze = SnisMunicipioBronze(**snis_bronze_valido)
        silver = snis_bronze_to_silver(bronze)
        assert isinstance(silver, SnisMunicipioSilver)
        pop = bronze.populacao_total
        assert silver.cobertura_agua_pct == pytest.approx(
            bronze.populacao_atendida_agua / pop * 100, abs=0.01
        )
        assert silver.cobertura_esgoto_pct == pytest.approx(
            bronze.populacao_atendida_esgoto / pop * 100, abs=0.01
        )

    def test_cobertura_cap_100(self, snis_bronze_valido):
        snis_bronze_valido["populacao_atendida_agua"] = 20_000_000  # > total
        bronze = SnisMunicipioBronze(**snis_bronze_valido)
        silver = snis_bronze_to_silver(bronze)
        assert silver.cobertura_agua_pct == 100.0

    def test_populacao_zero_sem_divisao(self, snis_bronze_valido):
        snis_bronze_valido["populacao_total"] = 0
        snis_bronze_valido["populacao_atendida_agua"] = 0
        snis_bronze_valido["populacao_atendida_esgoto"] = 0
        bronze = SnisMunicipioBronze(**snis_bronze_valido)
        silver = snis_bronze_to_silver(bronze)
        assert silver.cobertura_agua_pct == 0.0
        assert silver.cobertura_esgoto_pct == 0.0

    def test_lag_calculado(self, snis_bronze_valido):
        bronze = SnisMunicipioBronze(**snis_bronze_valido)
        silver = snis_bronze_to_silver(bronze)
        assert silver.lag_days >= 0  # 2024-03-15 é no passado

    def test_lag_negativo_sem_source_date(self, snis_bronze_valido):
        snis_bronze_valido.pop("source_date", None)
        bronze = SnisMunicipioBronze(**snis_bronze_valido)
        silver = snis_bronze_to_silver(bronze)
        assert silver.lag_days == -1


# ---------------------------------------------------------------------------
# IBGE Bronze — validação
# ---------------------------------------------------------------------------

class TestIbgeBronze:
    def test_valido(self, ibge_bronze_valido):
        b = IbgeMunicipioBronze(**ibge_bronze_valido)
        assert b.uf == "SP"
        assert b.idhm == 0.805
        assert b.source == "IBGE"

    def test_idhm_fora_do_range(self, ibge_bronze_valido):
        ibge_bronze_valido["idhm"] = 1.5
        with pytest.raises(ValidationError):
            IbgeMunicipioBronze(**ibge_bronze_valido)

    def test_taxa_desemprego_negativa(self, ibge_bronze_valido):
        ibge_bronze_valido["taxa_desemprego"] = -1.0
        with pytest.raises(ValidationError):
            IbgeMunicipioBronze(**ibge_bronze_valido)

    def test_populacao_negativa(self, ibge_bronze_valido):
        ibge_bronze_valido["populacao"] = -1
        with pytest.raises(ValidationError):
            IbgeMunicipioBronze(**ibge_bronze_valido)

    def test_campos_opcionais_none(self, ibge_bronze_valido):
        ibge_bronze_valido.pop("pib_per_capita")
        ibge_bronze_valido.pop("idhm")
        ibge_bronze_valido.pop("taxa_desemprego")
        b = IbgeMunicipioBronze(**ibge_bronze_valido)
        assert b.pib_per_capita is None
        assert b.idhm is None


# ---------------------------------------------------------------------------
# IBGE Bronze → Silver
# ---------------------------------------------------------------------------

class TestIbgeTransform:
    def test_transform_valido(self, ibge_bronze_valido):
        bronze = IbgeMunicipioBronze(**ibge_bronze_valido)
        silver = ibge_bronze_to_silver(bronze)
        assert isinstance(silver, IbgeMunicipioSilver)
        assert silver.populacao == bronze.populacao
        assert silver.idhm == 0.805

    def test_densidade_calculada(self, ibge_bronze_valido):
        bronze = IbgeMunicipioBronze(**ibge_bronze_valido)
        silver = ibge_bronze_to_silver(bronze)
        expected = bronze.populacao / bronze.area_km2
        assert silver.densidade_demografica == pytest.approx(expected, rel=1e-3)

    def test_densidade_zero_sem_area(self, ibge_bronze_valido):
        ibge_bronze_valido.pop("area_km2")
        bronze = IbgeMunicipioBronze(**ibge_bronze_valido)
        silver = ibge_bronze_to_silver(bronze)
        assert silver.densidade_demografica == 0.0

    def test_defaults_campos_opcionais(self, ibge_bronze_valido):
        ibge_bronze_valido.pop("pib_per_capita")
        ibge_bronze_valido.pop("idhm")
        ibge_bronze_valido.pop("taxa_desemprego")
        bronze = IbgeMunicipioBronze(**ibge_bronze_valido)
        silver = ibge_bronze_to_silver(bronze)
        assert silver.pib_per_capita == 0.0
        assert silver.idhm == 0.0
        assert silver.taxa_desemprego == 0.0

    def test_lag_calculado(self, ibge_bronze_valido):
        bronze = IbgeMunicipioBronze(**ibge_bronze_valido)
        silver = ibge_bronze_to_silver(bronze)
        assert silver.lag_days >= 0

    def test_lag_negativo_sem_source_date(self, ibge_bronze_valido):
        ibge_bronze_valido.pop("source_date")
        bronze = IbgeMunicipioBronze(**ibge_bronze_valido)
        silver = ibge_bronze_to_silver(bronze)
        assert silver.lag_days == -1


# ---------------------------------------------------------------------------
# Branches de erro/fallback não cobertos anteriormente
# ---------------------------------------------------------------------------

class TestIbgeBranchesFaltantes:
    def test_cod_ibge_nao_numerico_rejeitado(self, ibge_bronze_valido):
        ibge_bronze_valido["cod_ibge"] = "ABCDEFG"  # 7 chars, non-digit → validator raises
        with pytest.raises(ValidationError, match="dígitos"):
            IbgeMunicipioBronze(**ibge_bronze_valido)

    def test_source_date_formato_invalido_nao_crasha(self, ibge_bronze_valido):
        """source_date mal-formatado cai no except ValueError → lag_days = -1."""
        ibge_bronze_valido["source_date"] = "15/03/2024"  # formato DD/MM/YYYY
        bronze = IbgeMunicipioBronze(**ibge_bronze_valido)
        silver = ibge_bronze_to_silver(bronze)
        assert silver.lag_days == -1


class TestSnisBranchesFaltantes:
    def test_source_date_formato_invalido_nao_crasha(self, snis_bronze_valido):
        """source_date mal-formatado cai no except ValueError → lag_days = -1."""
        snis_bronze_valido["source_date"] = "01/06/2023"  # formato DD/MM/YYYY
        bronze = SnisMunicipioBronze(**snis_bronze_valido)
        silver = snis_bronze_to_silver(bronze)
        assert silver.lag_days == -1
