"""Testes do contrato SefazAliquotaBronze (validação + quarentena de outliers)."""
from __future__ import annotations

import pytest

from services.ingest.contracts.sefaz import SefazAliquotaBronze


class TestSefazAliquotaBronze:
    def test_valido(self):
        b = SefazAliquotaBronze(uf="sp", produto="Energia", aliquota_pct=25.0, fundamento_legal="Art. 52")
        assert b.uf == "SP"
        assert b.source == "SEFAZ"

    def test_uf_invalida_rejeitada(self):
        with pytest.raises(ValueError):
            SefazAliquotaBronze(uf="ZZ", produto="x", aliquota_pct=18.0)

    def test_aliquota_fora_de_faixa_rejeitada(self):
        with pytest.raises(ValueError):
            SefazAliquotaBronze(uf="SP", produto="x", aliquota_pct=99.0)

    def test_ncm_prefix_normalizado(self):
        b = SefazAliquotaBronze(uf="RJ", produto="x", aliquota_pct=20.0, ncm_prefix="8471")
        assert b.ncm_prefix == "8471"
        b2 = SefazAliquotaBronze(uf="RJ", produto="x", aliquota_pct=20.0, ncm_prefix="  ")
        assert b2.ncm_prefix is None
