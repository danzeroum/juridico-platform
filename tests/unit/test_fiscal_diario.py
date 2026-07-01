"""Testes reais do monitor de Diário Oficial (hash + termos fiscais)."""
from __future__ import annotations

from services.fiscal.ingestion.diario import (
    file_sha256,
    is_fiscally_relevant,
    matched_fiscal_terms,
)

# Texto no estilo de um Diário Oficial estadual com alteração de ICMS.
TEXTO_FISCAL = (
    "DECRETO Nº 12.345 — Altera o RICMS. Fica reduzida a alíquota interna de ICMS "
    "para 12% nas operações internas, mantido o adicional de FECP. Convênio CONFAZ ICMS 45/2026."
)
TEXTO_NEUTRO = "Portaria de nomeação de servidor público para cargo em comissão."


class TestHash:
    def test_sha256_deterministico_e_64_hex(self):
        h1 = file_sha256(b"conteudo do diario")
        h2 = file_sha256(b"conteudo do diario")
        assert h1 == h2 and len(h1) == 64

    def test_hash_muda_com_conteudo(self):
        assert file_sha256(b"a") != file_sha256(b"b")


class TestTermosFiscais:
    def test_detecta_termos_fiscais(self):
        termos = matched_fiscal_terms(TEXTO_FISCAL)
        assert "ICMS" in termos
        assert "RICMS" in termos
        assert "CONFAZ" in termos
        assert any("AL" in t for t in termos)  # ALÍQUOTA

    def test_texto_neutro_sem_termos(self):
        assert matched_fiscal_terms(TEXTO_NEUTRO) == []
        assert is_fiscally_relevant(TEXTO_NEUTRO) is False

    def test_relevancia_com_limiar(self):
        assert is_fiscally_relevant(TEXTO_FISCAL, min_terms=3) is True
        assert is_fiscally_relevant("apenas ICMS mencionado", min_terms=2) is False
