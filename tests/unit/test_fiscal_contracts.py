"""Testes dos contratos FiscalEngine: normalização, interestadual, DIFAL."""
from __future__ import annotations

import pytest

from services.shared.contracts.fiscal import (
    ALIQUOTA_INTER_IMPORTADO,
    ALIQUOTA_INTER_PADRAO,
    ALIQUOTA_INTER_REDUZIDA,
    FISCAL_CONTRACT_VERSION,
    UF,
    IcmsResolution,
    NcmCandidate,
    NcmTriageRequest,
    aliquota_interestadual,
    compute_difal,
    normalize_descricao,
)


class TestNormalizeDescricao:
    def test_remove_acento_pontuacao_e_colapsa_espacos(self):
        assert normalize_descricao("  Café  Torrado, 500g!! ") == "cafe torrado 500g"

    def test_string_vazia(self):
        assert normalize_descricao("") == ""

    def test_deterministico(self):
        s = "Máquina de Solda MIG/MAG"
        assert normalize_descricao(s) == normalize_descricao(s)


class TestAliquotaInterestadual:
    def test_sudeste_para_nordeste_7pct(self):
        pct, fund = aliquota_interestadual("SP", "BA")
        assert pct == ALIQUOTA_INTER_REDUZIDA
        assert "22/1989" in fund

    def test_entre_sudeste_12pct(self):
        pct, _ = aliquota_interestadual("SP", "RJ")
        assert pct == ALIQUOTA_INTER_PADRAO

    def test_sudeste_para_es_7pct(self):
        # ES é destino beneficiado (não faz parte do Sul/Sudeste privilegiado).
        pct, _ = aliquota_interestadual("MG", "ES")
        assert pct == ALIQUOTA_INTER_REDUZIDA

    def test_origem_es_12pct(self):
        pct, _ = aliquota_interestadual("ES", "BA")
        assert pct == ALIQUOTA_INTER_PADRAO

    def test_importado_acima_de_40pct_usa_4(self):
        pct, fund = aliquota_interestadual("SP", "RJ", importado=True, conteudo_importacao_pct=60.0)
        assert pct == ALIQUOTA_INTER_IMPORTADO
        assert "13/2012" in fund

    def test_importado_abaixo_de_40pct_nao_usa_4(self):
        pct, _ = aliquota_interestadual("SP", "RJ", importado=True, conteudo_importacao_pct=30.0)
        assert pct == ALIQUOTA_INTER_PADRAO

    def test_importado_sem_conteudo_informado_usa_4(self):
        pct, _ = aliquota_interestadual("SP", "BA", importado=True, conteudo_importacao_pct=None)
        assert pct == ALIQUOTA_INTER_IMPORTADO


class TestComputeDifal:
    def test_difal_positivo(self):
        assert compute_difal(20.0, 7.0) == 13.0

    def test_difal_nunca_negativo(self):
        assert compute_difal(7.0, 12.0) == 0.0

    def test_difal_none_quando_falta_dado(self):
        assert compute_difal(None, 7.0) is None
        assert compute_difal(18.0, None) is None


class TestContratos:
    def test_ncm_candidate_valida_codigo_8_digitos(self):
        with pytest.raises(ValueError):
            NcmCandidate(ncm_codigo="123", descricao="x", confidence=1.0, fonte_regra="TIPI")

    def test_request_rejeita_campo_extra(self):
        with pytest.raises(ValueError):
            NcmTriageRequest(
                descricao="produto", uf_origem=UF.SP, uf_destino=UF.RJ, campo_inexistente=1
            )

    def test_request_hint_precisa_8_digitos(self):
        with pytest.raises(ValueError):
            NcmTriageRequest(descricao="p", uf_origem=UF.SP, uf_destino=UF.RJ, ncm_hint="abc")

    def test_resolution_default_version(self):
        r = IcmsResolution()
        assert r.interna_pct is None
        assert FISCAL_CONTRACT_VERSION == "fiscal/v1"
