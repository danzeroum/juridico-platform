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


_PIB_PAYLOAD = [{"resultados": [{"series": [{"serie": {"2022": "110000000", "2023": "127649795"}}]}]}]


class TestFetchPib:
    def test_pega_ano_mais_recente(self):
        with patch.object(ibge.requests, "get", return_value=_FakeResp(_PIB_PAYLOAD)):
            pib, ano = ibge.fetch_pib("1302603")
        assert pib == 127649795.0
        assert ano == "2023"

    def test_cod_invalido_nao_chama_rede(self):
        with patch.object(ibge.requests, "get") as mock_get:
            assert ibge.fetch_pib("12") == (None, None)
            mock_get.assert_not_called()

    def test_falha_degrada(self):
        with patch.object(ibge.requests, "get", side_effect=ConnectionError("x")):
            assert ibge.fetch_pib("5300108") == (None, None)


_AREA_PAYLOAD = [{"resultados": [{"series": [{"serie": {"2010": "11401.1"}}]}]}]


class TestFetchArea:
    def test_parse_area(self):
        with patch.object(ibge.requests, "get", return_value=_FakeResp(_AREA_PAYLOAD)):
            area, ano = ibge.fetch_area("1302603")
        assert area == 11401.1
        assert ano == "2010"

    def test_cod_invalido_nao_chama_rede(self):
        with patch.object(ibge.requests, "get") as mock_get:
            assert ibge.fetch_area("99") == (None, None)
            mock_get.assert_not_called()

    def test_falha_degrada(self):
        with patch.object(ibge.requests, "get", side_effect=ConnectionError("x")):
            assert ibge.fetch_area("5300108") == (None, None)


_CEMPRE_PAYLOAD = [
    {"id": "367", "resultados": [{"series": [{"serie": {"2021": "28737"}}]}]},
    {"id": "707", "resultados": [{"series": [{"serie": {"2021": "554913"}}]}]},
    {"id": "708", "resultados": [{"series": [{"serie": {"2021": "519130"}}]}]},
]


class TestFetchCempre:
    def test_parse_multivariavel(self):
        with patch.object(ibge.requests, "get", return_value=_FakeResp(_CEMPRE_PAYLOAD)):
            out = ibge.fetch_cempre("1302603")
        assert out == {
            "empresas": 28737,
            "pessoal_ocupado": 554913,
            "pessoal_assalariado": 519130,
            "ano": "2021",
        }

    def test_cod_invalido_nao_chama_rede(self):
        with patch.object(ibge.requests, "get") as mock_get:
            assert ibge.fetch_cempre("1") == {}
            mock_get.assert_not_called()

    def test_falha_degrada_para_vazio(self):
        with patch.object(ibge.requests, "get", side_effect=ConnectionError("x")):
            assert ibge.fetch_cempre("5300108") == {}


_IPCA_12M = [{"resultados": [{"series": [{"serie": {"202605": "4.72"}}]}]}]
_IPCA_MENSAL = [{"resultados": [{"series": [{"serie": {"202604": "0.67", "202605": "0.58"}}]}]}]


class TestFetchIpca:
    def test_parse_12m_e_mensal(self):
        with patch.object(ibge.requests, "get", side_effect=[_FakeResp(_IPCA_12M), _FakeResp(_IPCA_MENSAL)]):
            out = ibge.fetch_ipca()
        assert out["acumulado_12m"] == 4.72
        assert out["referencia"] == "2026-05"
        assert out["mensal"] == [
            {"periodo": "2026-04", "valor": 0.67},
            {"periodo": "2026-05", "valor": 0.58},
        ]

    def test_falha_degrada_para_dict_vazio(self):
        with patch.object(ibge.requests, "get", side_effect=TimeoutError("slow")):
            assert ibge.fetch_ipca() == {}
