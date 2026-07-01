"""Testes do contrato ConfazRegraBronze."""
from __future__ import annotations

import pytest

from services.ingest.contracts.confaz import ConfazRegraBronze


class TestConfazRegraBronze:
    def test_valido_normaliza_ncm_e_uf(self):
        r = ConfazRegraBronze(ncm="8471.30.12", uf_origem="sp", uf_destino="ba", aliquota_pct=7.0)
        assert r.ncm == "84713012"
        assert r.uf_origem == "SP" and r.uf_destino == "BA"
        assert r.needs_review is True
        assert r.source == "CONFAZ"

    def test_ncm_invalido_rejeitado(self):
        with pytest.raises(ValueError):
            ConfazRegraBronze(ncm="abc")

    def test_aliquota_fora_de_faixa_rejeitada(self):
        with pytest.raises(ValueError):
            ConfazRegraBronze(ncm="84713012", aliquota_pct=90.0)

    def test_campos_opcionais_none(self):
        r = ConfazRegraBronze(ncm="22021000")
        assert r.aliquota_pct is None
        assert r.uf_origem is None
