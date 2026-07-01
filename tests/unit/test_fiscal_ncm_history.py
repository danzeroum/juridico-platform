"""Testes reais do histórico de NCM: parse + resolução temporal da cadeia."""
from __future__ import annotations

from datetime import date

import pytest

from services.fiscal.ingestion.ncm_history import parse_migracao, resolve_current

CSV = (
    "NCM origem;NCM destino;Vigência início;Vigência fim;Ato legal\n"
    "12345678;87654321;2020-01-01;;Resolução CAMEX 10/2019\n"
    "87654321;11112222;2023-01-01;;Resolução Gecex 272/2022\n"
    "99998888;;2022-01-01;;Extinção\n"
)


class TestParseMigracao:
    def test_parse_linhas(self):
        rows = parse_migracao(CSV)
        assert len(rows) == 3
        r0 = rows[0]
        assert r0["ncm_origem"] == "12345678"
        assert r0["ncm_destino"] == "87654321"
        assert r0["vigencia_inicio"] == "2020-01-01"
        assert "CAMEX" in r0["ato_legal"]

    def test_destino_vazio_vira_none(self):
        rows = parse_migracao(CSV)
        extinto = next(r for r in rows if r["ncm_origem"] == "99998888")
        assert extinto["ncm_destino"] is None

    def test_csv_sem_origem_levanta(self):
        with pytest.raises(ValueError):
            parse_migracao("foo;bar\n1;2\n")


class TestResolveCurrent:
    def setup_method(self):
        self.rows = parse_migracao(CSV)

    def test_segue_cadeia_completa(self):
        assert resolve_current("12345678", self.rows, date(2024, 1, 1)) == "11112222"

    def test_respeita_data_de_vigencia(self):
        # Em 2021 a segunda migração (2023) ainda não vale → para no intermediário.
        assert resolve_current("12345678", self.rows, date(2021, 6, 1)) == "87654321"

    def test_codigo_extinto_retorna_none(self):
        assert resolve_current("99998888", self.rows, date(2023, 1, 1)) is None

    def test_codigo_sem_migracao_inalterado(self):
        assert resolve_current("55556666", self.rows) == "55556666"

    def test_protecao_contra_ciclo(self):
        ciclo = [
            {"ncm_origem": "11110000", "ncm_destino": "22220000", "vigencia_inicio": "2020-01-01", "vigencia_fim": None, "ato_legal": None},
            {"ncm_origem": "22220000", "ncm_destino": "11110000", "vigencia_inicio": "2020-01-01", "vigencia_fim": None, "ato_legal": None},
        ]
        # Não deve entrar em loop infinito; retorna um dos códigos.
        assert resolve_current("11110000", ciclo, date(2024, 1, 1)) in {"11110000", "22220000"}
