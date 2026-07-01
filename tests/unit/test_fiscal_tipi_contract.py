"""Testes do contrato TipiBronze (ingestão RFB)."""
from __future__ import annotations

import pytest

from services.ingest.contracts.tipi import TipiBronze


class TestTipiBronze:
    def test_normaliza_ncm_com_pontos(self):
        b = TipiBronze(ncm_codigo="8471.30.12", descricao="Notebook")
        assert b.ncm_codigo == "84713012"

    def test_deriva_capitulo(self):
        b = TipiBronze(ncm_codigo="84713012", descricao="Notebook")
        assert b.capitulo == "84"

    def test_capitulo_explicito_prevalece(self):
        b = TipiBronze(ncm_codigo="84713012", descricao="x", capitulo="99")
        assert b.capitulo == "99"

    def test_ncm_invalido_rejeitado(self):
        with pytest.raises(ValueError):
            TipiBronze(ncm_codigo="123", descricao="x")

    def test_aliquota_fora_de_faixa_rejeitada(self):
        with pytest.raises(ValueError):
            TipiBronze(ncm_codigo="84713012", descricao="x", aliquota_ipi=999)

    def test_aliquota_none_permitida(self):
        b = TipiBronze(ncm_codigo="84713012", descricao="x", aliquota_ipi=None)
        assert b.aliquota_ipi is None
        assert b.source == "TIPI"
