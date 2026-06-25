"""Testes do coletor BCB/SGS (parsing puro, sem rede — requests mockado)."""
from __future__ import annotations

from unittest.mock import patch

from services.ingest.tasks import bcb


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


_SELIC = [{"data": "01/06/2026", "valor": "14.75"}]
_CAMBIO = [{"data": "20/06/2026", "valor": "5.43"}]


class TestFetchSerie:
    def test_retorna_lista(self):
        with patch.object(bcb.requests, "get", return_value=_FakeResp(_SELIC)):
            assert bcb.fetch_serie(432, 1) == _SELIC

    def test_falha_degrada_para_lista_vazia(self):
        with patch.object(bcb.requests, "get", side_effect=ConnectionError("blocked")):
            assert bcb.fetch_serie(432) == []

    def test_payload_nao_lista_degrada(self):
        with patch.object(bcb.requests, "get", return_value=_FakeResp({"erro": "x"})):
            assert bcb.fetch_serie(1) == []


class TestFetchMacro:
    def test_selic_e_cambio(self):
        with patch.object(bcb.requests, "get", side_effect=[_FakeResp(_SELIC), _FakeResp(_CAMBIO)]):
            out = bcb.fetch_macro()
        assert out["selic"] == 14.75
        assert out["selic_data"] == "01/06/2026"
        assert out["cambio_usd"] == 5.43
        assert out["cambio_data"] == "20/06/2026"

    def test_tudo_bloqueado_retorna_vazio(self):
        with patch.object(bcb.requests, "get", side_effect=ConnectionError("403")):
            assert bcb.fetch_macro() == {}

    def test_parcial_apenas_selic(self):
        with patch.object(bcb.requests, "get", side_effect=[_FakeResp(_SELIC), _FakeResp([])]):
            out = bcb.fetch_macro()
        assert out == {"selic": 14.75, "selic_data": "01/06/2026"}
