"""Testes do coletor IBGE (parsing puro, sem rede — requests mockado)."""
from __future__ import annotations

from unittest.mock import patch

from services.ingest.tasks import ibge


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


_MUNICIPIOS_PAYLOAD = [
    {
        "id": 5300108,
        "nome": "Brasília",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "DF"}}},
    },
    {
        "id": 1302603,
        "nome": "Manaus",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "AM"}}},
    },
]

_POP_PAYLOAD = [
    {
        "resultados": [
            {"series": [{"serie": {"2024": "2063547", "2025": "2303732"}}]}
        ]
    }
]


class TestFetchMunicipios:
    def test_parse_ok_e_ordenado(self):
        with patch.object(ibge.requests, "get", return_value=_FakeResp(_MUNICIPIOS_PAYLOAD)):
            out = ibge.fetch_municipios("DF")
        assert [m["municipio"] for m in out] == ["Brasília", "Manaus"]  # ordenado por nome
        assert out[0] == {"cod_ibge": "5300108", "municipio": "Brasília", "uf": "DF"}
        assert out[1]["cod_ibge"] == "1302603"

    def test_uf_invalida_retorna_vazio_sem_chamar_rede(self):
        with patch.object(ibge.requests, "get") as mock_get:
            assert ibge.fetch_municipios("XYZ") == []
            mock_get.assert_not_called()

    def test_falha_de_rede_degrada_para_vazio(self):
        with patch.object(ibge.requests, "get", side_effect=ConnectionError("boom")):
            assert ibge.fetch_municipios("SP") == []


class TestFetchPopulacao:
    def test_pega_ano_mais_recente(self):
        with patch.object(ibge.requests, "get", return_value=_FakeResp(_POP_PAYLOAD)):
            pop, ano = ibge.fetch_populacao("1302603")
        assert pop == 2303732
        assert ano == "2025"

    def test_cod_invalido_nao_chama_rede(self):
        with patch.object(ibge.requests, "get") as mock_get:
            assert ibge.fetch_populacao("123") == (None, None)
            mock_get.assert_not_called()

    def test_payload_inesperado_degrada(self):
        with patch.object(ibge.requests, "get", return_value=_FakeResp([])):
            assert ibge.fetch_populacao("5300108") == (None, None)
