"""Testes do icms_resolver: interna efetiva com FCP, interestadual, DIFAL."""
from __future__ import annotations

from services.fiscal.triage.icms_resolver import resolve_icms

SP_ROW = {"aliquota_pct": 18.0, "fcp_pct": None, "fundamento_legal": "Art. 52 I RICMS-SP"}
RJ_ROW = {"aliquota_pct": 18.0, "fcp_pct": 2.0, "fundamento_legal": "LC-RJ 210/2023"}


class TestResolveIcms:
    def test_operacao_interna_sem_interestadual(self):
        r = resolve_icms("SP", "SP", SP_ROW)
        assert r.interna_efetiva_pct == 18.0
        assert r.interestadual_pct is None
        assert r.difal_pct is None

    def test_rj_efetiva_inclui_fcp(self):
        r = resolve_icms("RJ", "RJ", RJ_ROW)
        assert r.interna_pct == 18.0
        assert r.fcp_pct == 2.0
        assert r.interna_efetiva_pct == 20.0  # modal + FECP

    def test_interestadual_sp_para_rj_com_difal(self):
        # SP→RJ: interestadual 12%; interna efetiva RJ = 20%; DIFAL = 8%.
        r = resolve_icms("SP", "RJ", RJ_ROW)
        assert r.interestadual_pct == 12.0
        assert r.interna_efetiva_pct == 20.0
        assert r.difal_pct == 8.0

    def test_interestadual_sp_para_ba_7pct(self):
        ba_row = {"aliquota_pct": 20.5, "fcp_pct": None, "fundamento_legal": "RICMS-BA"}
        r = resolve_icms("SP", "BA", ba_row)
        assert r.interestadual_pct == 7.0
        assert r.difal_pct == 13.5

    def test_sem_aliquota_interna_nao_inventa(self):
        r = resolve_icms("SP", "RJ", None)
        assert r.interna_pct is None
        assert r.interna_efetiva_pct is None
        assert r.difal_pct is None
        # Interestadual ainda é resolvido (regra geográfica).
        assert r.interestadual_pct == 12.0

    def test_importado_interestadual_4pct(self):
        r = resolve_icms("SP", "RJ", RJ_ROW, importado=True, conteudo_importacao_pct=70.0)
        assert r.interestadual_pct == 4.0
        assert r.difal_pct == 16.0

    def test_fundamento_combina_interno_e_interestadual(self):
        r = resolve_icms("SP", "RJ", RJ_ROW)
        assert "LC-RJ 210/2023" in r.fundamento_legal
        assert "22/1989" in r.fundamento_legal
