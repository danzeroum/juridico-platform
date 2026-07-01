"""Testes do data contract ABJ (services/ingest/contracts/abj.py)."""
import pytest
from pydantic import ValidationError

from services.ingest.contracts.abj import AbjIndicadorBronze, abj_bronze_to_silver


def test_bronze_valido_normaliza_tribunal():
    b = AbjIndicadorBronze(tribunal="tjsp", periodo="2024")
    assert b.tribunal == "TJSP"
    assert b.source == "ABJ"


def test_bronze_rejeita_taxa_fora_de_intervalo():
    with pytest.raises(ValidationError):
        AbjIndicadorBronze(tribunal="TJSP", periodo="2024", taxa_congestionamento=1.5)


def test_silver_deriva_congestionamento_da_formula_justica_em_numeros():
    # taxa ausente → derivada: pendentes / (baixados + pendentes)
    b = AbjIndicadorBronze(
        tribunal="TJSP", periodo="2024", casos_baixados=300, casos_pendentes=700
    )
    s = abj_bronze_to_silver(b)
    assert s.taxa_congestionamento == pytest.approx(0.7, abs=1e-4)


def test_silver_preserva_taxa_fornecida():
    b = AbjIndicadorBronze(tribunal="TJSP", periodo="2024", taxa_congestionamento=0.42)
    s = abj_bronze_to_silver(b)
    assert s.taxa_congestionamento == 0.42


def test_silver_congestionamento_none_sem_contadores():
    b = AbjIndicadorBronze(tribunal="TJSP", periodo="2024")
    s = abj_bronze_to_silver(b)
    assert s.taxa_congestionamento is None
