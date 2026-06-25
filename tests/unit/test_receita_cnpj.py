"""Testes do coletor on-demand de CNPJ (parsing puro, sem rede)."""
from __future__ import annotations

from unittest.mock import patch

from services.ingest.tasks import receita_cnpj


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


_CNPJ_PAYLOAD = {
    "razao_social": "Empresa Exemplo S.A.",
    "descricao_situacao_cadastral": "Ativa",
    "data_situacao_cadastral": "2005-03-15",
    "descricao_porte": "DEMAIS",
    "natureza_juridica": {"descricao": "Sociedade Anônima"},
    "capital_social": 500000.0,
    "data_inicio_atividade": "2005-03-15",
    "municipio": {"descricao": "São Paulo"},
    "uf": "sp",
    "cnae_fiscal_principal": {"codigo": "6201501", "descricao": "Desenvolvimento de software"},
}


class TestFetchCnpj:
    def test_parse_completo(self):
        with patch.object(receita_cnpj.requests, "get", return_value=_FakeResp(_CNPJ_PAYLOAD)):
            out = receita_cnpj.fetch_cnpj("00.000.000/0001-91")
        assert out["razao_social"] == "Empresa Exemplo S.A."
        assert out["situacao_cadastral"] == "ATIVA"
        assert out["porte"] == "DEMAIS"
        assert out["natureza_juridica"] == "Sociedade Anônima"
        assert out["municipio"] == "São Paulo"
        assert out["cnae_fiscal"] == "6201501"
        assert out["cnae_descricao"] == "Desenvolvimento de software"
        assert out["data_abertura"] == "2005-03-15"

    def test_cnpj_invalido_nao_chama_rede(self):
        with patch.object(receita_cnpj.requests, "get") as mock_get:
            assert receita_cnpj.fetch_cnpj("123") == {}
            mock_get.assert_not_called()

    def test_host_bloqueado_degrada_para_vazio(self):
        with patch.object(receita_cnpj.requests, "get", side_effect=ConnectionError("403")):
            assert receita_cnpj.fetch_cnpj("00000000000191") == {}

    def test_data_formato_br(self):
        payload = {**_CNPJ_PAYLOAD, "data_inicio_atividade": "15/03/2005"}
        with patch.object(receita_cnpj.requests, "get", return_value=_FakeResp(payload)):
            out = receita_cnpj.fetch_cnpj("00000000000191")
        assert out["data_abertura"] == "2005-03-15"
