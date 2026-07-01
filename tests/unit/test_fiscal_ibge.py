"""Testes reais do parse de municípios do IBGE (fixture com layout da DTB)."""
from __future__ import annotations

import pytest

from services.fiscal.ingestion.ibge_parse import detect_columns, parse_municipios

# Trecho no formato da DTB do IBGE (cabeçalho + linhas reais de código IBGE).
CSV_IBGE = (
    "Código Município Completo;Nome_Município;Sigla_UF\n"
    "3550308;São Paulo;SP\n"
    "3304557;Rio de Janeiro;RJ\n"
    "3106200;Belo Horizonte;MG\n"
    "9999999;Cidade Inexistente;ZZ\n"   # UF inválida → descartada
    ";Sem Código;SP\n"                   # sem código → descartada
)


class TestParseMunicipios:
    def test_extrai_municipios_validos(self):
        rows = parse_municipios(CSV_IBGE)
        assert len(rows) == 3
        sp = next(r for r in rows if r["uf"] == "SP")
        assert sp["codigo_ibge"] == "3550308"
        assert sp["municipio"] == "São Paulo"

    def test_descarta_uf_invalida_e_sem_codigo(self):
        rows = parse_municipios(CSV_IBGE)
        codigos = {r["codigo_ibge"] for r in rows}
        assert "9999999" not in codigos
        assert all(len(r["codigo_ibge"]) == 7 for r in rows)

    def test_detect_columns(self):
        colmap = detect_columns(["Código Município Completo", "Nome_Município", "Sigla_UF"])
        assert colmap == {"codigo": 0, "municipio": 1, "uf": 2}

    def test_csv_sem_colunas_reconheciveis_levanta(self):
        with pytest.raises(ValueError):
            parse_municipios("foo;bar\n1;2\n")

    def test_csv_vazio(self):
        assert parse_municipios("") == []
